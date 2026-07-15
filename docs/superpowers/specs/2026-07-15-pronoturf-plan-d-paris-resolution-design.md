# Design — Plan D : résolution des paris LLM (taux de réussite par type & niveau)

Date : 2026-07-15
Statut : validé (brainstorming), en attente de plan d'implémentation.
Réf. amont : `docs/superpowers/specs/2026-07-15-pronoturf-plan-c-backtest-design.md` (§Hors périmètre — « résolution/évaluation des paris LLM ») ; mémoire [plan-c-backtest-loop].

## Objectif

Étendre la boucle de mesure (Plan C) aux **paris de l'IA** : pour chaque recommandation
d'une analyse dont la course a une arrivée réelle, déterminer si le pari a **gagné**, puis
mesurer le **taux de réussite par type de pari** et **par niveau de confiance** (le second
dit si la conviction du LLM corrèle avec le résultat). Comme le Plan C, c'est de la
**mesure** : construite maintenant, elle se remplit à mesure que des analyses portent sur
des courses ensuite résultées. Rien n'est « appliqué » (ni la confiance affichée, ni les
paris proposés).

## Constat data (vérifié 2026-07-15)

- `analyses_llm` : 1 analyse courante (+2 historique). **0 analyse courante dont la course a
  déjà un résultat** → actuellement **zéro paire (pari, résultat)**. Mesure = infra d'abord,
  exactement comme le Plan C.
