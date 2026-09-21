#!/usr/bin/env python3
"""Calibre le seuil SDE depuis un fichier produit par script.evaluate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from script.metrics import best_f1_threshold


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.results.read_text(encoding="utf-8"))
        threshold, matrix = best_f1_threshold(
            payload["results"],
            score_field=payload["metadata"].get("score_field", "sde"),
            positive_label=payload["metadata"].get("positive_label", 2),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f"erreur: {error}\n")
    print(json.dumps({
        "threshold": threshold,
        "criterion": "F1",
        "f1": matrix.f1,
        "precision": matrix.precision,
        "recall": matrix.recall,
        "specificity": matrix.specificity,
        "confusion_matrix": matrix.__dict__,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
