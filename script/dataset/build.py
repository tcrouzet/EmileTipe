#!/usr/bin/env python3
"""Construit les datasets Kepler d'evaluation et d'apprentissage.

Deux etapes sont volontairement separees :

1. ``manifest`` telecharge le catalogue officiel et selectionne les systemes ;
2. ``download`` recupere leurs courbes FITS officielles depuis MAST.

La selection est deterministe : a catalogue et graine identiques, le manifeste
est strictement identique sur toutes les machines.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import ssl
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from tqdm import tqdm

from script import config


ARCHIVE_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
TCE_TABLE = "q1_q17_dr24_tce"
EXCLUSION_TCE_TABLE = "q1_q17_dr25_tce"
KOI_TABLE = "q1_q17_dr25_koi"
STELLAR_TABLE = "q1_q17_dr25_stellar"
TCE_COLUMNS = (
    "kepid",
    "tce_plnt_num",
    "tce_period",
    "tce_time0bk",
    "tce_duration",
    "av_training_set",
)
KOI_COLUMNS = (
    "kepid",
    "kepoi_name",
    "kepler_name",
    "koi_period",
    "koi_time0bk",
    "koi_duration",
    "koi_disposition",
)
LABELS = ("CONFIRMED", "CONTROL")
TCE_TRAINING_LABELS = ("AFP", "NTP")
CLASS_COUNTS = {"CONFIRMED": 42, "CONTROL": 2_958}
CLASS_SPLITS = {
    "CONFIRMED": {"train": 32, "validation": 5, "test": 5},
    "CONTROL": {"train": 2_068, "validation": 445, "test": 445},
}
TRAINING_CLASS_COUNTS = {"CONFIRMED": 1_500, "CONTROL": 1_500}
TRAINING_CLASS_SPLITS = {
    "CONFIRMED": {"train": 1_200, "validation": 300},
    "CONTROL": {"train": 1_200, "validation": 300},
}
DEFAULT_MAX_PERIOD_DAYS = 30.0
DEFAULT_SEED = 727
DEFAULT_QUARTERS = (4, 5, 6)
# Identifiants officiels des traitements DR25 pour les fichiers long cadence.
# Source : index public MAST des courbes Kepler.
QUARTER_FILE_IDS = {
    1: "2009166043257",
    2: "2009259160929",
    3: "2009350155506",
    4: "2010078095331",
    5: "2010174085026",
    6: "2010265121752",
    7: "2010355172524",
    8: "2011073133259",
    9: "2011177032512",
    10: "2011271113734",
    11: "2012004120508",
    12: "2012088054726",
    13: "2012179063303",
    14: "2012277125453",
    15: "2013011073258",
    16: "2013098041711",
    17: "2013131215648",
}
MAST_LIGHT_CURVE_ROOT = "https://archive.stsci.edu/pub/kepler/lightcurves"


@dataclass(frozen=True)
class DatasetProfile:
    """Parametres qui distinguent un dataset sans dupliquer sa construction."""

    directory_name: str
    purpose: str
    class_counts: dict[str, int]
    class_splits: dict[str, dict[str, int]]
    excluded_manifest: Path | None = None


DATASET_PROFILES = {
    "benchmark": DatasetProfile(
        directory_name="kepler_3000",
        purpose="final comparison benchmark with realistic class imbalance",
        class_counts=CLASS_COUNTS,
        class_splits=CLASS_SPLITS,
    ),
    "training": DatasetProfile(
        directory_name="kepler_training",
        purpose="balanced neural-network training and validation dataset",
        class_counts=TRAINING_CLASS_COUNTS,
        class_splits=TRAINING_CLASS_SPLITS,
        excluded_manifest=config.DATA_DIR / "kepler_3000" / "manifest.csv",
    ),
}


@dataclass(frozen=True)
class TCE:
    kepid: int
    planet_number: int
    period_days: float
    epoch_bkjd: float
    duration_hours: float
    label: str
    name: str = ""


@dataclass(frozen=True)
class System:
    kepid: int
    label: str
    events: tuple[TCE, ...]
    confirmed_events: tuple[TCE, ...] = ()


def tce_archive_query() -> str:
    columns = ",".join(TCE_COLUMNS)
    labels = "'AFP','NTP'"
    return (
        f"select {columns} from {TCE_TABLE} "
        f"where av_training_set in ({labels})"
    )


def confirmed_archive_query() -> str:
    columns = ",".join(KOI_COLUMNS)
    return (
        f"select {columns} from {KOI_TABLE} "
        "where koi_disposition='CONFIRMED'"
    )


def ids_archive_query(table: str) -> str:
    return f"select kepid from {table}"


def stellar_catalog_url() -> str:
    return (
        "https://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/"
        "nph-nstedAPI?"
        + urllib.parse.urlencode(
            {"table": STELLAR_TABLE, "select": "kepid", "format": "csv"}
        )
    )


def tap_url(query: str) -> str:
    return ARCHIVE_TAP_URL + "?" + urllib.parse.urlencode(
        {"query": query, "format": "csv"}
    )


def download_catalog(
    destination: Path, source_url: str, *, force: bool = False
) -> None:
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".csv.part")
    request = urllib.request.Request(
        source_url, headers={"User-Agent": "EmileType-TIPE/1.0"}
    )
    try:
        try:
            import certifi

            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(
            request, timeout=120, context=ssl_context
        ) as response:
            temporary.write_bytes(response.read())
        if temporary.stat().st_size < 100:
            raise ValueError("Le catalogue telecharge est anormalement petit")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def read_catalog(path: Path) -> list[TCE]:
    events: list[TCE] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for line_number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                label = row["av_training_set"].strip()
                period = float(row["tce_period"])
                if label not in TCE_TRAINING_LABELS or not math.isfinite(period):
                    continue
                events.append(
                    TCE(
                        kepid=int(row["kepid"]),
                        planet_number=int(row["tce_plnt_num"]),
                        period_days=period,
                        epoch_bkjd=float(row["tce_time0bk"]),
                        duration_hours=float(row["tce_duration"]),
                        label=label,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Valeur DR24 invalide a la ligne {line_number}"
                ) from error
    return events


def read_confirmed_catalog(path: Path) -> list[TCE]:
    """Lit les planètes dont la disposition officielle vaut CONFIRMED."""
    events: list[TCE] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for line_number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                period = float(row["koi_period"])
                if not math.isfinite(period):
                    continue
                name = (row.get("kepler_name") or row["kepoi_name"]).strip()
                events.append(
                    TCE(
                        kepid=int(row["kepid"]),
                        planet_number=0,
                        period_days=period,
                        epoch_bkjd=float(row["koi_time0bk"]),
                        duration_hours=float(row["koi_duration"]),
                        label="CONFIRMED",
                        name=name,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Valeur DR25 invalide a la ligne {line_number}"
                ) from error
    return events


def read_kepids(path: Path) -> set[int]:
    """Lit une table CSV ne contenant qu'un identifiant Kepler par ligne."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "kepid" not in reader.fieldnames:
            raise ValueError(f"Colonne kepid absente de {path}")
        return {
            int(row["kepid"])
            for row in reader
            if row.get("kepid") and row["kepid"].strip()
        }


