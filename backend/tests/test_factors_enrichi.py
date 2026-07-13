from app.scoring.factors import compute_factors
from app.scoring.ponderations import DEFAULT_PONDERATIONS

CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}


def _perf(place, distance_m=1400, discipline="plat", allocation=20000, hippodrome="DIEPPE"):
    return {"place": place, "distance_m": distance_m, "discipline": discipline,
            "allocation": allocation, "hippodrome": hippodrome}


def _partant(corde, place_corde=None, perfs=None, jockey_taux=None, entraineur_taux=None):
    return {"numero_corde": corde, "statut": "partant", "cote_valeur": 5.0, "poids_kg": 56.0,
            "musique": "1p2p3p", "nombre_courses": 10, "nombre_victoires": 3, "nombre_places": 4,
            "place_corde": place_corde, "performances": perfs or [], "ferrage": None,
            "jockey_taux": jockey_taux, "entraineur_taux": entraineur_taux}


def test_new_factors_present_and_bounded():
    perfs = [_perf(1), _perf(2), _perf(5)]  # 3 courses, 2 succès -> taux 2/3 sur tous les contextes
    factors = compute_factors([_partant(1, perfs=perfs, jockey_taux=0.4, entraineur_taux=0.5)], "plat", CTX)
    f = factors[1]
    for key in ("taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"):
        assert key in f and 0.0 <= f[key] <= 1.0
    assert abs(f["taux_distance"] - 2 / 3) < 1e-9
    assert f["jockey"] == 0.4 and f["entraineur"] == 0.5


def test_neutral_when_no_history():
    factors = compute_factors([_partant(1, perfs=[])], "plat", CTX)
    f = factors[1]
    for key in ("taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"):
        assert f[key] == 0.5


def test_corde_uses_place_corde_not_numero():
    # corde 1 a une mauvaise place réelle (10), corde 2 une bonne (1) -> corde 2 mieux notée
    factors = compute_factors(
        [_partant(1, place_corde=10), _partant(2, place_corde=1)], "plat", CTX
    )
    assert factors[2]["corde"] > factors[1]["corde"]


def test_default_ponderations_sum_to_one_all_disciplines():
    keys = {"forme", "taux_reussite", "ferrage_poids", "cote", "corde",
            "taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"}
    for discipline, poids in DEFAULT_PONDERATIONS.items():
        assert set(poids.keys()) == keys, discipline
        assert abs(sum(poids.values()) - 1.0) < 1e-9, discipline
