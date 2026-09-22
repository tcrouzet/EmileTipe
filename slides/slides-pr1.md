---
marp: true
theme: emiletype
paginate: true
size: 16:9
title: Quelle est la méthode optimale de détection d'une exoplanète ?
description: Présentation générale du projet
---

<!-- _class: title -->
<!-- _paginate: false -->

<p class="kicker">TIPE · PHYSIQUE, MATHS & INFORMATIQUE</p>

# Quelle est la méthode optimale de détection d’une exoplanète ?

Comparer un algorithme déterministe à un réseau de neurones.

<p class="author">Émile Crouzet</p>

---

## 1. Détecter une planète invisible

<div class="columns">
<div>

Une planète passant devant son étoile provoque une baisse faible et périodique de luminosité.

- le signal est court ;
- le bruit et l’activité stellaire peuvent lui ressembler ;
- les vraies planètes sont rares.

</div>
<div class="signal-card">
  <div class="orbit"><span class="star">★</span><span class="planet"></span></div>
  <svg viewBox="0 0 420 150" role="img" aria-label="Courbe de lumière montrant trois transits">
    <path class="axis" d="M12 120 H408" />
    <path class="curve" d="M12 45 L72 45 L78 102 L91 102 L97 45 L192 45 L198 102 L211 102 L217 45 L312 45 L318 102 L331 102 L337 45 L408 45" />
  </svg>
  <p>Temps → &nbsp;&nbsp; baisses périodiques du flux</p>
</div>
</div>

---

## 2. Deux approches à comparer

<div class="method-grid">
<article class="method classical">
  <span class="method-number">A</span>
  <h3>BLS (Box Least Squares)</h3>
  <p>Recherche explicitement une baisse périodique.</p>
  <ul>
    <li>modèle physique ;</li>
    <li>peu de paramètres ;</li>
    <li>calcul sobre ;</li>
    <li>librairie standard.</li>
  </ul>
</article>
<article class="method neural">
  <span class="method-number">B</span>
  <h3>Réseau de neurones</h3>
  <p>Apprend les formes utiles directement à partir des courbes.</p>
  <ul>
    <li>modèle plus flexible ;</li>
    <li>entraînement nécessaire ;</li>
    <li>coût et décisions moins lisibles ;</li>
    <li>tenter de faire mieux que BLS.</li>
  </ul>
</article>
</div>

<p class="question">Le gain de détection justifie-t-il la complexité supplémentaire ?</p>

---

## 3. Une comparaison sur les mêmes données

<p class="dataset-intro">À partir de la base de donnée Kepler, j’ai crée un échantillon de 3 000 étoiles, avec 42 abritant au moins une planète confirmée. Pour chaque étoile, j’ai téléchargé jusqu’à trois périodes d’observation de sa luminosité.</p>

<div class="dataset-line">
  <div><strong>3 000</strong><span>systèmes Kepler</span></div>
  <div><strong>42</strong><span>systèmes confirmés</span></div>
  <div><strong>2 958</strong><span>étoiles témoins</span></div>
  <div><strong>1,4 %</strong><span>de systèmes positifs</span></div>
</div>

<p class="note">J’utiliserai ces mêmes 3 000 étoiles pour évaluer le BLS puis le réseau de neurones. Je pourrai ainsi comparer les deux méthodes sur des données identiques.</p>

---

## 4. Résultats obtenus avec le BLS

<p class="library-line">Calcul réalisé avec la bibliothèque officielle <a href="https://docs.astropy.org/en/stable/timeseries/bls.html"><b>Astropy — <code>timeseries.BoxLeastSquares</code></b></a>, sur les 3 000 systèmes.</p>

<table class="score-table">
  <thead><tr><th>Mesure</th><th>Résultat</th><th>Interprétation</th></tr></thead>
  <tbody>
    <tr><td>Vrais positifs</td><td><b>11</b></td><td>11 planètes correctement signalées</td></tr>
    <tr><td>Faux positifs</td><td><b>14</b></td><td>14 alertes alors qu’aucune planète n’est connue</td></tr>
    <tr><td>Faux négatifs</td><td><b>31</b></td><td>31 planètes connues manquées par le BLS</td></tr>
    <tr><td>Vrais négatifs</td><td><b>2 944</b></td><td>2 944 étoiles correctement classées sans planète</td></tr>
    <tr class="metric"><td>Précision</td><td><b>44,0 %</b></td><td>parmi les 25 alertes, 11 sont justes</td></tr>
    <tr class="metric"><td>Rappel</td><td><b>26,2 %</b></td><td>parmi les 42 planètes connues, 11 sont retrouvées</td></tr>
  </tbody>
</table>

---

## 5. Mesurer efficacité et sobriété

<div class="outcome-grid">
<div>

### Qualité de détection

- précision : les alertes sont-elles justes ?
- rappel : combien de planètes sont retrouvées ?
- faux positifs et faux négatifs ;

</div>
<div>

### Coût de la méthode

- temps d’entraînement ;
- temps d’analyse par système ;
- mémoire et volume du modèle ;
- facilité d’explication du résultat.

</div>
</div>

<div class="conclusion">
  <span>Objectif final</span>
  <strong>Identifier le meilleur compromis entre détection, fiabilité et coût de calcul.</strong>
</div>

<p class="sources">Sources : NASA Kepler/MAST · Kovács, Zucker & Mazeh (BLS, 2002) · Shallue & Vanderburg (AstroNet, 2018)</p>
