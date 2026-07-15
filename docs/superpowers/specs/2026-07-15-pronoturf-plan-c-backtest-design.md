# Design — Plan C : boucle de mesure (ingestion des résultats + évaluation + calibration data-gated)

Date : 2026-07-15
Statut : validé (brainstorming), en attente de plan d'implémentation.
Réf. amont : `docs/superpowers/specs/2026-07-14-pronoturf-plateforme-paris-ia-design.md` (§Découpage — « Plan C — Calibration/backtest »).

## Objectif

Fermer la boucle prédiction → résultat : capturer les **arrivées réelles** des courses qu'on
pronostique, puis **évaluer** la qualité du scoring déterministe et la **calibration** de
l'indice de confiance. La calibration effective (confiance → probabilité, réglage des poids)
est **construite mais data-gated** : elle ne s'active que lorsque assez de paires
(prédiction, résultat) se sont accumulées. Cet incrément *mesure et expose* ; il ne réécrit
pas encore la confiance affichée ni les pondérations.

**Hors périmètre de cet incrément** (décidé au brainstorming) : la résolution/évaluation des
**paris LLM** (Simple/Couplé/Tiercé… gagnés ou non) — nécessite d'encoder les règles de
résolution des paris ; ce sera un incrément suivant. Le réglage automatique des poids et
l'application live de la calibration restent aussi pour plus tard.

## Constat data (vérifié le 2026-07-15)

