from app.analyse import signals as s


def test_softmax_sums_to_one_and_ranks():
    out = s.softmax([0.8, 0.5, 0.2])
    assert abs(sum(out) - 1.0) < 1e-9
    assert out[0] > out[1] > out[2]


def test_softmax_empty():
    assert s.softmax([]) == []


def test_proba_implicite_normalise_et_ignore_none():
    # cotes 2.0 et 4.0 -> inv 0.5 et 0.25 -> total 0.75 -> 0.666.., 0.333..
    out = s.proba_implicite([2.0, 4.0, None])
    assert abs(out[0] - 2 / 3) < 1e-6
    assert abs(out[1] - 1 / 3) < 1e-6
    assert out[2] is None


def test_course_shape_favori_ecrasant():
    forme = s.course_shape([0.9, 0.5, 0.45, 0.4])
    assert forme["favori_ecrasant"] is True
    assert forme["ecart_favori"] > 0


def test_course_shape_ouverte():
    forme = s.course_shape([0.55, 0.54, 0.53, 0.52])
    assert forme["favori_ecrasant"] is False


def test_build_signals_shape_and_value():
    classement = [
        {"numero_corde": 4, "nom_cheval": "A", "score_total": 0.8, "rang": 1,
         "cote": 5.0, "confiance": 0.5, "nb_courses_historique": 3, "details_facteurs": {}},
        {"numero_corde": 1, "nom_cheval": "B", "score_total": 0.4, "rang": 2,
         "cote": 2.0, "confiance": 0.5, "nb_courses_historique": 3, "details_facteurs": {}},
    ]
    out = s.build_signals(classement)
    assert set(out) == {"chevaux", "forme_course"}
    ch = out["chevaux"][0]
    assert {"proba_modele", "proba_implicite_cote", "value"} <= set(ch)
    # A a un meilleur score mais une cote plus haute -> value probablement positive
    assert ch["numero_corde"] == 4
    assert ch["value"] is not None


def test_build_signals_cote_absente_donne_value_none():
    classement = [
        {"numero_corde": 4, "nom_cheval": "A", "score_total": 0.8, "rang": 1,
         "cote": None, "confiance": 0.5, "nb_courses_historique": 1, "details_facteurs": {}},
    ]
    ch = s.build_signals(classement)["chevaux"][0]
    assert ch["proba_implicite_cote"] is None
    assert ch["value"] is None
