---
marp: true
theme: emiletype
paginate: true
size: 16:9
title: Quelle est la méthode optimale de détection d'une exoplanète ?
description: Présentation générale du projet EmileType
---

<!-- _class: title -->
<!-- _paginate: false -->

<p class="kicker">TIPE · PHYSIQUE & INFORMATIQUE</p>

# Quelle est la méthode optimale de détection d’une exoplanète ?

Comparer un algorithme physique classique à un réseau de neurones.

<p class="author">EmileType · Méthode des transits · Données Kepler</p>

---

## 1. Détecter une planète invisible

<div class="columns">
<div>

Une planète passant devant son étoile provoque une baisse faible et périodique de luminosité.

- le signal est très court ;
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
  <h3>Box Least Squares</h3>
  <p>Recherche explicitement une baisse périodique en forme de boîte.</p>
  <ul>
    <li>modèle physique lisible ;</li>
    <li>peu de paramètres ;</li>
    <li>calcul relativement sobre.</li>
  </ul>
</article>
<article class="method neural">
  <span class="method-number">B</span>
  <h3>Réseau de neurones</h3>
  <p>Apprend les formes utiles directement à partir des courbes.</p>
  <ul>
    <li>modèle plus flexible ;</li>
    <li>entraînement nécessaire ;</li>
    <li>coût et décisions moins lisibles.</li>
  </ul>
</article>
</div>

<p class="question">Le gain de détection justifie-t-il la complexité supplémentaire ?</p>

---

## 3. Une comparaison sur les mêmes données

<div class="dataset-line">
  <div><strong>3 000</strong><span>systèmes Kepler</span></div>
  <div><strong>42</strong><span>systèmes confirmés</span></div>
  <div><strong>2 958</strong><span>étoiles témoins</span></div>
  <div><strong>1,4 %</strong><span>de systèmes positifs</span></div>
</div>

<div class="flow">
  <span>Courbes officielles<br><b>Kepler / MAST</b></span>
  <i>→</i>
  <span>Entraînement<br><b>70 %</b></span>
  <i>→</i>
  <span>Validation<br><b>15 %</b></span>
  <i>→</i>
  <span>Test final<br><b>15 %</b></span>
</div>

<p class="note"><b>Dataset construit à partir de Kepler DR25 :</b> 42 hôtes de planètes confirmées (P ≤ 30 jours) et 2 958 contrôles sans aucun KOI ni TCE.<br>Pour chaque système, jusqu’à trois courbes de lumière sont téléchargées depuis MAST ; la sélection est reproductible.</p>

---

## 4. Mesurer efficacité et sobriété

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
