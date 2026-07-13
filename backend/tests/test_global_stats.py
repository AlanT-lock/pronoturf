from app.scoring import global_stats as gs


class FakeQ:
    def __init__(self, store, name): self.store, self.name, self.col, self.val = store, name, None, None
    def select(self, *a, **k): return self
    def eq(self, col, val): self.col, self.val = col, val; return self
    def execute(self):
        rows = [r for r in self.store.get(self.name, []) if r.get(self.col) == self.val]
        class R: pass
        res = R(); res.data = rows; return res


class FakeClient:
    def __init__(self, store): self.store = store
    def table(self, name): return FakeQ(self.store, name)


def test_jockey_taux_from_performances():
    store = {"chevaux_performances": [
        {"jockey_nom": "S.P", "place": 1}, {"jockey_nom": "S.P", "place": 4},
        {"jockey_nom": "S.P", "place": 2}, {"jockey_nom": "AUTRE", "place": 1},
    ]}
    assert gs.jockey_taux(FakeClient(store), "S.P") == 2 / 3


def test_jockey_taux_below_min_sample():
    store = {"chevaux_performances": [{"jockey_nom": "S.P", "place": 1}]}
    assert gs.jockey_taux(FakeClient(store), "S.P") is None


def test_jockey_taux_empty_name():
    assert gs.jockey_taux(FakeClient({}), None) is None
    assert gs.jockey_taux(FakeClient({}), "") is None


def test_entraineur_taux_from_resultats():
    store = {"entraineur_resultats": [
        {"entraineur_nom": "N.C", "place": 1}, {"entraineur_nom": "N.C", "place": 3},
        {"entraineur_nom": "N.C", "place": 8},
    ]}
    assert gs.entraineur_taux(FakeClient(store), "N.C") == 2 / 3
