import app.main as main
from fastapi.testclient import TestClient


class RecordingWriter:
    last = None
    def __init__(self, client): RecordingWriter.last = self; self.calls = []
    def save_course_import(self, course, partants):
        self.calls.append("course")
        return {"course_id": "c1", "partant_ids": ["p1"], "cheval_id_by_corde": {1: "ch1"}}
    def save_performances(self, perf, mapping):
        self.calls.append(("perf", len(perf), mapping)); return 1
    def save_entraineur_resultats(self, course, partants, mapping):
        self.calls.append("entraineur"); return 1


PROGRAMME = {"programme": {"reunions": [{
    "numOfficiel": 1, "dateReunion": 1783893600000, "timezoneOffset": 7200000,
    "pays": {"code": "FRA"},
    "hippodrome": {"code": "DIE", "libelleCourt": "DIEPPE"},
    "courses": [{"numOrdre": 1, "discipline": "PLAT", "distance": 1400,
                 "montantPrix": 20100, "heureDepart": 1783893600000,
                 "categorieParticularite": None}],
}]}}
PARTICIPANTS = {"participants": [{"numPmu": 1, "nom": "H1", "idCheval": "H1-a-b",
    "statut": "PARTANT", "placeCorde": 8}]}
PERF = {"participants": [{"numPmu": 1, "nomCheval": "H1", "coursesCourues": []}]}


def _setup(monkeypatch, perf_ok=True):
    async def fake_prog(date): return PROGRAMME
    async def fake_part(d, r, c): return PARTICIPANTS
    async def fake_perf(d, r, c):
        if not perf_ok: raise RuntimeError("PMU down")
        return PERF
    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    monkeypatch.setattr(main, "fetch_participants", fake_part)
    monkeypatch.setattr(main, "fetch_performances_detaillees", fake_perf)
    monkeypatch.setattr(main, "SupabaseWriter", RecordingWriter)
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()


def test_import_persists_history(monkeypatch):
    _setup(monkeypatch)
    try:
        r = TestClient(main.app).post("/courses/import",
            json={"date": "13072026", "numero_reunion": 1, "numero_course": 1})
        assert r.status_code == 200
        assert r.json()["course_id"] == "c1"
        calls = RecordingWriter.last.calls
        assert "course" in calls
        assert any(isinstance(c, tuple) and c[0] == "perf" for c in calls)
    finally:
        main.app.dependency_overrides.clear()


def test_import_survives_history_endpoint_failure(monkeypatch):
    _setup(monkeypatch, perf_ok=False)
    try:
        r = TestClient(main.app).post("/courses/import",
            json={"date": "13072026", "numero_reunion": 1, "numero_course": 1})
        assert r.status_code == 200          # import réussit malgré l'échec historique
        calls = RecordingWriter.last.calls
        assert "course" in calls
        assert not any(isinstance(c, tuple) and c[0] == "perf" for c in calls)
    finally:
        main.app.dependency_overrides.clear()