- Le schéma **contient déjà** deux tables créées au Plan 1 mais **jamais utilisées** (0 ligne,
  aucun code n'y écrit) :
  - `resultats (id, course_id, partant_id UNIQUE, position_arrivee, disqualifie, ecart, gains)`
    — l'arrivée réelle par partant.
  - `backtest_resultats (id, ponderation_config_id, periode_debut, periode_fin, nb_courses,
    precision_top1, precision_top3, calculated_at)` — snapshot agrégé par config de poids.
- Data actuelle : ~12 courses, 136 lignes `scores_pronostic` (prédictions), **0 `resultats`**
  → actuellement **zéro paire (prédiction, résultat)**. La calibration est donc statistiquement
  vide tant que la data n'a pas grossi — d'où le « data-gated ».
- La normalisation des participants extrait **déjà** `position_arrivee` quand la course est
  `terminée` (aujourd'hui utilisé pour `entraineur_resultats`). L'ingestion des résultats
  réutilise cette donnée ; **pas besoin de nouvelle source PMU**.
- Contrainte connue : [pmu-history-limitation] — historique mince par cheval ; les facteurs
  contextuels restent souvent neutres et la confiance basse. La boucle de mesure est justement
  ce qui rendra cette limite quantifiable dans le temps.

## Architecture

### A. Ingestion des résultats → table `resultats`

- **Writer** `SupabaseWriter.save_resultats(course_id, partants, partant_id_by_corde) -> int` :
  pour chaque partant d'une course **terminée**, upsert dans `resultats`
  (`course_id`, `partant_id`, `position_arrivee`, `disqualifie`) sur conflit `partant_id`
  (contrainte unique existante). `ecart`/`gains` laissés `NULL` en v1 (non fiables/indispo).
  `disqualifie` dérivé du statut d'arrivée si présent, sinon `false`.
- **Déclencheurs** (deux, complémentaires) :
  1. **Auto à l'import** : dans `import_course`, si `course.statut == "terminee"`, appeler
     `save_resultats` en plus de l'existant (à côté de `save_entraineur_resultats`, même
     donnée `partants` + `cheval_id_by_corde`/`partant_id`).
  2. **Rafraîchissement explicite** : `POST /courses/{id}/resultats` — re-fetch les
     participants PMU de la course (via `fetch_participants` avec la date/R/C stockés), et **si
     elle a couru** (arrivée présente), normalise + écrit `resultats` ; sinon renvoie un statut
     « pas encore courue ». Sert à **backfill** les courses pronostiquées avant la course.
- Idempotent (upsert sur `partant_id`). Re-capturer une course ne duplique pas.

### B. Harnais d'évaluation → module pur `app/backtest/`

Fonctions **pures** (pas d'I/O), testées en isolation :

- `evaluate_course(classement, resultats) -> dict` où `classement` = lignes rangées
  (numero_corde, rang, confiance) et `resultats` = map numero_corde → position_arrivee.
  Renvoie : `{ "gagnant_reel": numero_corde|None, "rang_predit_du_gagnant": int|None,
  "top1_hit": bool, "top3_hit": bool, "confiance_top1": float|None }`.
  - `top1_hit` = notre rang-1 prédit est le gagnant réel (position_arrivee == 1).
  - `top3_hit` = le gagnant réel est dans nos 3 premiers rangs prédits.
  - Courses sans gagnant identifiable (annulée, aucune arrivée) → exclues (renvoient
    `gagnant_reel=None`) et ne comptent pas dans les agrégats.
- `aggregate(evaluations) -> dict` : `{ "nb_courses": int, "precision_top1": float|None,
  "precision_top3": float|None, "brier_confiance": float|None }` sur les courses évaluables
  (`gagnant_reel` non None). `None` si `nb_courses == 0`. `brier_confiance` = moyenne de
  `(confiance_top1 - top1_hit)^2` (diagnostic secondaire ; `None` si aucune confiance).
- `calibration_bins(pairs, n_bins=5) -> list[dict]` : bucketise par `confiance_top1` (bornes
  [0,0.2,0.4,0.6,0.8,1]), renvoie par bucket `{ "bucket": "0.0–0.2", "n": int,
  "confiance_moyenne": float, "taux_top1_reel": float }` (buckets vides omis). C'est la
  **courbe de fiabilité** : confiance prédite vs réussite réelle.

### C. Calibration data-gated → `app/backtest/calibration.py`

- `MIN_PAIRS_CALIBRATION = 50` (constante, ajustable) : seuil minimal de paires évaluables.
- `calibrate_confidence(pairs) -> dict` :
  - si `len(pairs) < MIN_PAIRS_CALIBRATION` → `{ "disponible": False, "raison":
    "données insuffisantes", "nb_paires": len(pairs), "seuil": MIN_PAIRS_CALIBRATION }`.
  - sinon → `{ "disponible": True, "mapping": [...] }` où `mapping` = `calibration_bins`
    empirique servant de correspondance confiance→taux réel (proba calibrée par bucket).
- **Non appliquée** cet incrément : la confiance affichée et les poids ne sont pas modifiés.
  C'est un diagnostic exposé, prêt à être branché plus tard (toggle d'un plan futur).

### D. Endpoints

- `POST /courses/{id}/resultats` — capture/rafraîchit l'arrivée (voir §A). 404 course absente ;
  réponse `{ "course_id", "captured": bool, "nb_resultats": int, "statut": "terminee"|"a_venir" }`.
- `GET /backtest` — **lecture seule**, à la demande. Sur toutes les courses ayant à la fois des
  `scores_pronostic` ET des `resultats` : renvoie
  `{ "nb_courses", "precision_top1", "precision_top3", "brier_confiance",
  "calibration": [...bins...], "calibration_gate": {disponible, nb_paires, seuil} }`.
  `nb_courses == 0` → tout à `null`/`[]` + `calibration_gate.disponible=false` (jamais de 500).
- `POST /backtest/snapshot` — calcule l'agrégat et **persiste** une ligne dans
  `backtest_resultats` (`ponderation_config_id` = config active, `periode_debut`/`fin` = min/max
  des dates de réunion couvertes, `nb_courses`, `precision_top1`, `precision_top3`). Renvoie la
  ligne. (GET reste pur ; la persistance est une action explicite.)

### E. Frontend — panneau « Perf » (read-only, discret)

- Nouveau composant `PerfPanel` alimenté par `api.getBacktest()`.
- Placement discret : un panneau repliable / popover accessible depuis la barre supérieure du
  dashboard (n'encombre pas les 3 colonnes). Blanc/vert, cohérent avec l'existant.
- Contenu : `n` courses évaluées, précision top1 / top3 (en %), mini courbe de calibration
  (barres par bucket : hauteur = taux réel, repère = confiance moyenne). Quand
  `nb_courses` est faible / `calibration_gate.disponible == false` → état explicite
  **« données insuffisantes (n/seuil) »** au lieu de chiffres trompeurs.

## Décisions clés (validées)

1. **Boucle de mesure d'abord** (pas de calibration effective maintenant) : la data est trop
   mince ; on construit l'ingestion + l'évaluation + la mécanique de calibration, qui s'affinent
   à mesure que les paires s'accumulent.
2. **Évaluation = scoring déterministe + calibration de la confiance uniquement.** Résolution
   des paris LLM hors périmètre (incrément suivant).
3. **Réutilise les tables existantes** `resultats` et `backtest_resultats` (Plan 1) — aucune
   nouvelle migration de schéma **sauf** si une colonne manque (voir Risques). Pas de nouvelle
   source PMU (l'arrivée vient des participants déjà normalisés).
4. **Ingestion via deux déclencheurs** : auto à l'import si terminée + endpoint de
   rafraîchissement pour backfiller les courses pronostiquées avant la course.
5. **`GET /backtest` lecture seule** ; snapshot persisté via `POST /backtest/snapshot`.
6. **Calibration data-gated** à `MIN_PAIRS_CALIBRATION = 50`, exposée mais non appliquée.
7. **Surface** : backend + petit panneau Perf read-only ; tout gère `n=0` gracieusement.

## Découpage prévisionnel (un seul plan, ~9-10 tâches TDD)

1. Writer `save_resultats` + tests (FakeStore).
2. Câblage auto à l'import (import_course écrit `resultats` si terminée).
3. Endpoint `POST /courses/{id}/resultats` (refresh/backfill) + tests.
4. Module `app/backtest/evaluate.py` (`evaluate_course`, `aggregate`, `calibration_bins`) — pur, TDD.
5. Module `app/backtest/calibration.py` (`calibrate_confidence`, data-gated) — pur, TDD.
6. Endpoints `GET /backtest` + `POST /backtest/snapshot` (assemblage DB → pures) + tests.
7. Frontend : types + `api.getBacktest()` / `api.captureResultats(id)`.
8. Frontend : composant `PerfPanel` + montage discret dans la barre du dashboard.
9. Vérification E2E (contrôleur) : capturer les arrivées des courses déjà pronostiquées
   (backfill réel), `GET /backtest` renvoie précision + gate « insuffisant », panneau affiche
   l'état correct.

## Prérequis & risques

- **Aucune migration a priori** : `resultats` et `backtest_resultats` existent déjà. **Risque à
  vérifier en Task 1** : si un champ manque (p.ex. la date de réunion accessible pour
  `periode_debut/fin`, ou un besoin de stocker la calibration), prévoir une migration `0005`
  minimale appliquée manuellement par l'utilisateur (comme 0001–0004).
- **Disponibilité de l'arrivée PMU** : `position_arrivee` n'est peuplé que sur les courses
  effectivement courues ; le refresh doit gérer proprement « pas encore courue ».
- **Thin data** : tous les agrégats et la calibration renvoient un état « insuffisant » plutôt
  que des chiffres trompeurs ou une erreur. Le panneau Perf le reflète.
- **Vérif E2E navigateur** limitée (pas d'outil de pilotage) — on vérifie au niveau contrat
  HTTP + build, cf. mémoire projet [frontend-e2e-verification].
- **Backfill** : les 12 courses déjà pronostiquées permettent un premier `GET /backtest` non
  vide (mais très en-dessous du seuil de calibration) — utile pour valider la boucle E2E.
