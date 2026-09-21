"""Parametres communs du projet EmileType.

Les temps sont exprimes en jours. Le jeu Kaggle ne fournit pas la colonne temps :
on la reconstruit avec la cadence longue de Kepler (environ 29,4 minutes).
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DATA_FILE = DATA_DIR / "exoTest.csv"

# Acquisition Kepler
CADENCE_DAYS = 29.4 / (24.0 * 60.0)

# Espace de recherche BLS. Une grille uniforme en frequence evite de perdre la
# coherence de phase aux longues periodes.
MIN_PERIOD_DAYS = 0.5
MAX_PERIOD_DAYS = 30.0
N_PERIODS = 1_000
OFFICIAL_BLS_PERIODS = 100_000
TRANSIT_DURATIONS_DAYS = (0.04, 0.08, 0.125, 0.20, 0.30, 0.50)
# Une occultation planetaire n'occupe qu'une petite fraction de l'orbite.
MAX_TRANSIT_FRACTION = 0.12
N_PHASE_BINS = 400

# Nettoyage et decision. La fenetre doit etre nettement plus longue qu'un
# transit mais assez courte pour retirer les variations stellaires lentes.
DETREND_WINDOW_DAYS = 2.0
SIGMA_CLIP = 8.0
# Le SDE normalise le maximum du periodogramme par rapport a tous les autres
# essais. Ce seuil reste a calibrer exclusivement sur le jeu d'entrainement.
# Calibre par maximisation du F1 sur 37 positifs + 500 negatifs de exoTrain.
# Arrondi de 39.553755 afin de garder un seuil explicable et reproductible.
DETECTION_SDE_THRESHOLD = 40.0
# Seuil opérationnel du score Astropy vetting, obtenu après validation croisée
# stratifiée à 6 folds. Les métriques finales restent celles hors-fold.
OFFICIAL_BLS_VETTED_THRESHOLD = 162.8
CALIBRATION_DATASET = "exoTrain.csv"
CALIBRATION_SYSTEMS = 537
CALIBRATION_CRITERION = "F1"

# Dans les CSV Kaggle : 1 = sans exoplanete, 2 = avec exoplanete.
NEGATIVE_LABEL = 1
POSITIVE_LABEL = 2
