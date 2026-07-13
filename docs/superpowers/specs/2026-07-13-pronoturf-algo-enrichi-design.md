# Design — Algorithme de pronostic enrichi (facteurs contextuels + jockey/entraîneur)

Date : 2026-07-13
Statut : validé (brainstorming), en attente de plan d'implémentation.

## Objectif

Faire passer le scoring d'une analyse principalement basée sur la musique et la
cote à un **algorithme complet** qui réunit un maximum d'informations sur chaque
cheval pour produire de véritables pronostics : taux de réussite par **distance**,
par **discipline**, par **niveau de course (allocation)**, par **hippodrome**
(familiarité de l'environnement), plus les taux de réussite du **jockey** et de
l'**entraîneur**, et la correction de la **corde réelle**. Chaque pronostic est
assorti d'un **indice de confiance** disant sur quel volume de données il repose.

C'est la brique qui transforme pronoturf en plateforme personnelle où la donnée
se capitalise au fil des imports.

## Constat de faisabilité (données)

L'API PMU `offline.turfinfo.api.pmu.fr/rest/client/61` expose, en plus des
endpoints déjà utilisés (`/programme/{date}`, `.../participants`), l'endpoint
**`.../performances-detaillees/pretty`** qui renvoie pour chaque cheval la liste
`coursesCourues` de ses courses passées. Chaque course passée fournit :
`date`, `hippodrome`, `nomPrix`, `discipline`, `allocation`, `distance`,
`nbParticipants`, et sous `participants[itsHim==true]` : `place`
(`{place, rawValue, statusArrivee}`), `nomJockey`, `poidsJockey`, `corde`,
`reductionKilometrique`, `oeillere`.

Conséquences :
- Taux par **distance / discipline / niveau / hippodrome** : dérivables directement.
- Taux global **jockey** : accumulable depuis ces historiques (chaque course passée
  nomme le jockey + la place) → riche immédiatement.
- Taux global **entraîneur** : **absent** des courses passées (l'entraîneur n'est
  donné que sur la course du jour, via `participants.entraineur`). Il ne peut donc
  s'accumuler que depuis les courses **terminées** qu'on importe → montée en
  puissance lente (démarrage à froid assumé).
- Bonus disponibles et non exploités aujourd'hui : `placeCorde` (**vraie corde**,
  distincte de `numPmu` utilisé à tort actuellement pour le facteur corde),
  `oeilleres`, `allure`, pedigree, `robe`.

## Périmètre

**Inclus :** migration + modèles, ingestion de l'historique
(`performances-detaillees`), capture des résultats pour l'entraîneur, module de
calcul des taux par contexte, agrégation des stats jockey/entraîneur, intégration
au moteur de score + indice de confiance + nouvelles pondérations, affichage
frontend (confiance + jockey/entraîneur), correction de la corde, vérification E2E.

**Hors périmètre :** calibration des poids par backtest sur résultats réels
(Plan 4) — on fixe des poids par défaut raisonnables, ajustables en base ; scraping
Geny (Plan 3) ; déploiement/auth/RLS.

## Jeu de facteurs cible (~11)

| Facteur | Source | Statut |
|---|---|---|
| `forme` (musique) | participants | conservé |
| `taux_reussite` (carrière globale) | participants | conservé |
| `ferrage_poids` (déferrage trot / poids plat) | participants | conservé |
| `cote` | cotes | conservé |
| `corde` | participants `placeCorde` | **corrigé** (vraie corde, pas `numPmu`) |
| `taux_distance` | historique | nouveau |
| `taux_discipline` | historique | nouveau |
| `taux_niveau` (allocation) | historique | nouveau |
| `taux_hippodrome` (familiarité) | historique | nouveau |
| `jockey` | agrégat historique | nouveau |
| `entraineur` | agrégat résultats terminés | nouveau |

Plus un **indice de confiance** par cheval (hors pondération : c'est un méta-signal,
pas un facteur de score).

## Architecture des données (approche « historique brut persisté »)

### Nouvelles tables (migration `0003`)

