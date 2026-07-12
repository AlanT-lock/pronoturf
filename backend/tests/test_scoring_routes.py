from fastapi.testclient import TestClient

from app.main import app
from app.scoring.ponderations import DEFAULT_PONDERATIONS
from app.supabase_client import get_supabase_client


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """Mimics the tiny subset of supabase-py's fluent query builder used by routes.py."""

    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._filters: dict = {}
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        return self

    def execute(self):
        if self._op == "select":
            return FakeResult(self._store.select(self._name, self._filters))
        if self._op == "update":
            return FakeResult(self._store.update(self._name, self._filters, self._payload))
        if self._op == "delete":
            return FakeResult(self._store.delete(self._name, self._filters))
        if self._op in ("insert", "upsert"):
            return FakeResult(self._store.insert(self._name, self._payload))
        raise AssertionError(f"unsupported op {self._op}")


class FakeStore:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {
            "courses": [
                {
                    "id": "course-1", "numero_course": 1, "discipline": "plat", "statut": "terminee",
                    "distance_m": 1200, "reunion_id": "r1", "etat_terrain": None,
                },
            ],
            "partants": [
                {
                    "id": "p1", "course_id": "course-1", "numero_corde": 1, "musique": "1a1a2a",
                    "nombre_courses": 10, "nombre_victoires": 8, "nombre_places": 9, "poids_kg": 56.0,
                    "reduction_kilometrique": None, "ferrage": None, "statut": "partant", "champs_manuels": [],
                },
                {
                    "id": "p2", "course_id": "course-1", "numero_corde": 2, "musique": "9a9a0a",
                    "nombre_courses": 10, "nombre_victoires": 0, "nombre_places": 1, "poids_kg": 60.0,
                    "reduction_kilometrique": None, "ferrage": None, "statut": "partant", "champs_manuels": [],
                },
            ],
            "cotes": [
                {"id": "c1", "partant_id": "p1", "type_capture": "finale", "valeur": 2.0},
                {"id": "c2", "partant_id": "p2", "type_capture": "finale", "valeur": 18.0},
            ],
            "ponderations_config": [
                {
                    "id": "pond-1", "discipline": "plat", "nom": "defaut",
                    "poids": DEFAULT_PONDERATIONS["plat"], "actif": True,
                },
            ],
            "scores_pronostic": [],
        }
        self.inserted: dict[str, list[dict]] = {}
        self.deleted: list[str] = []

    @staticmethod
    def _match(row, filters):
        return all(row.get(k) == v for k, v in filters.items())

    def select(self, name, filters):
        return [r for r in self.tables.get(name, []) if self._match(r, filters)]

    def update(self, name, filters, payload):
        updated = []
        for row in self.tables.get(name, []):
            if self._match(row, filters):
                row.update(payload)
                updated.append(row)
        return updated

    def delete(self, name, filters):
        self.tables[name] = [r for r in self.tables.get(name, []) if not self._match(r, filters)]
        self.deleted.append(name)
        return []

    def insert(self, name, payload):
        rows = payload if isinstance(payload, list) else [payload]
        created = []
        for i, row in enumerate(rows):
            new_row = dict(row)
            new_row.setdefault("id", f"{name}-{len(self.tables.get(name, [])) + i + 1}")
            self.tables.setdefault(name, []).append(new_row)
            created.append(new_row)
        self.inserted.setdefault(name, []).extend(created)
        return created


class FakeClient:
    def __init__(self, store):
        self._store = store

    def table(self, name):
        return FakeQuery(self._store, name)


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


def test_get_course_404_when_missing():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        assert client.get("/courses/does-not-exist").status_code == 404
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
        rangs = sorted(r["rang_pronostique"] for r in body["classement"])
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
