#!/usr/bin/env python3
"""Evalue le BLS sur un jeu Kepler et produit les donnees du dashboard."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from script import config
from script.bls.bls import box_least_squares, read_kepler_csv


def _analyse_curve(task: tuple[int, int, list[float], int]) -> dict:
    row, label, flux, periods = task
    started = time.perf_counter()
    result = box_least_squares(flux, n_periods=periods)
    return {
        "row": row,
        "label": label,
        **asdict(result),
        "elapsed_seconds": time.perf_counter() - started,
    }


def evaluate(input_path: Path, periods: int, workers: int, limit: int | None) -> dict:
    curves = list(read_kepler_csv(input_path))
    if limit is not None:
        curves = curves[:limit]
    if not curves:
        raise ValueError("Aucune courbe exploitable")

    tasks = [(row, label, flux, periods) for row, (label, flux) in enumerate(curves)]
    results: list[dict] = []
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_analyse_curve, task) for task in tasks]
        for completed, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if completed == 1 or completed % 10 == 0 or completed == len(tasks):
                elapsed = time.perf_counter() - started
                print(
                    f"{completed:>4}/{len(tasks)} courbes — {elapsed:.1f} s",
                    file=sys.stderr,
                    flush=True,
                )
    results.sort(key=lambda item: item["row"])
    elapsed = time.perf_counter() - started
    return {
        "metadata": {
            "dataset": input_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "systems": len(results),
            "periods_tested": periods,
            "workers": workers,
            "elapsed_seconds": elapsed,
            "default_threshold": config.DETECTION_SDE_THRESHOLD,
            "score_field": "sde",
            "positive_label": config.POSITIVE_LABEL,
            "negative_label": config.NEGATIVE_LABEL,
            "cadence_days": config.CADENCE_DAYS,
            "detrend_window_days": config.DETREND_WINDOW_DAYS,
            "calibration": {
                "dataset": config.CALIBRATION_DATASET,
                "systems": config.CALIBRATION_SYSTEMS,
                "criterion": config.CALIBRATION_CRITERION,
            },
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=config.DEFAULT_DATA_FILE)
    parser.add_argument(
        "--output", type=Path, default=config.PROJECT_ROOT / "web" / "results.json"
    )
    parser.add_argument("--periods", type=int, default=config.N_PERIODS)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.periods < 2 or args.workers < 1:
        parser.error("--periods doit valoir au moins 2 et --workers au moins 1")

    try:
        payload = evaluate(args.input, args.periods, args.workers, args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"erreur: {error}\n")
    print(f"Resultats ecrits dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