**`chevaux_performances`** — courses passées brutes par cheval :
`id`, `cheval_id` (FK `chevaux`), `date_course`, `hippodrome`, `discipline`,
`distance_m`, `allocation`, `nb_participants`, `place` (int, nullable),
`status_arrivee` (text), `raw_place` (text : "1", "DP", "T"…), `jockey_nom`,
`poids_jockey` (float, nullable), `corde` (int, nullable), `oeillere` (text, nullable).
Contrainte d'unicité `(cheval_id, date_course, hippodrome, distance_m)` → upsert
idempotent (`on_conflict`), un ré-import ne duplique pas.

**`entraineur_resultats`** — alimentée uniquement par les courses **terminées**
importées (seule source pour l'entraîneur) :
`id`, `entraineur_nom`, `cheval_id` (FK `chevaux`), `date_course`, `hippodrome`,
`discipline`, `place` (int, nullable), `status_arrivee` (text).
Contrainte d'unicité `(entraineur_nom, cheval_id, date_course)` → idempotent.

> Les **stats globales jockey/entraîneur** sont obtenues par **agrégation**
> (`GROUP BY jockey_nom` sur `chevaux_performances` ; `GROUP BY entraineur_nom` sur
> `entraineur_resultats`), pas par compteurs maintenus à la main — toujours
> cohérentes, aucun risque de double-comptage.

### Flux d'ingestion (à l'import, en plus de l'existant)

1. Récupérer `performances-detaillees` ; pour chaque cheval, parser `coursesCourues`
   (participant `itsHim`) → upsert dans `chevaux_performances`.
2. Si la course importée est **terminée** (arrivée définitive), enregistrer pour
   chaque partant `(entraineur, cheval_id, date, hippodrome, discipline, place)` dans
   `entraineur_resultats`.
3. **Dégradation gracieuse** : cheval débutant (aucun historique), endpoint
   indisponible, payload vide → on n'écrit rien ; **l'import réussit quand même** ;
   les facteurs contextuels tomberont en neutre au score. L'historique n'est jamais
   un bloquant de l'import.

## Calcul des facteurs (au moment du score)

Pour chaque cheval, on lit son `chevaux_performances` et on filtre selon le
contexte de la course du jour :

- **`taux_distance`** : courses dont `distance_m` ∈ [distance_jour × 0.9, × 1.1] (**±10 %**).
- **`taux_discipline`** : courses de même `discipline`.
- **`taux_niveau`** : courses dont `allocation` ∈ [allocation_jour × 0.7, × 1.3] (**±30 %**).
- **`taux_hippodrome`** : courses au même `hippodrome`.
- **`jockey`** : taux global du jockey du jour (agrégat `chevaux_performances` :
  succès top-3 / courses montées, toutes montures confondues).
- **`entraineur`** : taux global de l'entraîneur du jour (agrégat
  `entraineur_resultats` : succès top-3 / courses).

Les facteurs `jockey` et `entraineur` suivent les **mêmes règles** que les taux par
contexte : même définition du succès (top 3), et **échantillon minimal** (`< 3`
courses pour ce jockey / cet entraîneur → facteur **neutre 0.5**).

Règles communes :
- **Définition d'un succès** : arrivé **dans les 3 premiers** (`place ∈ {1,2,3}`),
  cohérent avec le `taux_reussite` carrière actuel. Une place nulle / non-placé
  (`status_arrivee` non classé, `place` NULL, `raw_place` type "DP"/"T"…) compte
  comme non-succès mais **compte dans le dénominateur** (course courue).
- **Taux** = succès / courses_dans_le_contexte, borné [0,1].
- **Échantillon minimal** : `< 3` courses dans le contexte → facteur **neutre 0.5**
  (on ne juge pas sur trop peu de données).
- **Normalisation** : les taux sont utilisés en **valeur absolue [0,1]** (un taux de
  40 % vaut 40 % quel que soit le peloton). `cote`, `corde`, `poids` restent en
  **min-max relatif** à la course (comportement actuel conservé).

