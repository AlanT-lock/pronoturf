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


def test_cron_import_concurrent_compte_toutes_les_courses(monkeypatch):
    store = FakeStore()
    programme = {"programme": {"reunions": [
        {"numOfficiel": 1, "pays": {"code": "FRA"},
         "hippodrome": {"code": "X", "libelleCourt": "TEST"},
         "courses": [
             {"numOrdre": 1, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
             {"numOrdre": 2, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
             {"numOrdre": 3, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
         ]},
    ]}}
    _setup(monkeypatch, store, programme=programme)

    async def fake_import(client, d, r, c):
        return {"course_id": f"course-{c}", "partant_ids": []}

    import app.main as main
    monkeypatch.setattr(main, "import_one_course", fake_import)
    monkeypatch.setattr(cr, "score_and_persist", lambda client, cid: [])
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert body["imported"] == 3 and body["scored"] == 3
        assert body["errors"] == []
    finally:
        app.dependency_overrides.clear()


def test_cron_score_echoue_apres_import_reussi(monkeypatch):
    store = FakeStore()
    programme = {"programme": {"reunions": [
        {"numOfficiel": 1, "pays": {"code": "FRA"},
         "hippodrome": {"code": "X", "libelleCourt": "TEST"},
         "courses": [
             {"numOrdre": 1, "discipline": "PLAT", "distance": 1200, "montantPrix": 1000,
              "heureDepart": 1784264400000, "nombreDeclaresPartants": 5, "paris": []},
         ]},
    ]}}
    _setup(monkeypatch, store, programme=programme)

    async def fake_import(client, d, r, c):
        return {"course_id": "course-1", "partant_ids": []}

    import app.main as main
    monkeypatch.setattr(main, "import_one_course", fake_import)

    def boom(client, cid):
        raise RuntimeError("scoring KO")

    monkeypatch.setattr(cr, "score_and_persist", boom)
    try:
        body = TestClient(app).get("/cron/daily", headers=BEARER).json()
        assert body["imported"] == 1 and body["scored"] == 0
        assert len(body["errors"]) == 1 and "R1C1" in body["errors"][0]
    finally:
        app.dependency_overrides.clear()


def test_cron_panne_capture_setup_n_abort_pas_le_run(monkeypatch):
    store = FakeStore()
    _setup(monkeypatch, store)

    class BoomClient(FakeClient):
        def table(self, name):
            if name == "courses":
                raise RuntimeError("supabase KO")
            return super().table(name)

    app.dependency_overrides[get_supabase_client] = lambda: BoomClient(store)
    try:
        resp = TestClient(app).get("/cron/daily", headers=BEARER)
        assert resp.status_code == 200  # pas de 500
        body = resp.json()
        assert any("capture-setup" in e for e in body["errors"])
        assert body["imported"] == 0  # programme vide dans _setup -> 0, mais l'étape a tourné
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
