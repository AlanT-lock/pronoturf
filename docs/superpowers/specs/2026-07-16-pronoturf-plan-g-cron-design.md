# Design — Plan G : boucle quotidienne automatisée (cron capture + import + score)

Date : 2026-07-16
Statut : validé (brainstorming), en attente de plan.
Réf. : [plan-c-backtest-loop] (calibration data-gated à 50 paires, ~7 aujourd'hui) ;
[vercel-deployment] (backend serverless `pronoturf-api`) ; backlog Plan C (500 sur dates purgées).

## Objectif

Faire grossir la data de mesure **sans action manuelle** : un job quotidien qui (1) capture
les arrivées des courses pronostiquées, (2) importe **et score** toutes les courses du jour,
(3) persiste un snapshot backtest hebdomadaire. Effet attendu : ~40-50 paires
(prédiction, résultat)/jour → **calibration active (seuil 50 paires) en ~2 semaines**,
backtest des poids significatif, stats de paris qui grossissent. **Pas d'analyse LLM
automatique** (coût Opus maîtrisé — elle reste déclenchée par l'utilisateur).

## Décisions (validées)

1. **Boucle complète, toutes les courses du programme** (pas de filtre France/Quinté).
2. **Un seul cron quotidien** — `vercel.json` du backend : `"crons": [{"path": "/cron/daily",
   "schedule": "0 4 * * *"}]` (04:00 UTC ≈ 06h Paris : arrivées de la veille connues,
   programme du jour publié). Compatible plan Hobby (cron quotidien). Vercel Cron invoque en
   **GET**.
3. **Sécurité `CRON_SECRET`** : env var Vercel (secret généré) ; Vercel l'envoie
   automatiquement en `Authorization: Bearer <CRON_SECRET>` sur les invocations cron ; le
   handler renvoie **401** si l'en-tête ne correspond pas. Déclenchable manuellement via curl
   avec le bearer.
4. **Fenêtre de capture 7 jours** : on ne tente la capture que pour les courses non terminées
   dont la réunion date de ≤ 7 jours (au-delà, PMU purge le programme → on arrête de
   réessayer). Toute erreur PMU par course est **absorbée et comptée** (règle le 500 du
   backlog Plan C dans le contexte cron).
5. **Snapshot backtest le dimanche** (jour Europe/Paris) — 1 ligne hebdo dans
   `backtest_resultats` (courbe longitudinale).
6. **Fuseau Europe/Paris** pour « aujourd'hui »/« hier » (journée hippique) — via
   `zoneinfo.ZoneInfo("Europe/Paris")`.
7. **`maxDuration` 60 → 300** (`backend/vercel.json`) : ~50 courses × (3 fetchs PMU + writes
   Supabase + scoring) ≈ 2-3 min. 300s permis sur tous les plans (Fluid Compute).
8. **Idempotence** : import (upserts) et capture (upsert `partant_id`) déjà idempotents ;
   re-runs sûrs. `score_and_persist` remplace (delete+insert) — un re-run rafraîchit le
   pronostic avec les cotes du moment, acceptable.

## Architecture

### A. Refactors préalables (mêmes patterns que `score_and_persist` au Plan B)

- **`app/main.py`** : extraire le corps de `import_course` en helper
  `import_one_course(supabase_client, date_str, numero_reunion, numero_course) -> dict`
  (renvoie `{"course_id", "partant_ids"}`) ; l'endpoint `POST /courses/import` devient un
  wrapper mince. Comportement strictement identique (perfs best-effort, entraineur/resultats
  si terminée).
- **`app/backtest/routes.py`** : extraire le corps de `capture_resultats` en helper
  `capture_one_resultats(client, course_id) -> dict` (renvoie `{"captured", "statut",
  "nb_resultats"}`) ; l'endpoint devient un wrapper. Comportement identique (404 course
  absente reste côté endpoint via `_get_course_or_404`).

### B. Module `app/cron/routes.py` — `GET /cron/daily`

1. **Auth** : lire `settings.cron_secret` (nouveau champ `Settings`, chargé de l'env comme
   les autres) ; comparer à l'en-tête `Authorization` (`Bearer <secret>`,
   `secrets.compare_digest`) ; sinon **401**. Si `cron_secret` non configuré → **503**
   (le job refuse de tourner sans secret ; jamais d'exécution non authentifiée).
2. **Étape capture** : courses en base avec `statut != 'terminee'` et date de réunion dans
   les 7 derniers jours (jointure `courses → reunions.date`) → pour chacune,
   `capture_one_resultats` sous try/except (erreur → `errors[]`, on continue).
3. **Étape import+score du jour** : `fetch_programme(aujourd'hui Paris, JJMMAAAA)` → pour
   chaque réunion/course du programme : `import_one_course` puis `score_and_persist`, chaque
   course sous try/except. Compteurs `imported`/`scored`.
4. **Étape snapshot** : si dimanche (Paris), appeler la logique de
   `post_backtest_snapshot` (tolérer le cas « rien à évaluer » sans erreur).
5. **Réponse** : `{"date": ..., "captured": n, "imported": n, "scored": n,
   "snapshot": bool, "errors": [str, ...]}` (messages d'erreur tronqués, visibles dans les
   logs Vercel).

### C. Config & déploiement

- `Settings.cron_secret: str | None = None` ; env `CRON_SECRET` ajoutée au projet Vercel
  `pronoturf-api` (secret généré, jamais affiché).
- `backend/vercel.json` : bloc `crons` + `maxDuration: 300`.
- Tests : FakeStore + PMU monkeypatché — 401 sans/mauvais bearer, 503 sans secret configuré,
  capture fenêtrée (course vieille de 8 jours ignorée), erreurs par course absorbées,
  compteurs corrects, snapshot uniquement le dimanche (date monkeypatchée).

## Hors périmètre

- Analyse LLM automatique (coût) ; notification/alerting ; sub-daily scheduling ;
  fidélité PMU des paris ; UI (aucun changement de contrat).

## Découpage prévisionnel (~4 tâches TDD)

1. Refactor `import_one_course` + `capture_one_resultats` (wrappers minces, non-régression).
2. `Settings.cron_secret` + module `app/cron/routes.py` (auth + les 3 étapes) + montage
   routeur + tests.
3. `vercel.json` (crons + maxDuration 300).
4. Vérification (contrôleur) : run manuel local (bearer) sur la vraie base → compteurs
   cohérents ; déploiement prod + `CRON_SECRET` en env ; run manuel prod via curl ;
   vérifier l'enregistrement du cron dans Vercel.
