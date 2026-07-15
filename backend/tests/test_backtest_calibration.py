from app.backtest import calibration as cal


def test_gate_bloque_sous_le_seuil():
    pairs = [(0.5, True)] * 10
    out = cal.calibrate_confidence(pairs)
    assert out["disponible"] is False
    assert out["nb_paires"] == 10
    assert out["seuil"] == cal.MIN_PAIRS_CALIBRATION


def test_disponible_au_dessus_du_seuil():
    pairs = [(0.1, False)] * 30 + [(0.9, True)] * 30  # 60 >= 50
    out = cal.calibrate_confidence(pairs)
    assert out["disponible"] is True
    assert out["nb_paires"] == 60
    assert isinstance(out["mapping"], list) and out["mapping"]
    # le mapping est bien une courbe de fiabilité par bucket
    buckets = {b["bucket"] for b in out["mapping"]}
    assert "0.0–0.2" in buckets and "0.8–1.0" in buckets
