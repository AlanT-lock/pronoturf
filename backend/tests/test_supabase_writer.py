from datetime import date, datetime, timezone

from app.models import (
    CourseNormalized,
    CoteNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)
from app.supabase_writer import SupabaseWriter


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self._client = client
        self._name = name
        self._payload = None

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        self._client.last_on_conflict[self._name] = on_conflict
        return self

    def execute(self):
        row = dict(self._payload)
        row["id"] = f"fake-id-{self._name}-{row.get('numero_course') or row.get('numero_corde') or row.get('code_pmu') or row.get('nom') or row.get('id_pmu')}"
        self._client.calls.append((self._name, dict(row)))
        return FakeResponse([row])


class FakeSupabaseClient:
    def __init__(self):
        self.calls = []
        self.last_on_conflict = {}

    def table(self, name):
        return FakeTable(self, name)


def _sample_course() -> CourseNormalized:
    hippodrome = HippodromeNormalized(code_pmu="DEA", nom="DEAUVILLE", pays="FRA")
    reunion = ReunionNormalized(date=date(2026, 7, 12), numero_reunion=1, hippodrome=hippodrome)
    return CourseNormalized(
        numero_course=1,
        discipline="plat",
        distance_m=1200,
        categorie_classe="COURSE_A_CONDITIONS",
        heure_depart=datetime(2026, 7, 12, 14, 30, tzinfo=timezone.utc),
        statut="terminee",
        reunion=reunion,
    )


def _sample_partants() -> list[PartantNormalized]:
    return [
        PartantNormalized(
            numero_corde=1,
            nom_cheval="MAJNOUN",
            id_pmu_cheval="MAJNOUN-MALICIEUSE-WOOTTON BASSETT",
            sexe="MALES",
            driver_jockey_nom="M.BARZALONA",
            entraineur_nom="FH.GRAFFARD (S)",
            poids_kg=58.0,
            reduction_kilometrique=None,
            ferrage=None,
            musique=None,
            statut="partant",
            cotes=[CoteNormalized(type_capture="finale", valeur=2.3, capture_at=datetime.now(tz=timezone.utc))],
            position_arrivee=3,
            age=8,
            nombre_courses=46,
            nombre_victoires=2,
            nombre_places=24,
            gains_carriere=3416500,
            gains_annee_en_cours=33000,
        )
    ]


def test_save_course_import_writes_all_tables_and_returns_ids():
    fake_client = FakeSupabaseClient()
    writer = SupabaseWriter(fake_client)

    result = writer.save_course_import(_sample_course(), _sample_partants())

    table_names_called = [name for name, _ in fake_client.calls]
    assert table_names_called == [
        "hippodromes",
        "reunions",
        "courses",
        "chevaux",
        "intervenants",
        "intervenants",
        "partants",
        "cotes",
    ]
    assert result["course_id"] is not None
    assert len(result["partant_ids"]) == 1

    # Verify rider role is derived from discipline (plat -> jockey)
    intervenant_rows = [row for name, row in fake_client.calls if name == "intervenants"]
    roles_par_nom = {row["nom"]: row["role"] for row in intervenant_rows}
    assert roles_par_nom["M.BARZALONA"] == "jockey"
    assert roles_par_nom["FH.GRAFFARD (S)"] == "entraineur"


def test_save_course_import_writes_partant_stats_and_cote_on_conflict():
    fake_client = FakeSupabaseClient()
    writer = SupabaseWriter(fake_client)
    writer.save_course_import(_sample_course(), _sample_partants())

    partant_payload = next(row for name, row in fake_client.calls if name == "partants")
    assert partant_payload["nombre_victoires"] == 2
    assert partant_payload["gains_carriere"] == 3416500

    cote_calls = [row for name, row in fake_client.calls if name == "cotes"]
    assert cote_calls, "au moins une cote écrite"
    assert fake_client.last_on_conflict["cotes"] == "partant_id,type_capture"
