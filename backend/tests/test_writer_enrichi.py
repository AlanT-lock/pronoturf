from datetime import date, datetime, timezone

from app.models import (
    CourseNormalized, HippodromeNormalized, PartantNormalized,
    PerformanceNormalized, ReunionNormalized,
)


class FakeQ:
    def __init__(self, store, name):
        self.store, self.name, self.payload, self.op = store, name, None, None
    def upsert(self, payload, on_conflict=None):
        self.op, self.payload = "upsert", payload; return self
    def insert(self, payload):
        self.op, self.payload = "insert", payload; return self
    def select(self, *a, **k): self.op = "select"; return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self):
        rows = self.payload if isinstance(self.payload, list) else [self.payload]
        out = []
        for r in rows:
            nr = dict(r); nr.setdefault("id", f"{self.name}-{len(self.store.setdefault(self.name, []))+1}")
            self.store[self.name].append(nr); out.append(nr)
        class R: pass
        res = R(); res.data = out; return res


class FakeClient:
    def __init__(self): self.store = {}
    def table(self, name): return FakeQ(self.store, name)


def _course(statut="a_venir"):
    return CourseNormalized(
        numero_course=1, discipline="plat", distance_m=1400, allocation=20100.0,
        categorie_classe=None, heure_depart=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
        statut=statut,
        reunion=ReunionNormalized(
            date=date(2026, 7, 13), numero_reunion=1,
            hippodrome=HippodromeNormalized(code_pmu="DIE", nom="DIEPPE", pays="FRA"),
        ),
    )


def _partant(corde, entraineur=None, pos=None):
    return PartantNormalized(
        numero_corde=corde, nom_cheval=f"H{corde}", id_pmu_cheval=f"H{corde}-a-b", sexe=None,
        driver_jockey_nom="J.DOE", entraineur_nom=entraineur, poids_kg=58.0,
        reduction_kilometrique=None, ferrage=None, musique=None, statut="partant", cotes=[],
        position_arrivee=pos,
    )


def test_save_course_import_returns_cheval_id_by_corde():
    from app.supabase_writer import SupabaseWriter
    w = SupabaseWriter(FakeClient())
    result = w.save_course_import(_course(), [_partant(1), _partant(2)])
    assert set(result["cheval_id_by_corde"].keys()) == {1, 2}
    assert all(result["cheval_id_by_corde"].values())


def test_save_performances_writes_rows():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    perfs = {1: [PerformanceNormalized(num_pmu=1, date_course=date(2026, 6, 1),
             hippodrome="DIEPPE", discipline="plat", distance_m=1400, allocation=20100.0,
             nb_participants=9, place=2, status_arrivee="PLACE", raw_place="2",
             jockey_nom="S.PASQUIER", poids_jockey=58.0, corde=8, oeillere=None)]}
    n = w.save_performances(perfs, {1: "cheval-1"})
    assert n == 1
    row = client.store["chevaux_performances"][0]
    assert row["cheval_id"] == "cheval-1" and row["place"] == 2 and row["jockey_nom"] == "S.PASQUIER"


def test_save_performances_skips_unknown_corde():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    perfs = {9: [PerformanceNormalized(num_pmu=9, date_course=date(2026, 6, 1), distance_m=1400, hippodrome="X")]}
    assert w.save_performances(perfs, {1: "cheval-1"}) == 0
    assert client.store.get("chevaux_performances", []) == []


def test_save_entraineur_resultats_only_finished_with_place():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    partants = [_partant(1, entraineur="N.CAULLERY", pos=1), _partant(2, entraineur=None, pos=2)]
    n = w.save_entraineur_resultats(_course(statut="terminee"), partants, {1: "cheval-1", 2: "cheval-2"})
    assert n == 1
    row = client.store["entraineur_resultats"][0]
    assert row["entraineur_nom"] == "N.CAULLERY" and row["place"] == 1 and row["cheval_id"] == "cheval-1"
