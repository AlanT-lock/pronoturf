from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def _seed(store):
    """course-1 (p1 corde1, p2 corde2) : arrivée corde1 1er, corde2 2e ;
    analyse llm : SIMPLE_GAGNANT [1] (gagne), SIMPLE_PLACE [2] (2 partants -> top2, gagne)."""
    store.tables["resultats"] = [
        {"id": "r1", "course_id": "course-1", "partant_id": "p1", "position_arrivee": 1, "disqualifie": False},
        {"id": "r2", "course_id": "course-1", "partant_id": "p2", "position_arrivee": 2, "disqualifie": False},
    ]
    store.tables["analyses_llm"] = [
        {"id": "a1", "course_id": "course-1", "modele": "claude-opus-4-8", "source": "llm",
         "recommandations": [
             {"type_pari": "SIMPLE_GAGNANT", "selection": [1], "base": [], "tournant": [],
              "confiance": 70, "niveau": "eleve", "avis": "x"},
             {"type_pari": "SIMPLE_PLACE", "selection": [2], "base": [], "tournant": [],
              "confiance": 60, "niveau": "moyen", "avis": "y"},
         ],
         "lecture_globale": "z", "coup_de_coeur_value": None, "input_snapshot": {},
         "confiance_globale": 65},
    ]


def test_backtest_paris_vide_gracieux():
    store = FakeStore()
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["paris"] == {"nb_analyses_resolues": 0, "par_type": [], "par_niveau": []}
    finally:
        app.dependency_overrides.clear()


def test_backtest_paris_calcule_taux():
    store = FakeStore()
    _seed(store)
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        paris = body["paris"]
        assert paris["nb_analyses_resolues"] == 1
        by_type = {d["type_pari"]: d for d in paris["par_type"]}
        assert by_type["SIMPLE_GAGNANT"]["nb"] == 1 and by_type["SIMPLE_GAGNANT"]["taux_reussite"] == 1.0
        assert by_type["SIMPLE_PLACE"]["taux_reussite"] == 1.0
        by_niv = {d["niveau"]: d for d in paris["par_niveau"]}
        assert by_niv["eleve"]["nb"] == 1 and by_niv["moyen"]["nb"] == 1
    finally:
        app.dependency_overrides.clear()