- Forme d'une recommandation persistée (Plan B) : `{type_pari, selection[], base[],
  tournant[], confiance (0–100), niveau (faible/moyen/eleve), avis}`. La résolution s'appuie
  sur `selection`.
- Les arrivées réelles sont dans `resultats` (Plan C) : `{course_id, partant_id,
  position_arrivee, disqualifie}`. Le nombre de partants se lit via les lignes `partants` de
  la course.

## Décision de fidélité (validée)

**Résolution en DÉSORDRE + règle de placé simple.** Pas de distinction ordre exact vs
désordre ; pas de gestion fine des non-partants au-delà de « cheval sans position = perdu ».
- **Placé** = arriver dans le top-K, avec **K = 3 si nb_partants ≥ 8, sinon K = 2**.

## Architecture

### A. Module pur `app/backtest/paris.py` (aucun I/O)

- `PLACE_MIN_RUNNERS = 8` (seuil pour K=3 vs K=2), constante.
- `_places_payantes(nb_partants) -> int` : `3 if nb_partants >= PLACE_MIN_RUNNERS else 2`.
- `resoudre_pari(recommandation, arrivee, nb_partants) -> dict` où `arrivee` = `{numero_corde:
  position_arrivee}` (uniquement les arrivés). Renvoie
  `{type_pari, niveau, gagnant: bool|None}`. `None` = non résolu (arrivée vide / sans
  gagnant identifiable) ; sinon `True`/`False`. Règles (désordre, sur `selection`) :

  | type_pari | condition de gain (désordre) |
  |---|---|
  | `SIMPLE_GAGNANT` | `selection[0]` arrive 1er |
  | `SIMPLE_PLACE` | `selection[0]` dans le top-K |
  | `COUPLE_GAGNANT` | `{selection[0], selection[1]}` == l'ensemble {1er, 2e} |
  | `COUPLE_PLACE` | `selection[0]` **et** `selection[1]` dans le top-K |
  | `DEUX_SUR_QUATRE` | ≥ 2 chevaux de `selection` dans le top-4 |
  | `TRIO` | `{selection[0..2]}` == l'ensemble {top-3} |
  | `TIERCE` | `{selection[0..2]}` == l'ensemble {top-3} (désordre) |
  | `QUARTE_PLUS` | `{selection[0..3]}` == l'ensemble {top-4} |
  | `QUINTE_PLUS` | `{selection[0..4]}` == l'ensemble {top-5} |

  - `selection` trop courte pour le type, ou cheval sélectionné non partant / non arrivé →
    le pari **perd** (`False`), pas d'exception.
  - Type hors des 9 ci-dessus (ne devrait pas arriver, `ANALYSABLE` les couvre) → `None`.
  - Arrivée sans gagnant (aucune `position_arrivee == 1`) → `None` (course non résolue).
- `resoudre_analyse(recommandations, arrivee, nb_partants) -> list[dict]` : mappe
  `resoudre_pari` sur chaque reco.

### B. Agrégat + endpoint (extension de `GET /backtest`)

- Nouveau helper dans `app/backtest/routes.py` : assemble, pour chaque course ayant **une
  analyse `analyses_llm`** ET **un résultat**, l'arrivée (`resultats` → `{corde: position}`
  via le join `partant_id → numero_corde` déjà utilisé) + le nombre de partants, puis
  `resoudre_analyse`. Ne compte que les recos résolues (`gagnant` non `None`).
- `GET /backtest` gagne un bloc **`paris`** :
  ```
  "paris": {
    "nb_analyses_resolues": int,          // nb de courses analysées ET résultées
    "par_type": [ {type_pari, nb, taux_reussite} ],   // par type de pari, taux ∈ [0,1]
    "par_niveau": [ {niveau, nb, taux_reussite} ]      // faible/moyen/eleve
  }
  ```
  Gracieux à zéro : `{"nb_analyses_resolues": 0, "par_type": [], "par_niveau": []}`.
- **Lecture seule, aucune persistance, aucune migration.** (On ne stocke pas de snapshot de
  paris en v1 ; calcul à la demande.)

### C. Frontend — section « Paris IA » dans `PerfPanel`

- Type `Backtest` étendu : `paris: { nb_analyses_resolues, par_type: BetTypeStat[],
  par_niveau: BetNiveauStat[] }`.
- `PerfPanel` gagne une section « Paris IA » : taux de réussite par type de pari (libellé via
  `libellePari`) et par niveau, chaque ligne avec son `n`. Ton « échantillon mince » (ex.
  `n` en évidence, message discret) tant que `nb_analyses_resolues` est faible ; état
  « aucune analyse résultée » quand `nb_analyses_resolues == 0`. Blanc/vert, cohérent.

## Décisions clés (validées)

1. **Résolution désordre + placé top-3(≥8)/top-2** (pas d'ordre exact, pas de fidélité PMU
   fine). Simplicité assumée pour démarrer la mesure.
2. **Base = la `selection` de la reco** (pas `base`/`tournant`).
3. **Étend `GET /backtest`** avec un bloc `paris` ; pas de nouvel endpoint, pas de migration,
   pas de persistance de snapshot pour les paris en v1.
4. **Descriptif avec `n`** (pas de hard-gate) : les taux sont affichés avec leur effectif ;
   honnêteté sur la finesse. Inclut source `llm` **et** `regles` (les deux sont des paris
   proposés ; on pourra filtrer par source plus tard).
5. **Mesure seulement** : rien n'est appliqué (ni confiance, ni sélection de paris).

## Découpage prévisionnel (un seul plan, ~5-6 tâches TDD)

1. Module `app/backtest/paris.py` (`resoudre_pari`, `resoudre_analyse`, `_places_payantes`) — pur, TDD.
2. Agrégat des paris + extension `GET /backtest` (bloc `paris`) dans `routes.py` + tests (FakeStore).
3. Frontend : type `Backtest` étendu (`paris`).
4. Frontend : section « Paris IA » dans `PerfPanel`.
5. Vérification E2E (contrôleur) : analyser une course déjà courue + backfill son résultat → `GET /backtest.paris` non vide ; cas vide gracieux.

## Hors périmètre (Plan D — cet incrément)

- Fidélité PMU complète (ordre exact vs désordre par type, règles de placé exactes selon la
  taille du peloton, gestion fine des non-partants/rapports) → plan futur si besoin.
- Rapports/gains réels des paris (ROI) → nécessiterait les rapports PMU ; hors périmètre.
- Persistance de snapshots de paris + filtre par source llm/regles → plus tard.
- Application (proposer automatiquement les types de paris les plus rentables) → plan futur.

## Prérequis & risques

- **Aucune migration** (réutilise `analyses_llm`, `resultats`, `partants`).
- **Thin data** : `par_type`/`par_niveau` renvoient un effectif `n` ; le panneau reflète la
  finesse plutôt que d'afficher un taux trompeur. Actuellement ~0 analyse résolue.
- **Simplification assumée** : Trio et Tiercé résolvent à l'identique en désordre (même
  condition sur 3) ; acceptable en v1, documenté.
- **Vérif E2E navigateur** limitée (pas d'outil de pilotage) — contrat HTTP + build, cf.
  mémoire [frontend-e2e-verification].
