from app.pmu_normalizer import normalize_programme

PROG = {"programme": {"reunions": [
    {"numOfficiel": 1, "pays": {"code": "FRA"},
     "hippodrome": {"code": "PLC", "libelleCourt": "ParisLongchamp"},
     "courses": [
        {"numOrdre": 1, "discipline": "PLAT", "distance": 1400, "montantPrix": 25000,
         "heureDepart": 1784030100000, "nombreDeclaresPartants": 12,
         "paris": [{"typePari": "SIMPLE_GAGNANT"}, {"typePari": "E_SIMPLE_GAGNANT"}, {"typePari": "TRIO"}]},
        {"numOrdre": 3, "discipline": "PLAT", "distance": 2400, "montantPrix": 90000,
         "heureDepart": 1784032500000, "nombreDeclaresPartants": 16, "arriveeDefinitive": False,
         "paris": [{"typePari": "QUINTE_PLUS"}, {"typePari": "TIERCE"}, {"typePari": "SIMPLE_GAGNANT"}]},
     ]},
]}}


def test_normalize_programme_structure():
    out = normalize_programme(PROG)
    assert len(out["reunions"]) == 1
    r = out["reunions"][0]
    assert r["numero_reunion"] == 1 and r["hippodrome"] == "ParisLongchamp" and r["pays"] == "FRA"
    assert len(r["courses"]) == 2


def test_course_fields_and_paris_deduped():
    c = normalize_programme(PROG)["reunions"][0]["courses"][0]
    assert c["numero_course"] == 1
    assert c["discipline"] == "plat"
    assert c["distance_m"] == 1400
    assert c["allocation"] == 25000
    assert c["nombre_partants"] == 12
    assert c["statut"] == "a_venir"
    assert c["paris"] == ["SIMPLE_GAGNANT", "TRIO"]   # E_ dédupliqué
    assert c["est_quinte"] is False
    assert c["heure_depart"].startswith("2026-")       # ISO


def test_quinte_flagged():
    c3 = normalize_programme(PROG)["reunions"][0]["courses"][1]
    assert c3["est_quinte"] is True
    assert "QUINTE_PLUS" in c3["paris"]
