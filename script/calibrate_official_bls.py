#!/usr/bin/env python3
"""Calibre le seuil du BLS Astropy sur des scores hors jeu de test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def calibrate(results: list[dict], beta: float = 1.0) -> dict:
    if beta <= 0:
        raise ValueError("beta doit etre strictement positif")
    ranked = sorted(results, key=lambda item: float(item["score"]), reverse=True)
    positives = sum(int(item["label"]) == 2 for item in ranked)
    negatives = len(ranked) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("La calibration exige des exemples positifs et negatifs")

    beta_squared = beta * beta
    true_positive = 0
    false_positive = 0
    average_precision = 0.0
    best: dict | None = None
    index = 0
    while index < len(ranked):
        threshold = float(ranked[index]["score"])
        while index < len(ranked) and float(ranked[index]["score"]) == threshold:
            if int(ranked[index]["label"]) == 2:
                true_positive += 1
                average_precision += true_positive / (index + 1) / positives
            else:
                false_positive += 1
            index += 1
        false_negative = positives - true_positive
        true_negative = negatives - false_positive
        precision = true_positive / (true_positive + false_positive)
        recall = true_positive / positives
        denominator = beta_squared * precision + recall
        f_beta = (
            (1.0 + beta_squared) * precision * recall / denominator
            if denominator
            else 0.0
        )
        candidate = {
            "threshold": threshold,
            "precision": precision,
            "recall": recall,
            "f_beta": f_beta,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
        }
        if best is None or (
            candidate["f_beta"], candidate["precision"], candidate["threshold"]
        ) > (best["f_beta"], best["precision"], best["threshold"]):
            best = candidate

    assert best is not None
    return {
        "criterion": f"F{beta:g}",
        "systems": len(ranked),
        "positives": positives,
        "negatives": negatives,
        "average_precision": average_precision,
        **best,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--beta", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    calibration = calibrate(payload["results"], args.beta)
    print(json.dumps(calibration, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(
            json.dumps(calibration, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