**Indice de confiance** (par cheval, dans [0,1]) : croît avec le volume total
d'historique du cheval et le fait que jockey/entraîneur soient connus. Formule
initiale proposée : `confiance = min(1, nb_courses_historique / 10)` pondérée à la
baisse si jockey ou entraîneur inconnus. Renvoyée avec `nb_courses_historique` pour
affichage. (Formule ajustable ; ce n'est pas un facteur de score.)

Tous les seuils (±10 %, ±30 %, succès = top 3, échantillon = 3, plafond confiance
= 10) sont des **constantes configurables** dans le module de scoring.

## Intégration au moteur de score

- `compute_factors` calcule les 6 nouveaux facteurs en plus des 5 existants ; ils
  entrent dans `details_facteurs` (`valeur × poids_effectif = contribution`).
- La **redistribution des poids** déjà en place gère les facteurs neutres/absents :
  un cheval sans historique voit le poids de ses facteurs contextuels redistribué
  sur ses facteurs connus (pas de dilution injuste).
- **Pondérations** : la migration met à jour `ponderations_config` avec des poids
  par défaut pour ~11 facteurs, **par discipline**, somme = 1. Défauts fixés par
  l'implémentation (validé), ajustables en base. Calibration fine = Plan 4 (backtest),
  rendu possible par l'historique brut stocké.
- Le score renvoie `confiance` et `nb_courses_historique` par ligne de classement,
  en plus de la structure existante.

## Frontend

- **`PronosticTable`** : les nouveaux facteurs apparaissent automatiquement dans le
  détail dépliable (itération générique déjà en place). Ajout d'un **badge de
  confiance** par ligne (pastille + « N courses ») pour repérer d'un coup d'œil les
  pronostics solides vs fragiles.
- **`PartantsTable`** : afficher **jockey** et **entraîneur** (noms déjà disponibles
  via l'enrichissement backend, à étendre au besoin) en colonnes.
- Types TS étendus : `ScoreRow` gagne `confiance?: number` et
  `nb_courses_historique?: number`.

## Gestion d'erreurs & cas limites

- **Débutant** (0 historique) : tous les facteurs contextuels → neutre 0.5,
  confiance basse.
- **Endpoint historique indisponible** : import réussit, historique sauté, loggé ;
  facteurs neutres au score.
- **Entraîneur en démarrage à froid** : neutre tant que `entraineur_resultats` est
  vide pour lui.
- **Allocation manquante** sur une course passée : la course est ignorée pour le
  seul `taux_niveau` (comptée pour les autres contextes).

## Tests

- **Calcul des facteurs** (unitaire, depuis fixtures d'historique) : filtres
  distance/discipline/niveau/hippodrome ; définition du succès (top 3, non-placé au
  dénominateur) ; échantillon `< 3` → neutre ; indice de confiance ; bornes [0,1].
- **Ingestion** : parse d'un fixture `performances-detaillees` → lignes
  `chevaux_performances` (idempotence de l'upsert) ; course terminée →
  `entraineur_resultats`.
- **Agrégation** : stats jockey (depuis performances) et entraîneur (depuis
  résultats) correctes.
- **Moteur** : intégration des 6 facteurs, somme des poids = 1, redistribution
  quand facteurs neutres, `confiance`/`nb_courses_historique` renvoyés.
- **Corde** : le facteur corde utilise bien `placeCorde` et non `numPmu`.
- **Endpoint / E2E** : import réel PMU peuple l'historique ; le score reflète les
  nouveaux facteurs ; frontend build clean.
- Réutilise le pattern `FakeStore`/`FakeQuery` existant (étendu aux nouvelles tables
  et à l'agrégation).

## Découpage prévisionnel du plan (~8 tâches)

1. Migration `0003` + modèles Pydantic (`chevaux_performances`, `entraineur_resultats`).
2. Ingestion historique : `fetch_performances_detaillees` (client) + parse (normalizer)
   + écriture (writer, upsert idempotent).
3. Capture résultats entraîneur pour les courses terminées.
4. Module de calcul des taux par contexte (distance/discipline/niveau/hippodrome) +
   définition succès + échantillon mini + indice de confiance.
5. Agrégation des stats globales jockey/entraîneur.
6. Intégration moteur : nouveaux facteurs dans `compute_factors`/`engine`,
   correction corde (`placeCorde`), pondérations par défaut, renvoi confiance.
7. Frontend : badge de confiance dans `PronosticTable`, colonnes jockey/entraîneur
   dans `PartantsTable`, types TS.
8. Vérification E2E (contrôleur) : import réel + score, contrôle des nouveaux
   facteurs et de la confiance.

Un seul spec (ce document), un seul plan.
