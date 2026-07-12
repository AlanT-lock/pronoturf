# Plan 1 — Backlog issu de la revue finale (à traiter en Plan 2+)

Revue finale de branche (Opus) sur `13eecbc..f2d1433`. Verdict : **prêt à merger, aucun problème critique.** Les points ci-dessous sont du durcissement ou des décisions de conception à trancher avant/pendant le Plan 2 — aucun ne casse le chemin nominal (vérifié de bout en bout contre l'API PMU réelle + Supabase réel, 13 tests verts).

## Décisions de conception à trancher (nécessitent un choix explicite)

1. **Sémantique de `cotes` (le plus prioritaire pour le Plan 2).** L'upsert `cotes` n'a pas d'`on_conflict` et la table n'a pas de contrainte unique → chaque import **insère** de nouvelles lignes. Réimporter la même course duplique les cotes. Deux intentions possibles, à choisir :
   - **Time-series de snapshots** (cohérent avec la spec : « cote à H-2h, H-30min, définitive ») → garder l'append-only, mais indexer `(partant_id, type_capture, capture_at)` pour que le Plan 2 puisse requêter « la plus récente ». Le scoring devra faire `distinct on (partant_id, type_capture) order by capture_at desc`.
   - **Une ligne par type de capture** → ajouter `unique(partant_id, type_capture)` + `on_conflict` sur l'upsert.
   Recommandation : time-series (aligné spec), à confirmer.

2. **RLS (le plus gros angle mort sécurité).** Les 11 tables sont créées **sans RLS**, et la spec dit « le frontend lit directement dans Supabase ». Si le frontend Next.js du Plan 2 utilise la clé anon côté client, toutes les lignes sont lisibles/écrivables publiquement. À trancher avant le Plan 2 : soit tout passe par le backend FastAPI (service-role, le frontend n'accède jamais Supabase directement — contredit le « directement » de la spec), soit on active RLS avec des policies de lecture. Réactive aussi l'avertissement « RLS disabled » de l'advisor Supabase.

## Durcissement (à intégrer dans la migration/route du Plan 2)

3. **Pas de gestion d'erreur dans la route** (`main.py`). `find_course_in_programme` (ValueError, course introuvable) et une panne PMU (`httpx.HTTPStatusError`) remontent en HTTP 500 opaque. Ajouter `try/except` → `HTTPException(404)` / `HTTPException(502)`. Faible impact (outil local mono-utilisateur) mais un `numero_reunion`/`numero_course` mal tapé mérite un 404 clair.

4. **Clés PMU obligatoires → KeyError possible sur un cheval non-partant.** `pmu_normalizer.py` lit `raw["numPmu"]`, `raw["nom"]`, `raw["idCheval"]`, `raw["statut"]` sans `.get()`. Un partant malformé (ex : non-partant sans `idCheval`) fait échouer **tout** l'import, et violerait `chevaux.id_pmu NOT NULL`. Guarder / ignorer les participants sans `idCheval`. Non observé sur les vraies courses testées, mais variance réelle non couverte.

5. **`_DISCIPLINE_MAP[...]` est un lookup dur** (`pmu_normalizer.py`) → `KeyError` sur une discipline inconnue (ex : première course d'obstacle, mapping non vérifié). Passer en `.get()` avec `ValueError("discipline inconnue: X")` pour un échec plus informatif. + confirmer le mapping obstacle (OBSTACLE/STEEPLE-CHASE/HAIES/CROSS) dès une vraie course d'obstacle.

6. **Index sur les colonnes FK.** Postgres n'indexe pas les FK automatiquement. Ajouter des index sur `partants.course_id`, `partants.cheval_id`, `cotes.partant_id`, `courses.reunion_id`, `reunions.hippodrome_id`, etc. dans la migration du Plan 2 (utile dès que le Plan 2/4 joint courses→partants→cotes sur beaucoup de courses).

7. **`config.py` instancie `settings = Settings()` à l'import** → importer `app.main` exige `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` dans l'env. Les tests passent uniquement parce qu'un vrai `.env` existe sur la machine ; sur un checkout propre / CI sans `.env`, `pytest` échouerait à la collecte. Envisager des settings lazy ou un `.env` de test pour rendre la suite portable.

## Cosmétique / notes

8. **`position_arrivee`** est normalisé depuis `ordreArrivee` mais jamais persisté (la table `resultats` est prévue pour le Plan 4). Donnée morte sur le modèle pour l'instant — ajouter un commentaire `# persisté en Plan 4` ou retirer le champ jusque-là.

9. **`FakeTable` ignore `on_conflict`** dans les tests → une faute de frappe dans une des 6 chaînes `on_conflict` échapperait à pytest (elles ont été vérifiées à la main contre la migration). C'est aussi pourquoi le point #1 est passé. Ajouter une assertion légère que le double enregistre `on_conflict`.

10. **`capture_at` recalculé par cote** via `datetime.now()` → chaque cote d'un même import a un timestamp légèrement différent. Cosmétique ; calculer une fois par import (aide aussi la requête « plus récente par import » du point #1).

11. **`httpx.AsyncClient` recréé par appel** dans `pmu_client.py`, pas de test du chemin `raise_for_status()`. OK pour des imports d'une course ; à revoir si le backtest du Plan 4 boucle sur beaucoup de courses (coût TLS par requête, pas de retry).

## Note process

Le Plan 1 a été exécuté directement sur `main` (choix explicite de l'utilisateur, OK pour un MVP solo), alors que l'en-tête du plan recommandait un flux branche/worktree.
