# Quelle est la méthode optimale de détection d'une exoplanète ?

# Motivation  (≤ 50 mots)

Les télescopes ne voient pas les exoplanètes, mais, quand l’une transite devant son étoile, elle en fait varier la luminosité. Curieux de l’IA, tout en restant méfiant, je me suis demandé si les réseaux de neurones pouvaient aider à optimiser la détection.

# Ancrage dans le thème (≤ 50 mots)

Repérer un signal rare rejoint les thèmes de cette année :

**Sobriété** : ne pas utiliser un algorithme inutilement lourd.

**Efficacité** : ne pas rater les transits noyés dans des milliers de mesures bruitées.

**Optimisation** : trouver le bon compromis entre précision et coût de calcul.

# Positionnement thématique

PHYSIQUE (physique interdisciplinaire)  
SCIENCES INDUSTRIELLES (traitement du signal)  
INFORMATIQUE (informatique pratique) 

# Mots-clés

Exoplanète		Exoplanet  
Courbe de lumière	Light curve  
Méthode des transits	Transit method  
Traitement du signal	Signal processing  
Réseau de neurones	Neural network

# Bibliographie commentée (≤650 mots)

La détection d'exoplanètes par la méthode des transits repose sur un principe simple : lorsqu'une planète passe devant son étoile, elle occulte une infime partie de sa lumière, provoquant une baisse périodique et régulière du flux mesuré \[1\]. Cette méthode indirecte, utilisée par le télescope spatial Kepler entre 2009 et 2018, a permis la découverte de plusieurs milliers d'exoplanètes en observant en continu la luminosité de centaines de milliers d'étoiles \[2\].

Le jeu de données Kepler, tel que documenté sur Kaggle \[3\] et repris dans le projet NASA-Exoplanet \[4\] dont je me suis inspiré, illustre la difficulté du problème : sur 5087 étoiles étudiées, seulement 37 présentent une exoplanète confirmée. Ce déséquilibre extrême entre les deux classes rend la détection statistiquement délicate : un modèle qui prédirait systématiquement l'absence d'exoplanète obtiendrait un taux de bonnes réponses supérieur à 99 %, sans jamais rien détecter utilement. Ce taux global est donc trompeur. Prenons un exemple : si le programme signale 10 étoiles comme "candidates exoplanètes", mais que seules 6 en ont vraiment une, sa précision est de 6 sur 10 : il se trompe souvent. Si, par ailleurs, il existe 37 vraies exoplanètes dans les données et qu'il n'en a trouvé que 6, son rappel est de 6 sur 37 : il en rate beaucoup. Un bon algorithme doit être bon sur les deux estimations \[5\].

Sur le plan méthodologique, les missions spatiales n'utilisent pas un simple seuil de luminosité mais des algorithmes plus élaborés, notamment le Box Least Squares (BLS), qui recherche dans le signal une forme de créneau périodique caractéristique d'un transit, en testant systématiquement différentes périodes et durées candidates \[6\]. Cette méthode reste un algorithme classique, fondé sur un modèle physique explicite, par opposition aux approches d'apprentissage automatique.

Plusieurs études récentes ont exploré l'usage de réseaux de neurones pour cette tâche de classification. Wang et al. (2025) entraînent un réseau de neurones convolutif directement sur les courbes de lumière du jeu de données Kepler et montrent qu'il peut apprendre à distinguer un transit planétaire du bruit sans modèle physique explicite préalable \[7\].

Fazel et al. (2023) comparent plusieurs algorithmes sur les mêmes données et obtiennent, avec une forêt aléatoire, une précision de 0,92 et un rappel de 0,95, illustrant qu'une méthode d'apprentissage automatique peut rivaliser avec les approches classiques sur ce problème de signal rare et bruité \[5\].

Ces travaux montrent deux limites qui structurent ma problématique. D'une part, la performance d'un réseau de neurones dépend fortement du traitement du déséquilibre des classes, sous peine de biaiser l'apprentissage vers la classe majoritaire. D'autre part, ces méthodes ont un coût de calcul et une complexité supérieurs à une détection BLS, posant la question de l'arbitrage entre précision et efficacité, cœur du thème de cette année.

# Problématique retenue

Un algorithme BLS, fondé sur un modèle physique explicite, permet-il une détection des transits d'exoplanètes aussi efficace, en taux de détection et en coût de calcul, qu'un réseau de neurones entraîné sur les mêmes données ?

# Objectifs du TIPE (≤100 mots)

* Implémenter l'algorithme BLS et l'appliquer aux courbes de lumière Kepler pour détecter les transits périodiques.  
* Entraîner un réseau de neurones sur les mêmes données pour effectuer la même tâche de classification.  
* Comparer le taux de détection des deux méthodes sur le jeu de données déséquilibré.  
* Comparer leur coût de calcul (temps d'exécution, complexité).  
* Conclure sur l'existence ou non d'un compromis entre efficacité de détection et sobriété algorithmique.

# Références bibliographiques

1. [Wikipédia, *Méthodes de détection des exoplanètes*, section « Méthode des transits »](https://fr.wikipedia.org/wiki/M%C3%A9thodes_de_d%C3%A9tection_des_exoplan%C3%A8tes)  
2. [NASA Science, *Ways to Find a Planet*](https://exoplanets.nasa.gov/alien-worlds/ways-to-find-a-planet/)  
3. [Kaggle, *Exoplanet Hunting in Deep Space — Kepler Labelled Time Series Data*](https://www.kaggle.com/datasets/keplersmachines/kepler-labelled-time-series-data)  
4. [B. Oliveira, *NASA-Exoplanet* (dépôt GitHub)](https://github.com/BriantOliveira/NASA-Exoplanet)  
5. [F. Fazel et al., *Exoplanet Detection using Kepler Time Series Data*, 2023, HAL](https://hal.science/hal-04419879/document)  
6. [Astropy Project, *Box Least Squares (BLS) Periodogram*](https://docs.astropy.org/en/stable/timeseries/bls.html)  
7. [J. Wang et al., *Training a Convolutional Neural Network for Exoplanet Detection*, 2025, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12048670/)

