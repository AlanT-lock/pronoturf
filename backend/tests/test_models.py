from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    CourseNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)


def test_course_normalized_rejects_invalid_discipline():
    hippodrome = HippodromeNormalized(code_pmu="DEA", nom="DEAUVILLE", pays="FRA")
    reunion = ReunionNormalized(date=date(2026, 7, 12), numero_reunion=1, hippodrome=hippodrome)
    with pytest.raises(ValidationError):
        CourseNormalized(
            numero_course=1,
            discipline="GALOP",  # invalide
            distance_m=1200,
            categorie_classe="COURSE_A_CONDITIONS",
            heure_depart=datetime(2026, 7, 12, 14, 30),
            statut="a_venir",
            reunion=reunion,
        )


def test_partant_normalized_accepts_minimal_fields():
    partant = PartantNormalized(
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
        cotes=[],
    )
    assert partant.numero_corde == 1
    assert partant.poids_kg == 58.0
