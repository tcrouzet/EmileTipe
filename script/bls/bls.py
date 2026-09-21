#!/usr/bin/env python3
"""Recherche de transits periodiques par Box Least Squares (BLS).

Cette implementation sans dependance replie la courbe pour chaque periode,
regroupe les points en phase, puis recherche la fenetre circulaire dont le flux
est le plus faible. Elle est destinee a rester lisible pour le TIPE ; les
parametres sont tous regroupes dans :mod:`script.config`.

Exemples (depuis la racine du projet) :

    python3 -m script.bls.bls --input data/exoTest.csv --row 0
    python3 -m script.bls.bls --input data/exoTest.csv --limit 10 --csv resultats.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

try:
    from script import config
    from script.bls.official import official_box_least_squares
    from script.bls.preprocessing import preprocess_flux, robust_location_scale
except ModuleNotFoundError:  # Autorise aussi ``python3 script/bls/bls.py``.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from script import config
    from script.bls.official import official_box_least_squares
    from script.bls.preprocessing import preprocess_flux, robust_location_scale


@dataclass(frozen=True)
class BLSResult:
    """Meilleur modele de transit trouve dans une courbe."""

    period_days: float
    duration_days: float
    transit_epoch_days: float
    depth: float
    snr: float
    power: float
    sde: float
    points_in_transit: int
    n_points: int

    @property
    def detected(self) -> bool:
        return self.sde >= config.DETECTION_SDE_THRESHOLD


def frequency_periods(
    minimum: float, maximum: float, count: int
) -> Iterator[float]:
    """Produit des periodes sur une grille reguliere en frequence."""
    if minimum <= 0 or maximum <= minimum or count < 2:
        raise ValueError("La grille exige 0 < minimum < maximum et count >= 2")
    high_frequency = 1.0 / minimum
    low_frequency = 1.0 / maximum
    step = (high_frequency - low_frequency) / (count - 1)
    for index in range(count):
        yield 1.0 / (high_frequency - index * step)


def clean_flux(
    flux: Iterable[float],
    sigma_clip: float = config.SIGMA_CLIP,
    cadence_days: float = config.CADENCE_DAYS,
    detrend_window_days: float = config.DETREND_WINDOW_DAYS,
) -> tuple[list[float], float]:
    """Alias public du pretraitement, conserve pour compatibilite."""
    return preprocess_flux(
        flux,
        cadence_days=cadence_days,
        detrend_window_days=detrend_window_days,
        sigma_clip=sigma_clip,
    )


def _best_box_for_period(
    times: Sequence[float],
    flux: Sequence[float],
    period: float,
    durations: Sequence[float],
    phase_bins: int,
    noise_sigma: float,
) -> tuple[float, float, float, int, float] | None:
    sums = [0.0] * phase_bins
    counts = [0] * phase_bins
    for sample_time, value in zip(times, flux):
        bin_index = int(((sample_time % period) / period) * phase_bins)
        if bin_index == phase_bins:  # Protection contre un arrondi exceptionnel.
            bin_index = 0
        sums[bin_index] += value
        counts[bin_index] += 1

    doubled_sums = sums + sums
    doubled_counts = counts + counts
    prefix_sums = [0.0]
    prefix_counts = [0]
    for value_sum, value_count in zip(doubled_sums, doubled_counts):
        prefix_sums.append(prefix_sums[-1] + value_sum)
        prefix_counts.append(prefix_counts[-1] + value_count)

    total_sum = sum(sums)
    total_count = len(flux)
    best: tuple[float, float, float, int, float] | None = None
    tested_widths: set[int] = set()

    for duration in durations:
        if duration >= period or duration / period > config.MAX_TRANSIT_FRACTION:
            continue
        width = max(1, min(phase_bins - 1, round(duration / period * phase_bins)))
        if width in tested_widths:
            continue
        tested_widths.add(width)
        effective_duration = width * period / phase_bins

        for start in range(phase_bins):
            stop = start + width
            inside_count = prefix_counts[stop] - prefix_counts[start]
            outside_count = total_count - inside_count
            if inside_count < 2 or outside_count < 2:
                continue
            inside_sum = prefix_sums[stop] - prefix_sums[start]
            inside_mean = inside_sum / inside_count
            outside_mean = (total_sum - inside_sum) / outside_count
            depth = outside_mean - inside_mean
            if depth <= 0:  # Un transit est une baisse, jamais une hausse.
                continue
            uncertainty = noise_sigma * math.sqrt(
                1.0 / inside_count + 1.0 / outside_count
            )
            snr = depth / uncertainty
            if best is None or snr > best[0]:
                epoch = ((start + width / 2.0) / phase_bins) * period
                best = snr, depth, effective_duration, inside_count, epoch

    if best is None:
        return None
    snr, depth, duration, inside_count, epoch = best
    return snr, depth, duration, inside_count, epoch


def box_least_squares(
    flux: Iterable[float],
    *,
    times_days: Iterable[float] | None = None,
    cadence_days: float = config.CADENCE_DAYS,
    min_period_days: float = config.MIN_PERIOD_DAYS,
    max_period_days: float = config.MAX_PERIOD_DAYS,
    n_periods: int = config.N_PERIODS,
    durations_days: Sequence[float] = config.TRANSIT_DURATIONS_DAYS,
    phase_bins: int = config.N_PHASE_BINS,
    detrend_window_days: float = config.DETREND_WINDOW_DAYS,
) -> BLSResult:
    """Retourne le meilleur transit periodique ajuste a ``flux``.

    ``power`` vaut SNR² : c'est la reduction de chi-deux du meilleur modele
    en boite par rapport a un flux constant lorsque le bruit est homoscedastique.
    """
    if cadence_days <= 0 or phase_bins < 10:
        raise ValueError("cadence_days doit etre positif et phase_bins >= 10")
    raw_flux = [float(value) for value in flux]
    if times_days is None:
        finite_flux = [value for value in raw_flux if math.isfinite(value)]
        times = [index * cadence_days for index in range(len(finite_flux))]
    else:
        raw_times = [float(value) for value in times_days]
        if len(raw_times) != len(raw_flux):
            raise ValueError("times_days et flux doivent avoir la meme longueur")
        samples = sorted(
            (sample_time, value)
            for sample_time, value in zip(raw_times, raw_flux)
            if math.isfinite(sample_time) and math.isfinite(value)
        )
        if not samples:
            raise ValueError("La courbe ne contient aucun echantillon fini")
        origin = samples[0][0]
        times = [sample_time - origin for sample_time, _ in samples]
        finite_flux = [value for _, value in samples]

    cleaned, noise_sigma = clean_flux(
        finite_flux,
        cadence_days=cadence_days,
        detrend_window_days=detrend_window_days,
    )
    baseline = times[-1] - times[0]
    effective_maximum = min(max_period_days, baseline / 2.0)
    if effective_maximum <= min_period_days:
        raise ValueError("Courbe trop courte pour la plage de periodes demandee")

    best_result: BLSResult | None = None
    period_powers: list[float] = []
    for period in frequency_periods(min_period_days, effective_maximum, n_periods):
        candidate = _best_box_for_period(
            times, cleaned, period, durations_days, phase_bins, noise_sigma
        )
        if candidate is None:
            period_powers.append(0.0)
            continue
        snr, depth, duration, points, epoch = candidate
        period_powers.append(snr * snr)
        if best_result is None or snr > best_result.snr:
            best_result = BLSResult(
                period_days=period,
                duration_days=duration,
                transit_epoch_days=epoch,
                depth=depth,
                snr=snr,
                power=snr * snr,
                sde=0.0,
                points_in_transit=points,
                n_points=len(cleaned),
            )

    if best_result is None:
        raise ValueError("Aucun modele de transit valide n'a ete trouve")
    period_location, period_scale = robust_location_scale(period_powers)
    sde = (best_result.power - period_location) / period_scale
    return BLSResult(
        period_days=best_result.period_days,
        duration_days=best_result.duration_days,
        transit_epoch_days=best_result.transit_epoch_days,
        depth=best_result.depth,
        snr=best_result.snr,
        power=best_result.power,
        sde=sde,
        points_in_transit=best_result.points_in_transit,
        n_points=best_result.n_points,
    )


def read_kepler_csv(path: Path) -> Iterator[tuple[int, list[float]]]:
    """Lit un CSV Kaggle et produit les paires ``(label, flux)`` valides."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError(f"Fichier vide : {path}") from error
        if not header or header[0].strip().upper() != "LABEL":
            raise ValueError("La premiere colonne du CSV doit etre LABEL")
        if len(header) < 11:
            raise ValueError(
                f"{path} ne contient que {len(header) - 1} mesures de flux ; "
                "il en faut au moins 10"
            )
        for line_number, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue
            try:
                label = int(float(row[0]))
                values = [float(value) for value in row[1:] if value.strip()]
            except ValueError as error:
                raise ValueError(f"Valeur invalide a la ligne {line_number}") from error
            if len(values) >= 10:
                yield label, values


