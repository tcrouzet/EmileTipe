# EmileTipe — détection de transits dans les courbes de lumière de Kepler

Ce projet étudie une question simple : **un réseau de neurones peut-il mieux détecter les systèmes planétaires qu'une méthode physique classique, le Box Least Squares (BLS), sur exactement les mêmes observations ?**

La première étape, documentée ici, construit un jeu de 3 000 systèmes Kepler et établit une référence reproductible avec le BLS officiel d'Astropy. Le réseau de neurones sera ajouté dans une étape ultérieure. Il devra utiliser les mêmes systèmes, les mêmes labels et les mêmes partitions afin que la comparaison soit scientifiquement interprétable.

Le tableau de bord contenu dans `web/` présente les résultats système par système et la matrice de confusion du BLS. Son URL GitHub Pages prévue est <https://tcrouzet.github.io/EmileTipe/> ; elle ne deviendra accessible qu'après passage du dépôt en visibilité publique ou activation d'un forfait GitHub compatible avec Pages sur les dépôts privés.

## 1. Que contiennent les données Kepler ?

### 1.1 De l'image du télescope à la courbe de lumière

Le télescope spatial Kepler a mesuré de manière répétée la lumière reçue de plus de 150 000 étoiles. Il ne fournit pas directement une réponse « planète » ou « pas de planète ». Pour chaque étoile, il fournit principalement une **série temporelle photométrique** : à chaque instant `t`, on associe un flux lumineux `F(t)`.

Un transit se produit quand une planète passe entre l'étoile et l'observateur. Le flux baisse alors pendant quelques heures, puis retrouve son niveau habituel. Dans le cas simple d'une planète petite devant une étoile uniformément lumineuse, la profondeur relative du transit est approximativement :

```text
δ = (F_hors transit - F_transit) / F_hors transit ≈ (R_planète / R_étoile)²
```

Une planète de période orbitale `P` produit donc une baisse de flux répétée aux dates `t₀ + nP`. L'objet étudié par le BLS n'est ni une photographie ni un tableau déjà classé : c'est l'ensemble des couples irrégulièrement espacés `(temps, flux)` mesurés pour une étoile.

### 1.2 Un fichier FITS correspond à un segment d'observation