def confirmed_systems(
    events: Iterable[TCE], *, max_period_days: float
) -> list[System]:
    by_system: dict[int, list[TCE]] = defaultdict(list)
    for event in events:
        by_system[event.kepid].append(event)
    systems: list[System] = []
    for kepid, all_events in by_system.items():
        ordered = tuple(sorted(all_events, key=lambda event: event.period_days))
        eligible = tuple(
            event for event in ordered if event.period_days <= max_period_days
        )
        if eligible:
            systems.append(
                System(kepid, "CONFIRMED", eligible, confirmed_events=ordered)
            )
    return systems


def control_systems(kepids: Iterable[int], excluded_kepids: set[int]) -> list[System]:
    """Construit les témoins sans KOI ni TCE connu dans DR25."""
    return [
        System(kepid, "CONTROL", ())
        for kepid in set(kepids) - excluded_kepids
        if 0 < kepid < 100_000_000
    ]


def unambiguous_systems(
    events: Iterable[TCE], *, max_period_days: float,
    excluded_kepids: set[int] | None = None,
) -> dict[str, list[System]]:
    """Regroupe par etoile et exclut tout systeme aux labels contradictoires."""
    by_system: dict[int, list[TCE]] = defaultdict(list)
    for event in events:
        by_system[event.kepid].append(event)

    systems = {label: [] for label in TCE_TRAINING_LABELS}
    for kepid, all_events in by_system.items():
        if excluded_kepids and kepid in excluded_kepids:
            continue
        labels = {event.label for event in all_events}
        if len(labels) != 1:
            continue
        eligible = tuple(
            sorted(
                (event for event in all_events if event.period_days <= max_period_days),
                key=lambda event: (event.period_days, event.planet_number),
            )
        )
        if not eligible:
            continue
        label = next(iter(labels))
        systems[label].append(System(kepid, label, eligible))
    return systems


