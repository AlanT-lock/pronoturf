# Mini-rapport de faisabilité — Aspiturf comme source d'historique enrichi

Date : 2026-07-14
Statut : exploratoire (aide à la décision, avant tout plan).

## Contexte & objectif

L'algorithme enrichi (Plan 3) souffre d'une limite de données : l'API PMU
`performances-detaillees` ne renvoie qu'**~1 course passée par cheval**, si bien que
les facteurs par contexte (distance/discipline/niveau/hippodrome) restent le plus souvent
neutres (échantillon < 3) — cf. [[pmu-history-limitation]]. On cherche une source
fournissant un **historique de performances profond** par cheval (et des stats
jockey/entraîneur), pour peupler `chevaux_performances` en masse.

## Ce qu'est Aspiturf (faits vérifiés)

- **Base de données turf gratuite**, en ligne depuis 2014, alimentée par les
  **données PMU** (mêmes courses que celles qu'on ingère déjà).
- Couvre : **courses, chevaux, jockeys, entraîneurs, statistiques**.
- Deux modes d'accès :
  - **Téléchargement en masse** via « Aspiload » — **dump SQL** importable dans MySQL.
  - **CSV par course** (téléchargeables après inscription).
- Services connexes : *Aspibet* (cotes temps réel sur les grandes courses),
  *AspiLoose* (stats avancées).
- Inscription/login requis. Un **dépôt GitLab** (`rodrigues.joachim/aspiturf`, GPL-3.0)
  fournit de l'outillage autour de la base.
- Avertissement du site : les données « peuvent être inexactes ».

Sources : aspiturf.com, aspiturf.com/connec, aspiturf.com/propos, forum.aspiturf.com
(fils « API turf – données des courses PMU », « La base »), gitlab.com/rodrigues.joachim/aspiturf.

## Adéquation au besoin

**Forte, sur le papier**, pour trois raisons :

1. **Même source (PMU) que notre modèle** → le rapprochement d'identités est le point
   le plus risqué de toute intégration tierce, et ici il est *a priori* facile : si
   Aspiturf conserve les identifiants PMU (numéro de course, `numPmu`, id cheval) ou
   au minimum date + hippodrome + nom, on peut mapper sur nos `chevaux`/`courses`
   existants sans moteur de matching floue lourd.
2. **Profondeur historique** (depuis 2014) → exactement ce qui manque à
   `chevaux_performances` : plusieurs courses passées par cheval, avec place à l'arrivée,
   discipline, distance, hippodrome, jockey — les champs que nos facteurs contextuels
   consomment déjà.
3. **Format SQL en masse** → pas de scraping fragile ; un import batch ponctuel suffit à
   backfiller, puis des mises à jour incrémentales.

## Points de faisabilité technique

| Aspect | Évaluation |
|---|---|
| Accès | Gratuit, inscription. Dump SQL (MySQL) + CSV/course. |
| Format cible | On est sur **Postgres/Supabase** → un dump **MySQL** demande une conversion (schéma + types). Les **CSV** sont plus neutres et probablement plus simples à charger via `COPY`. |
| Mapping identités | À confirmer : présence d'ids PMU. Sinon, clé naturelle (date + hippodrome + nom cheval) — gérable. |
| Champs requis | Nos besoins : `cheval, date_course, hippodrome, discipline, distance_m, allocation, place, jockey_nom`. Aspiturf annonce courses/chevaux/jockeys/entraîneurs — **à confirmer champ par champ sur un échantillon**. |
| Volume | Base nationale depuis 2014 = volumineuse ; l'import initial est un batch, pas une requête temps réel. Prévoir une table de staging. |
| Fraîcheur | À confirmer (fréquence de mise à jour du dump). Pour les courses du jour, on garde l'API PMU ; Aspiturf sert surtout au **backfill historique**. |
| Qualité | Avertissement « peut être inexacte » → prévoir des contrôles (dates plausibles, places cohérentes) avant d'alimenter le scoring. |

## Risques & inconnues

1. **Schéma exact non confirmé** — le README GitLab n'était pas accessible ; le forum est
   une SPA difficile à lire par outil. Le schéma réel se lira sur un dump téléchargé.
2. **CGU / droit des bases de données** — réutiliser une base tierce, même « gratuite »,
   a des implications ; faible risque en usage strictement personnel, à clarifier si
   pronoturf devient une plateforme partagée.
3. **Dépendance à un projet communautaire** — pérennité et régularité des mises à jour non
   garanties (un seul mainteneur apparent).
4. **Conversion MySQL→Postgres** — friction modérée ; les CSV contournent le problème.

## Spike recommandé (avant tout plan d'ingestion)

Petit lot de validation, ~une demi-journée, sans toucher au code produit :

1. **Créer un compte** Aspiturf, télécharger **un échantillon** (le CSV d'une course +
   un extrait du dump SQL).
2. **Inspecter le schéma réel** : lister les colonnes, repérer (a) les identifiants PMU
   éventuels, (b) les champs correspondant à `chevaux_performances`, (c) la présence de la
   **place à l'arrivée** et du **jockey par course passée** (indispensables aux facteurs).
3. **Prototype de mapping** (hors prod, dans `/tmp` ou un notebook) : charger l'échantillon,
   rapprocher 2-3 chevaux de nos `chevaux` existants (par id PMU ou date+hippodrome+nom),
   vérifier qu'on reconstitue bien N>3 courses par cheval.
4. **Décision** : si le mapping tient et que les champs y sont → rédiger un plan
   d'ingestion (table de staging `aspiturf_import`, normaliseur, écriture idempotente vers
   `chevaux_performances`, contrôle qualité). Sinon → se rabattre sur Geny (scraping) ou
   rester sur PMU + accumulation.

## Verdict

**Faisable et prometteur pour le backfill d'historique**, avec un bon alignement (source
PMU commune) et un accès gratuit en masse. Deux réserves à lever par un spike court :
le **schéma exact** (présence de la place à l'arrivée + jockey par course passée + ids PMU)
et la **qualité/fraîcheur**. Recommandation : **faire le spike** (télécharger un échantillon
et inspecter), pas encore un plan d'ingestion complet. Aspiturf reste le meilleur candidat
« volume/effort » devant Geny (scraping plus lourd) pour combler le trou d'historique.