Les observations sont téléchargées depuis [MAST — Kepler Mission](https://archive.stsci.edu/missions-and-data/kepler) dans le format astronomique FITS. Kepler découpe sa mission en **quarters**, des campagnes d'environ trois mois. Un fichier `*_llc.fits` contient la courbe d'une étoile pendant un quarter en cadence longue (*long cadence*), soit une intégration toutes les **29,4 minutes** environ.

Chaque fichier comprend trois parties, appelées HDU :

| HDU | Contenu |
|---|---|
| `PRIMARY` | métadonnées de la cible : identifiant KIC, quarter, position céleste, magnitude Kepler… |
| `LIGHTCURVE` | table temporelle : une ligne par cadence et 20 colonnes de mesure |
| `APERTURE` | masque de pixels employé pour la photométrie |

Les colonnes de `LIGHTCURVE` se répartissent en plusieurs familles :

| Famille | Variables principales | Signification |
|---|---|---|
| Temps | `TIME`, `TIMECORR`, `CADENCENO` | date barycentrique, correction temporelle et numéro de cadence |
| Photométrie brute | `SAP_FLUX`, `SAP_FLUX_ERR` | flux mesuré dans l'ouverture et son incertitude |
| Fond | `SAP_BKG`, `SAP_BKG_ERR` | estimation de la lumière de fond |
| Photométrie corrigée | `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR` | flux après correction des tendances instrumentales par le pipeline PDC |
| Qualité | `SAP_QUALITY` | masque de bits signalant les cadences affectées par un incident |
| Position | `PSF_CENTR*`, `MOM_CENTR*`, `POS_CORR*` | position de l'image de l'étoile sur le détecteur |

`TIME` est exprimé en jours BKJD (*Barycentric Kepler Julian Date*) :

```text
BKJD = BJD - 2 454 833
```

`PDCSAP_FLUX` est exprimé en électrons par seconde (`e⁻/s`). Le pipeline de ce projet n'utilise que trois colonnes :

- `TIME`, qui préserve les dates réelles et donc les interruptions d'observation ;
- `PDCSAP_FLUX`, choisi plutôt que `SAP_FLUX` parce qu'il est déjà corrigé d'une partie des effets instrumentaux communs ;
- `SAP_QUALITY`, utilisé pour ne conserver que les lignes de qualité nulle.

Les incertitudes `PDCSAP_FLUX_ERR`, les positions et le fond ne sont actuellement **pas fournis au BLS**. C'est un choix méthodologique explicite et une limite : un futur modèle pourra éventuellement exploiter ces variables, mais il faudra alors distinguer le gain dû à l'algorithme du gain dû à des entrées supplémentaires. La structure des FITS est détaillée dans le [Kepler Archive Manual](https://archive.stsci.edu/kepler/manuals/archive_manual.pdf).

### 1.3 Qu'est-ce qu'un « système » dans ce projet ?

Un système est une étoile identifiée par son **Kepler Input Catalog ID** (`KIC`). Il peut contenir zéro, une ou plusieurs planètes connues. Jusqu'à trois fichiers trimestriels sont associés à chaque KIC, puis leurs points sont réunis en une seule série de longueur variable :

```text
système KIC = [(t₁, F₁), (t₂, F₂), …, (tₙ, Fₙ)] + métadonnées + label
```

Les segments ne sont pas recollés artificiellement dans le temps : les trous entre quarters ou entre cadences restent présents dans `TIME`. En revanche, chaque segment est divisé par son propre flux médian avant concaténation :

```text
flux_relatif(t) = PDCSAP_FLUX(t) / médiane_du_quarter - 1
```

Le flux relatif vaut donc approximativement zéro hors transit ; un transit apparaît comme une petite excursion négative.

Exemple réel, le système positif **KIC 5542466 / Kepler-1756**, dont la planète connue a une période de 2,35574505 jours et une durée de transit cataloguée de 1,796 heure :

| Quarter | Lignes FITS | Mesures valides retenues | Intervalle BKJD | Flux médian |
|---:|---:|---:|---:|---:|
| Q4 | 4 397 | 3 870 | 352,40–442,20 | 7 663,47 e⁻/s |
| Q5 | 4 634 | 4 231 | 443,92–537,63 | 8 109,93 e⁻/s |
| Q7 | 4 375 | 3 638 | 630,22–719,55 | 7 620,17 e⁻/s |
| **Système complet** | **13 406** | **11 739** | trois segments | série de 11 739 couples `(t, F)` |

Q7 remplace ici Q6, indisponible pour cette cible. Cet exemple montre pourquoi les systèmes n'ont pas tous le même nombre de points et pourquoi une courbe Kepler contient des trous. Le BLS accepte directement ces temps irréguliers. Un réseau de neurones exigera plus tard une décision supplémentaire documentée : rééchantillonnage, découpage en fenêtres ou architecture acceptant les longueurs variables.

![Courbe de lumière réelle du système KIC 5542466, avant et après repliement à la période orbitale](docs/kic-5542466-light-curve.png)

Le panneau supérieur représente le flux relatif réellement fourni au début du traitement : trois plages d'observation sont visibles, séparées par des lacunes. À cette échelle, les transits de quelques heures sont presque invisibles. Le panneau inférieur superpose toutes les orbites en ramenant chaque mesure à sa phase dans une période de 2,355745 jours. La baisse cohérente autour de la phase zéro devient alors visible ; c'est précisément l'information périodique recherchée par le BLS. La ligne rouge est une médiane par intervalle de phase, uniquement ajoutée pour rendre la figure lisible.

## 2. Comment le dataset de 3 000 systèmes est-il construit ?

### 2.1 Les catégories astronomiques de Kepler

Il faut distinguer les catégories des catalogues de celles retenues pour l'expérience :

| Catégorie astronomique | Définition | Utilisation ici |
|---|---|---|
| **Cible Kepler** | étoile observée par Kepler | population de départ |
| **TCE** (*Threshold Crossing Event*) | signal périodique ayant franchi le seuil du pipeline de détection | tous ses hôtes sont exclus des contrôles |
| **KOI** (*Kepler Object of Interest*) | TCE retenu pour une analyse astronomique plus poussée | tous ses hôtes sont exclus des contrôles |
| **CANDIDATE** | KOI compatible avec une planète, mais non confirmé | non utilisé comme positif ou négatif |
| **FALSE POSITIVE** | KOI attribué à une autre cause : binaire à éclipses, contamination, artefact… | non utilisé comme contrôle |
| **CONFIRMED** | planète dont la nature a été confirmée | source de la classe positive |
| **CONTROL** | catégorie créée pour ce projet : cible sans aucun KOI ni TCE DR25 | classe négative expérimentale |

Le mot `CONTROL` ne signifie donc pas « étoile dont on sait qu'elle ne possède aucune planète ». Il signifie plus précisément « aucune signature n'a été enregistrée comme KOI ou TCE dans DR25 ». Une planète trop petite, trop longue, non transitante ou manquée par le pipeline peut exister autour d'un contrôle. C'est une incertitude de label inévitable dans ce type d'étude.

### 2.2 Sources des labels et des observations

Quatre tables publiques sont croisées :

- [Kepler DR25 KOI](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html), interrogée avec `koi_disposition = 'CONFIRMED'` pour les positifs ;
- la même table KOI sans filtre, afin d'exclure des contrôles tous les candidats et faux positifs connus ;
- [Kepler DR25 TCE](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html), afin d'exclure tout hôte possédant un événement détecté, même non devenu KOI ;
- le catalogue stellaire `q1_q17_dr25_stellar`, qui fournit la population des cibles observées.

Les courbes correspondantes sont ensuite obtenues depuis MAST. Les URL exactes, les requêtes et les empreintes SHA-256 des catalogues téléchargés sont conservées dans `data/kepler_3000/provenance.json`.

Le dataset Kaggle *Kepler Labelled Time Series Data*, téléchargé initialement dans `data/`, n'est pas la vérité terrain de cette expérience. Il contient des courbes déjà transformées et des labels de candidats. Il ne permet pas de repartir des mêmes FITS ni de définir aussi strictement la population de contrôle.

### 2.3 Sélection des deux classes

L'unité statistique est le système KIC, et non chaque planète. La construction applique les étapes suivantes :

1. regrouper par KIC tous les KOI de disposition `CONFIRMED` ;
2. rendre positif tout système possédant au moins une planète confirmée de période `P ≤ 30 jours` ;
3. former la population de contrôle à partir des cibles stellaires après retrait de **tous** les hôtes KOI, TCE ou confirmés ;
4. classer chaque population par une clé SHA-256 dépendant de la graine `727`, puis prendre les effectifs fixés ;
5. répartir séparément chaque classe entre entraînement, validation et test, toujours avec cette clé déterministe.

Avant échantillonnage, 1 610 systèmes confirmés satisfont le critère de période et 182 762 contrôles satisfont le critère d'exclusion. Le sous-ensemble final est volontairement très déséquilibré :

| Label du dataset | Sens exact | Systèmes |
|---|---|---:|
| `CONFIRMED` | ≥ 1 planète confirmée avec `P ≤ 30 jours` | 42 |
| `CONTROL` | cible DR25 sans aucun KOI ni TCE DR25 | 2 958 |
| **Total** |  | **3 000** |

Les 42 positifs contiennent 59 planètes confirmées au total : 54 sont dans le domaine `P ≤ 30 jours` du BLS, et 11 étoiles sont multiplanétaires. La prévalence des systèmes positifs vaut 42/3 000 = **1,4 %**. Cette rareté est un aspect central de l'expérience : même un faible taux de fausses alertes peut alors dégrader fortement la précision.

### 2.4 Découpage expérimental

| Partition | Confirmés | Contrôles | Total | Rôle prévu |
|---|---:|---:|---:|---|
| entraînement | 32 | 2 068 | 2 100 | ajustement d'une méthode apprenante |
| validation | 5 | 445 | 450 | choix des hyperparamètres et du seuil |
| test | 5 | 445 | 450 | mesure finale indépendante |

Pour la référence BLS actuellement affichée, les 3 000 scores sont également évalués par validation croisée à six plis : le seuil de chaque pli est choisi sans consulter les systèmes évalués dans ce pli. Cette seconde représentation permet d'obtenir une décision hors pli pour chaque système. Lors de la comparaison finale avec le réseau, le protocole devra être figé avant de consulter le test.

### 2.5 Sélection des segments de courbe

Le téléchargement cherche d'abord les quarters Q4, Q5 et Q6 pour obtenir trois intervalles comparables. Lorsqu'un de ces fichiers n'existe pas, il cherche un remplacement dans Q1–Q3 puis Q7–Q17. Au maximum trois fichiers sont conservés par système.

| Nombre de fichiers FITS disponibles | Systèmes |
|---:|---:|
| 3 | 2 786 |
| 2 | 97 |
| 1 | 117 |
| 0 | 0 |

Tous les positifs disposent de trois fichiers. Les différences de couverture constituent néanmoins un biais possible : une série plus courte contient moins de transits observables. Les observations occupent environ 9,2 Go et ne sont pas versionnées dans Git.

### 2.6 Contenu du manifeste

`data/kepler_3000/manifest.csv` contient une ligne par système :

| Variable | Sens |
|---|---|
| `kepid` | identifiant KIC de l'étoile |
| `label` | `CONFIRMED` ou `CONTROL` |
| `has_confirmed_planet` | indicateur binaire 0/1 |
| `confirmed_planet_count` | nombre total de planètes confirmées du système |
| `detectable_planet_count` | nombre de planètes confirmées avec `P ≤ 30 jours` |
| `confirmed_planet_names` | noms officiels séparés par `;` |
| `split` | `train`, `validation` ou `test` |
| `signal_count` | nombre de signaux confirmés recherchables par le BLS |
| `periods_days` | périodes cataloguées, en jours |
| `epochs_bkjd` | dates centrales de transit, en BKJD |
| `durations_hours` | durées de transit cataloguées, en heures |
| `quarters` | quarters demandés initialement ; les fichiers réellement obtenus sont consignés dans `download_status.csv` |

`provenance.json` décrit la sélection et les sources ; `download_status.csv` permet la reprise des téléchargements ; `fits/<KIC>/` contient les courbes brutes.

### 2.7 Reproductibilité et reprise après interruption

Installation :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Construction du manifeste, puis téléchargement ou reprise du dataset :

```bash
.venv/bin/python -m script.dataset.build manifest
.venv/bin/python -m script.dataset.build download --fallback
```

Le script écrit son état au fur et à mesure. Une relance ne retélécharge pas les fichiers déjà validés et reprend au premier élément incomplet.

## 3. Méthode Box Least Squares

### 3.1 Principe physique et mathématique

Lorsqu'une planète passe devant son étoile, elle masque une petite partie du disque stellaire et provoque une baisse quasi périodique du flux observé. À première approximation, un transit ressemble à une boîte :

- un flux constant hors transit ;
- une baisse de profondeur donnée pendant une courte durée ;
- une répétition à la période orbitale.

Le **Box Least Squares** replie la courbe de lumière sur de nombreuses périodes d'essai. Pour chaque période, il cherche la phase, la durée et la profondeur de la boîte qui minimisent les résidus quadratiques entre le modèle et les observations. Le maximum de puissance du périodogramme indique la périodicité rectangulaire la plus compatible avec les données.

Le BLS est particulièrement adapté aux transits : un périodogramme sinusoïdal classique dilue un signal bref, alors que le modèle en boîte concentre l'information dans la fraction de phase effectivement occupée par le transit.

### 3.2 Bibliothèque retenue

L'implémentation utilisée est [`astropy.timeseries.BoxLeastSquares`](https://docs.astropy.org/en/stable/timeseries/bls.html), fournie par **Astropy**, bibliothèque scientifique de référence en astronomie. Ce choix évite de comparer le futur réseau à une approximation personnelle du BLS et fournit une implémentation testée, documentée et fondée sur l'algorithme publié.

Références principales :

- Kovács, Zucker & Mazeh (2002), [*A box-fitting algorithm in the search for periodic transits*](https://doi.org/10.1051/0004-6361:20020802) ;
- Astropy Collaboration (2022), [*The Astropy Project: Sustaining and Growing a Community-oriented Open-source Project and the Latest Major Release (v5.0)*](https://doi.org/10.3847/1538-4357/ac7c74).

La version est bornée dans `requirements.txt` (`astropy>=8,<9`) afin de limiter les variations de résultats entre environnements.

### 3.3 Prétraitement des courbes

Pour chaque système, le traitement réellement exécuté est le suivant :

1. dans chaque FITS, garder `TIME` et `PDCSAP_FLUX` uniquement lorsque `SAP_QUALITY = 0` et que les deux valeurs sont finies ;
2. diviser le flux par la médiane du quarter et soustraire 1 ;
3. concaténer les segments et les trier par `TIME` ;
4. soustraire une médiane glissante d'environ 2 jours (99 cadences) pour retirer les variations lentes ;
5. centrer les résidus par leur médiane et les diviser par `1,4826 × MAD`, estimation robuste de l'écart-type ;
6. borner les valeurs normalisées entre −8 et +8 ;
7. fournir au BLS les deux vecteurs `TIME` et flux résiduel normalisé.

Cette opération transforme donc les électrons par seconde en une grandeur sans dimension exprimée en unités de bruit robuste. Le temps est seulement décalé pour commencer à zéro ; les écarts temporels ne sont pas supprimés.

Les mêmes données brutes et des règles de prétraitement documentées devront être fournies au réseau de neurones. Toute différence de représentation devra être annoncée comme une composante de la méthode comparée.

### 3.4 Domaine de recherche et score de décision

La recherche officielle évalue **100 000 périodes entre 0,5 et 30 jours** et plusieurs durées de transit. La taille de la grille a été vérifiée par une étude de convergence sur les positifs d'entraînement :

| Nombre de périodes | Périodes retrouvées |
|---:|---:|
| 50 000 | 22/32 |
| 100 000 | 23/32 |
| 200 000 | 23/32 |

Le passage de 100 000 à 200 000 points n'améliore donc plus cette mesure tout en doublant approximativement le coût du périodogramme.

Un pic BLS élevé ne suffit pas : les variations stellaires, les discontinuités instrumentales et les harmoniques peuvent également produire une forte puissance. Le pipeline applique donc un contrôle (*vetting*) et emploie le score :

```text
score = sqrt(max(0, -Δlog L_harmonique) / (durée / période))
```

où `Δlog L_harmonique` mesure l'avantage du signal en boîte sur un modèle harmonique. Le seuil retenu par validation est **162,8**. Une prédiction est positive si le score est supérieur ou égal à ce seuil. Ce nombre n'est pas une constante universelle : il dépend du dataset, du prétraitement et du compromis recherché entre rappel et fausses alertes.

### 3.5 Résultats de référence

Les prédictions hors pli de la validation croisée donnent :

|  | Planète confirmée | Contrôle |
|---|---:|---:|
| **BLS positif** | 11 vrais positifs | 14 faux positifs |
| **BLS négatif** | 31 faux négatifs | 2 944 vrais négatifs |

Soit :

- précision : **44,0 %** ;
- rappel : **26,2 %** ;
- score F1 : **32,8 %** ;
- spécificité : **99,53 %**.

La période connue, ou son harmonique ×0,5/×2 à 1 % près, est retrouvée pour 29 des 42 systèmes positifs. Parmi les 11 systèmes finalement déclarés positifs, 10 ont une période correcte selon ce critère.

Ces chiffres ne signifient pas que le BLS « fonctionne à 44 % ». La précision mesure la proportion de vraies planètes parmi les alertes, tandis que le rappel mesure la proportion des systèmes confirmés retrouvés. Dans un dataset où seuls 1,4 % des systèmes sont positifs, 14 fausses alertes suffisent déjà à réduire fortement la précision. Le résultat exprime donc un compromis conservateur : très peu de faux positifs, mais beaucoup de planètes manquées.

Exécution complète :

```bash
.venv/bin/python -m script.evaluate_fits --split train --engine official \
  --threshold 162.8 --output data/bls-official-train.json
.venv/bin/python -m script.evaluate_fits --split validation --engine official \
  --threshold 162.8 --output data/bls-official-validation.json
.venv/bin/python -m script.evaluate_fits --split test --engine official \
  --threshold 162.8 --output data/bls-official-test.json
.venv/bin/python -m script.cross_validate_official_bls
.venv/bin/python script/export_official_dashboard.py
```

Les paramètres sont centralisés dans `script/config.py`. Les résultats numériques sont exportés dans `data/bls-official-*.json`, puis la version destinée au site dans `web/results.json`.

## 4. Comparaison future avec un réseau de neurones

L'hypothèse à tester est qu'un réseau de neurones peut apprendre des formes plus riches qu'une boîte périodique : géométrie réelle du transit, bruit corrélé, variabilité stellaire et signatures instrumentales. Une amélioration n'est cependant démontrée que si le protocole reste identique.

La comparaison devra donc respecter les conditions suivantes :

- mêmes 3 000 identifiants KIC et mêmes labels ;
- mêmes plis de validation croisée ou même jeu de test final gelé ;
- absence de fuite d'information entre observations d'un même système ;
- seuils choisis uniquement sur les plis d'entraînement/validation ;
- publication de la matrice de confusion, de la précision, du rappel, du F1 et des courbes précision-rappel ;
- prise en compte du temps de calcul et du coût d'entraînement.

L'objectif n'est donc pas d'atteindre artificiellement 100 %, mais de déterminer si le réseau améliore de façon reproductible le compromis entre planètes retrouvées et fausses alertes par rapport au meilleur BLS retenu.

## 5. Tableau de bord et vérifications

Le tableau de bord statique est contenu dans `web/`. Il affiche les 3 000 décisions, la matrice de confusion, les métriques, les scores et les périodes estimées. Il peut être consulté localement sans modifier les données :

```bash
cd web
../.venv/bin/python -m http.server 8000
```

Puis ouvrir <http://localhost:8000>. Le workflow de déploiement GitHub Pages est installé, mais GitHub refuse actuellement son activation parce que le dépôt est privé et que le forfait du propriétaire ne prend pas en charge Pages pour les dépôts privés. Une fois ce point réglé, chaque modification de `web/` sur `main` republiera automatiquement le site.

Tests :

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Organisation du dépôt

```text
script/
  config.py                    paramètres communs
  dataset/build.py             construction et reprise du dataset
  bls/official.py              BLS Astropy et validation croisée
  export_official_dashboard.py export des résultats vers le site
web/                           dashboard statique GitHub Pages
slides/                        présentation générale du projet
tests/                         tests automatisés
data/kepler_3000/              manifeste et provenance
```

Les données volumineuses et les résultats intermédiaires régénérables ne sont pas publiés dans Git. Le manifeste et la provenance permettent d'identifier précisément les observations utilisées.
