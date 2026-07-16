# Plan G — boucle quotidienne automatisée (cron) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un `GET /cron/daily` sécurisé (`CRON_SECRET`), déclenché chaque matin par Vercel Cron, qui capture les arrivées (fenêtre 7 jours), importe + score toutes les courses du jour, et snapshot le backtest le dimanche — pour que la data de mesure grossisse sans action manuelle.

**Architecture:** Deux refactors (extraire `import_one_course` dans `main.py` et `capture_one_resultats` dans `backtest/routes.py`, endpoints = wrappers minces, pattern `score_and_persist`) ; nouveau module `app/cron/routes.py` (auth Bearer + 3 étapes, try/except par course) ; `Settings.cron_secret` ; `vercel.json` (bloc `crons` + `maxDuration` 300). Pas de LLM. Pur backend.

**Tech Stack :** FastAPI + pytest (FakeStore/monkeypatch) ; Vercel Cron.

**Réf. spec :** `docs/superpowers/specs/2026-07-16-pronoturf-plan-g-cron-design.md`.

## Global Constraints

- **Auth** : 401 si `Authorization` absent/différent de `Bearer <CRON_SECRET>` (`secrets.compare_digest`) ; **503 si `cron_secret` non configuré** (jamais d'exécution non authentifiée).
- **Try/except PAR COURSE** dans les étapes capture et import+score : une erreur est ajoutée à `errors[]` (message tronqué à ~80 car.) et le run continue. Le fetch du programme entier a son propre try/except.
- **Fenêtre capture 7 jours** (date de réunion ≥ aujourd'hui-7, fuseau Europe/Paris) ; capture AVANT import (les imports du jour, `a_venir`, ne sont pas tentés en capture).
- **Fuseau Europe/Paris** via un helper module-level `_today_paris()` (monkeypatchable en test). Snapshot si `weekday() == 6` (dimanche).
- **Contrainte FakeStore** : pas de `.neq()` — sélectionner toutes les courses puis filtrer `statut != "terminee"` en Python. Jointure dates via `.in_()` (supporté).
- **Cycle d'import** : `app/main.py` inclut le routeur cron → le cron ne peut PAS importer `import_one_course` au niveau module ; **import tardif dans le handler** (`from app.main import import_one_course`), commenté.
- **Monkeypatch préservé** : `import_one_course` reste dans `app/main.py` et utilise les noms module-level de `main` (`fetch_programme`, `SupabaseWriter`…) → les tests existants qui patchent `main.*` restent verts sans modification.
- Réponse : `{"date", "captured", "imported", "scored", "snapshot", "errors"}`.
- Gate : `cd backend && .venv/bin/pytest` — toute la suite verte (157 avant plan). TDD strict.
- Cron Vercel : GET, `"0 4 * * *"` (~06h Paris). `maxDuration` 60 → **300**.

## Structure des fichiers

- `backend/app/main.py` — **modifier** : extraire `import_one_course`, monter le routeur cron.
- `backend/app/backtest/routes.py` — **modifier** : extraire `capture_one_resultats`.
- `backend/app/config.py` — **modifier** : `cron_secret`.
- `backend/app/cron/__init__.py`, `backend/app/cron/routes.py` — **créer**.
- `backend/vercel.json` — **modifier** : `crons` + `maxDuration` 300.
- `backend/tests/test_cron_routes.py` — **créer**.

---

### Task 1: Refactors `import_one_course` + `capture_one_resultats`

**Files:**
- Modify: `backend/app/main.py`, `backend/app/backtest/routes.py`

**Interfaces:**
- Produces : `app.main.import_one_course(supabase_client, date_str, numero_reunion, numero_course) -> dict` (`{"course_id", "partant_ids"}`) ; `app.backtest.routes.capture_one_resultats(client, course_id) -> dict` (`{"course_id", "captured", "statut", "nb_resultats"}`, lève `HTTPException(404)` si course absente). Consommés par Task 2.
- **Refactor pur** : aucun nouveau test ici ; la non-régression EST le test (les suites `test_import_*` et `test_backtest_routes*` patchent `main.*`/`br.*` et doivent rester vertes sans modification).

- [ ] **Step 1: `main.py` — extraire le helper**

Remplacer le bloc endpoint `import_course` (de `@app.post("/courses/import")` à son `return`) par :

```python
async def import_one_course(supabase_client, date_str: str, numero_reunion: int, numero_course: int) -> dict:
    """Importe une course (programme+participants+historique) ; réutilisé par l'endpoint et le cron."""
    programme = await fetch_programme(date_str)
    raw_reunion, raw_course = find_course_in_programme(programme, numero_reunion, numero_course)
    course = normalize_course(raw_reunion, raw_course)

    raw_participants = await fetch_participants(date_str, numero_reunion, numero_course)
    partants = normalize_partants(raw_participants["participants"], course_terminee=course.statut == "terminee")

    writer = SupabaseWriter(supabase_client)
    result = writer.save_course_import(course, partants)

    try:
        raw_perf = await fetch_performances_detaillees(date_str, numero_reunion, numero_course)
        perf_by_num_pmu = normalize_performances(raw_perf)
        writer.save_performances(perf_by_num_pmu, result["cheval_id_by_corde"])
    except Exception:
        # Historique indisponible : l'import reste valide, facteurs contextuels neutres au score.
        pass

    if course.statut == "terminee":
        writer.save_entraineur_resultats(course, partants, result["cheval_id_by_corde"])
        writer.save_resultats(result["course_id"], partants, result["partant_id_by_corde"])

    return {"course_id": result["course_id"], "partant_ids": result["partant_ids"]}


@app.post("/courses/import")
async def import_course(request: ImportCourseRequest, supabase_client=Depends(get_supabase_client)) -> dict:
    return await import_one_course(supabase_client, request.date, request.numero_reunion, request.numero_course)
```

(Attention : `import_one_course` référence les noms module-level de `main` — c'est voulu, les tests monkeypatchent `main.fetch_programme`/`main.SupabaseWriter` etc.)

- [ ] **Step 2: `backtest/routes.py` — extraire le helper**

Remplacer le bloc endpoint `capture_resultats` par :

```python
async def capture_one_resultats(client, course_id: str) -> dict:
    """Capture l'arrivée réelle d'une course (re-fetch PMU) ; réutilisé par l'endpoint et le cron."""
    course = _get_course_or_404(client, course_id)
    reunion = _reunion_of(client, course)
    ddmmyyyy = _date.fromisoformat(reunion["date"]).strftime("%d%m%Y")

    programme = await fetch_programme(ddmmyyyy)
    raw_reunion, raw_course = find_course_in_programme(
        programme, reunion["numero_reunion"], course["numero_course"]
    )
    course_norm = normalize_course(raw_reunion, raw_course)
    if course_norm.statut != "terminee":
        return {"course_id": course_id, "captured": False,
                "statut": course_norm.statut, "nb_resultats": 0}

    raw_participants = await fetch_participants(
        ddmmyyyy, reunion["numero_reunion"], course["numero_course"]
    )
    partants = normalize_partants(raw_participants["participants"], course_terminee=True)

    existing = (
        client.table("partants").select("id, numero_corde").eq("course_id", course_id).execute().data
    )
    partant_id_by_corde = {p["numero_corde"]: p["id"] for p in existing}

    n = SupabaseWriter(client).save_resultats(course_id, partants, partant_id_by_corde)
    client.table("courses").update({"statut": "terminee"}).eq("id", course_id).execute()
    return {"course_id": course_id, "captured": True, "statut": "terminee", "nb_resultats": n}


@router.post("/courses/{course_id}/resultats")
async def capture_resultats(course_id: str, client=Depends(get_supabase_client)) -> dict:
    return await capture_one_resultats(client, course_id)
```

(Les tests patchent `br.fetch_programme` etc. — noms module-level inchangés → verts sans modification.)

- [ ] **Step 3: Non-régression**

Run: `cd backend && .venv/bin/pytest tests/test_import_route.py tests/test_import_resultats.py tests/test_import_history.py tests/test_backtest_routes.py -q`
Expected: PASS (identique à avant). Puis `cd backend && .venv/bin/pytest -q` → 157 verts.

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/main.py backend/app/backtest/routes.py
git commit -m "refactor(backend): import_one_course + capture_one_resultats reutilisables (wrappers minces)"
```

---

### Task 2: `Settings.cron_secret` + module cron + tests

**Files:**
- Create: `backend/app/cron/__init__.py`, `backend/app/cron/routes.py`
- Modify: `backend/app/config.py`, `backend/app/main.py`
- Test: `backend/tests/test_cron_routes.py`

**Interfaces:**
- Consumes : `import_one_course` (import tardif), `capture_one_resultats`, `score_and_persist`, `post_backtest_snapshot`, `fetch_programme`/`normalize_programme`, `settings`.
- Produces : `GET /cron/daily` (contrat de réponse cf. Global Constraints) ; `_today_paris()` monkeypatchable.

- [ ] **Step 1: Écrire les tests rouges**

Create `backend/tests/test_cron_routes.py` :

```python
from datetime import date

import app.cron.routes as cr
from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore

BEARER = {"Authorization": "Bearer test-secret"}


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def _setup(monkeypatch, store, today=date(2026, 7, 16), programme=None):
    _override(store)
    monkeypatch.setattr(cr.settings, "cron_secret", "test-secret")
    monkeypatch.setattr(cr, "_today_paris", lambda: today)

    async def fake_prog(d):
        return programme if programme is not None else {"programme": {"reunions": []}}

    monkeypatch.setattr(cr, "fetch_programme", fake_prog)


def test_cron_503_sans_secret_configure(monkeypatch):
    store = FakeStore()
    _override(store)
    monkeypatch.setattr(cr.settings, "cron_secret", None)
    try:
        assert TestClient(app).get("/cron/daily", headers=BEARER).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_cron_401_sans_ou_mauvais_bearer(monkeypatch):
    store = FakeStore()
    _setup(monkeypatch, store)
    try:
        client = TestClient(app)
        assert client.get("/cron/daily").status_code == 401
        assert client.get("/cron/daily", headers={"Authorization": "Bearer faux"}).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_cron_capture_fenetre_7_jours(monkeypatch):
    store = FakeStore()
    # course-1 (reunion r1 datée 2026-07-13, statut terminee dans la FakeStore -> ignorée) ;
    # on ajoute une non-terminée récente et une non-terminée trop vieille.
    store.tables["reunions"].append({"id": "r-old", "hippodrome_id": "h1", "date": "2026-07-01", "numero_reunion": 9})
    store.tables["courses"][0]["statut"] = "a_venir"  # course-1 (r1: 2026-07-13, dans la fenêtre)
    store.tables["courses"].append({"id": "course-old", "numero_course": 1, "discipline": "plat",
                                    "statut": "a_venir", "distance_m": 1200, "reunion_id": "r-old",
                                    "etat_terrain": None, "allocation": 1000})
    _setup(monkeypatch, store, today=date(2026, 7, 16))

    tried = []

    async def fake_capture(client, course_id):
        tried.append(course_id)
        return {"course_id": course_id, "captured": True, "statut": "terminee", "nb_resultats": 2}

    monkeypatch.setattr(cr, "capture_one_resultats", fake_capture)
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert tried == ["course-1"]           # course-old (15 jours) exclue de la fenêtre
        assert body["captured"] == 1
        assert body["errors"] == []
    finally:
        app.dependency_overrides.clear()


def test_cron_import_score_du_jour_et_erreurs_absorbees(monkeypatch):
    store = FakeStore()
    programme = {"programme": {"reunions": [
        {"numOfficiel": 1, "pays": {"code": "FRA"},
         "hippodrome": {"code": "X", "libelleCourt": "TEST"},
         "courses": [
             {"numOrdre": 1, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
             {"numOrdre": 2, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
         ]},
    ]}}
    _setup(monkeypatch, store, programme=programme)

    async def fake_import(client, d, r, c):
        if c == 2:
            raise RuntimeError("PMU en rade")
        return {"course_id": "course-1", "partant_ids": []}

    import app.main as main
    monkeypatch.setattr(main, "import_one_course", fake_import)
    monkeypatch.setattr(cr, "score_and_persist", lambda client, cid: [])
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert body["imported"] == 1 and body["scored"] == 1
        assert len(body["errors"]) == 1 and "R1C2" in body["errors"][0]
    finally:
        app.dependency_overrides.clear()


def test_cron_snapshot_le_dimanche_seulement(monkeypatch):
    store = FakeStore()
    _setup(monkeypatch, store, today=date(2026, 7, 19))  # un dimanche
    called = []
    monkeypatch.setattr(cr, "post_backtest_snapshot", lambda client: called.append(1))
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert body["snapshot"] is True and called == [1]
    finally:
        app.dependency_overrides.clear()

    store2 = FakeStore()
    _setup(monkeypatch, store2, today=date(2026, 7, 16))  # un jeudi
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert body["snapshot"] is False
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_cron_routes.py -q`
Expected: FAIL (module `app.cron.routes` absent).

- [ ] **Step 3: Implémenter**

`backend/app/config.py` — ajouter au modèle `Settings` (après `cors_origins`) :

```python
    # Secret du cron quotidien (Vercel Cron l'envoie en Authorization: Bearer).
    cron_secret: str | None = None
```

Create `backend/app/cron/__init__.py` (vide) et `backend/app/cron/routes.py` :

```python
"""Job quotidien : capture des arrivées + import/score du jour + snapshot hebdo.

Déclenché par Vercel Cron (GET /cron/daily, Authorization: Bearer CRON_SECRET).
Chaque course est traitée sous try/except : une erreur PMU (course purgée, réseau)
est comptée dans `errors`, jamais fatale au run.
"""

import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException

from app.backtest.routes import capture_one_resultats, post_backtest_snapshot
from app.config import settings
from app.pmu_client import fetch_programme
from app.pmu_normalizer import normalize_programme
from app.scoring.routes import score_and_persist
from app.supabase_client import get_supabase_client

router = APIRouter()

CAPTURE_WINDOW_DAYS = 7


def _today_paris() -> date:
    """Journée hippique courante (les courses vont jusqu'à ~minuit heure de Paris)."""
    return datetime.now(ZoneInfo("Europe/Paris")).date()


@router.get("/cron/daily")
async def cron_daily(
    client=Depends(get_supabase_client),
    authorization: str | None = Header(None),
) -> dict:
    if not settings.cron_secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET non configuré")
    if not authorization or not secrets.compare_digest(
        authorization, f"Bearer {settings.cron_secret}"
    ):
        raise HTTPException(status_code=401, detail="Non autorisé")

    today = _today_paris()
    errors: list[str] = []

    # --- 1) Capture des arrivées des courses non terminées (fenêtre 7 jours). ---
    captured = 0
    courses = client.table("courses").select("id, reunion_id, numero_course, statut").execute().data
    pending = [c for c in courses if c.get("statut") != "terminee"]  # FakeStore: pas de .neq()
    dates_by_reunion: dict[str, str] = {}
    reunion_ids = list({c["reunion_id"] for c in pending})
    if reunion_ids:
        for r in client.table("reunions").select("id, date").in_("id", reunion_ids).execute().data:
            dates_by_reunion[r["id"]] = r["date"]
    cutoff = today - timedelta(days=CAPTURE_WINDOW_DAYS)
    for c in pending:
        d = dates_by_reunion.get(c["reunion_id"])
        if d is None or date.fromisoformat(d) < cutoff:
            continue  # PMU purge les vieux programmes : on arrête de réessayer
        try:
            out = await capture_one_resultats(client, c["id"])
            if out.get("captured"):
                captured += 1
        except Exception as e:
            errors.append(f"capture {c['id'][:8]}: {str(e)[:80]}")

    # --- 2) Import + score de toutes les courses du jour (pas d'analyse LLM : coût). ---
    # Import tardif : app.main inclut ce routeur, un import module-level créerait un cycle.
    from app.main import import_one_course

    imported = scored = 0
    ddmmyyyy = today.strftime("%d%m%Y")
    try:
        programme = normalize_programme(await fetch_programme(ddmmyyyy))
        for reunion in programme["reunions"]:
            for course in reunion["courses"]:
                label = f"R{reunion['numero_reunion']}C{course['numero_course']}"
                try:
                    res = await import_one_course(
                        client, ddmmyyyy, reunion["numero_reunion"], course["numero_course"]
                    )
                    imported += 1
                    score_and_persist(client, res["course_id"])
                    scored += 1
                except Exception as e:
                    errors.append(f"{label}: {str(e)[:80]}")
    except Exception as e:
        errors.append(f"programme: {str(e)[:80]}")

    # --- 3) Snapshot backtest hebdomadaire (dimanche). ---
    snapshot = False
    if today.weekday() == 6:
        try:
            post_backtest_snapshot(client)
            snapshot = True
        except HTTPException:
            pass  # rien à évaluer -> pas un échec du cron
        except Exception as e:
            errors.append(f"snapshot: {str(e)[:80]}")

    return {"date": today.isoformat(), "captured": captured, "imported": imported,
            "scored": scored, "snapshot": snapshot, "errors": errors}
```

**Piège d'implémentation** : dans l'étape 2, appeler `import_one_course` via le module pour que le monkeypatch des tests s'applique — soit `import app.main as main_mod` tardif puis `main_mod.import_one_course(...)`, soit exactement comme ci-dessus MAIS alors le test patch `main.import_one_course` **avant** l'appel HTTP et le binding tardif le récupère (c'est le cas : l'import est dans le corps du handler, exécuté à chaque requête). Garder l'import tardif **dans le handler**.

`backend/app/main.py` — monter le routeur : ajouter `from app.cron.routes import router as cron_router` (après l'import backtest) et `app.include_router(cron_router)` (après les autres).

- [ ] **Step 4: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_cron_routes.py -q` → PASS (5 tests).
Run: `cd backend && .venv/bin/pytest -q` → toute la suite verte (~162).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/config.py backend/app/cron backend/app/main.py backend/tests/test_cron_routes.py
git commit -m "feat(cron): GET /cron/daily (capture 7j + import/score du jour + snapshot dominical)"
```

---

### Task 3: `vercel.json` (cron + maxDuration 300)

**Files:**
- Modify: `backend/vercel.json`

- [ ] **Step 1: Mettre à jour la config**

Remplacer le contenu de `backend/vercel.json` par :

```json
{
  "functions": {
    "api/index.py": {
      "maxDuration": 300
    }
  },
  "crons": [
    { "path": "/cron/daily", "schedule": "0 4 * * *" }
  ],
  "rewrites": [
    { "source": "/(.*)", "destination": "/api/index" }
  ]
}
```

- [ ] **Step 2: Sanity + commit**

Run: `cd backend && .venv/bin/python -c "import json; json.load(open('vercel.json')); print('json ok')"`

```bash
cd /Users/alantouati/pronoturf
git add backend/vercel.json
git commit -m "chore(deploy): cron quotidien 04:00 UTC + maxDuration 300"
```

---

### Task 4: Vérification + déploiement (contrôleur)

**Files:** aucun.

- [ ] **Step 1: Run manuel local (vraie base)** — exporter un `CRON_SECRET` de test local (env du process), lancer le handler via TestClient avec le bearer → vérifier le récap (`captured`/`imported`/`scored` cohérents avec le programme du jour, `errors` peu nombreux et explicables). NB : ce run importe + score réellement les ~40-50 courses du jour dans Supabase (c'est le but).
- [ ] **Step 2: Secret prod** — générer un secret fort (`openssl rand -hex 32`), l'ajouter en env `CRON_SECRET` production du projet Vercel `pronoturf-api` (sans l'afficher).
- [ ] **Step 3: Déployer** — merge dans `main`, push, `cd backend && vercel deploy --prod`. Vérifier `/health`, puis un **run manuel prod** : `curl -H "Authorization: Bearer $CRON_SECRET" https://pronoturf-api.vercel.app/cron/daily` → 200 + récap (rapide car le run local a déjà tout importé — idempotent). Vérifier 401 sans bearer.
- [ ] **Step 4: Cron enregistré** — `vercel crons ls` (ou l'inspect du déploiement) montre `/cron/daily @ 0 4 * * *`. Noter dans le ledger que le premier run automatique aura lieu le lendemain ~06h Paris (à vérifier dans les logs Vercel).

---

## Ce que ce plan produit

Chaque matin, sans intervention : les arrivées de la veille sont capturées, toutes les courses du jour sont importées et pronostiquées (sans coût LLM), et le dimanche un snapshot fige les métriques. ~40-50 paires (prédiction, résultat)/jour → calibration active (seuil 50) en ~2 semaines, backtest des poids exploitable, stats de paris qui grossissent.

## Hors périmètre

- Analyse LLM automatique, alerting/notifications, scheduling sub-quotidien, UI.
