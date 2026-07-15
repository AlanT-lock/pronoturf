# Plan D (résolution des paris LLM) — review backlog

Plan : `docs/superpowers/plans/2026-07-15-pronoturf-plan-d-paris-resolution.md`
Branche : `feat/plan-d-paris` (base `e058ad1`).
Final review : Opus, `e058ad1..7744f25` (4 commits) — verdict « Ready to merge: YES », zéro Critical, zéro Important.

## Ce qui a été vérifié en profondeur (RAS)

- **Numérotation `selection` ↔ arrivée** : les deux sont en `numero_corde` (repli : `nums = [c["numero_corde"] …]` ; LLM : présente/retourne `numero_corde`). Aucun décalage de corde.
- Bloc `paris` **additif** ; clés pré-existantes de `GET /backtest` et autres endpoints (`_evaluations`, `_pairs`, `capture_resultats`, `post_backtest_snapshot`) inchangés. Sources `llm` **et** `regles` incluses. Gracieux à `n=0` (HTTP 200). Pas d'injection, pas de div/0, non-partant/sélection courte gardés. Aucune migration, aucune persistance (mesure seulement).
- **E2E live** (Task 5) : analyse réelle Opus 4.8 d'une course résultée → `GET /backtest.paris` : `nb_analyses_resolues=1`, taux par type (SIMPLE_GAGNANT 1.0 — la reco #1 du LLM a réellement gagné cette course, TRIO 0.0) + par niveau. Chaîne complète prouvée. Suite 150/150.

## Minor — DEFER

1. `resoudre_pari` : `places` (et les `def topn`/`pos`) construits même sur le chemin type inconnu (`else: return`). Micro-coût, aucun impact ; « ne devrait pas arriver » (ANALYSABLE couvre les types).
2. `pos(c)` : wrapper d'une ligne utilisé une seule fois (`SIMPLE_GAGNANT`) — pur style, inlinable.
3. **`nb_analyses_resolues` est en réalité un compte de COURSES** (`len(courses_resolues)`) — **intentionnel** (spec §B : « nb de courses analysées ET résultées »), donc conforme. Mais le nom + le libellé FR « analyse(s) résolue(s) » peuvent induire en erreur si une course porte à la fois une analyse `llm` et une `regles` (2 analyses comptées comme 1 course ; leurs recos alimentent toutes deux `par_type`/`par_niveau`, doublant `n` pour cette course). Renommer `nb_courses_resolues` dans une passe future.
4. Course résultée sans gagnant identifiable (`position==1` absent, tous DQ) : exclue du compte et des taux (correct — non résolu → exclu), à noter.
5. `resoudre_pari` : `recommandation["type_pari"]` en accès direct → `KeyError`/500 sur une ligne corrompue. Le modèle Pydantic `Recommandation` rend `type_pari` requis → les lignes persistées l'ont toujours ; risque faible, defer.

## Hors périmètre (rappel spec)

Fidélité PMU complète (ordre exact, règles de placé fines, non-partants, rapports/ROI), persistance de snapshots de paris, filtre par source llm/regles, application (proposer les paris les plus rentables) → plans futurs.
