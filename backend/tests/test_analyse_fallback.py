from app.analyse.fallback import analyse_deterministe

SIGNALS = {
    "forme_course": {"favori_ecrasant": True, "ecart_favori": 0.3, "dispersion": 0.2},
    "chevaux": [
        {"numero_corde": 4, "nom_cheval": "A", "rang": 1, "value": 0.12},
        {"numero_corde": 1, "nom_cheval": "B", "rang": 2, "value": -0.05},
        {"numero_corde": 7, "nom_cheval": "C", "rang": 3, "value": 0.02},
        {"numero_corde": 2, "nom_cheval": "D", "rang": 4, "value": None},
        {"numero_corde": 9, "nom_cheval": "E", "rang": 5, "value": -0.01},
    ],
}


def test_recommande_seulement_paris_analysables():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT", "MULTI", "TRIO"])
    codes = [r["type_pari"] for r in out["recommandations"]]
    assert "SIMPLE_GAGNANT" in codes and "TRIO" in codes
    assert "MULTI" not in codes  # hors ANALYSABLE


def test_selection_taille_par_pari():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT", "TIERCE", "QUINTE_PLUS"])
    by = {r["type_pari"]: r for r in out["recommandations"]}
    assert by["SIMPLE_GAGNANT"]["selection"] == [4]
    assert by["TIERCE"]["selection"] == [4, 1, 7]
    assert by["QUINTE_PLUS"]["selection"] == [4, 1, 7, 2, 9]
    # base/tournant remplis pour les combinés
    assert by["TIERCE"]["base"] == [4]
    assert by["TIERCE"]["tournant"] == [1, 7]


def test_coup_de_coeur_meilleur_value_positif():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT"])
    assert out["coup_de_coeur_value"]["numero_corde"] == 4  # value +0.12 le plus haut


def test_source_et_niveau():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT"])
    assert out["source"] == "regles"
    assert out["recommandations"][0]["niveau"] in {"faible", "moyen", "eleve"}


def test_pas_de_value_positive_donne_coup_none():
    signals = {"forme_course": {"favori_ecrasant": False, "ecart_favori": 0.0, "dispersion": 0.0},
               "chevaux": [{"numero_corde": 1, "nom_cheval": "X", "rang": 1, "value": None}]}
    out = analyse_deterministe(signals, ["SIMPLE_GAGNANT"])
    assert out["coup_de_coeur_value"] is None
