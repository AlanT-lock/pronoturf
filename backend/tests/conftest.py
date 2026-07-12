import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def pmu_programme_sample() -> dict:
    return json.loads((FIXTURES_DIR / "pmu_programme_sample.json").read_text())


@pytest.fixture
def pmu_participants_plat_sample() -> dict:
    return json.loads((FIXTURES_DIR / "pmu_participants_plat_sample.json").read_text())
