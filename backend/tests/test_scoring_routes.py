from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def test_score_endpoint_returns_ranked_pronostic():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post("/courses/course-1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["classement"][0]["numero_corde"] == 1  # meilleur profil (cote basse, forme meilleure)
        assert body["classement"][0]["rang"] == 1
        assert store.inserted.get("scores_pronostic")
        assert len(store.tables["scores_pronostic"]) == 2
        assert "confiance" in body["classement"][0]
        assert "nb_courses_historique" in body["classement"][0]
    finally:
        app.dependency_overrides.clear()


def test_score_endpoint_replaces_existing_scores():
    store = FakeStore()
    store.tables["scores_pronostic"].append(
        {"id": "old", "course_id": "course-1", "partant_id": "p1", "ponderation_config_id": "pond-1",
         "score_total": 0.1, "rang_pronostique": 1, "details_facteurs": {}}
    )
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post("/courses/course-1/score")
        assert resp.status_code == 200
        assert "old" not in [r["id"] for r in store.tables["scores_pronostic"]]
        assert len(store.tables["scores_pronostic"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_score_endpoint_404_when_course_missing():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post("/courses/does-not-exist/score")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_course_returns_course_and_partants_with_cote_retenue():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.get("/courses/course-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["course"]["id"] == "course-1"
        partant1 = next(p for p in body["partants"] if p["numero_corde"] == 1)
        assert partant1["cote_retenue"] == 2.0
    finally:
        app.dependency_overrides.clear()


def test_get_course_partants_expose_sexe_from_cheval():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.get("/courses/course-1").json()
        partant1 = next(p for p in body["partants"] if p["numero_corde"] == 1)
        partant2 = next(p for p in body["partants"] if p["numero_corde"] == 2)
        assert partant1["sexe"] == "H"
        assert partant2["sexe"] == "F"
    finally:
        app.dependency_overrides.clear()


def test_get_course_partants_expose_jockey_entraineur():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.get("/courses/course-1").json()
        p1 = next(p for p in body["partants"] if p["numero_corde"] == 1)
        assert p1["jockey_nom"] == "S.PASQUIER"
        assert p1["entraineur_nom"] == "N.CAULLERY"
    finally:
        app.dependency_overrides.clear()


def test_get_course_404_when_missing():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        assert client.get("/courses/does-not-exist").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_course_partants_have_partant_id():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        body = client.get("/courses/course-1").json()
        assert body["partants"], "au moins un partant"
        for p in body["partants"]:
            assert "partant_id" in p and p["partant_id"]
            assert "nom_cheval" in p
    finally:
        app.dependency_overrides.clear()


def test_patch_course_updates_etat_terrain():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.patch("/courses/course-1", json={"etat_terrain": "souple"})
        assert resp.status_code == 200
        assert resp.json()["etat_terrain"] == "souple"
    finally:
        app.dependency_overrides.clear()


def test_patch_partant_updates_fields_and_champs_manuels():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.patch("/partants/p1", json={"ferrage": "DEFERRE_ANTERIEURS"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ferrage"] == "DEFERRE_ANTERIEURS"
        assert "ferrage" in body["champs_manuels"]
    finally:
        app.dependency_overrides.clear()


def test_patch_partant_404_when_missing():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.patch("/partants/does-not-exist", json={"ferrage": "DEFERRE_ANTERIEURS"})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_pronostic_reads_scores_after_scoring():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        client.post("/courses/course-1/score")
        resp = client.get("/courses/course-1/pronostic")
        assert resp.status_code == 200
        body = resp.json()
        assert body["course_id"] == "course-1"
        assert len(body["classement"]) == 2
        rangs = sorted(r["rang"] for r in body["classement"])
        assert rangs == [1, 2]
    finally:
        app.dependency_overrides.clear()


def test_get_pronostic_404_when_course_missing():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        assert client.get("/courses/does-not-exist/pronostic").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_score_response_includes_nom_cheval_and_corde():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        body = client.post("/courses/course-1/score").json()
        top = body["classement"][0]
        assert "nom_cheval" in top and top["nom_cheval"]
        assert "numero_corde" in top
        assert "rang" in top
    finally:
        app.dependency_overrides.clear()


def test_get_pronostic_includes_confiance():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        client.post("/courses/course-1/score")
        body = client.get("/courses/course-1/pronostic").json()
        row = body["classement"][0]
        assert "confiance" in row
        assert "nb_courses_historique" in row
    finally:
        app.dependency_overrides.clear()


def test_pronostic_shape_matches_score_shape():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        client.post("/courses/course-1/score")
        body = client.get("/courses/course-1/pronostic").json()
        row = body["classement"][0]
        assert {"partant_id", "numero_corde", "nom_cheval", "score_total", "rang", "details_facteurs"} <= set(row)
    finally:
        app.dependency_overrides.clear()


def test_score_classement_expose_jockey_entraineur():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.post("/courses/course-1/score").json()
        top = next(r for r in body["classement"] if r["numero_corde"] == 1)
        assert top["jockey_nom"] == "S.PASQUIER"
        assert top["entraineur_nom"] == "N.CAULLERY"
    finally:
        app.dependency_overrides.clear()


def test_score_classement_expose_cote():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.post("/courses/course-1/score").json()
        row1 = next(r for r in body["classement"] if r["numero_corde"] == 1)
        assert row1["cote"] == 2.0
    finally:
        app.dependency_overrides.clear()
