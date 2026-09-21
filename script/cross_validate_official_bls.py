#!/usr/bin/env python3
"""Validation croisée du BLS Astropy et de ses critères de vetting."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Callable

from script import config
from script.calibrate_official_bls import calibrate


ScoreFunction = Callable[[dict], float]


SCORES: dict[str, ScoreFunction] = {
    "depth_snr": lambda row: float(row["depth_snr"]),
    "box_vs_harmonic": lambda row: math.sqrt(
        max(0.0, -float(row["harmonic_delta_log_likelihood"]))
    ),
    "short_transit_snr": lambda row: float(row["depth_snr"])
    / math.sqrt(max(float(row["duration_fraction"]), 1e-12)),
    "short_box_vs_harmonic": lambda row: math.sqrt(
        max(0.0, -float(row["harmonic_delta_log_likelihood"]))
        / max(float(row["duration_fraction"]), 1e-12)
    ),
}


def fold_for(row: dict, folds: int, ranks: dict[int, int]) -> int:
    return ranks[int(row["kepid"])] % folds


def stratified_ranks(rows: list[dict]) -> dict[int, int]:
    ranks: dict[int, int] = {}
    for label in (1, 2):
        group = sorted(
            (row for row in rows if int(row["label"]) == label),
            key=lambda row: hashlib.sha256(
                f"727:bls-cv:{label}:{row['kepid']}".encode()
            ).hexdigest(),
        )
        ranks.update({int(row["kepid"]): rank for rank, row in enumerate(group)})
    return ranks


def transformed(rows: list[dict], score_function: ScoreFunction) -> list[dict]:
    return [
        {"label": int(row["label"]), "score": score_function(row)} for row in rows
    ]


def cross_validate(rows: list[dict], folds: int = 6) -> dict:
    if folds < 2:
        raise ValueError("Il faut au moins deux folds")
    ranks = stratified_ranks(rows)
    predictions: list[dict] = []
    fold_reports: list[dict] = []
    for fold in range(folds):
        development = [
            row for row in rows if fold_for(row, folds, ranks) != fold
        ]
        held_out = [row for row in rows if fold_for(row, folds, ranks) == fold]
        candidates = []
        for name, score_function in SCORES.items():
            calibration = calibrate(transformed(development, score_function))
            candidates.append((calibration["f_beta"], calibration["precision"], name, calibration))
        _, _, selected_name, calibration = max(candidates)
        score_function = SCORES[selected_name]
        threshold = float(calibration["threshold"])
        fold_predictions = []
        for row in held_out:
            score = score_function(row)
            prediction = {
                "kepid": int(row["kepid"]),
                "label": int(row["label"]),
                "fold": fold,
                "score_name": selected_name,
                "score": score,
                "threshold": threshold,
                "detected": score >= threshold,
            }
            fold_predictions.append(prediction)
            predictions.append(prediction)
        fold_reports.append(
            {
                "fold": fold,
                "development_systems": len(development),
                "evaluation_systems": len(held_out),
                "evaluation_positives": sum(
                    prediction["label"] == 2 for prediction in fold_predictions
                ),
                "selected_score": selected_name,
                "development_calibration": calibration,
            }
        )

    tp = sum(row["label"] == 2 and row["detected"] for row in predictions)
    fp = sum(row["label"] == 1 and row["detected"] for row in predictions)
    fn = sum(row["label"] == 2 and not row["detected"] for row in predictions)
    tn = sum(row["label"] == 1 and not row["detected"] for row in predictions)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "method": "astropy.timeseries.BoxLeastSquares + nested vetting selection",
        "folds": folds,
        "systems": len(predictions),
        "metrics": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "fold_reports": fold_reports,
        "predictions": sorted(predictions, key=lambda row: row["kepid"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="*",
        default=[
            config.DATA_DIR / "bls-official-train.json",
            config.DATA_DIR / "bls-official-validation.json",
            config.DATA_DIR / "bls-official-test.json",
        ],
    )
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument(
        "--output",
        type=Path,
        default=config.DATA_DIR / "bls-official-cross-validation.json",
    )
    args = parser.parse_args()
    rows: list[dict] = []
    for path in args.inputs:
        rows.extend(json.loads(path.read_text(encoding="utf-8"))["results"])
    report = cross_validate(rows, args.folds)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    print(f"Resultats ecrits dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
