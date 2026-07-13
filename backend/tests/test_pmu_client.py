import httpx
import respx

from app.pmu_client import PMU_BASE_URL, fetch_participants, fetch_programme, fetch_performances_detaillees


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


@respx.mock
async def test_fetch_performances_detaillees_hits_correct_url():
    sample_response = {
        "participants": [
            {
                "numPmu": 1,
                "nomCheval": "TEST_HORSE",
                "coursesCourues": []
            }
        ]
    }
    route = respx.get(f"{PMU_BASE_URL}/programme/13072026/R1/C1/performances-detaillees/pretty").mock(
        return_value=httpx.Response(200, json=sample_response)
    )
    result = await fetch_performances_detaillees("13072026", 1, 1)
    assert route.called
    assert result == sample_response
