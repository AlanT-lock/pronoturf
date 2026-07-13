from app.scoring import context_stats as cs


def _p(place=None, distance_m=1400, discipline="plat", allocation=20000, hippodrome="DIEPPE"):
    return {"place": place, "distance_m": distance_m, "discipline": discipline,
            "allocation": allocation, "hippodrome": hippodrome}


def test_is_success_top3():
    assert cs.is_success(_p(place=1))
    assert cs.is_success(_p(place=3))
    assert not cs.is_success(_p(place=4))
    assert not cs.is_success(_p(place=None))


def test_taux_distance_within_band():
    perfs = [_p(place=1, distance_m=1400), _p(place=5, distance_m=1450),
             _p(place=2, distance_m=1350), _p(place=1, distance_m=3000)]  # 3000 hors bande
    # 3 courses dans [1260,1540] : places 1,5,2 -> 2 succès / 3
    assert cs.taux_distance(perfs, 1400) == 2 / 3


def test_taux_below_min_sample_returns_none():
    perfs = [_p(place=1, distance_m=1400), _p(place=2, distance_m=1400)]  # 2 < MIN_SAMPLE
    assert cs.taux_distance(perfs, 1400) is None


def test_taux_discipline_filters():
    perfs = [_p(place=1, discipline="plat"), _p(place=1, discipline="plat"),
             _p(place=4, discipline="plat"), _p(place=1, discipline="trot_attele")]
    assert cs.taux_discipline(perfs, "plat") == 2 / 3


def test_taux_niveau_within_band_and_skips_none_allocation():
    perfs = [_p(place=1, allocation=20000), _p(place=4, allocation=24000),
             _p(place=2, allocation=16000), _p(place=1, allocation=None)]  # None ignoré
    # bande ±30% de 20000 = [14000,26000] : 20000,24000,16000 -> places 1,4,2 -> 2/3
    assert cs.taux_niveau(perfs, 20000) == 2 / 3


def test_taux_hippodrome_filters():
    perfs = [_p(place=1, hippodrome="DIEPPE"), _p(place=2, hippodrome="DIEPPE"),
             _p(place=4, hippodrome="DIEPPE"), _p(place=1, hippodrome="VINCENNES")]
    assert cs.taux_hippodrome(perfs, "DIEPPE") == 2 / 3


def test_confidence_scales_and_clamps():
    assert cs.confidence(0, False, False) == 0.0
    assert cs.confidence(10, True, True) == 1.0
    assert cs.confidence(20, True, True) == 1.0          # plafonné
    mid = cs.confidence(5, True, True)
    assert 0.0 < mid < 1.0
    # jockey/entraineur inconnus abaissent la confiance
    assert cs.confidence(10, False, False) < cs.confidence(10, True, True)
