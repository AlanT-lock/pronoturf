from app.scoring.factors import compute_factors

CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}


def _p(corde, musique="1a1a1a", courses=10, victoires=5, places=8, cote=3.0, poids=58.0, rk=None, ferrage=None, statut="partant"):
    return {
        "numero_corde": corde, "musique": musique, "nombre_courses": courses,
        "nombre_victoires": victoires, "nombre_places": places, "cote_valeur": cote,
        "poids_kg": poids, "reduction_kilometrique": rk, "ferrage": ferrage, "statut": statut,
    }


def test_compute_factors_excludes_non_partants():
    factors = compute_factors([_p(1), _p(2, statut="non_partant")], "plat", CTX)
    assert 1 in factors
    assert 2 not in factors


def test_compute_factors_all_in_unit_range():
    partants = [_p(1, cote=2.0, victoires=8), _p(2, cote=15.0, victoires=1), _p(3, cote=6.0, victoires=4)]
    factors = compute_factors(partants, "plat", CTX)
    for corde_factors in factors.values():
        for key, value in corde_factors.items():
            assert 0.0 <= value <= 1.0, (key, value)


def test_cote_factor_favours_low_odds():
    partants = [_p(1, cote=2.0), _p(2, cote=20.0)]
    factors = compute_factors(partants, "plat", CTX)
    assert factors[1]["cote"] > factors[2]["cote"]


def test_taux_reussite_favours_more_wins():
    partants = [_p(1, courses=10, victoires=8, places=9), _p(2, courses=10, victoires=0, places=1)]
    factors = compute_factors(partants, "plat", CTX)
    assert factors[1]["taux_reussite"] > factors[2]["taux_reussite"]


def test_plat_has_corde_factor_trot_uses_reduction():
    plat = compute_factors([_p(1), _p(2)], "plat", CTX)
    assert "corde" in plat[1]
    # en trot attelé, ferrage_poids s'appuie sur le déferrage / réduction, corde reste calculée sur numero_corde
    trot = compute_factors([_p(1, rk=78.3, ferrage="DEFERRE_POSTERIEURS"), _p(2, rk=79.0, ferrage=None)], "trot_attele", CTX)
    assert 0.0 <= trot[1]["ferrage_poids"] <= 1.0
