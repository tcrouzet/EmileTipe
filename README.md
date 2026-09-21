# EmileTipe — détecter des exoplanètes dans les données de Kepler

## Question étudiée

Le but du projet est de comparer deux méthodes sur **exactement les mêmes observations** :

1. le **Box Least Squares** (BLS), méthode classique conçue spécialement pour rechercher des transits planétaires ;
2. un **réseau de neurones**, qui sera développé dans une deuxième étape.

La question n'est pas simplement « quelle méthode donne le plus grand pourcentage ? ». Elle est plus précise :

> Sur un ensemble réaliste contenant très peu de systèmes planétaires, un réseau de neurones retrouve-t-il davantage de planètes que le BLS sans produire trop de fausses alertes ?

La première version du projet construit donc un dataset commun de 3 000 systèmes Kepler, applique un BLS fondé sur Astropy et mesure ses performances. Ce résultat sera la référence à battre.

Le [tableau de bord public](https://tcrouzet.github.io/EmileTipe/) permet d'examiner les résultats système par système.

## Vue d'ensemble : du télescope à la décision

Avant d'entrer dans les détails, voici toute la chaîne de traitement :

```text
Lumière d'une étoile
        │
        ▼
Mesures Kepler : date + flux lumineux
        │
        ▼
Fichiers FITS de plusieurs quarters
        │
        ├──────────────► catalogues NASA ──► label connu
        │                                      │
        ▼                                      │
Nettoyage et normalisation                     │
        │                                      │
        ▼                                      │
Deux vecteurs : temps tᵢ et flux yᵢ            │
        │                                      │
        ▼                                      │
BLS : recherche d'une baisse périodique        │
        │                                      │
        ▼                                      │
Score puis décision « détecté / non détecté »  │
        │                                      │
        └──────── comparaison au label ◄───────┘
```

Il faut retenir une séparation essentielle :

- le BLS reçoit les **mesures de temps et de flux** ;
- le label issu des catalogues n'est utilisé qu'après le calcul, pour vérifier si la réponse est juste.

La période connue d'une planète, son nom et sa durée cataloguée ne sont jamais donnés au BLS pour l'aider à chercher. Les utiliser comme entrée serait une fuite de la réponse attendue.

---

## 1. Que mesure le télescope Kepler ?

### 1.1 Une étoile devient une série de nombres

Kepler a observé continuellement plus de 150 000 étoiles. Pour chaque étoile, le télescope mesure la lumière reçue à intervalles réguliers.

Une observation élémentaire peut être représentée par un couple :

```text
(date de la mesure, flux lumineux mesuré)
```

En répétant la mesure, on obtient une **série temporelle** :

```text
(t₁, F₁), (t₂, F₂), …, (tₙ, Fₙ)
```

où :

- `tᵢ` est la date de la mesure numéro `i` ;
- `Fᵢ` est le flux reçu à cette date ;
- `n` est le nombre de mesures disponibles.

La grandeur intéressante n'est donc pas le flux à une date isolée, mais son évolution au cours du temps. La représentation graphique de `F` en fonction de `t` est appelée **courbe de lumière**.

### 1.2 Pourquoi un transit fait-il baisser le flux ?

Une planète n'émet presque pas de lumière visible par rapport à son étoile. Mais si son orbite est correctement orientée, elle peut passer devant l'étoile vue depuis le télescope. Elle masque alors une partie de la surface lumineuse : c'est un **transit**.

On note :

- `F₀` le flux habituel hors transit ;
- `Fₜ` le flux mesuré pendant le transit ;
- `Rₚ` le rayon de la planète ;
- `R★` le rayon de l'étoile.

La profondeur relative du transit est :

```text
δ = (F₀ - Fₜ) / F₀
```

Dans un modèle géométrique simple, le rapport de surface masquée donne :

```text
δ ≈ (Rₚ / R★)²
```

Exemple : si le rayon de la planète vaut 10 % du rayon de l'étoile, alors :

```text
δ ≈ 0,1² = 0,01 = 1 %
```

Le flux baisse donc d'environ 1 %. Pour une petite planète, la baisse peut être bien plus faible et devenir comparable au bruit de mesure ou à la variabilité naturelle de l'étoile.

### 1.3 Les trois informations caractéristiques d'un transit

Une suite de transits est principalement décrite par trois nombres :

| Grandeur | Symbole | Signification |
|---|---:|---|
| période | `P` | temps entre deux transits successifs |
| époque | `t₀` | date choisie comme centre d'un transit |
| durée | `D` | temps écoulé entre le début et la fin du transit |

Les centres des transits doivent se trouver approximativement aux dates :

```text
t₀, t₀ + P, t₀ + 2P, …, t₀ + kP
```

La profondeur informe sur le rapport des rayons. La période informe sur l'orbite. La répétition est fondamentale : une baisse isolée peut être un défaut instrumental, tandis qu'une baisse de forme semblable revenant régulièrement est plus compatible avec une orbite.

### 1.4 Pourquoi toute planète ne produit-elle pas un signal visible ?

Même une planète réelle peut être absente de la courbe ou impossible à détecter :

- son orbite ne passe pas devant l'étoile depuis notre ligne de visée ;
- son transit est trop peu profond par rapport au bruit ;
- sa période est trop longue pour observer plusieurs passages ;
- un transit tombe dans une interruption des observations ;
- l'étoile possède elle-même des variations de luminosité ;
- le prétraitement peut atténuer le signal.

Ainsi, « planète confirmée » ne signifie pas automatiquement « transit facile à retrouver dans les trois segments utilisés ici ».

---

## 2. À quoi ressemble un fichier Kepler ?

### 2.1 Quarters et cadence

La mission est découpée en **quarters**, c'est-à-dire en périodes d'observation d'environ trois mois. Kepler devait pivoter régulièrement, ce qui changeait la position des étoiles sur le détecteur. Les données sont donc fournies séparément pour chaque quarter.

Le projet utilise les fichiers de **cadence longue** dont le nom se termine par `*_llc.fits`. Une mesure est intégrée environ toutes les 29,4 minutes :

```text
29,4 min ≈ 0,0204 jour
```

Un quarter de 90 jours contient théoriquement environ :

```text
90 / 0,0204 ≈ 4 400 mesures
```

Le nombre réel est inférieur à cause des interruptions, des valeurs absentes et des mesures signalées comme mauvaises.

### 2.2 Le format FITS

Les données sont téléchargées depuis [MAST](https://archive.stsci.edu/missions-and-data/kepler) au format FITS, format standard de l'astronomie. Un fichier de courbe Kepler contient trois blocs appelés **HDU** :

| Bloc | Ce qu'il contient |
|---|---|
| `PRIMARY` | informations sur la cible : identifiant, quarter, coordonnées, magnitude… |
| `LIGHTCURVE` | tableau contenant une ligne par mesure temporelle |
| `APERTURE` | masque des pixels utilisés pour calculer le flux |

Le tableau `LIGHTCURVE` standard possède 20 colonnes. Elles ne sont pas toutes utilisées dans ce projet.

### 2.3 Les familles de variables disponibles

| Famille | Colonnes | Rôle |
|---|---|---|
| temps | `TIME`, `TIMECORR`, `CADENCENO` | dater et numéroter les mesures |
| flux d'ouverture | `SAP_FLUX`, `SAP_FLUX_ERR` | flux extrait directement des pixels et incertitude |
| fond lumineux | `SAP_BKG`, `SAP_BKG_ERR` | estimation du fond et incertitude |
| flux corrigé | `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR` | flux corrigé des tendances instrumentales connues |
| qualité | `SAP_QUALITY` | indicateur binaire des problèmes détectés |
| position | `PSF_CENTR*`, `MOM_CENTR*`, `POS_CORR*` | position de l'image de l'étoile sur le capteur |

Le détail officiel se trouve dans le [Kepler Archive Manual](https://archive.stsci.edu/kepler/manuals/archive_manual.pdf).

### 2.4 Les trois colonnes effectivement utilisées

Le programme lit seulement :

#### `TIME`

`TIME` est la date barycentrique exprimée en jours BKJD :

```text
BKJD = BJD - 2 454 833
```

Soustraire cette constante évite d'enregistrer de très grands nombres. Une valeur `TIME = 352,4` signifie donc environ 352,4 jours après l'origine temporelle choisie par Kepler.

Les dates sont conservées. Si Kepler n'observe rien pendant plusieurs jours, le trou reste visible dans les valeurs de `TIME`.

#### `PDCSAP_FLUX`

Cette colonne contient le flux en électrons par seconde (`e⁻/s`). `PDC` signifie *Pre-search Data Conditioning* : le pipeline Kepler a déjà cherché à corriger plusieurs tendances instrumentales communes.

Le flux `SAP_FLUX`, plus brut, est disponible mais n'est pas utilisé. Le choix de `PDCSAP_FLUX` permet de commencer avec une courbe déjà calibrée pour la recherche de transits.

#### `SAP_QUALITY`

Cette valeur indique si la mesure a subi un événement connu : perte de pointage, rayon cosmique, réaction de la sonde, etc. Le programme conserve uniquement :

```text
SAP_QUALITY = 0
```

Cela signifie qu'aucun indicateur de qualité n'est levé pour cette cadence.

### 2.5 Exemple d'une ligne réelle

Voici une mesure du quarter Q4 de l'étoile KIC 5542466 :

| Variable | Valeur |
|---|---:|
| `TIME` | 352,3970285 BKJD |
| `PDCSAP_FLUX` | 7 653,161 e⁻/s |
| `SAP_QUALITY` | 0 |

Le flux médian de ce quarter vaut 7 663,471 e⁻/s. La première normalisation calcule :

```text
7 653,161 / 7 663,471 - 1 ≈ -0,00135
```

La mesure se trouve donc environ 0,135 % sous le niveau médian du quarter. Une seule valeur négative ne prouve rien : il faut vérifier si des baisses analogues se répètent périodiquement.

### 2.6 Quelles variables ne sont pas utilisées ?

Le BLS actuel n'utilise ni l'incertitude `PDCSAP_FLUX_ERR`, ni le fond, ni les positions sur le capteur. Au terme du prétraitement, son entrée contient uniquement :

```text
temps = [t₁, t₂, …, tₙ]
flux  = [y₁, y₂, …, yₙ]
```

Cette précision est importante pour la comparaison future. Si un réseau reçoit davantage de variables, une amélioration pourra venir des informations supplémentaires et pas seulement de l'architecture neuronale. La comparaison principale devra donc commencer avec les mêmes informations physiques.

---

## 3. Qu'appelle-t-on un système dans ce projet ?

### 3.1 Une étoile, pas une ligne et pas une planète

Chaque étoile du catalogue Kepler possède un identifiant `KIC` (*Kepler Input Catalog*). L'unité classée par le projet est cette étoile :

```text
un exemple du dataset = un identifiant KIC = un système stellaire
```

Un même système peut contenir plusieurs planètes. Il reste pourtant un seul exemple de classification :

```text
« au moins une planète confirmée recherchable »
ou
« aucune signature KOI/TCE cataloguée »
```

On ne crée donc pas plusieurs courbes identiques lorsqu'une étoile possède plusieurs planètes.

### 3.2 Plusieurs fichiers forment une seule courbe

Le programme cherche jusqu'à trois quarters pour chaque KIC. Il lit leurs mesures valides, normalise chaque quarter, rassemble les points et les trie par date.

La représentation d'un système est donc :

```text
KIC
 ├── quarter A : (t₁, F₁), …
 ├── quarter B : (tⱼ, Fⱼ), …
 └── quarter C : (tₖ, Fₖ), …

après concaténation : [(t₁, y₁), …, (tₙ, yₙ)]
```

La longueur `n` varie d'une étoile à l'autre. Les trous temporels ne sont pas remplacés par des valeurs inventées.

### 3.3 Exemple complet : KIC 5542466

KIC 5542466 est l'hôte de la planète confirmée Kepler-1756 b. Le catalogue donne :

- période : 2,35574505 jours ;
- durée du transit : 1,796 heure ;
- partition du dataset : test.

Trois fichiers ont été obtenus :

| Quarter | Lignes du FITS | Lignes conservées | Dates BKJD | Flux médian |
|---:|---:|---:|---:|---:|
| Q4 | 4 397 | 3 870 | 352,40 à 442,20 | 7 663,47 e⁻/s |
| Q5 | 4 634 | 4 231 | 443,92 à 537,63 | 8 109,93 e⁻/s |
| Q7 | 4 375 | 3 638 | 630,22 à 719,55 | 7 620,17 e⁻/s |
| **total** | **13 406** | **11 739** | trois segments | 11 739 couples `(tᵢ, yᵢ)` |

Q6 n'était pas disponible pour cette étoile ; Q7 a été utilisé comme remplacement. C'est la raison du grand trou entre les deuxième et troisième segments.

![Courbe de lumière réelle du système KIC 5542466, avant et après repliement à la période orbitale](docs/kic-5542466-light-curve.png)

Comment lire la figure :

1. le panneau supérieur montre le flux relatif en fonction de la date ;
2. les variations longues et les lacunes sont nettement visibles ;
3. le transit, qui ne dure que 1,796 heure, est difficile à voir sur plusieurs centaines de jours ;
4. le panneau inférieur replie tous les points à la période connue uniquement pour illustrer le phénomène ;
5. les transits successifs se retrouvent alors autour de la même abscisse, zéro heure ;
6. la médiane rouge fait apparaître la baisse commune au milieu.

La période connue utilisée pour cette figure n'est pas donnée au BLS. Dans l'expérience, le BLS doit la retrouver seul en essayant de nombreuses périodes.

---

## 4. Que signifient TCE, KOI, candidat et confirmé ?

Ces mots décrivent des étapes successives, pas des synonymes.

### 4.1 Cible Kepler

Une **cible** est simplement une étoile observée. À ce stade, aucune planète n'est supposée.

### 4.2 TCE : un signal automatique

Un **TCE** (*Threshold Crossing Event*) est un signal périodique qui franchit le seuil du pipeline automatique Kepler. Cela signifie : « le calcul a trouvé quelque chose d'assez significatif pour être enregistré ».

Un TCE n'est pas encore une planète. Une binaire à éclipses, du bruit ou un artefact peuvent produire un signal périodique.

### 4.3 KOI : un objet étudié plus sérieusement

Un **KOI** (*Kepler Object of Interest*) est un objet retenu pour une analyse plus approfondie. Un KOI reçoit une disposition, notamment :

- `CANDIDATE` : le signal reste compatible avec une planète, sans confirmation définitive ;
- `FALSE POSITIVE` : une autre explication a été retenue ;
- `CONFIRMED` : la nature planétaire est confirmée.

### 4.4 CONTROL : une catégorie créée ici

`CONTROL` n'est pas une disposition officielle de planète. Dans ce projet, un contrôle est une cible du catalogue stellaire DR25 qui n'apparaît chez **aucun hôte KOI et aucun hôte TCE DR25**.

La progression peut se résumer ainsi :

```text
cible observée
   │
   ├── aucun TCE/KOI catalogué ──► peut devenir CONTROL dans ce projet
   │
   └── signal TCE
          │
          └── éventuellement KOI
                 ├── CANDIDATE
                 ├── FALSE POSITIVE
                 └── CONFIRMED ──► peut devenir positif dans ce projet
```

Il serait incorrect de mettre les faux positifs ou les candidats dans les contrôles : leur courbe contient justement un signal ressemblant parfois fortement à un transit. Ils formeraient une autre question scientifique, celle du *vetting* des candidats.

Il serait également incorrect d'affirmer que les contrôles ne possèdent aucune planète. Ils ne possèdent **aucun signal catalogué dans les tables utilisées**. Une planète non transitante ou trop faible peut toujours être présente.

---

## 5. Comment le dataset de 3 000 systèmes est-il construit ?

### 5.1 Sources utilisées

Le script `script/dataset/build.py` croise quatre sources NASA :

| Source | Information extraite | Utilité |
|---|---|---|
| table `q1_q17_dr25_koi`, disposition `CONFIRMED` | KIC, noms, périodes, époques et durées | construire les positifs |
| table complète `q1_q17_dr25_koi` | tous les KIC possédant un KOI | les exclure des contrôles |
| table `q1_q17_dr25_tce` | tous les KIC possédant un TCE | les exclure des contrôles |
| table `q1_q17_dr25_stellar` | tous les KIC stellaires observés | population de départ des contrôles |

Les observations FITS sont ensuite téléchargées depuis MAST. Les requêtes exactes et les empreintes SHA-256 des fichiers sources sont conservées dans `data/kepler_3000/provenance.json`.

Le dataset Kaggle téléchargé au début du projet n'est plus utilisé comme vérité terrain. Il contient des courbes déjà transformées et des labels de candidats. Cela empêchait de définir proprement les négatifs et de repartir des mêmes observations brutes pour les deux méthodes.

### 5.2 Construction de la classe positive

Le script procède dans cet ordre :

1. il lit tous les événements dont `koi_disposition = 'CONFIRMED'` ;
2. il les regroupe par KIC, car plusieurs planètes peuvent tourner autour de la même étoile ;
3. il garde un système si au moins une de ses planètes confirmées a une période inférieure ou égale à 30 jours ;
4. il obtient ainsi 1 610 systèmes éligibles avant sous-échantillonnage ;
5. il en sélectionne 42 de manière déterministe.

Pourquoi imposer `P ≤ 30 jours` ? Parce que le BLS ne recherche que les périodes comprises entre 0,5 et 30 jours. Mettre dans la classe positive uniquement des planètes hors de cette plage rendrait leur détection impossible par construction.

Les 42 systèmes retenus contiennent :

- 59 planètes confirmées au total ;
- 54 planètes dont la période est inférieure ou égale à 30 jours ;
- 11 systèmes contenant plusieurs planètes confirmées.

### 5.3 Construction de la classe de contrôle

Le script part des cibles du catalogue stellaire, puis retire :

1. tout KIC apparaissant dans la table KOI, quelle que soit sa disposition ;
2. tout KIC apparaissant dans la table TCE ;
3. tout hôte confirmé, par sécurité explicite.

Après ces exclusions, il reste 182 762 contrôles éligibles. Le script en sélectionne 2 958.

Cette règle est volontairement plus stricte que « aucune planète confirmée ». Une étoile candidate n'est pas utilisée comme contrôle.

### 5.4 Pourquoi seulement 42 positifs ?

Le projet cherche à reproduire une situation où les systèmes détectables sont rares. Les effectifs sont :

| Classe | Nombre | Proportion |
|---|---:|---:|
| `CONFIRMED` | 42 | 1,4 % |
| `CONTROL` | 2 958 | 98,6 % |
| **total** | **3 000** | **100 %** |

Si le dataset contenait 1 500 positifs et 1 500 négatifs, la précision serait artificiellement plus facile à obtenir. Dans une recherche réelle, une méthode rencontre surtout des étoiles sans signal catalogué. Le déséquilibre fait donc partie de la question étudiée.

### 5.5 Sélection déterministe

La sélection utilise la graine `727`. Pour chaque KIC, le programme calcule une clé SHA-256 à partir de la graine, du label et de l'identifiant, puis trie les systèmes selon cette clé.

Ce mécanisme joue le rôle d'un tirage pseudo-aléatoire mais possède deux avantages :

- une nouvelle exécution choisit exactement les mêmes systèmes ;
- le choix ne dépend pas de l'ordre des lignes renvoyées par le serveur.

Il ne faut pas interpréter SHA-256 comme une méthode astronomique : c'est uniquement un moyen reproductible de sélectionner un sous-ensemble.

### 5.6 Répartition entraînement, validation et test

Chaque classe est répartie séparément afin que les trois partitions contiennent des positifs :

| Partition | Confirmés | Contrôles | Total |
|---|---:|---:|---:|
| entraînement | 32 | 2 068 | 2 100 |
| validation | 5 | 445 | 450 |
| test | 5 | 445 | 450 |

Le rôle des partitions sera particulièrement important pour le réseau de neurones :

- **entraînement** : ajuster les poids du réseau ;
- **validation** : choisir l'architecture, les hyperparamètres et le seuil ;
- **test** : mesurer une seule fois la performance finale.

Le BLS est déterministe, mais son domaine de périodes, son prétraitement, son score et son seuil sont aussi des choix de méthode. Il ne faut donc pas les optimiser sur les mêmes systèmes qui servent à annoncer le résultat final.

### 5.7 Téléchargement des courbes

Pour chaque KIC, le script demande d'abord Q4, Q5 et Q6. Si un fichier manque, il cherche un remplacement dans Q1, Q2, Q3, puis Q7 à Q17. Il conserve au maximum trois fichiers.

La couverture finale est :

| Fichiers FITS disponibles | Systèmes |
|---:|---:|
| 3 | 2 786 |
| 2 | 97 |
| 1 | 117 |
| 0 | 0 |

Tous les positifs ont trois fichiers. Certains contrôles ont une couverture plus courte, ce qui constitue un biais possible : avec moins de jours observés, on a moins de chances de voir plusieurs événements périodiques.

Les FITS occupent environ 9,2 Go. Ils ne sont pas publiés dans Git, mais chaque observation peut être retéléchargée depuis sa source.

### 5.8 Que contient `manifest.csv` ?

Le manifeste possède une ligne par KIC. Ses colonnes ne sont pas toutes des entrées de l'algorithme :

| Colonne | Sens | Donnée au BLS ? |
|---|---|---:|
| `kepid` | identifiant de l'étoile | seulement pour retrouver ses fichiers |
| `label` | `CONFIRMED` ou `CONTROL` | non, utilisé pour l'évaluation |
| `has_confirmed_planet` | version binaire du label | non |
| `confirmed_planet_count` | nombre total de planètes confirmées | non |
| `detectable_planet_count` | nombre de planètes avec `P ≤ 30 j` | non |
| `confirmed_planet_names` | noms officiels | non |
| `split` | partition expérimentale | non |
| `signal_count` | signaux recherchables connus | non |
| `periods_days` | périodes cataloguées | non, seulement pour vérifier la période trouvée |
| `epochs_bkjd` | centres de transit catalogués | non |
| `durations_hours` | durées cataloguées | non |
| `quarters` | quarters initialement demandés | non |

Cette table sert donc à organiser l'expérience et à connaître la réponse attendue. Les entrées physiques du BLS viennent des FITS.

---

## 6. Comment la courbe est-elle préparée ?

Le BLS fonctionne mieux si le niveau moyen et les variations très lentes ont été retirés. Le prétraitement doit cependant éviter d'effacer les transits courts.

### Étape 1 — retirer les mesures invalides

Pour chaque quarter, une ligne est conservée si :

```text
TIME est fini
PDCSAP_FLUX est fini
SAP_QUALITY = 0
```

### Étape 2 — mettre les quarters au même niveau

Le flux absolu peut différer entre quarters. Pour chaque quarter, on calcule sa médiane `M`, puis :

```text
rᵢ = Fᵢ / M - 1
```

Interprétation :

- `rᵢ = 0` : flux égal à la médiane ;
- `rᵢ = -0,001` : flux 0,1 % sous la médiane ;
- `rᵢ = +0,001` : flux 0,1 % au-dessus.

La médiane est préférée à la moyenne parce qu'elle est moins déplacée par quelques valeurs extrêmes.

### Étape 3 — concaténer sans supprimer les trous

Les couples `(TIME, r)` de tous les quarters sont réunis et triés par `TIME`. Aucune interpolation n'est faite. Le temps du premier point est ensuite soustrait à toutes les dates ; la courbe commence donc à `t = 0`, mais les écarts sont conservés.

### Étape 4 — retirer les variations lentes

Une médiane glissante d'environ deux jours, soit 99 cadences, estime une tendance locale `mᵢ`. On calcule :

```text
eᵢ = rᵢ - mᵢ
```

Une variation sur plusieurs jours est alors fortement réduite. Un transit de quelques heures devrait être mieux préservé car il occupe une petite partie de la fenêtre.

Ce choix n'est pas neutre : un filtre trop court pourrait supprimer le transit ; un filtre trop long laisserait trop de variabilité stellaire. Deux jours est donc un paramètre de la méthode.

### Étape 5 — exprimer le flux en unités de bruit

On centre les résidus par leur médiane, puis on estime leur dispersion avec la MAD :

```text
MAD = médiane(|eᵢ - médiane(e)|)
σ_robuste = 1,4826 × MAD
yᵢ = (eᵢ - médiane(e)) / σ_robuste
```

Le facteur `1,4826` rend cette estimation comparable à un écart-type lorsque le bruit est gaussien. Après transformation, `y = -3` signifie approximativement « trois niveaux de bruit robuste sous la médiane ».

### Étape 6 — limiter les valeurs extrêmes

Les valeurs sont bornées entre `-8` et `+8`. Cette opération empêche quelques points aberrants de dominer le calcul :

```text
yᵢ final = min(8, max(-8, yᵢ))
```

Elle peut également limiter un transit extrêmement profond. C'est donc encore un choix à documenter, pas une vérité physique.

### Résultat du prétraitement

Pour un système, le BLS reçoit finalement :

```text
t = dates en jours, avec les trous réels
y = flux sans dimension, centré et exprimé en bruit robuste
```

---

## 7. Comment fonctionne le Box Least Squares ?

### 7.1 Idée intuitive

Le BLS cherche un motif qui ressemble à une boîte :

```text
flux normal ─────────┐       ┌─────────
                    │       │
flux en transit     └───────┘
```

Le modèle est volontairement simple. Un vrai transit possède des bords arrondis et dépend de l'assombrissement centre-bord de l'étoile, mais une boîte donne une approximation rapide de trois propriétés : sa position, sa durée et sa profondeur.

### 7.2 Pourquoi ne voit-on pas directement les transits ?

Une période de 10 jours observée pendant 270 jours produit environ 27 transits. Chaque transit peut ne durer que quelques heures. Sur le graphique complet, ces petites baisses sont noyées parmi des milliers de points.

L'idée est donc de tester une période `P`, puis de superposer mentalement tous les intervalles de longueur `P`. Si `P` est correcte, les transits se placent les uns au-dessus des autres. Si `P` est incorrecte, les baisses se répartissent à des phases différentes et ne forment pas de motif stable.

### 7.3 Calcul de la phase

Pour une période d'essai `P` et une origine `t₀`, on transforme chaque date en phase :

```text
φᵢ = partie fractionnaire de ((tᵢ - t₀) / P)
```

La phase est comprise entre 0 et 1 :

- `φ = 0` : début d'un cycle ;
- `φ = 0,5` : milieu du cycle ;
- `φ` proche de 1 : fin du cycle.

Deux mesures séparées exactement de `P` jours ont la même phase. Replier la courbe revient à tracer `yᵢ` en fonction de `φᵢ` plutôt qu'en fonction de la date absolue.

### 7.4 Ajustement de la boîte

Pour chaque période, le BLS essaie également plusieurs durées et plusieurs positions de la boîte. Le modèle possède deux niveaux :

```text
mᵢ = niveau normal             hors de la boîte
mᵢ = niveau normal - profondeur dans la boîte
```

Il choisit les paramètres qui réduisent le plus les résidus :

```text
RSS = Σ (yᵢ - mᵢ)²
```

Autrement dit, il compare la courbe à une ligne presque constante puis demande : « une petite boîte négative répétée améliore-t-elle nettement l'explication des données ? »

Le calcul est répété pour un grand nombre de périodes. La période donnant le meilleur signal devient le candidat principal du système.

### 7.5 Domaine réellement exploré

L'implémentation sépare la recherche en trois bandes :

| Périodes testées | Durées de boîte testées en jours | Équivalent en heures |
|---|---|---|
| 0,5 à 1 jour | 0,02 ; 0,04 ; 0,06 | 0,48 ; 0,96 ; 1,44 h |
| 1 à 3 jours | 0,04 ; 0,08 ; 0,125 ; 0,20 | 0,96 ; 1,92 ; 3 ; 4,8 h |
| 3 à 30 jours | 0,08 ; 0,125 ; 0,20 ; 0,30 ; 0,50 | 1,92 ; 3 ; 4,8 ; 7,2 ; 12 h |

Au total, environ 100 000 périodes sont distribuées uniformément en **fréquence** `1/P`. Une grille régulière en fréquence contrôle mieux le décalage de phase accumulé sur une longue observation qu'une grille simplement régulière en période.

Une étude de convergence a vérifié la densité de la grille sur les 32 positifs d'entraînement :

| Taille de grille | Périodes connues retrouvées |
|---:|---:|
| 50 000 | 22/32 |
| 100 000 | 23/32 |
| 200 000 | 23/32 |

Passer de 100 000 à 200 000 ne retrouve aucun système supplémentaire dans ce test. La grille de 100 000 est donc conservée pour réduire le temps de calcul.

### 7.6 Pourquoi utiliser Astropy ?

Le calcul est réalisé par [`astropy.timeseries.BoxLeastSquares`](https://docs.astropy.org/en/stable/timeseries/bls.html), avec :

```python
BoxLeastSquares(...).power(
    period_grid,
    durations,
    objective="snr",
    method="fast",
    oversample=10,
)
```

Astropy est une bibliothèque scientifique communautaire de référence en astronomie. Le projet ne compare donc pas le futur réseau à une réécriture approximative du BLS, mais à l'implémentation maintenue par Astropy.

Références :

- Kovács, Zucker et Mazeh (2002), [*A box-fitting algorithm in the search for periodic transits*](https://doi.org/10.1051/0004-6361:20020802) ;
- Astropy Collaboration (2022), [présentation d'Astropy v5](https://doi.org/10.3847/1538-4357/ac7c74).

La dépendance est bornée dans `requirements.txt` à `astropy>=8,<9`.

### 7.7 Ce que renvoie le BLS pour un système

Pour le meilleur motif trouvé, le programme enregistre notamment :

| Résultat | Interprétation |
|---|---|
| `period_days` | période estimée |
| `duration_days` | durée estimée de la boîte |
| `transit_epoch_days` | position temporelle estimée du transit |
| `depth` | profondeur de la boîte dans le flux normalisé |
| `depth_snr` | rapport signal sur bruit de la profondeur |
| `log_likelihood` | qualité d'ajustement statistique |
| `observed_transits` | nombre de passages couverts par les observations |

Le BLS trouve toujours son meilleur motif, même sur une étoile sans planète. Il faut donc encore décider si ce meilleur motif est suffisamment crédible.

---

## 8. Du meilleur motif à une décision binaire

### 8.1 Pourquoi la puissance BLS seule ne suffit pas

Une étoile variable peut produire une oscillation presque sinusoïdale. Une binaire à éclipses peut produire des baisses profondes. Une discontinuité instrumentale peut ressembler à une boîte. Ces signaux peuvent obtenir un score BLS élevé sans correspondre à une planète.

Astropy calcule donc des statistiques supplémentaires avec `compute_stats`. Le projet compare notamment le modèle en boîte à un modèle harmonique, plus adapté à une variation lisse.

### 8.2 Score de contrôle utilisé

On note :

- `ΔlogL_harmonique` la statistique Astropy comparant le modèle harmonique au modèle en boîte ;
- `D/P` la fraction de l'orbite occupée par le transit.

Le score retenu est :

```text
S = √[ max(0, -ΔlogL_harmonique) / (D/P) ]
```

Dans la convention renvoyée ici par Astropy, une valeur négative de `ΔlogL_harmonique` favorise la boîte. Le signe moins transforme cet avantage en quantité positive. La division par `D/P` privilégie les baisses courtes par rapport à la période, forme attendue pour un transit planétaire plutôt que pour une variation occupant une grande partie du cycle.

Ce score de contrôle est construit autour des statistiques du BLS Astropy ; ce n'est pas une constante officielle valable pour toute étude.

### 8.3 Choix du seuil

Une décision nécessite un seuil `T` :

```text
si S ≥ T : système déclaré détecté
si S < T : système déclaré non détecté
```

Un seuil faible retrouve davantage de planètes mais accepte davantage de faux positifs. Un seuil élevé réduit les fausses alertes mais manque des planètes.

Le seuil opérationnel est `162,8`, arrondi depuis `162,771681…`. Il maximise le score F1 sur les données de développement dans la plupart des plis.

### 8.4 Validation croisée à six plis, étape par étape

Même si le BLS n'apprend pas des millions de poids, choisir son score et son seuil à partir des labels est déjà une forme d'ajustement. Pour ne pas mesurer le résultat sur les mêmes objets qui ont choisi le seuil :

1. les 42 positifs et les 2 958 contrôles sont répartis de manière stratifiée en six plis ;
2. chaque pli contient 500 systèmes, dont 7 positifs ;
3. on met un pli de côté ;
4. sur les 2 500 autres systèmes, on compare quatre scores de contrôle et on choisit le seuil maximisant F1 ;
5. on applique ce choix aux 500 systèmes laissés de côté ;
6. on recommence jusqu'à ce que chaque système ait été laissé de côté une fois ;
7. on réunit les 3 000 décisions qui ont toutes été produites hors de leur ensemble de calibration.

Le score `short_box_vs_harmonic`, c'est-à-dire la formule ci-dessus, a été choisi dans les six plis. Cinq plis ont choisi un seuil proche de 162,77 et un pli un seuil proche de 172,77.

---

## 9. Comment lire les résultats ?

### 9.1 Les quatre cas possibles

| Vérité du catalogue | Décision BLS | Nom |
|---|---|---|
| confirmé | détecté | vrai positif (`TP`) |
| contrôle | détecté | faux positif (`FP`) |
| confirmé | non détecté | faux négatif (`FN`) |
| contrôle | non détecté | vrai négatif (`TN`) |

Résultat hors pli :

|  | 42 confirmés | 2 958 contrôles |
|---|---:|---:|
| **BLS détecté** | 11 vrais positifs | 14 faux positifs |
| **BLS non détecté** | 31 faux négatifs | 2 944 vrais négatifs |

### 9.2 Précision

La précision répond à la question :

> Parmi les systèmes signalés par le BLS, combien sont réellement confirmés dans le catalogue ?

```text
précision = TP / (TP + FP)
          = 11 / (11 + 14)
          = 11 / 25
          = 44,0 %
```

Le BLS émet 25 alertes ; 11 correspondent à un système confirmé et 14 à un contrôle.

### 9.3 Rappel

Le rappel répond à une autre question :

> Parmi tous les systèmes confirmés du dataset, combien sont retrouvés ?

```text
rappel = TP / (TP + FN)
       = 11 / (11 + 31)
       = 11 / 42
       = 26,2 %
```

Le seuil est donc conservateur : il évite beaucoup de fausses alertes mais ne retient qu'environ un quart des systèmes confirmés.

### 9.4 F1

Le score F1 est la moyenne harmonique de la précision et du rappel :

```text
F1 = 2 × précision × rappel / (précision + rappel)
   = 32,8 %
```

Il devient faible si l'une des deux grandeurs est faible. Il permet de rechercher un compromis, mais il ne remplace pas l'examen séparé de la précision et du rappel.

### 9.5 Pourquoi l'accuracy serait trompeuse

L'exactitude globale vaudrait :

```text
accuracy = (TP + TN) / 3 000
         = (11 + 2 944) / 3 000
         = 98,5 %
```

Ce nombre semble excellent. Pourtant, une méthode répondant toujours « aucun système détecté » aurait :

```text
2 958 / 3 000 = 98,6 %
```

Elle aurait une meilleure accuracy tout en ne trouvant aucune planète. C'est pourquoi l'accuracy n'est pas la métrique principale sur ce dataset déséquilibré.

### 9.6 Période retrouvée et classification ne sont pas identiques

Pour vérifier la période, une estimation est considérée correcte si elle est à 1 % près :

- de la période cataloguée ;
- de sa moitié ;
- ou de son double.

Les facteurs 1/2 et 2 sont acceptés parce qu'un périodogramme peut confondre une période avec une harmonique.

Le BLS retrouve ainsi une période compatible pour 29 des 42 systèmes positifs. Mais seulement 11 franchissent le seuil de classification. Parmi ces 11 alertes positives correctes, 10 possèdent une période compatible.

Cela montre les deux étapes distinctes :

1. trouver un pic à une période intéressante ;
2. décider que ce pic est assez crédible pour déclencher une alerte.

### 9.7 Interprétation honnête

Le résultat ne signifie ni « BLS marche à 44 % », ni « BLS ne vaut rien ».

- La précision de 44 % signifie que 11 des 25 alertes sont confirmées.
- Le rappel de 26,2 % signifie que 31 des 42 systèmes confirmés sont manqués au seuil retenu.
- Le taux de faux positifs parmi les contrôles est seulement `14/2 958 ≈ 0,47 %`.
- Mais, puisque les positifs sont très rares, ces 14 erreurs suffisent à dépasser les 11 bonnes alertes.

Le futur réseau devra donc améliorer le compromis : retrouver plus de systèmes confirmés sans laisser exploser les fausses alertes.

---

## 10. Comment comparer correctement le futur réseau de neurones ?

La comparaison devra respecter au minimum les règles suivantes :

1. utiliser les mêmes 3 000 KIC et les mêmes labels ;
2. ne jamais placer deux observations du même KIC dans des partitions différentes ;
3. commencer avec la même information physique : temps et flux ;
4. choisir les hyperparamètres et le seuil sans consulter le test final ;
5. publier la matrice de confusion, la précision, le rappel et F1 ;
6. comparer aussi les courbes précision-rappel pour ne pas dépendre d'un seul seuil ;
7. mesurer le temps de calcul et, pour le réseau, le coût de l'entraînement ;
8. documenter toute représentation imposée au réseau : taille fixe, interpolation, fenêtres ou repliement.

Le réseau pourrait être meilleur parce qu'il peut apprendre des formes plus complexes qu'une boîte : bords arrondis, bruit corrélé, variabilité stellaire ou artefacts caractéristiques. Mais cette conclusion ne sera valable que si aucune information du catalogue n'entre accidentellement dans ses données d'entrée.

---

## 11. Reproduire l'expérience

### 11.1 Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 11.2 Construire ou reprendre le dataset

```bash
.venv/bin/python -m script.dataset.build manifest
.venv/bin/python -m script.dataset.build download --fallback
```

Le téléchargement est reprenable. Les fichiers déjà validés ne sont pas téléchargés une seconde fois. L'état est conservé dans `data/kepler_3000/download_status.csv`.

### 11.3 Calculer les scores BLS

```bash
.venv/bin/python -m script.evaluate_fits --split train --engine official \
  --threshold 162.8 --output data/bls-official-train.json
.venv/bin/python -m script.evaluate_fits --split validation --engine official \
  --threshold 162.8 --output data/bls-official-validation.json
.venv/bin/python -m script.evaluate_fits --split test --engine official \
  --threshold 162.8 --output data/bls-official-test.json
```

### 11.4 Refaire la validation croisée et le dashboard

```bash
.venv/bin/python -m script.cross_validate_official_bls
.venv/bin/python script/export_official_dashboard.py
```

### 11.5 Régénérer la figure d'exemple

```bash
.venv/bin/python -m script.plot_system_example
```

### 11.6 Lancer le dashboard localement

```bash
cd web
../.venv/bin/python -m http.server 8000
```

Puis ouvrir <http://localhost:8000>. La version publique est déployée automatiquement sur [GitHub Pages](https://tcrouzet.github.io/EmileTipe/) lorsque `web/` change sur `main`.

### 11.7 Exécuter les tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

---

## 12. Fichiers importants

```text
data/kepler_3000/
  manifest.csv                 un système et son label par ligne
  provenance.json             sources, requêtes et paramètres de sélection
  download_status.csv         état reprenable des téléchargements
  fits/<KIC>/*.fits            observations, non publiées dans Git

script/
  config.py                    paramètres communs
  dataset/build.py             création du dataset
  bls/official.py              appel au BLS Astropy
  bls/preprocessing.py         normalisation et filtrage
  evaluate_fits.py             calcul des scores sur les systèmes
  cross_validate_official_bls.py
                               choix hors pli du score et du seuil
  export_official_dashboard.py création de web/results.json
  plot_system_example.py       figure scientifique du README

web/                           dashboard statique
tests/                         tests automatisés
slides/                        présentation générale
```

## Glossaire minimal

| Terme | Définition courte |
|---|---|
| BLS | recherche d'une baisse rectangulaire et périodique dans une série temporelle |
| cadence | intervalle entre deux mesures successives |
| courbe de lumière | flux d'une étoile représenté en fonction du temps |
| FITS | format de fichier scientifique utilisé en astronomie |
| flux | quantité de lumière mesurée par unité de temps |
| KIC | identifiant d'une étoile dans le Kepler Input Catalog |
| KOI | objet Kepler sélectionné pour une analyse approfondie |
| quarter | segment d'environ trois mois de la mission Kepler |
| transit | passage d'une planète devant son étoile, produisant une baisse de flux |
| TCE | signal périodique ayant franchi le seuil automatique du pipeline Kepler |

## Limites actuelles à garder en tête

- Les contrôles ne sont pas garantis sans planète ; ils sont sans KOI ni TCE catalogué.
- Seuls un à trois quarters sont utilisés, et non toute la mission Kepler.
- Tous les positifs ont trois fichiers, contrairement à certains contrôles.
- Les incertitudes de flux ne sont pas utilisées par le BLS actuel.
- Le filtre médian et l'écrêtage peuvent modifier certains signaux.
- La plage 0,5–30 jours exclut les périodes plus longues.
- Le score de contrôle et le seuil sont propres à ce protocole.

Ces limites devront être conservées ou explicitement prises en compte lors de la comparaison avec le réseau de neurones.
