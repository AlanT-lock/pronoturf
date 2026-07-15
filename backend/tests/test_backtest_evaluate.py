from app.backtest import evaluate as ev


def _classement(triples):
    # triples: list of (numero_corde, rang, confiance)
    return [{"numero_corde": c, "rang": r, "confiance": conf} for c, r, conf in triples]


def test_evaluate_course_top1_hit():
    classement = _classement([(4, 1, 0.8), (1, 2, 0.8), (7, 3, 0.8)])
    out = ev.evaluate_course(classement, {4: 1, 1: 2, 7: 3})  # 4 gagne, on l'avait rang1
    assert out["gagnant_reel"] == 4
    assert out["rang_predit_du_gagnant"] == 1
    assert out["top1_hit"] is True
    assert out["top3_hit"] is True
    assert out["confiance_top1"] == 0.8


def test_evaluate_course_top3_hit_but_not_top1():
    classement = _classement([(4, 1, 0.5), (1, 2, 0.5), (7, 3, 0.5)])
    out = ev.evaluate_course(classement, {4: 2, 1: 3, 7: 1})  # 7 gagne, on l'avait rang3
    assert out["gagnant_reel"] == 7
    assert out["rang_predit_du_gagnant"] == 3
    assert out["top1_hit"] is False
    assert out["top3_hit"] is True


def test_evaluate_course_miss():
    classement = _classement([(4, 1, 0.5), (1, 2, 0.5), (7, 3, 0.5), (9, 4, 0.5)])
    out = ev.evaluate_course(classement, {4: 2, 1: 3, 7: 4, 9: 1})  # 9 gagne (rang4)
    assert out["top1_hit"] is False
    assert out["top3_hit"] is False


def test_evaluate_course_sans_gagnant():
    classement = _classement([(4, 1, 0.5)])
    out = ev.evaluate_course(classement, {4: 2})  # aucun position==1
    assert out["gagnant_reel"] is None


def test_aggregate_ignore_courses_sans_gagnant():
    evals = [
        {"gagnant_reel": 4, "top1_hit": True, "top3_hit": True, "confiance_top1": 0.9},
        {"gagnant_reel": 7, "top1_hit": False, "top3_hit": True, "confiance_top1": 0.5},
        {"gagnant_reel": None, "top1_hit": False, "top3_hit": False, "confiance_top1": None},
    ]
    agg = ev.aggregate(evals)
    assert agg["nb_courses"] == 2
    assert agg["precision_top1"] == 0.5
    assert agg["precision_top3"] == 1.0
    # brier = mean((0.9-1)^2, (0.5-0)^2) = mean(0.01, 0.25) = 0.13
    assert abs(agg["brier_confiance"] - 0.13) < 1e-9


def test_aggregate_vide():
    agg = ev.aggregate([])
    assert agg == {"nb_courses": 0, "precision_top1": None,
                   "precision_top3": None, "brier_confiance": None}


def test_calibration_bins_groups_and_rates():
    pairs = [(0.1, False), (0.15, True), (0.85, True), (0.9, True)]
    bins = ev.calibration_bins(pairs)
    labels = {b["bucket"]: b for b in bins}
    assert labels["0.0–0.2"]["n"] == 2
    assert labels["0.0–0.2"]["taux_top1_reel"] == 0.5
    assert labels["0.8–1.0"]["n"] == 2
    assert labels["0.8–1.0"]["taux_top1_reel"] == 1.0
    # buckets vides omis
    assert "0.2–0.4" not in labels
