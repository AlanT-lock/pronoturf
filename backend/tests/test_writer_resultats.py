from app.models import CoteNormalized  # noqa: F401  (garde l'import du module models chargé)
from app.supabase_writer import SupabaseWriter


class FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._payload = None

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        self._store.setdefault(self._name, []).append((payload, on_conflict))
        return self

    def execute(self):
        class R:
            data = [{"id": "r1"}]
        return R()


class FakeClient:
    def __init__(self):
        self.calls = {}

    def table(self, name):
        return FakeTable(self.calls, name)


class P:
    """Partant minimal pour save_resultats (seuls numero_corde/position_arrivee comptent)."""
    def __init__(self, numero_corde, position_arrivee):
        self.numero_corde = numero_corde
        self.position_arrivee = position_arrivee


def test_save_resultats_ecrit_les_arrives_et_ignore_les_non_arrives():
    client = FakeClient()
    writer = SupabaseWriter(client)
    partants = [P(1, 3), P(2, None), P(4, 1)]  # 2 arrivés, 1 non arrivé
    pid = {1: "pa-1", 2: "pa-2", 4: "pa-4"}
    n = writer.save_resultats("course-9", partants, pid)
    assert n == 2
    rows = [payload for payload, _oc in client.calls["resultats"]]
    cordes = {r["partant_id"]: r["position_arrivee"] for r in rows}
    assert cordes == {"pa-1": 3, "pa-4": 1}
    assert all(r["course_id"] == "course-9" for r in rows)
    assert all(r["disqualifie"] is False for r in rows)
    # upsert sur partant_id (idempotence)
    assert all(oc == "partant_id" for _payload, oc in client.calls["resultats"])