def read_kepler_fits_system(
    dataset_dir: Path, kepid: int
) -> tuple[list[float], list[float]]:
    """Lit, normalise par trimestre et concatene les FITS d'un systeme."""
    try:
        from astropy.io import fits
    except ImportError as error:
        raise ValueError(
            "La lecture FITS exige les dependances de requirements.txt"
        ) from error

    system_dir = dataset_dir / "fits" / f"{kepid:09d}"
    paths = sorted(system_dir.glob("*_llc.fits"))
    if not paths:
        raise ValueError(f"Aucun FITS trouve pour KIC {kepid}")

    samples: list[tuple[float, float]] = []
    for path in paths:
        with fits.open(path, memmap=True) as hdus:
            table = hdus[1].data
            valid = [
                (float(time_value), float(flux_value))
                for time_value, flux_value, quality in zip(
                    table["TIME"], table["PDCSAP_FLUX"], table["SAP_QUALITY"]
                )
                if int(quality) == 0
                and math.isfinite(float(time_value))
                and math.isfinite(float(flux_value))
            ]
        if len(valid) < 10:
            continue
        quarter_median = statistics.median(value for _, value in valid)
        if quarter_median == 0:
            continue
        samples.extend(
            (sample_time, value / quarter_median - 1.0)
            for sample_time, value in valid
        )

    if len(samples) < 10:
        raise ValueError(f"Pas assez de mesures valides pour KIC {kepid}")
    samples.sort()
    return [time for time, _ in samples], [value for _, value in samples]


