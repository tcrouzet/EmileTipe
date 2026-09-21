#!/usr/bin/env python3
"""Evalue le BLS sur les FITS du dataset Kepler commun."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from script import config
from script.bls.bls import box_least_squares, read_kepler_fits_system
from script.bls.official import official_box_least_squares


def _analyse(task: tuple[str, int, str, str, int, str, str, float | None]) -> dict:
    dataset_dir_raw, kepid, label, periods_raw, periods, names, engine, threshold = task
    started = time.perf_counter()
    times, flux = read_kepler_fits_system(Path(dataset_dir_raw), kepid)
    if engine == "official":
        result = official_box_least_squares(times, flux, n_periods=periods)
        score = result.vetted_score
    else:
        result = box_least_squares(flux, times_days=times, n_periods=periods)
        score = result.sde
    return {
        "kepid": kepid,
        "label": 2 if label == "CONFIRMED" else 1,
        "catalog_label": label,
        "confirmed_planet_names": names,
        "known_periods_days": periods_raw,
        **asdict(result),
        "score": score,
        "detected": threshold is not None and score >= threshold,
        "elapsed_seconds": time.perf_counter() - started,
    }


def select_rows(
    dataset_dir: Path,
    split: str,
    positive_limit: int | None,
    negative_limit: int | None,
) -> list[dict[str, str]]:
    with (dataset_dir / "manifest.csv").open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["split"] == split]
    positives = [row for row in rows if row["label"] == "CONFIRMED"]
    controls = [row for row in rows if row["label"] == "CONTROL"]
    afp = [row for row in rows if row["label"] == "AFP"]
    ntp = [row for row in rows if row["label"] == "NTP"]
    if positive_limit is not None:
        positives = positives[:positive_limit]
    if controls:
        negatives = controls[:negative_limit] if negative_limit is not None else controls
    elif negative_limit is not None:
        total_negatives = len(afp) + len(ntp)
        afp_limit = round(negative_limit * len(afp) / total_negatives)
        negatives = afp[:afp_limit] + ntp[: negative_limit - afp_limit]
    else:
        negatives = afp + ntp
    return positives + negatives


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir", type=Path, default=config.DATA_DIR / "kepler_3000"
    )
    parser.add_argument("--split", choices=("train", "validation", "test"), default="validation")
    parser.add_argument("--positive-limit", type=int)
    parser.add_argument("--negative-limit", type=int)
    parser.add_argument("--engine", choices=("official", "custom"), default="official")
    parser.add_argument("--periods", type=int, default=config.OFFICIAL_BLS_PERIODS)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument(
        "--output", type=Path, default=config.DATA_DIR / "bls-fits-validation.json"
    )
    args = parser.parse_args()
    if args.periods < 2 or args.workers < 1:
        parser.error("--periods doit valoir au moins 2 et --workers au moins 1")

    rows = select_rows(
        args.dataset_dir, args.split, args.positive_limit, args.negative_limit
    )
    tasks = [
        (
            str(args.dataset_dir),
            int(row["kepid"]),
            row["label"],
            row["periods_days"],
            args.periods,
            row["confirmed_planet_names"],
            args.engine,
            args.threshold,
        )
        for row in rows
    ]
    results: list[dict] = []
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(_analyse, task) for task in tasks]
        for completed, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if completed == 1 or completed % 10 == 0 or completed == len(tasks):
                print(f"{completed}/{len(tasks)} systemes", flush=True)
    results.sort(key=lambda item: item["kepid"])

    tp = sum(item["label"] == 2 and item["detected"] for item in results)
    fp = sum(item["label"] == 1 and item["detected"] for item in results)
    fn = sum(item["label"] == 2 and not item["detected"] for item in results)
    tn = sum(item["label"] == 1 and not item["detected"] for item in results)
    payload = {
        "metadata": {
            "dataset": args.dataset_dir.name,
            "split": args.split,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "systems": len(results),
            "periods_tested": args.periods,
            "engine": args.engine,
            "threshold": args.threshold,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "metrics": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(payload["metrics"], ensure_ascii=False))
    print(f"Resultats ecrits dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
