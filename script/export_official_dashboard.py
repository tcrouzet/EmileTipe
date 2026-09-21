#!/usr/bin/env python3
"""Exporte les résultats du BLS Astropy dans le format du dashboard."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from script import config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        default=[
            config.DATA_DIR / "bls-official-train.json",
            config.DATA_DIR / "bls-official-validation.json",
            config.DATA_DIR / "bls-official-test.json",
        ],
    )
    parser.add_argument(
        "--cross-validation",
        type=Path,
        default=config.DATA_DIR / "bls-official-cross-validation.json",
    )
    parser.add_argument(
        "--output", type=Path, default=config.PROJECT_ROOT / "web" / "results.json"
    )
    args = parser.parse_args()
    results: list[dict] = []
    elapsed = 0.0
    for path in args.inputs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        elapsed += float(payload["metadata"]["elapsed_seconds"])
        for row in payload["results"]:
            row["score"] = math.sqrt(
                max(0.0, -float(row["harmonic_delta_log_likelihood"]))
                / max(float(row["duration_fraction"]), 1e-12)
            )
            results.append(row)
    results.sort(key=lambda row: int(row["kepid"]))
    cv = json.loads(args.cross_validation.read_text(encoding="utf-8"))
    output = {
        "metadata": {
            "dataset": "Kepler DR25 — 3 000 systèmes",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "systems": len(results),
            "periods_tested": config.OFFICIAL_BLS_PERIODS,
            "elapsed_seconds": elapsed,
            "engine": "astropy.timeseries.BoxLeastSquares",
            "score_field": "score",
            "score_label": "Score BLS vetting",
            "default_threshold": config.OFFICIAL_BLS_VETTED_THRESHOLD,
            "positive_label": config.POSITIVE_LABEL,
            "negative_label": config.NEGATIVE_LABEL,
            "cross_validation_metrics": cv["metrics"],
        },
        "results": results,
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{len(results)} resultats ecrits dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
