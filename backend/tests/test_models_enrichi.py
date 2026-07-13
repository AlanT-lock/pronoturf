from datetime import date

from app.models import PartantNormalized, CourseNormalized, PerformanceNormalized, ReunionNormalized, HippodromeNormalized


def test_partant_has_place_corde_optional():
    p = PartantNormalized(
        numero_corde=1, nom_cheval="X", id_pmu_cheval="X-Y-Z", sexe=None,
        driver_jockey_nom=None, entraineur_nom=None, poids_kg=None,
        reduction_kilometrique=None, ferrage=None, musique=None, statut="partant", cotes=[],
    )
    assert p.place_corde is None
    p2 = p.model_copy(update={"place_corde": 8})
    assert p2.place_corde == 8


def test_course_has_allocation_optional():
    c = CourseNormalized(
        numero_course=1, discipline="plat", distance_m=1400, categorie_classe=None,
        heure_depart="2026-07-13T12:00:00+00:00", statut="a_venir",
        reunion=ReunionNormalized(
            date=date(2026, 7, 13), numero_reunion=1,
            hippodrome=HippodromeNormalized(code_pmu="DIE", nom="DIEPPE", pays="FRA"),
        ),
    )
    assert c.allocation is None


def test_performance_normalized_fields():
    perf = PerformanceNormalized(
        num_pmu=1, date_course=date(2026, 6, 1), hippodrome="DIEPPE", discipline="plat",
        distance_m=1400, allocation=20100.0, nb_participants=9, place=2,
        status_arrivee="PLACE", raw_place="2", jockey_nom="S.PASQUIER",
        poids_jockey=58.0, corde=8, oeillere="SANS_OEILLERES",
    )
    assert perf.num_pmu == 1
    assert perf.place == 2
