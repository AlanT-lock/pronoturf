import httpx
import respx

from app.pmu_client import PMU_BASE_URL, fetch_participants, fetch_programme


@respx.mock
async def test_fetch_programme_calls_expected_url(pmu_programme_sample):
    route = respx.get(f"{PMU_BASE_URL}/programme/12072026").mock(
        return_value=httpx.Response(200, json=pmu_programme_sample)
    )
    result = await fetch_programme("12072026")
    assert route.called
    assert result == pmu_programme_sample


@respx.mock
async def test_fetch_participants_calls_expected_url(pmu_participants_plat_sample):
    route = respx.get(f"{PMU_BASE_URL}/programme/12072026/R1/C1/participants").mock(
        return_value=httpx.Response(200, json=pmu_participants_plat_sample)
    )
    result = await fetch_participants("12072026", 1, 1)
    assert route.called
    assert result == pmu_participants_plat_sample
