# Plan C (boucle de mesure) — review backlog

Plan : `docs/superpowers/plans/2026-07-15-pronoturf-plan-c-backtest.md`
Branche : `feat/plan-c-backtest` (base `ef2ea3b`).
Final review : Opus, `ef2ea3b..fe59419` (9 commits) — verdict « Ready to merge: YES », zéro Critical, zéro Important.

## Important — CORRIGÉ pendant l'exécution

- **Période du snapshot** calculée sur toutes les courses *scorées*, pas les *couvertes* (pronostic ET résultat) → une course scorée-mais-non-résultée pouvait élargir `periode_debut`/`periode_fin`. **Fix `a765013`** : `course_ids = scored ∩ resulted` (`resultats.course_id` avec `position_arrivee` non-null). Test de régression (course-2 scorée non-résultée au 2026-08-01 n'élargit pas la période) vérifié rouge-sans-fix / vert-avec. Confirmé aussi en E2E live (période 2026-07-12→14, la course 15/07 pending exclue).

## Minor — DEFER (triés au final review)

1. `evaluate.calibration_bins` : bornes de bucket `i/n_bins` (float). Correct pour `n_bins=5` (garde `conf==1.0` via dernier bucket inclusif) ; fragilité latente uniquement si `n_bins` change → passer à des bornes entières + test à ce moment-là.
2. `evaluate_course` : comportement en cas d'**égalité** non défini (deux `rang==1`, ou deux `position==1`) → `next()` prend le premier. Le brief ne le spécifie pas ; rare à la position 1. À documenter si l'incrément « résolution des paris » en a besoin.
3. `GET /backtest` expose les bins `calibration` bruts même quand `calibration_gate.disponible == false`. Le `PerfPanel` masque la courbe tant que `disponible` est faux → jamais affichée. Inoffensif ; optionnellement blanchir côté serveur plus tard.
4. `post_backtest_snapshot` re-requête `scores_pronostic` (déjà chargé dans `_evaluations`). Round-trip en trop, action rare → pur confort.
5. `_pairs` : hint de retour `list[tuple]` plus lâche que `list[tuple[float, bool]]`. Trivial.

## Nouvelles observations (final review) — DEFER

6. `capture_resultats` peut **500** si la course a disparu du programme PMU (dates trop anciennes) : `find_course_in_programme` lève `ValueError` et `raw_participants["participants"]` peut KeyError. **Même pattern non gardé que l'`import_course` existant → pas une régression.** Le backfill de vieilles courses (l'usage visé) est justement là où la purge PMU mord. Forward-looking : envelopper le bloc PMU/normalize et renvoyer 502 « indisponible amont » plutôt que 500.
7. Écart sémantique période vs `nb_courses` : `resulted` accepte toute `position_arrivee` non-null alors que `nb_courses` exige un gagnant (`position==1`). Une course résultée-sans-gagnant (tous DNF/DSQ) pourrait nudger la période sans compter dans `nb_courses`. Satisfait la contrainte littérale « scored AND resulted » et les courses évaluables restent dans l'intervalle. Cosmétique.

## Vérifié en E2E live (Task 9)

Backfill réel (PMU + Supabase) : 12 courses → 11 arrivées capturées (111 lignes `resultats`), 1 a_venir. `GET /backtest` : nb_courses=11, précision top1=0.36, top3=0.55, Brier=0.37, `calibration_gate {disponible:false, nb_paires:7, seuil:50}`. `POST /backtest/snapshot` : ligne persistée, période 2026-07-12→14. Suite 133/133.
