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


def test_post_resultats_404_course_absente():
    store = FakeStore()
    _override(store)
    try:
        assert TestClient(app).post("/courses/inconnue/resultats").status_code == 404
    finally:
        app.dependency_overrides.clear()
