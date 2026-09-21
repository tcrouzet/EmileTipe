"""Metriques de classification et calibration d'un seuil de detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def precision(self) -> float:
        total = self.true_positive + self.false_positive
        return self.true_positive / total if total else 0.0

    @property
    def recall(self) -> float:
        total = self.true_positive + self.false_negative
        return self.true_positive / total if total else 0.0

    @property
    def specificity(self) -> float:
        total = self.true_negative + self.false_positive
        return self.true_negative / total if total else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0


def confusion_matrix(
    results: Sequence[Mapping[str, float]],
    threshold: float,
    *,
    score_field: str = "sde",
    positive_label: int = 2,
) -> ConfusionMatrix:
    tp = fp = tn = fn = 0
    for row in results:
        positive = int(row["label"]) == positive_label
        detected = float(row[score_field]) >= threshold
        if positive and detected:
            tp += 1
        elif detected:
            fp += 1
        elif positive:
            fn += 1
        else:
            tn += 1
    return ConfusionMatrix(tp, fp, tn, fn)


def best_f1_threshold(
    results: Sequence[Mapping[str, float]],
    *,
    score_field: str = "sde",
    positive_label: int = 2,
) -> tuple[float, ConfusionMatrix]:
    """Selectionne le seuil maximisant F1, uniquement sur la calibration."""
    if not results:
        raise ValueError("La calibration exige au moins un resultat")
    candidates = sorted({float(row[score_field]) for row in results})
    scored = [
        (confusion_matrix(results, threshold, score_field=score_field,
                          positive_label=positive_label), threshold)
        for threshold in candidates
    ]
    matrix, threshold = max(
        scored,
        key=lambda item: (item[0].f1, item[0].specificity, item[1]),
    )
    return threshold, matrix
