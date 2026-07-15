import app.backtest.routes as br
from fastapi.testclient import TestClient
from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


class _Course:
    def __init__(self, statut):
        self.statut = statut


def test_post_resultats_capture_si_course_courue(monkeypatch):
    store = FakeStore()
    _override(store)

    async def fake_prog(date):
        assert date == "13072026"  # reunion date 2026-07-13 -> JJMMAAAA
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(br, "fetch_programme", fake_prog)
    monkeypatch.setattr(br, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(br, "normalize_course", lambda *a, **k: _Course("terminee"))

    async def fake_part(date, r, c):
        return {"participants": []}

    monkeypatch.setattr(br, "fetch_participants", fake_part)

    class P:
        def __init__(self, corde, pos):
            self.numero_corde = corde
            self.position_arrivee = pos

    monkeypatch.setattr(br, "normalize_partants", lambda parts, course_terminee: [P(1, 1), P(2, 2)])
    try:
        r = TestClient(app).post("/courses/course-1/resultats")
        assert r.status_code == 200
        body = r.json()
        assert body["captured"] is True
        assert body["statut"] == "terminee"
        assert body["nb_resultats"] == 2
        assert len(store.tables["resultats"]) == 2  # p1, p2 (cordes 1,2 -> partant_ids)
    finally:
        app.dependency_overrides.clear()


def test_post_resultats_pas_encore_courue(monkeypatch):
    store = FakeStore()
    _override(store)

    async def fake_prog(date):
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(br, "fetch_programme", fake_prog)
    monkeypatch.setattr(br, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(br, "normalize_course", lambda *a, **k: _Course("a_venir"))
    try:
        r = TestClient(app).post("/courses/course-1/resultats")
        assert r.status_code == 200
        body = r.json()
        assert body["captured"] is False and body["statut"] == "a_venir"
        assert body["nb_resultats"] == 0
        assert store.tables["resultats"] == []
    finally:
        app.dependency_overrides.clear()


def _seed_scored_course_with_result(store):
    """La FakeStore a course-1 (p1 corde1, p2 corde2). On ajoute pronostic + arrivée :
    p1 rang1 (corde1), p2 rang2 (corde2) ; arrivée: corde1 gagne (top1_hit=True)."""
    store.tables["scores_pronostic"] = [
        {"id": "s1", "course_id": "course-1", "partant_id": "p1", "ponderation_config_id": "pond-1",
         "score_total": 0.8, "rang_pronostique": 1, "details_facteurs": {}, "confiance": 0.9,
         "nb_courses_historique": 3},
        {"id": "s2", "course_id": "course-1", "partant_id": "p2", "ponderation_config_id": "pond-1",
         "score_total": 0.4, "rang_pronostique": 2, "details_facteurs": {}, "confiance": 0.9,
         "nb_courses_historique": 3},
    ]
    store.tables["resultats"] = [
        {"id": "r1", "course_id": "course-1", "partant_id": "p1", "position_arrivee": 1, "disqualifie": False},
        {"id": "r2", "course_id": "course-1", "partant_id": "p2", "position_arrivee": 2, "disqualifie": False},
    ]


def test_get_backtest_vide_gracieux():
    store = FakeStore()
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["nb_courses"] == 0
        assert body["precision_top1"] is None and body["precision_top3"] is None
        assert body["calibration"] == []
        assert body["calibration_gate"]["disponible"] is False
    finally:
        app.dependency_overrides.clear()


def test_get_backtest_calcule_precision():
    store = FakeStore()
    _seed_scored_course_with_result(store)
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["nb_courses"] == 1
        assert body["precision_top1"] == 1.0  # corde1 (rang1) a gagné
        assert body["precision_top3"] == 1.0
        assert body["calibration_gate"]["disponible"] is False  # 1 < 50
        assert body["calibration_gate"]["nb_paires"] == 1
    finally:
        app.dependency_overrides.clear()


def test_post_backtest_snapshot_persiste():
    store = FakeStore()
    _seed_scored_course_with_result(store)
    _override(store)
    try:
        r = TestClient(app).post("/backtest/snapshot")
        assert r.status_code == 200
        assert len(store.tables["backtest_resultats"]) == 1
        row = store.tables["backtest_resultats"][0]
        assert row["nb_courses"] == 1
        assert row["precision_top1"] == 1.0
        assert row["ponderation_config_id"] == "pond-1"
    finally:
        app.dependency_overrides.clear()


def test_post_resultats_404_course_absente():
    store = FakeStore()
    _override(store)
    try:
        assert TestClient(app).post("/courses/inconnue/resultats").status_code == 404
    finally:
        app.dependency_overrides.clear()
