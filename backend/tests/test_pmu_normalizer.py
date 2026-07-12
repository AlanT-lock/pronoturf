from app.pmu_normalizer import (
    find_course_in_programme,
    normalize_course,
    normalize_partants,
)


def test_find_course_in_programme_returns_reunion_and_course(pmu_programme_sample):
    raw_reunion, raw_course = find_course_in_programme(pmu_programme_sample, 1, 1)
    assert raw_reunion["numOfficiel"] == 1
    assert raw_course["numOrdre"] == 1


def test_normalize_course_maps_plat_discipline(pmu_programme_sample):
    raw_reunion, raw_course = find_course_in_programme(pmu_programme_sample, 1, 1)
    course = normalize_course(raw_reunion, raw_course)
    assert course.discipline == "plat"
    assert course.statut == "terminee"
    assert course.distance_m == 1200
    assert course.reunion.hippodrome.code_pmu == "DEA"


def test_normalize_partants_plat_maps_poids_and_cotes(pmu_participants_plat_sample):
    partants = normalize_partants(pmu_participants_plat_sample["participants"], course_terminee=True)
    majnoun = next(p for p in partants if p.nom_cheval == "MAJNOUN")
    assert majnoun.numero_corde == 1
    assert majnoun.poids_kg == 58.0
    assert majnoun.position_arrivee == 3
    valeurs_par_type = {c.type_capture: c.valeur for c in majnoun.cotes}
    assert valeurs_par_type["reference"] == 1.4
    assert valeurs_par_type["finale"] == 2.3
    assert "direct" not in valeurs_par_type  # course terminée -> direct devient finale


def test_normalize_partants_trot_maps_deferre_and_reduction(pmu_participants_trot_sample):
    partants = normalize_partants(pmu_participants_trot_sample["participants"], course_terminee=True)
    igor = next(p for p in partants if p.nom_cheval == "IGOR THEPOL")
    assert igor.ferrage == "DEFERRE_POSTERIEURS"
    assert igor.reduction_kilometrique == 78.3
    assert igor.poids_kg is None
    assert igor.musique == "7aDm5a(25)6mDm9m3mDm9m"


def test_normalize_course_reunion_date_uses_local_racing_day(pmu_programme_sample):
    raw_reunion, raw_course = find_course_in_programme(pmu_programme_sample, 1, 1)
    course = normalize_course(raw_reunion, raw_course)
    # dateReunion 1783807200000 = 2026-07-11 22:00 UTC = 2026-07-12 00:00 Paris (offset +2h)
    assert course.reunion.date.isoformat() == "2026-07-12"


def test_normalize_partants_trot_maps_stats(pmu_participants_trot_sample):
    partants = normalize_partants(pmu_participants_trot_sample["participants"], course_terminee=True)
    igor = next(p for p in partants if p.nom_cheval == "IGOR THEPOL")
    assert igor.age == 8
    assert igor.nombre_courses == 46
    assert igor.nombre_victoires == 2
    assert igor.nombre_places == 24
    assert igor.gains_carriere == 3416500
    assert igor.gains_annee_en_cours == 33000
