#!/usr/bin/env python3
"""Produit une figure scientifique d'un système Kepler réel pour le README."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from script import config
from script.bls.bls import read_kepler_fits_system
from script.bls.preprocessing import preprocess_flux


def manifest_row(dataset_dir: Path, kepid: int) -> dict[str, str]:
    with (dataset_dir / "manifest.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if int(row["kepid"]) == kepid:
                return row
    raise ValueError(f"KIC {kepid} absent du manifeste")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kepid", type=int, default=5_542_466)
    parser.add_argument(
        "--dataset-dir", type=Path, default=config.DATA_DIR / "kepler_3000"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.PROJECT_ROOT / "docs" / "kic-5542466-light-curve.png",
    )
    args = parser.parse_args()

    row = manifest_row(args.dataset_dir, args.kepid)
    if not row["periods_days"] or not row["epochs_bkjd"]:
        raise ValueError("La figure repliée exige une période et une époque connues")
    period = float(row["periods_days"].split(";")[0])
    epoch = float(row["epochs_bkjd"].split(";")[0])
    times, relative_flux = read_kepler_fits_system(args.dataset_dir, args.kepid)
    time = np.asarray(times)
    flux = np.asarray(relative_flux)
    cleaned, _ = preprocess_flux(
        flux,
        cadence_days=config.CADENCE_DAYS,
        detrend_window_days=config.DETREND_WINDOW_DAYS,
        sigma_clip=config.SIGMA_CLIP,
    )
    cleaned_flux = np.asarray(cleaned)
    phase_hours = (((time - epoch + period / 2) % period) - period / 2) * 24

    figure, axes = plt.subplots(2, 1, figsize=(10, 6.2), constrained_layout=True)
    axes[0].scatter(time, 1_000 * flux, s=1.5, alpha=0.5, color="#2563eb")
    low, high = np.percentile(1_000 * flux, [0.5, 99.5])
    axes[0].set_ylim(low, high)
    axes[0].set(
        title=f"KIC {args.kepid} — flux relatif observé",
        xlabel="Temps (BKJD)",
        ylabel="Flux relatif (‰)",
    )

    axes[1].scatter(
        phase_hours, cleaned_flux, s=1.5, alpha=0.12, color="#64748b",
        label="mesures individuelles",
    )
    edges = np.linspace(-period * 12, period * 12, 121)
    centers = (edges[:-1] + edges[1:]) / 2
    medians = np.asarray([
        np.median(cleaned_flux[(phase_hours >= left) & (phase_hours < right)])
        if np.any((phase_hours >= left) & (phase_hours < right))
        else np.nan
        for left, right in zip(edges[:-1], edges[1:])
    ])
    axes[1].plot(
        centers, medians, color="#dc2626", linewidth=2, label="médiane par phase",
    )
    axes[1].axvline(0, color="#0f172a", linewidth=0.8, linestyle="--")
    axes[1].set(
        title=f"Même courbe repliée à P = {period:.6f} jours",
        xlabel="Temps par rapport au centre du transit (heures)",
        ylabel="Flux normalisé (écarts-types robustes)",
    )
    axes[1].legend(frameon=False, loc="lower right")
    for axis in axes:
        axis.grid(alpha=0.18)
        axis.spines[["top", "right"]].set_visible(False)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_format = args.output.suffix.lstrip(".").lower() or "svg"
    metadata = {"Date": None} if output_format == "svg" else None
    figure.savefig(args.output, format=output_format, metadata=metadata, dpi=160)
    plt.close(figure)
    print(f"Figure écrite dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
