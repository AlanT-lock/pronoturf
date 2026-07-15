from app.scoring.ponderations import DEFAULT_PONDERATIONS


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
        self._filters[col] = ("eq", val)
        return self

    def in_(self, col, vals):
        self._filters[col] = ("in", set(vals))
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
                    "allocation": 20000,
                },
            ],
            "partants": [
                {
                    "id": "p1", "course_id": "course-1", "numero_corde": 1, "musique": "1a1a2a",
                    "nombre_courses": 10, "nombre_victoires": 8, "nombre_places": 9, "poids_kg": 56.0,
                    "reduction_kilometrique": None, "ferrage": None, "statut": "partant", "champs_manuels": [],
                    "cheval_id": "ch1",
                    "place_corde": 1, "driver_jockey_id": "iv1", "entraineur_id": "iv2",
                },
                {
                    "id": "p2", "course_id": "course-1", "numero_corde": 2, "musique": "9a9a0a",
                    "nombre_courses": 10, "nombre_victoires": 0, "nombre_places": 1, "poids_kg": 60.0,
                    "reduction_kilometrique": None, "ferrage": None, "statut": "partant", "champs_manuels": [],
                    "cheval_id": "ch2",
                    "place_corde": 2, "driver_jockey_id": None, "entraineur_id": None,
                },
            ],
            "chevaux": [
                {"id": "ch1", "nom": "Fusain De Losque", "sexe": "H"},
                {"id": "ch2", "nom": "Belle Étoile", "sexe": "F"},
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
            "analyses_llm": [],
            "analyses_llm_historique": [],
            "chevaux_performances": [],
            "entraineur_resultats": [],
            "reunions": [{"id": "r1", "hippodrome_id": "h1", "date": "2026-07-13", "numero_reunion": 1}],
            "hippodromes": [{"id": "h1", "nom": "DIEPPE", "code_pmu": "DIE", "pays": "FRA"}],
            "intervenants": [
                {"id": "iv1", "nom": "S.PASQUIER", "role": "jockey"},
                {"id": "iv2", "nom": "N.CAULLERY", "role": "entraineur"},
            ],
        }
        self.inserted: dict[str, list[dict]] = {}
        self.deleted: list[str] = []

    @staticmethod
    def _match(row, filters):
        for col, (op, val) in filters.items():
            if op == "eq" and row.get(col) != val:
                return False
            if op == "in" and row.get(col) not in val:
                return False
        return True

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