def _result_record(row: int, label: int, result: BLSResult, seconds: float) -> dict:
    record = {"row": row, "label": label, **asdict(result)}
    record["detected"] = result.detected
    record["elapsed_seconds"] = seconds
    return record


def _write_csv(path: Path, records: Sequence[dict]) -> None:
    if not records:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=config.DEFAULT_DATA_FILE)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        help="Dataset FITS contenant manifest.csv et fits/",
    )
    parser.add_argument("--kepid", type=int, help="Identifiant KIC a lire en mode FITS")
    parser.add_argument("--row", type=int, help="Indice (base 0) d'une seule courbe")
    parser.add_argument("--limit", type=int, help="Nombre maximal de courbes")
    parser.add_argument("--csv", type=Path, help="Ecrit aussi les resultats en CSV")
    parser.add_argument("--periods", type=int, default=config.N_PERIODS)
    parser.add_argument(
        "--engine",
        choices=("official", "custom"),
        default="official",
        help="Moteur FITS; Astropy officiel par defaut",
    )
    args = parser.parse_args(argv)

    try:
        if args.dataset_dir is not None:
            if args.kepid is None:
                parser.error("--kepid est requis avec --dataset-dir")
            times, values = read_kepler_fits_system(args.dataset_dir, args.kepid)
            started = time.perf_counter()
            if args.engine == "official":
                periods = (
                    config.OFFICIAL_BLS_PERIODS
                    if args.periods == config.N_PERIODS
                    else args.periods
                )
                result = official_box_least_squares(
                    times, values, n_periods=periods
                )
                detected = (
                    result.vetted_score >= config.OFFICIAL_BLS_VETTED_THRESHOLD
                )
            else:
                result = box_least_squares(
                    values, times_days=times, n_periods=args.periods
                )
                detected = result.detected
            record = {
                "kepid": args.kepid,
                **asdict(result),
                "engine": args.engine,
                "detected": detected,
                "elapsed_seconds": time.perf_counter() - started,
            }
            print(json.dumps(record, ensure_ascii=False))
            if args.csv:
                _write_csv(args.csv, [record])
            return 0

        curves = read_kepler_csv(args.input)
        records: list[dict] = []
        for index, (label, values) in enumerate(curves):
            if args.row is not None and index != args.row:
                continue
            started = time.perf_counter()
            result = box_least_squares(values, n_periods=args.periods)
            record = _result_record(index, label, result, time.perf_counter() - started)
            records.append(record)
            print(json.dumps(record, ensure_ascii=False))
            if args.row is not None or (args.limit is not None and len(records) >= args.limit):
                break
        if not records:
            raise ValueError("Aucune courbe exploitable dans le fichier")
        if args.csv:
            _write_csv(args.csv, records)
    except (OSError, ValueError) as error:
        parser.exit(2, f"erreur: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
