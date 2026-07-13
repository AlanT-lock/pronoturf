from app.pmu_normalizer import normalize_performances


RAW_PERF = {
    "participants": [
        {
            "numPmu": 1,
            "nomCheval": "NO REMORSE",
            "coursesCourues": [
                {
                    "date": 1748772000000,
                    "timezoneOffset": 7200000,
                    "hippodrome": "DIEPPE",
                    "discipline": "PLAT",
                    "allocation": 20100,
                    "distance": 1400,
                    "nbParticipants": 9,
                    "participants": [
                        {
                            "numPmu": 3,
                            "place": {"place": 2, "rawValue": "2", "statusArrivee": "PLACE"},
                            "nomCheval": "NO REMORSE",
                            "nomJockey": "S.PASQUIER",
                            "poidsJockey": 58.0,
                            "corde": 8,
                            "itsHim": True,
                            "oeillere": "SANS_OEILLERES",
                        },
                        {"numPmu": 1, "itsHim": False, "nomCheval": "AUTRE"},
                    ],
                }
            ],
        }
    ]
}


def test_normalize_performances_keys_by_num_pmu():
    result = normalize_performances(RAW_PERF)
    assert set(result.keys()) == {1}
    perfs = result[1]
    assert len(perfs) == 1
    p = perfs[0]
    assert p.num_pmu == 1
    assert p.hippodrome == "DIEPPE"
    assert p.discipline == "plat"            # mappé
    assert p.distance_m == 1400
    assert p.allocation == 20100
    assert p.place == 2                       # depuis participant itsHim
    assert p.status_arrivee == "PLACE"
    assert p.jockey_nom == "S.PASQUIER"
    assert p.corde == 8


def test_normalize_performances_handles_missing_history():
    assert normalize_performances({"participants": []}) == {}
    assert normalize_performances({}) == {}


def test_normalize_performances_non_place():
    raw = {
        "participants": [
            {
                "numPmu": 2, "nomCheval": "X",
                "coursesCourues": [
                    {
                        "date": 1748772000000, "hippodrome": "VINCENNES",
                        "discipline": "ATTELE", "allocation": 30000, "distance": 2700, "nbParticipants": 12,
                        "participants": [
                            {"numPmu": 5, "place": {"place": None, "rawValue": "DP", "statusArrivee": "NON_PLACE"}, "itsHim": True, "nomJockey": "J.DOE"},
                        ],
                    }
                ],
            }
        ]
    }
    p = normalize_performances(raw)[2][0]
    assert p.place is None
    assert p.raw_place == "DP"
    assert p.discipline == "trot_attele"


def test_normalize_performances_skips_course_without_itshim():
    raw = {
        "participants": [
            {
                "numPmu": 4, "nomCheval": "NO_HIM",
                "coursesCourues": [
                    {
                        "date": 1748772000000, "hippodrome": "LONGCHAMP",
                        "discipline": "PLAT", "allocation": 25000, "distance": 2400, "nbParticipants": 10,
                        "participants": [
                            {"numPmu": 7, "itsHim": False, "nomCheval": "NO_HIM", "nomJockey": "J.SMITH"},
                            {"numPmu": 8, "itsHim": False, "nomCheval": "OTHER"},
                        ],
                    }
                ],
            }
        ]
    }
    result = normalize_performances(raw)
    # Course without itsHim participant should be silently dropped - horse exists but with empty perfs list
    assert result == {4: []}
    assert result[4] == []
