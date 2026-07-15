import app.main as main


class _Writer:
    """Espionne SupabaseWriter pour vérifier que save_resultats est appelé si terminée."""
    def __init__(self, client):
        self.resultats_calls = []

    def save_course_import(self, course, partants):
        return {"course_id": "c-1", "partant_ids": ["pa-1"],
                "cheval_id_by_corde": {1: "ch-1"}, "partant_id_by_corde": {1: "pa-1"}}

    def save_performances(self, *a, **k):
        return 0

    def save_entraineur_resultats(self, *a, **k):
        return 0

    def save_resultats(self, course_id, partants, partant_id_by_corde):
        self.resultats_calls.append((course_id, partant_id_by_corde))
        return len(partants)


def _patch(monkeypatch, statut):
    from app.models import CourseNormalized  # type import only

    class C:
        statut = None
    course = C()
    course.statut = statut

    async def fake_prog(date):
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    monkeypatch.setattr(main, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(main, "normalize_course", lambda *a, **k: course)

    async def fake_part(*a, **k):
        return {"participants": []}

    monkeypatch.setattr(main, "fetch_participants", fake_part)
    monkeypatch.setattr(main, "normalize_partants", lambda *a, **k: ["p"])

    async def fake_perf(*a, **k):
        return {}

    monkeypatch.setattr(main, "fetch_performances_detaillees", fake_perf)
    monkeypatch.setattr(main, "normalize_performances", lambda *a, **k: {})

    writer = _Writer(None)
    monkeypatch.setattr(main, "SupabaseWriter", lambda client: writer)
    return writer


def test_import_ecrit_resultats_si_course_terminee(monkeypatch):
    from fastapi.testclient import TestClient
    writer = _patch(monkeypatch, "terminee")
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()
    try:
        r = TestClient(main.app).post(
            "/courses/import", json={"date": "15072026", "numero_reunion": 1, "numero_course": 1}
        )
        assert r.status_code == 200
        assert writer.resultats_calls == [("c-1", {1: "pa-1"})]
    finally:
        main.app.dependency_overrides.clear()


def test_import_n_ecrit_pas_resultats_si_a_venir(monkeypatch):
    from fastapi.testclient import TestClient
    writer = _patch(monkeypatch, "a_venir")
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()
    try:
        r = TestClient(main.app).post(
            "/courses/import", json={"date": "15072026", "numero_reunion": 1, "numero_course": 1}
        )
        assert r.status_code == 200
        assert writer.resultats_calls == []
    finally:
        main.app.dependency_overrides.clear()
