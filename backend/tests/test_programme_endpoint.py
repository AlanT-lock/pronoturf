import app.main as main
from fastapi.testclient import TestClient

PROG = {"programme": {"reunions": [
    {"numOfficiel": 1, "pays": {"code": "FRA"},
     "hippodrome": {"code": "PLC", "libelleCourt": "ParisLongchamp"},
     "courses": [
        {"numOrdre": 3, "discipline": "PLAT", "distance": 2400, "montantPrix": 90000,
         "heureDepart": 1784032500000, "nombreDeclaresPartants": 16,
         "paris": [{"typePari": "QUINTE_PLUS"}, {"typePari": "SIMPLE_GAGNANT"}]},
     ]},
]}}


def test_get_programme_returns_normalized(monkeypatch):
    async def fake_prog(date):
        assert date == "14072026"
        return PROG
    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    r = TestClient(main.app).get("/programme/14072026")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "14072026"
    c = body["reunions"][0]["courses"][0]
    assert c["est_quinte"] is True
    assert body["reunions"][0]["hippodrome"] == "ParisLongchamp"
