# pronoturf — Plan 2 : saisie manuelle + moteur de scoring + frontend — design

Date : 2026-07-12
Statut : validé (design), en attente de plan d'implémentation
Parent : `docs/superpowers/specs/2026-07-12-pronoturf-mvp-design.md`
Suit : `docs/superpowers/plans/2026-07-12-pronoturf-plan1-schema-pmu-ingestion.md` (Plan 1, terminé)

## Contexte

Le Plan 1 a livré l'ingestion PMU d'une course (programme, partants, cotes) dans Supabase, via `POST /courses/import`. Le Plan 2 ajoute la couche de valeur : compléter les données à la main, calculer un score de pronostic pondéré par cheval, et l'afficher dans un frontend Next.js. Tests en local uniquement (pas de déploiement Vercel pour l'instant).

Ce document affine la spec parente sur trois décisions prises en brainstorming, puis détaille le moteur de scoring, les endpoints et le frontend.

## Décisions structurantes (brainstorming 2026-07-12)

1. **Extension du schéma pour capter les stats PMU déjà disponibles.** L'API PMU fournit dans `participants` des compteurs qu'on n'a pas stockés en Plan 1 : `nombreCourses`, `nombreVictoires`, `nombrePlaces` (+ 2ᵉ/3ᵉ), `gainsParticipant` (gainsCarriere, gainsAnneeEnCours, gainsAnneePrecedente), `age`. On les ajoute au schéma pour que le moteur de scoring les utilise.

2. **`cotes` : une ligne par `(partant_id, type_capture)`.** Ajout d'une contrainte `unique(partant_id, type_capture)` et d'un `on_conflict` sur l'upsert des cotes. Réimporter une course met à jour les cotes au lieu de les dupliquer (cohérent avec l'import à la demande, pas de polling continu au MVP).

3. **Le frontend lit via l'API FastAPI, pas Supabase en direct.** Contrairement à la formulation initiale de la spec parente (« le frontend lit Supabase directement »), le frontend Next.js n'accède jamais Supabase directement au Plan 2 : il passe par des endpoints FastAPI. La clé service-role reste côté backend, aucune RLS à configurer, tout tourne en local. L'option « lecture Supabase directe » (avec RLS) reste ouverte pour une phase ultérieure si la performance l'exige.

## Extension du schéma (migration `0002`)

- **`cotes`** : ajouter `unique(partant_id, type_capture)`.
- **`partants`** : ajouter `nombre_courses int`, `nombre_victoires int`, `nombre_places int`, `gains_carriere numeric`, `gains_annee_en_cours numeric`, `age int`. (Les stats varient par engagement/date, on les rattache au partant, pas au cheval.)

Le normalizer (`pmu_normalizer.py`) et le writer (`supabase_writer.py`) du Plan 1 sont étendus pour peupler ces colonnes depuis le payload PMU déjà récupéré (aucun nouvel appel API).

## Moteur de scoring (`app/scoring/engine.py`)

Les pondérations vivent en base (`ponderations_config`, une config `actif` par défaut par discipline — table déjà créée en Plan 1). Le moteur :

1. Charge la config de pondération active pour la discipline de la course.
2. Calcule chaque facteur normalisé sur `[0, 1]` pour chaque partant (voir facteurs ci-dessous).
3. Redistribue proportionnellement le poids des facteurs non disponibles (poids 0 ou donnée absente) sur les facteurs disponibles, pour que la somme des poids effectifs reste 1.
4. `score_total = Σ (poids_effectif_i × facteur_i)`, stocké sur `[0, 1]` (ou ×100 pour lisibilité — à fixer dans le plan).
5. Écrit une ligne `scores_pronostic` par partant avec `rang_pronostique` (tri décroissant du score) et `details_facteurs` (jsonb : valeur normalisée + contribution de chaque facteur), pour rester explicable.

Les partants `non_partant` sont exclus du calcul et du classement.

### Facteurs calculables en Plan 2

| Facteur | Source | Normalisation | Poids défaut (trot / plat) |
|---|---|---|---|
| Forme récente | parsing `musique` | score des N dernières places → `[0,1]` | 25% / 25% |
| Taux victoire/place | compteurs PMU | `(victoires + places) / courses`, borné | 15% / 15% |
| Ferrage (trot) / poids porté (plat) | `ferrage` / `poids_kg` | trot : barème déferré ; plat : poids relatif inversé | 10% / 10% |
| Cote marché | `cotes` (reference ou finale) | inverse de la cote, normalisé sur la course | 15% / 15% |
| Corde / numéro de départ | `numero_corde` | avantage relatif (plat surtout) | — / 5% |

