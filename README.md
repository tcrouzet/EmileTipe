# EmileTipe — détection de transits dans les courbes de lumière de Kepler

Ce projet étudie une question simple : **un réseau de neurones peut-il mieux détecter les systèmes planétaires qu'une méthode physique classique, le Box Least Squares (BLS), sur exactement les mêmes observations ?**

La première étape, documentée ici, construit un jeu de 3 000 systèmes Kepler et établit une référence reproductible avec le BLS officiel d'Astropy. Le réseau de neurones sera ajouté dans une étape ultérieure. Il devra utiliser les mêmes systèmes, les mêmes labels et les mêmes partitions afin que la comparaison soit scientifiquement interprétable.

Le [tableau de bord](https://tcrouzet.github.io/EmileTipe/) présente les résultats système par système et la matrice de confusion du BLS.

## 1. Construction du jeu de données

### 1.1 Unité statistique et labels

L'unité étudiée est un **système stellaire**, identifié par son Kepler Input Catalog ID (`KIC`), et non une planète isolée. Le problème est une classification binaire fortement déséquilibrée :

| Classe | Définition | Nombre de systèmes |
|---|---|---:|
| `CONFIRMED` | au moins une planète Kepler confirmée autour de l'étoile | 42 |
| `CONTROL` | aucune entrée dans les catalogues DR25 des KOI ou des TCE | 2 958 |
| **Total** |  | **3 000** |

Les 42 systèmes positifs contiennent 59 planètes confirmées. Onze sont des systèmes multiplanétaires et 54 des 59 planètes ont une période inférieure ou égale à 30 jours, intervalle exploré par le BLS.

Cette faible prévalence, 42/3 000 = **1,4 %**, est volontaire. Un jeu artificiellement équilibré rendrait la tâche plus facile mais ne testerait pas correctement le principal problème d'une recherche de transits : obtenir peu de fausses alertes au milieu d'une grande majorité d'étoiles sans planète connue.

### 1.2 Sources scientifiques

Les labels et les identifiants proviennent d'archives publiques de la NASA :

- [NASA Exoplanet Archive — Planetary Systems Composite Parameters](https://exoplanetarchive.ipac.caltech.edu/docs/API_PSCompPars_columns.html), pour sélectionner les planètes confirmées découvertes par Kepler ;
- [Kepler DR25 KOI table](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html), catalogue des objets d'intérêt Kepler ;
- [Kepler DR25 TCE table](https://exoplanetarchive.ipac.caltech.edu/docs/API_kepcandidate_columns.html), catalogue des événements de franchissement de seuil produits par le pipeline Kepler ;
- [MAST — Kepler Mission](https://archive.stsci.edu/missions-and-data/kepler), pour les courbes de lumière calibrées au format FITS.

Le dataset Kaggle *Kepler Labelled Time Series Data*, téléchargé initialement dans `data/`, reste disponible comme point de comparaison historique. Il n'est pas utilisé comme vérité terrain principale : ses étiquettes sont issues de candidats et sa représentation par courbes déjà transformées ne permet pas la comparaison expérimentale souhaitée avec les observations FITS complètes.

### 1.3 Procédure de sélection

La construction est entièrement déterministe, avec une graine fixée dans `script/config.py` :

1. sélectionner les hôtes de planètes **confirmées**, découvertes par Kepler et disposant d'un `KIC` exploitable ;
2. conserver 42 systèmes positifs ;
3. construire l'ensemble interdit des étoiles présentes dans le catalogue DR25 des KOI ou dans celui des TCE ;
4. tirer les contrôles dans le catalogue stellaire DR25 après exclusion de cet ensemble interdit ;
5. télécharger jusqu'à trois courbes de lumière Kepler *long cadence* par système depuis MAST ;
6. enregistrer chaque choix et chaque URL dans les fichiers de provenance.

Cette définition des contrôles est stricte : un contrôle n'est pas simplement une étoile dont aucune planète n'est confirmée ; c'est une étoile sans KOI et sans TCE DR25. Elle réduit le risque d'introduire comme négatif un signal déjà considéré comme candidat. Elle ne prouve cependant pas l'absence physique de planète : une planète non détectée peut toujours exister. Les labels décrivent donc l'état des catalogues, pas une vérité absolue sur chaque étoile.

La couverture effectivement téléchargée est la suivante :

| Courbes FITS disponibles | Systèmes |
|---:|---:|
| 3 | 2 786 |
| 2 | 97 |
| 1 | 117 |
| 0 | 0 |

Tous les systèmes positifs possèdent trois fichiers FITS. Les observations représentent environ 9,2 Go et ne sont pas versionnées dans Git ; elles sont régénérables à partir du manifeste.

Les principaux artefacts sont :

- `data/kepler_3000/manifest.csv` : un enregistrement par système, avec son label et les paramètres connus des planètes ;
- `data/kepler_3000/provenance.json` : sources, requêtes et paramètres de construction ;
- `data/kepler_3000/download_status.csv` : état des téléchargements, utilisé pour reprendre une exécution interrompue ;
- `data/kepler_3000/fits/` : observations brutes, volontairement ignorées par Git.

### 1.4 Reproductibilité et reprise après interruption

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

### 1.5 Validation et test

Le BLS ne fait pas d'apprentissage au sens d'un réseau de neurones, mais son seuil de décision et ses règles de sélection sont néanmoins des paramètres ajustés sur les données. Les évaluer sur les mêmes objets produirait une estimation optimiste.

Le projet utilise donc une **validation croisée à six plis** : à chaque itération, cinq sixièmes des systèmes servent à choisir le seuil et le sixième restant sert à mesurer la performance. Chaque système est évalué exactement une fois hors du pli ayant servi au réglage. Les 3 000 prédictions hors pli sont ensuite réunies dans une unique matrice de confusion.

Cette procédure sera conservée pour le futur réseau de neurones. Un jeu de test final, laissé intact pendant le développement comparatif, pourra en complément servir à la conclusion du TIPE.

## 2. Méthode Box Least Squares

### 2.1 Principe physique et mathématique

Lorsqu'une planète passe devant son étoile, elle masque une petite partie du disque stellaire et provoque une baisse quasi périodique du flux observé. À première approximation, un transit ressemble à une boîte :

- un flux constant hors transit ;
- une baisse de profondeur donnée pendant une courte durée ;
- une répétition à la période orbitale.

Le **Box Least Squares** replie la courbe de lumière sur de nombreuses périodes d'essai. Pour chaque période, il cherche la phase, la durée et la profondeur de la boîte qui minimisent les résidus quadratiques entre le modèle et les observations. Le maximum de puissance du périodogramme indique la périodicité rectangulaire la plus compatible avec les données.

Le BLS est particulièrement adapté aux transits : un périodogramme sinusoïdal classique dilue un signal bref, alors que le modèle en boîte concentre l'information dans la fraction de phase effectivement occupée par le transit.

### 2.2 Bibliothèque retenue

L'implémentation utilisée est [`astropy.timeseries.BoxLeastSquares`](https://docs.astropy.org/en/stable/timeseries/bls.html), fournie par **Astropy**, bibliothèque scientifique de référence en astronomie. Ce choix évite de comparer le futur réseau à une approximation personnelle du BLS et fournit une implémentation testée, documentée et fondée sur l'algorithme publié.

Références principales :

- Kovács, Zucker & Mazeh (2002), [*A box-fitting algorithm in the search for periodic transits*](https://doi.org/10.1051/0004-6361:20020802) ;
- Astropy Collaboration (2022), [*The Astropy Project: Sustaining and Growing a Community-oriented Open-source Project and the Latest Major Release (v5.0)*](https://doi.org/10.3847/1538-4357/ac7c74).

La version est bornée dans `requirements.txt` (`astropy>=8,<9`) afin de limiter les variations de résultats entre environnements.

### 2.3 Prétraitement des courbes

Pour chaque système, les segments FITS disponibles sont concaténés puis :

1. les valeurs non finies et les mesures invalides sont retirées ;
2. le flux est normalisé par segment ;
3. les variations lentes sont supprimées afin de préserver les baisses brèves ;
4. les valeurs aberrantes positives sont rejetées sans supprimer arbitrairement les transits négatifs ;
5. le BLS est calculé sur la série temporelle nettoyée.

Les mêmes données brutes et des règles de prétraitement documentées devront être fournies au réseau de neurones. Toute différence de représentation devra être annoncée comme une composante de la méthode comparée.

### 2.4 Domaine de recherche et score de décision

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

### 2.5 Résultats de référence

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

## 3. Comparaison future avec un réseau de neurones

L'hypothèse à tester est qu'un réseau de neurones peut apprendre des formes plus riches qu'une boîte périodique : géométrie réelle du transit, bruit corrélé, variabilité stellaire et signatures instrumentales. Une amélioration n'est cependant démontrée que si le protocole reste identique.

La comparaison devra donc respecter les conditions suivantes :

- mêmes 3 000 identifiants KIC et mêmes labels ;
- mêmes plis de validation croisée ou même jeu de test final gelé ;
- absence de fuite d'information entre observations d'un même système ;
- seuils choisis uniquement sur les plis d'entraînement/validation ;
- publication de la matrice de confusion, de la précision, du rappel, du F1 et des courbes précision-rappel ;
- prise en compte du temps de calcul et du coût d'entraînement.

L'objectif n'est donc pas d'atteindre artificiellement 100 %, mais de déterminer si le réseau améliore de façon reproductible le compromis entre planètes retrouvées et fausses alertes par rapport au meilleur BLS retenu.

## 4. Tableau de bord et vérifications

Le tableau de bord statique est contenu dans `web/`. Il affiche les 3 000 décisions, la matrice de confusion, les métriques, les scores et les périodes estimées. Il peut être consulté localement sans modifier les données :

```bash
cd web
../.venv/bin/python -m http.server 8000
```

Puis ouvrir <http://localhost:8000>. Le déploiement public est assuré par GitHub Pages à chaque modification de `web/` sur la branche `main`.

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
