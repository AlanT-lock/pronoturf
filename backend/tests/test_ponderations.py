from app.scoring.ponderations import DEFAULT_PONDERATIONS, load_active_ponderation


def test_default_ponderations_sum_to_one_per_discipline():
    for discipline, poids in DEFAULT_PONDERATIONS.items():
        assert abs(sum(poids.values()) - 1.0) < 1e-9, discipline


def test_default_ponderations_cover_all_disciplines():
    assert set(DEFAULT_PONDERATIONS) == {"trot_attele", "trot_monte", "plat", "obstacle"}


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table):
        self._table = table

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeResult(self._table.rows)

    def insert(self, payload):
        row = dict(payload)
        row["id"] = "seeded-id"
        self._table.rows = [row]
        return self


class _FakeTable:
    def __init__(self):
        self.rows = []


class _FakeClient:
    def __init__(self):
        self._tables = {}

    def table(self, name):
        self._tables.setdefault(name, _FakeTable())
        return _FakeQuery(self._tables[name])


def test_load_active_ponderation_seeds_when_absent():
    client = _FakeClient()
    result = load_active_ponderation(client, "plat")
    assert result["poids"] == DEFAULT_PONDERATIONS["plat"]
    assert result["id"] == "seeded-id"
