"""Pretraitement robuste des courbes de lumiere Kepler."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence


def robust_location_scale(values: Sequence[float]) -> tuple[float, float]:
    """Retourne la mediane et une estimation robuste de l'ecart-type."""
    location = statistics.median(values)
    mad = statistics.median(abs(value - location) for value in values)
    scale = 1.4826 * mad
    if scale <= 0:
        scale = statistics.pstdev(values)
    return location, scale if scale > 0 else 1e-12


def running_median(values: Sequence[float], window: int) -> list[float]:
    """Calcule une tendance locale par mediane glissante centree.

    La version volontairement simple est suffisante pour les 3 197 points des
    courbes Kaggle et rend le pretraitement facile a expliquer dans le TIPE.
    """
    if window < 3:
        return [statistics.median(values)] * len(values)
    if window % 2 == 0:
        window += 1
    half = window // 2
    return [
        statistics.median(values[max(0, index - half) : index + half + 1])
        for index in range(len(values))
    ]


def preprocess_flux(
    flux: Iterable[float],
    *,
    cadence_days: float,
    detrend_window_days: float,
    sigma_clip: float,
) -> tuple[list[float], float]:
    """Detrend, centre, normalise et ecrete une courbe de lumiere.

    Le flux de Kaggle est centre autour de zero et contient souvent une derive
    stellaire bien plus forte que les transits. Soustraire une mediane locale
    empeche le BLS d'interpreter cette derive lente comme une occultation.
    """
    values: list[float] = []
    for raw_value in flux:
        value = float(raw_value)
        if math.isfinite(value):
            values.append(value)
    if len(values) < 10:
        raise ValueError("Une courbe doit contenir au moins 10 valeurs finies")

    window = max(3, round(detrend_window_days / cadence_days))
    trend = running_median(values, window)
    residuals = [value - local_trend for value, local_trend in zip(values, trend)]
    location, noise = robust_location_scale(residuals)
    normalized = [(value - location) / noise for value in residuals]
    return [max(-sigma_clip, min(sigma_clip, value)) for value in normalized], 1.0
