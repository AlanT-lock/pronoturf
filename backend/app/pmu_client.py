import httpx

PMU_BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/61"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


async def fetch_programme(date_str: str) -> dict:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(f"{PMU_BASE_URL}/programme/{date_str}")
        response.raise_for_status()
        return response.json()


async def fetch_participants(date_str: str, numero_reunion: int, numero_course: int) -> dict:
    url = f"{PMU_BASE_URL}/programme/{date_str}/R{numero_reunion}/C{numero_course}/participants"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def fetch_performances_detaillees(date_str: str, numero_reunion: int, numero_course: int) -> dict:
    url = f"{PMU_BASE_URL}/programme/{date_str}/R{numero_reunion}/C{numero_course}/performances-detaillees/pretty"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
