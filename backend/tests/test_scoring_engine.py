from app.scoring.engine import score_course
from app.scoring.ponderations import DEFAULT_PONDERATIONS


def _p(corde, musique="1a1a1a", courses=10, victoires=5, places=8, cote=3.0, poids=58.0, statut="partant"):
    return {
        "numero_corde": corde, "musique": musique, "nombre_courses": courses,
        "nombre_victoires": victoires, "nombre_places": places, "cote_valeur": cote,
        "poids_kg": poids, "reduction_kilometrique": None, "ferrage": None, "statut": statut,
    }


def test_score_course_ranks_by_score_desc():
    partants = [
        _p(1, musique="9a9a9a", victoires=0, places=1, cote=25.0),
        _p(2, musique="1a1a2a", victoires=8, places=9, cote=2.0),
        _p(3, musique="5a4a6a", victoires=3, places=5, cote=6.0),
    ]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    assert [r["numero_corde"] for r in ranked] == sorted(
        [r["numero_corde"] for r in ranked], key=lambda c: -next(x["score_total"] for x in ranked if x["numero_corde"] == c)
    )
    assert ranked[0]["numero_corde"] == 2  # le meilleur profil gagne
    assert ranked[0]["rang"] == 1
    assert ranked[-1]["numero_corde"] == 1


def test_effective_weights_sum_to_one_after_redistribution():
    partants = [_p(1), _p(2)]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    for r in ranked:
        total = sum(f["poids_effectif"] for f in r["details_facteurs"].values())
        assert abs(total - 1.0) < 1e-9


def test_score_in_unit_range_and_details_consistent():
    partants = [_p(1, cote=2.0), _p(2, cote=10.0)]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    for r in ranked:
        assert 0.0 <= r["score_total"] <= 1.0
        recomputed = sum(f["contribution"] for f in r["details_facteurs"].values())
        assert abs(recomputed - r["score_total"]) < 1e-9


def test_non_partant_excluded_from_ranking():
    ranked = score_course([_p(1), _p(2, statut="non_partant")], "plat", DEFAULT_PONDERATIONS["plat"])
    assert [r["numero_corde"] for r in ranked] == [1]