def _selection_key(system: System, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{system.label}:{system.kepid}".encode()).hexdigest()


def select_systems(
    candidates: dict[str, list[System]], *, class_counts: dict[str, int], seed: int
) -> list[System]:
    selected: list[System] = []
    for label in class_counts:
        available = candidates.get(label, [])
        requested = class_counts[label]
        if len(available) < requested:
            raise ValueError(
                f"Classe {label}: {len(available)} systemes eligibles, "
                f"{requested} demandes"
            )
        selected.extend(
            sorted(available, key=lambda item: _selection_key(item, seed))[:requested]
        )
    return selected


def split_for_rank(
    rank: int,
    label: str,
    class_splits: dict[str, dict[str, int]] = CLASS_SPLITS,
) -> str:
    offset = 0
    for split, count in class_splits[label].items():
        offset += count
        if rank < offset:
            return split
    raise ValueError(f"Rang {rank} hors des partitions de la classe {label}")


def manifest_rows(
    systems: Sequence[System],
    *,
    seed: int,
    class_splits: dict[str, dict[str, int]] = CLASS_SPLITS,
) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []
    for label in LABELS:
        group = sorted(
            (system for system in systems if system.label == label),
            key=lambda item: _selection_key(item, seed),
        )
        for rank, system in enumerate(group):
            rows.append(
                system_manifest_row(
                    system,
                    split_for_rank(rank, label, class_splits),
                )
            )
    return sorted(rows, key=lambda row: (str(row["split"]), str(row["label"]), int(row["kepid"])))


def system_manifest_row(
    system: System, split: str
) -> dict[str, str | int | float]:
    events = system.events
    confirmed = system.confirmed_events
    return {
        "kepid": system.kepid,
        "label": system.label,
        "has_confirmed_planet": 1 if system.label == "CONFIRMED" else 0,
        "confirmed_planet_count": len(confirmed),
        "detectable_planet_count": len(events) if confirmed else 0,
        "confirmed_planet_names": ";".join(event.name for event in confirmed),
        "split": split,
        "signal_count": len(events),
        "periods_days": ";".join(f"{event.period_days:.12g}" for event in events),
        "epochs_bkjd": ";".join(f"{event.epoch_bkjd:.12g}" for event in events),
        "durations_hours": ";".join(f"{event.duration_hours:.12g}" for event in events),
        "quarters": ";".join(map(str, DEFAULT_QUARTERS)),
    }


def write_csv(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_kepids(path: Path) -> set[int]:
    """Retourne les KIC d'un manifeste a exclure d'un autre dataset."""
    return {int(row["kepid"]) for row in read_manifest(path)}


def portable_path(path: Path) -> str:
    """Evite d'inscrire un chemin propre a la machine dans la provenance."""
    try:
        return str(path.resolve().relative_to(config.PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def build_manifest(args: argparse.Namespace) -> None:
    root: Path = args.dataset_dir
    profile = DATASET_PROFILES[args.profile]
    catalog_root: Path = args.catalog_dir
    confirmed_catalog = catalog_root / "q1_q17_dr25_confirmed_koi.csv"
    stellar_catalog = catalog_root / "q1_q17_dr25_stellar_kepids.csv"
    all_tce_catalog = catalog_root / "q1_q17_dr25_all_tce_kepids.csv"
    all_koi_catalog = catalog_root / "q1_q17_dr25_all_koi_kepids.csv"
    manifest = root / "manifest.csv"
    confirmed_url = tap_url(confirmed_archive_query())
    stellar_url = stellar_catalog_url()
    all_tce_url = tap_url(ids_archive_query(EXCLUSION_TCE_TABLE))
    all_koi_url = tap_url(ids_archive_query(KOI_TABLE))
    download_catalog(confirmed_catalog, confirmed_url, force=args.force_catalog)
    download_catalog(stellar_catalog, stellar_url, force=args.force_catalog)
    download_catalog(all_tce_catalog, all_tce_url, force=args.force_catalog)
    download_catalog(all_koi_catalog, all_koi_url, force=args.force_catalog)

    confirmed_events = read_confirmed_catalog(confirmed_catalog)
    confirmed_kepids = {event.kepid for event in confirmed_events}
    excluded_kepids = (
        read_kepids(all_tce_catalog)
        | read_kepids(all_koi_catalog)
        | confirmed_kepids
    )
    excluded_manifest = args.exclude_manifest or profile.excluded_manifest
    held_out_kepids: set[int] = set()
    if excluded_manifest is not None:
        if not excluded_manifest.exists():
            raise ValueError(
                f"Manifeste a exclure introuvable: {excluded_manifest}. "
                "Construire d'abord le dataset de comparaison."
            )
        held_out_kepids = manifest_kepids(excluded_manifest)

    candidates = {
        "CONFIRMED": confirmed_systems(
            confirmed_events, max_period_days=args.max_period
        ),
        "CONTROL": control_systems(read_kepids(stellar_catalog), excluded_kepids),
    }
    if held_out_kepids:
        candidates = {
            label: [
                system
                for system in systems
                if system.kepid not in held_out_kepids
            ]
            for label, systems in candidates.items()
        }
    selected = select_systems(
        candidates, class_counts=profile.class_counts, seed=args.seed
    )
    rows = manifest_rows(
        selected,
        seed=args.seed,
        class_splits=profile.class_splits,
    )
    write_csv(manifest, rows)

    counts = {
        label: sum(row["label"] == label for row in rows) for label in LABELS
    }
    split_names = tuple(
        dict.fromkeys(
            split
            for label in LABELS
            for split in profile.class_splits[label]
        )
    )
    splits = {
        split: sum(row["split"] == split for row in rows)
        for split in split_names
    }
    provenance = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "purpose": profile.purpose,
        "catalogs": {
            "confirmed_planets": {
                "table": KOI_TABLE,
                "source": confirmed_url,
                "sha256": sha256(confirmed_catalog),
            },
            "observed_stars": {
                "table": STELLAR_TABLE,
                "source": stellar_url,
                "sha256": sha256(stellar_catalog),
            },
            "excluded_tce_hosts": {
                "table": EXCLUSION_TCE_TABLE,
                "source": all_tce_url,
                "sha256": sha256(all_tce_catalog),
            },
            "excluded_koi_hosts": {
                "table": KOI_TABLE,
                "source": all_koi_url,
                "sha256": sha256(all_koi_catalog),
            },
        },
        "manifest_sha256": sha256(manifest),
        "selection": {
            "seed": args.seed,
            "labels": list(LABELS),
            "class_counts": profile.class_counts,
            "class_splits": profile.class_splits,
            "max_period_days": args.max_period,
            "control_definition": "DR25 stellar target without any DR25 KOI or TCE",
            "all_known_koi_and_tce_hosts_excluded_from_controls": True,
            "quarters": list(DEFAULT_QUARTERS),
        },
        "eligible_systems_before_sampling": {
            label: len(candidates[label]) for label in LABELS
        },
        "selected_systems": counts,
        "splits": splits,
    }
    if excluded_manifest is not None:
        provenance["leakage_prevention"] = {
            "excluded_manifest": portable_path(excluded_manifest),
            "excluded_manifest_sha256": sha256(excluded_manifest),
            "excluded_systems": len(held_out_kepids),
            "overlap_after_selection": sum(
                int(row["kepid"]) in held_out_kepids for row in rows
            ),
        }
    planets = sum(int(row["confirmed_planet_count"]) for row in rows)
    detectable_planets = sum(int(row["detectable_planet_count"]) for row in rows)
    multiplanet_systems = sum(
        int(row["confirmed_planet_count"]) > 1 for row in rows
    )
    provenance["confirmed_planets"] = {
        "host_systems": counts["CONFIRMED"],
        "known_planets": planets,
        "within_period_limit": detectable_planets,
        "multiplanet_systems": multiplanet_systems,
    }
    (root / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(rows)} systemes ecrits dans {manifest}")
    print("Classes : " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"Planetes confirmees connues : {planets}")
    print("Splits  : " + ", ".join(f"{key}={value}" for key, value in splits.items()))


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def download_light_curves(args: argparse.Namespace) -> None:
    root: Path = args.dataset_dir
    rows = read_manifest(root / "manifest.csv")
    if args.split:
        rows = [row for row in rows if row["split"] == args.split]
    if args.limit is not None:
        rows = rows[: args.limit]
    quarters = args.quarters or list(DEFAULT_QUARTERS)
    fallback_quarters = [1, 2, 3, *range(7, 18)] if args.fallback else []
    unsupported = set(quarters) - QUARTER_FILE_IDS.keys()
    if unsupported:
        raise ValueError(f"Trimestres sans identifiant MAST configure: {sorted(unsupported)}")
    fits_root = root / "fits"
    fits_root.mkdir(parents=True, exist_ok=True)
    status_path = root / "download_status.csv"
    selected_ids = {int(row["kepid"]) for row in rows}
    status_by_id: dict[int, dict[str, str | int]] = {}
    if status_path.exists():
        for previous in read_manifest(status_path):
            kepid = int(previous["kepid"])
            if kepid in selected_ids:
                # Les journaux produits avant l'ajout du fallback n'avaient
                # pas cette colonne. Un statut ok ancien signifie Q4+Q5+Q6.
                previous.setdefault(
                    "quarters",
                    "4;5;6" if previous.get("status") == "ok" else "",
                )
                status_by_id[kepid] = previous
    cached_filenames = {
        path.name for path in (fits_root / "mastDownload").glob("**/*_llc.fits")
    }
    ssl_context = ssl.create_default_context()
    try:
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    def fetch_system(row: dict[str, str]) -> dict[str, str | int]:
        kepid = int(row["kepid"])
        padded = f"{kepid:09d}"
        directory = fits_root / padded
        directory.mkdir(parents=True, exist_ok=True)
        available_quarters: list[int] = []
        errors: list[str] = []
        for quarter in quarters + fallback_quarters:
            if len(available_quarters) >= len(DEFAULT_QUARTERS):
                break
            filename = f"kplr{padded}-{QUARTER_FILE_IDS[quarter]}_llc.fits"
            destination = directory / filename
            if destination.exists() and destination.stat().st_size > 10_000:
                available_quarters.append(quarter)
                continue
            # Reconnait aussi le fichier du cache Lightkurve cree par un essai.
            if filename in cached_filenames:
                available_quarters.append(quarter)
                continue
            prefix = padded[:4]
            url = f"{MAST_LIGHT_CURVE_ROOT}/{prefix}/{padded}/{filename}"
            temporary = destination.with_suffix(".fits.part")
            request = urllib.request.Request(url, headers={"User-Agent": "EmileType-TIPE/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=120, context=ssl_context) as response:
                    with temporary.open("wb") as stream:
                        while block := response.read(1024 * 1024):
                            stream.write(block)
                with temporary.open("rb") as stream:
                    if stream.read(6) != b"SIMPLE":
                        raise ValueError("en-tete FITS absent")
                temporary.replace(destination)
                available_quarters.append(quarter)
            except Exception as error:
                temporary.unlink(missing_ok=True)
                errors.append(f"Q{quarter}: {error}")
        downloaded = len(available_quarters)
        state = "ok" if downloaded >= len(DEFAULT_QUARTERS) else "partial" if downloaded else "missing"
        return {
            "kepid": kepid,
            "status": state,
            "files": downloaded,
            "quarters": ";".join(map(str, available_quarters)),
            "error": " | ".join(errors)[:500],
        }

    terminal_states = {"ok", "partial", "missing"}
    if args.retry_missing or args.fallback:
        terminal_states = {"ok"}
    pending_rows = [
        row
        for row in rows
        if status_by_id.get(int(row["kepid"]), {}).get("status")
        not in terminal_states
    ]
    skipped = len(rows) - len(pending_rows)
    print(
        f"Reprise: {skipped} systemes deja traites, "
        f"{len(pending_rows)} a telecharger",
        flush=True,
    )

    state_counts = Counter(str(item["status"]) for item in status_by_id.values())
    with tqdm(
        total=len(rows),
        initial=skipped,
        desc="Courbes MAST",
        unit="systeme",
        dynamic_ncols=True,
    ) as progress, ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch_system, row) for row in pending_rows]
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            kepid = int(result["kepid"])
            previous = status_by_id.get(kepid)
            if previous is not None:
                state_counts[str(previous["status"])] -= 1
            status_by_id[kepid] = result
            state_counts[str(result["status"])] += 1
            progress.set_postfix(
                complets=state_counts["ok"],
                partiels=state_counts["partial"],
                absents=state_counts["missing"],
                refresh=False,
            )
            progress.update()
            if index == 1 or index % 25 == 0 or index == len(pending_rows):
                status = sorted(
                    status_by_id.values(), key=lambda item: int(item["kepid"])
                )
                write_csv(status_path, status)
    print(f"Journal ecrit dans {status_path}")


def repair_missing_systems(args: argparse.Namespace) -> None:
    """Remplace deterministiquement les témoins sans aucun FITS."""
    root: Path = args.dataset_dir
    manifest_path = root / "manifest.csv"
    status_path = root / "download_status.csv"
    rows = read_manifest(manifest_path)
    statuses = {row["kepid"]: row for row in read_manifest(status_path)}
    missing_rows = [
        row for row in rows if int(statuses.get(row["kepid"], {}).get("files", 0)) == 0
    ]
    if not missing_rows:
        print("Aucun systeme sans courbe a remplacer")
        return
    if any(row["label"] != "CONTROL" for row in missing_rows):
        raise ValueError("Un systeme CONFIRMED est sans courbe; remplacement interdit")

    catalog_root: Path = args.catalog_dir
    stellar_catalog = catalog_root / "q1_q17_dr25_stellar_kepids.csv"
    all_tce_catalog = catalog_root / "q1_q17_dr25_all_tce_kepids.csv"
    all_koi_catalog = catalog_root / "q1_q17_dr25_all_koi_kepids.csv"
    excluded = read_kepids(all_tce_catalog) | read_kepids(all_koi_catalog)
    profile = DATASET_PROFILES[args.profile]
    excluded_manifest = args.exclude_manifest or profile.excluded_manifest
    if excluded_manifest is not None:
        excluded |= manifest_kepids(excluded_manifest)
    candidates = sorted(
        control_systems(read_kepids(stellar_catalog), excluded),
        key=lambda system: _selection_key(system, args.seed),
    )
    used = {int(row["kepid"]) for row in rows}
    reserves = iter(system for system in candidates if system.kepid not in used)
    replacements: list[dict[str, int | str]] = []
    by_kepid = {int(row["kepid"]): row for row in rows}
    for old in missing_rows:
        replacement = next(reserves, None)
        if replacement is None:
            raise ValueError("Plus aucun systeme temoin de reserve")
        old_kepid = int(old["kepid"])
        del by_kepid[old_kepid]
        by_kepid[replacement.kepid] = system_manifest_row(
            replacement, old["split"]
        )
        used.add(replacement.kepid)
        replacements.append(
            {
                "removed_kepid": old_kepid,
                "replacement_kepid": replacement.kepid,
                "split": old["split"],
            }
        )

    updated = sorted(
        by_kepid.values(),
        key=lambda row: (row["split"], row["label"], int(row["kepid"])),
    )
    write_csv(manifest_path, updated)
    provenance_path = root / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["manifest_sha256"] = sha256(manifest_path)
    provenance.setdefault("availability_replacements", []).append(
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "reason": "no Kepler long-cadence FITS found in Q1-Q17",
            "systems": replacements,
        }
    )
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for replacement in replacements:
        print(
            f"{replacement['removed_kepid']} -> "
            f"{replacement['replacement_kepid']} ({replacement['split']})"
        )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--profile",
        choices=tuple(DATASET_PROFILES),
        default="benchmark",
        help="benchmark rare ou dataset equilibre pour l'apprentissage",
    )
    command.add_argument(
        "--dataset-dir",
        type=Path,
        help="remplace le repertoire defini par le profil",
    )
    command.add_argument(
        "--catalog-dir",
        type=Path,
        default=config.DATA_DIR / "kepler_3000" / "source",
        help="cache commun des catalogues NASA",
    )
    command.add_argument(
        "--exclude-manifest",
        type=Path,
        help="manifeste dont tous les KIC doivent etre exclus",
    )
    subparsers = command.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest", help="Selectionne les systemes")
    manifest.add_argument("--max-period", type=float, default=DEFAULT_MAX_PERIOD_DAYS)
    manifest.add_argument("--seed", type=int, default=DEFAULT_SEED)
    manifest.add_argument("--force-catalog", action="store_true")
    manifest.set_defaults(handler=build_manifest)

    download = subparsers.add_parser("download", help="Telecharge les courbes MAST")
    download.add_argument("--quarters", type=int, nargs="+")
    download.add_argument("--split", choices=("train", "validation", "test"))
    download.add_argument("--limit", type=int)
    download.add_argument("--workers", type=int, default=4)
    download.add_argument(
        "--retry-missing",
        action="store_true",
        help="Retente aussi les trimestres deja notes partial/missing",
    )
    download.add_argument(
        "--fallback",
        action="store_true",
        help="Complete les systemes partiels avec Q1-Q3 puis Q7-Q17 jusqu'a 3 FITS",
    )
    download.set_defaults(handler=download_light_curves)

    repair = subparsers.add_parser(
        "repair", help="Remplace les temoins qui n'ont aucun FITS"
    )
    repair.add_argument("--seed", type=int, default=DEFAULT_SEED)
    repair.set_defaults(handler=repair_missing_systems)
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.dataset_dir is None:
        args.dataset_dir = (
            config.DATA_DIR / DATASET_PROFILES[args.profile].directory_name
        )
    try:
        args.handler(args)
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"erreur: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
