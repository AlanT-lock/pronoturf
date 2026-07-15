from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def test_get_analyse_404_quand_absente():
    store = FakeStore()
    _override(store)
    try:
        assert TestClient(app).get("/courses/course-1/analyse").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_cree_via_repli_sans_cle(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post(
            "/courses/course-1/analyse",
            json={"paris": ["SIMPLE_GAGNANT", "TRIO", "MULTI"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "regles"
        assert body["course_id"] == "course-1"
        codes = [r["type_pari"] for r in body["recommandations"]]
        assert "SIMPLE_GAGNANT" in codes and "TRIO" in codes and "MULTI" not in codes
        assert body["input_snapshot"]["paris"] == ["SIMPLE_GAGNANT", "TRIO", "MULTI"]
        assert len(store.tables["analyses_llm"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_existante_sans_force_ne_rappelle_pas_le_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    store.tables["analyses_llm"].append({
        "id": "a-existante", "course_id": "course-1", "modele": "regles-v1",
        "source": "regles", "recommandations": [], "lecture_globale": "déjà là",
        "coup_de_coeur_value": None, "input_snapshot": {}, "confiance_globale": 50,
        "created_at": "2026-07-14T00:00:00Z",
    })
    _override(store)

    import app.analyse.routes as routes

    def boom(*a, **k):
        raise AssertionError("analyser ne doit PAS être appelé quand une analyse existe")

    monkeypatch.setattr(routes, "analyser", boom)
    try:
        client = TestClient(app)
        resp = client.post("/courses/course-1/analyse", json={"paris": ["SIMPLE_GAGNANT"]})
        assert resp.status_code == 200
        assert resp.json()["id"] == "a-existante"
        # GET renvoie la même
        assert client.get("/courses/course-1/analyse").json()["id"] == "a-existante"
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_force_archive_et_remplace(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    store.tables["analyses_llm"].append({
        "id": "a-vieille", "course_id": "course-1", "modele": "regles-v1",
        "source": "regles", "recommandations": [], "lecture_globale": "ancienne",
        "coup_de_coeur_value": None, "input_snapshot": {}, "confiance_globale": 50,
        "created_at": "2026-07-14T00:00:00Z",
    })
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post(
            "/courses/course-1/analyse?force=true",
            json={"paris": ["SIMPLE_GAGNANT"]},
        )
        assert resp.status_code == 200
        assert len(store.tables["analyses_llm_historique"]) == 1  # ancienne archivée
        assert len(store.tables["analyses_llm"]) == 1              # une seule courante
        assert store.tables["analyses_llm"][0]["id"] != "a-vieille"
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_404_course_absente():
    store = FakeStore()
    _override(store)
    try:
        resp = TestClient(app).post("/courses/inexistante/analyse", json={"paris": []})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
