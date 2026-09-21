"""BLS de référence fondé sur l'implémentation officielle d'Astropy."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np
from astropy.timeseries import BoxLeastSquares

from script import config
from script.bls.preprocessing import preprocess_flux


# Les durées doivent toutes être strictement inférieures à la période minimale
# de chaque bande, contrainte imposée par Astropy et cohérente physiquement.
SEARCH_BANDS = (
    (0.5, 1.0, (0.02, 0.04, 0.06)),
    (1.0, 3.0, (0.04, 0.08, 0.125, 0.20)),
    (3.0, 30.0, (0.08, 0.125, 0.20, 0.30, 0.50)),
)


@dataclass(frozen=True)
class OfficialBLSResult:
    period_days: float
    duration_days: float
    transit_epoch_days: float
    depth: float
    depth_snr: float
    log_likelihood: float
    score: float
    n_points: int
    vetted_score: float = 0.0
    duration_fraction: float = 0.0
    odd_even_sigma: float = 0.0
    secondary_snr: float = 0.0
    harmonic_delta_log_likelihood: float = 0.0
    observed_transits: int = 0
    positive_transit_fraction: float = 0.0
    strongest_transit_fraction: float = 0.0


def _frequency_grid(minimum: float, maximum: float, count: int) -> np.ndarray:
    frequencies = np.linspace(1.0 / maximum, 1.0 / minimum, count)
    return np.sort(1.0 / frequencies)


def official_box_least_squares(
    times_days: Iterable[float],
    flux: Iterable[float],
    *,
    n_periods: int = config.OFFICIAL_BLS_PERIODS,
) -> OfficialBLSResult:
    """Recherche le meilleur transit avec ``astropy.timeseries.BoxLeastSquares``."""
    raw_times = np.asarray(list(times_days), dtype=float)
    raw_flux = np.asarray(list(flux), dtype=float)
    if raw_times.shape != raw_flux.shape:
        raise ValueError("times_days et flux doivent avoir la meme longueur")
    finite = np.isfinite(raw_times) & np.isfinite(raw_flux)
    if np.count_nonzero(finite) < 10:
        raise ValueError("La courbe doit contenir au moins 10 mesures finies")
    order = np.argsort(raw_times[finite])
    times = raw_times[finite][order]
    values = raw_flux[finite][order]
    times = times - times[0]
    cleaned, _ = preprocess_flux(
        values,
        cadence_days=config.CADENCE_DAYS,
        detrend_window_days=config.DETREND_WINDOW_DAYS,
        sigma_clip=config.SIGMA_CLIP,
    )
    cleaned_array = np.asarray(cleaned)
    model = BoxLeastSquares(times, cleaned_array)

    total_frequency_width = sum(
        1.0 / minimum - 1.0 / maximum
        for minimum, maximum, _ in SEARCH_BANDS
    )
    best: OfficialBLSResult | None = None
    for minimum, maximum, durations in SEARCH_BANDS:
        width = 1.0 / minimum - 1.0 / maximum
        count = max(2, math.ceil(n_periods * width / total_frequency_width))
        period_grid = _frequency_grid(minimum, maximum, count)
        result = model.power(
            period_grid,
            np.asarray(durations),
            objective="snr",
            method="fast",
            oversample=10,
        )
        index = int(np.nanargmax(result.power))
        candidate = OfficialBLSResult(
            period_days=float(result.period[index]),
            duration_days=float(result.duration[index]),
            transit_epoch_days=float(result.transit_time[index]),
            depth=float(result.depth[index]),
            depth_snr=float(result.depth_snr[index]),
            log_likelihood=float(result.log_likelihood[index]),
            score=float(result.power[index]),
            n_points=len(cleaned_array),
        )
        if best is None or candidate.score > best.score:
            best = candidate
    if best is None:
        raise ValueError("Astropy BLS n'a retourne aucun modele")
    stats = model.compute_stats(
        best.period_days, best.duration_days, best.transit_epoch_days
    )
    odd_depth, odd_error = map(float, stats["depth_odd"])
    even_depth, even_error = map(float, stats["depth_even"])
    odd_even_error = math.hypot(odd_error, even_error)
    phased_depth, phased_error = map(float, stats["depth_phased"])
    counts = np.asarray(stats["per_transit_count"])
    likelihoods = np.asarray(stats["per_transit_log_likelihood"])[counts > 0]
    positive_likelihoods = likelihoods[likelihoods > 0]
    harmonic_delta = float(stats["harmonic_delta_log_likelihood"])
    duration_fraction = best.duration_days / best.period_days
    return replace(
        best,
        vetted_score=math.sqrt(
            max(0.0, -harmonic_delta) / max(duration_fraction, 1e-12)
        ),
        duration_fraction=duration_fraction,
        odd_even_sigma=(
            abs(odd_depth - even_depth) / odd_even_error
            if odd_even_error > 0 and math.isfinite(odd_even_error)
            else math.inf
        ),
        secondary_snr=(
            max(0.0, phased_depth / phased_error)
            if phased_error > 0 and math.isfinite(phased_error)
            else math.inf
        ),
        harmonic_delta_log_likelihood=harmonic_delta,
        observed_transits=int(np.count_nonzero(counts)),
        positive_transit_fraction=(
            float(np.mean(likelihoods > 0)) if len(likelihoods) else 0.0
        ),
        strongest_transit_fraction=(
            float(np.max(positive_likelihoods) / np.sum(positive_likelihoods))
            if len(positive_likelihoods) and np.sum(positive_likelihoods) > 0
            else 1.0
        ),
    )
