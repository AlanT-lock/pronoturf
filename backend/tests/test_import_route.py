from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client


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
        return self

    def execute(self):
        row = dict(self._payload)
        row["id"] = f"fake-id-{self._name}-{len(self._client.calls)}"
        self._client.calls.append((self._name, dict(row)))
        return FakeResponse([row])


class FakeSupabaseClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return FakeTable(self, name)


client = TestClient(app)


def test_import_course_returns_course_and_partant_ids(pmu_programme_sample, pmu_participants_plat_sample):
    app.dependency_overrides[get_supabase_client] = lambda: FakeSupabaseClient()
    try:
        with patch("app.main.fetch_programme", new=AsyncMock(return_value=pmu_programme_sample)), patch(
            "app.main.fetch_participants", new=AsyncMock(return_value=pmu_participants_plat_sample)
        ):
            response = client.post(
                "/courses/import",
                json={"date": "12072026", "numero_reunion": 1, "numero_course": 1},
            )
        assert response.status_code == 200
        body = response.json()
        assert "course_id" in body
        assert len(body["partant_ids"]) == 2
    finally:
        app.dependency_overrides.clear()