**Parsing de la musique** : chaîne type `7aDm5a(25)6mDm9m3mDm9m`. Chiffres `1`–`9` = place à l'arrivée, `0` = non-placé/au-delà, lettres = discipline (`a` attelé, `m` monté, `p`/`s`/`h` plat/steeple/haies), `D`/`T`/`A` = disqualifié/tombé/arrêté (traités comme mauvaise perf), `(25)` = marqueur d'année (ignoré pour le score, sert juste à délimiter). On prend les N premières performances (N à fixer, ex. 5), on mappe chaque place sur un score décroissant (1ᵉ = meilleur, non-placé/disqualifié = pire), moyenne pondérée (perfs récentes comptent plus).

### Facteurs différés (poids 0 pour l'instant, redistribués)

- **Fraîcheur** (jours depuis dernière course) — nécessite l'endpoint PMU `performances-detaillees` (dates de courses), non intégré au Plan 2 pour ne pas ajouter un 2ᵉ appel ; arrive en Plan 3+.
- **Couple cheval/driver-jockey**, **forme entraîneur du mois** — nécessitent Geny (Plan 3) ou l'historique des résultats (Plan 4).

## Saisie manuelle

PMU couvrant désormais l'essentiel, le formulaire est léger :
- **Niveau course** : `etat_terrain`.
- **Niveau partant** : override/complétion des champs que PMU n'a pas fournis (ex. ferrage de dernière minute). Chaque champ saisi à la main est enregistré dans `partants.champs_manuels` (jsonb, liste des noms de champs) pour tracer l'origine de la donnée.

## Endpoints FastAPI (Plan 2)

- `GET /courses/{id}` — course + partants (avec stats) + cotes, pour l'affichage.
- `PATCH /partants/{id}` — saisie/override manuel ; met à jour le partant et ajoute les champs modifiés à `champs_manuels`.
- `PATCH /courses/{id}` — saisie niveau course (`etat_terrain`).
- `POST /courses/{id}/score` — calcule les scores, écrit `scores_pronostic`, renvoie le classement.
- `GET /courses/{id}/pronostic` — lit le classement pronostiqué (rang, cheval, score, détail des facteurs, cote en regard).

## Frontend Next.js (une page de travail)

1. Champ de saisie de l'identifiant de course (réunion + numéro) → bouton « Importer » (`POST /courses/import`).
2. Tableau des partants importés (avec stats PMU), formulaire inline pour les champs manquants (état du terrain, ferrage de dernière minute) → `PATCH`.
3. Bouton « Calculer le pronostic » (`POST /courses/{id}/score`).
4. Tableau de classement pronostiqué : rang, cheval, score, cote officielle en regard, détail des facteurs (survol/expand pour voir la contribution de chaque facteur).

Stack : Next.js (App Router), appels aux endpoints FastAPI locaux. Pas d'auth, pas de déploiement.

## Hors scope Plan 2 (plans suivants)

- Saisie/import des résultats réels post-course et calcul de précision du pronostic (Plan 4).
- Ingestion Geny (stats driver/entraîneur, couple) (Plan 3).
- Facteur fraîcheur via `performances-detaillees` (Plan 3+).
- RLS / lecture Supabase directe par le frontend.
- Déploiement (Vercel/prod).

## Découpage en tâches (aperçu, détaillé dans le plan)

1. Migration `0002` : `unique(partant_id, type_capture)` sur `cotes` + colonnes stats sur `partants` ; `on_conflict` cotes dans le writer.
2. Étendre normalizer + writer pour peupler les stats PMU.
3. Moteur de scoring : parsing musique, normalisation des facteurs, pondération + redistribution, écriture `scores_pronostic`. Config de pondération par défaut (seed).
4. Endpoints lecture (`GET /courses/{id}`, `GET /courses/{id}/pronostic`), scoring (`POST /courses/{id}/score`), saisie (`PATCH`).
5. Frontend Next.js (page de travail).
6. Vérification bout-en-bout (import → saisie → score → affichage) contre l'API PMU réelle et Supabase.

## Note

Outil d'aide à la décision statistique — aucune garantie de résultat. Les paris hippiques comportent une part de hasard irréductible.
