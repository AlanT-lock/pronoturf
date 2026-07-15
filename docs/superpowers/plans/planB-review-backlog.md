# Plan B (analyse IA + persistance) — review backlog

Plan : `docs/superpowers/plans/2026-07-14-pronoturf-plateforme-plan-b.md`
Branche : `feat/plateforme-plan-b-analyse-ia` (base `198a40e`).
Final review : Opus, `198a40e..e07ec22` (9 commits) — verdict « Ready to merge: with fixes », zéro Important.

## Critical — CORRIGÉ

- **C1 — `cote` n'atteignait pas `build_signals`** (`backend/app/scoring/routes.py::score_and_persist`).
  Les lignes enrichies portaient `nom_cheval`/`jockey_nom`/`entraineur_nom` mais pas `cote` ;
  `build_signals` lisait donc `cote=None` pour tous les chevaux → `value`/`proba_implicite_cote`
  et `coup_de_coeur_value` toujours `None`, dimension « value bet » morte, `input_snapshot`
  persisté dégradé (HTTP 200, aucun crash — d'où l'invisibilité : les tests unitaires signals/llm
  injectaient `cote`/`value` dans des dicts fabriqués à la main).
  **Fix (commit `60a342d`)** : `cote_map = _retained_cotes_par_partant(client, ...)` (réutilise le
  helper existant, batché) + `"cote": cote_map.get(...)` par ligne. Chemin de persistance inchangé.
  2 tests de non-régression ajoutés (lignes du classement portent `cote` ; le repli d'analyse
  produit un `coup_de_coeur_value` non-null + `value`/`proba_implicite_cote` non-null dans
  `input_snapshot`), tous deux vérifiés rouge-sans-fix / vert-avec-fix. Suite complète 113/113.

## Minor — DEFER (triés au final review)

1. `signals.softmax` : branche `total<=0` = code mort (inatteignable, `exp(x−max)∈(0,1]`). Inoffensif.
2. `signals.build_signals` : `details_facteurs` passé par référence superficielle. Aucun mutateur en aval (classement reconstruit par requête, lu/sérialisé seulement). Pas de risque d'aliasing.
3. `llm.analyser` : `paris_analysables` calculé avant le court-circuit `ANTHROPIC_API_KEY`. Une compréhension de liste triviale.
4. `llm.analyser` : `except Exception` large sans log. **Repli silencieux = design voulu**, mais ajouter un `logger.warning` (pas un `raise`) rendrait les échecs LLM observables une fois la clé en place — **follow-up recommandé** (couvre aussi les erreurs de mapping post-`parse`).
5. `main.py` : import du routeur analyse casse l'ordre alphabétique. Cosmétique, aucun linter configuré dans le repo.

## Non vérifiable sans infra live (attendu)

- Vrai appel Opus 4.8 via `messages.parse` (pas de `ANTHROPIC_API_KEY` — chemin exercé seulement via fakes/monkeypatch). Décision de session : build sans clé.
- Round-trip Supabase réel + `insert().execute().data[0]` renvoyant `id`/`created_at` par défauts DB.
- Migration `0004` appliquée sur un vrai Postgres (`unique(course_id)`, FK `courses`).
