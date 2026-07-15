from app.backtest import paris as P


def R(type_pari, selection, niveau="moyen"):
    return {"type_pari": type_pari, "selection": selection, "niveau": niveau}


# Arrivée : corde 4 gagne, puis 1, 7, 8, 3, 9 ; 10 partants -> placé top 3.
ARR = {4: 1, 1: 2, 7: 3, 8: 4, 3: 5, 9: 6}
NB = 10


def test_places_payantes_seuil():
    assert P._places_payantes(8) == 3
    assert P._places_payantes(7) == 2


def test_simple_gagnant():
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", [4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", [1]), ARR, NB)["gagnant"] is False


def test_simple_place():
    assert P.resoudre_pari(R("SIMPLE_PLACE", [7]), ARR, NB)["gagnant"] is True   # 3e, top3
    assert P.resoudre_pari(R("SIMPLE_PLACE", [8]), ARR, NB)["gagnant"] is False  # 4e


def test_simple_place_seuil_petit_peloton():
    arr = {4: 1, 1: 2, 7: 3}
    # 3 partants -> placé top 2 : le 3e (corde 7) ne paie pas.
    assert P.resoudre_pari(R("SIMPLE_PLACE", [7]), arr, 3)["gagnant"] is False
    assert P.resoudre_pari(R("SIMPLE_PLACE", [1]), arr, 3)["gagnant"] is True


def test_couple_gagnant_desordre():
    assert P.resoudre_pari(R("COUPLE_GAGNANT", [1, 4]), ARR, NB)["gagnant"] is True   # {1,4}=={top2}
    assert P.resoudre_pari(R("COUPLE_GAGNANT", [4, 7]), ARR, NB)["gagnant"] is False


def test_couple_place():
    assert P.resoudre_pari(R("COUPLE_PLACE", [1, 7]), ARR, NB)["gagnant"] is True   # tous deux top3
    assert P.resoudre_pari(R("COUPLE_PLACE", [1, 8]), ARR, NB)["gagnant"] is False  # 8 = 4e


def test_deux_sur_quatre():
    assert P.resoudre_pari(R("DEUX_SUR_QUATRE", [4, 8, 9]), ARR, NB)["gagnant"] is True  # 4(1er),8(4e) dans top4
    assert P.resoudre_pari(R("DEUX_SUR_QUATRE", [4, 3, 9]), ARR, NB)["gagnant"] is False  # seul 4 dans top4


def test_trio_et_tierce_desordre():
    assert P.resoudre_pari(R("TRIO", [7, 4, 1]), ARR, NB)["gagnant"] is True      # {4,1,7}=={top3}
    assert P.resoudre_pari(R("TIERCE", [1, 7, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("TIERCE", [1, 7, 8]), ARR, NB)["gagnant"] is False


def test_quarte_quinte_desordre():
    assert P.resoudre_pari(R("QUARTE_PLUS", [8, 7, 1, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("QUINTE_PLUS", [3, 8, 7, 1, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("QUINTE_PLUS", [9, 8, 7, 1, 4]), ARR, NB)["gagnant"] is False  # 9=6e


def test_selection_trop_courte_perd():
    assert P.resoudre_pari(R("TIERCE", [4, 1]), ARR, NB)["gagnant"] is False
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", []), ARR, NB)["gagnant"] is False


def test_arrivee_sans_gagnant_non_resolu():
    out = P.resoudre_pari(R("SIMPLE_GAGNANT", [4]), {4: 2, 1: 3}, NB)
    assert out["gagnant"] is None


def test_niveau_propage():
    out = P.resoudre_pari(R("SIMPLE_GAGNANT", [4], niveau="eleve"), ARR, NB)
    assert out["niveau"] == "eleve" and out["type_pari"] == "SIMPLE_GAGNANT"


def test_resoudre_analyse_liste():
    recos = [R("SIMPLE_GAGNANT", [4]), R("TIERCE", [1, 7, 4])]
    out = P.resoudre_analyse(recos, ARR, NB)
    assert [o["gagnant"] for o in out] == [True, True]


def test_agreger_paris_par_type_et_niveau():
    resolus = [
        {"type_pari": "SIMPLE_GAGNANT", "niveau": "eleve", "gagnant": True},
        {"type_pari": "SIMPLE_GAGNANT", "niveau": "moyen", "gagnant": False},
        {"type_pari": "TIERCE", "niveau": "faible", "gagnant": True},
        {"type_pari": "TIERCE", "niveau": "faible", "gagnant": None},  # ignoré
    ]
    par_type, par_niveau = P.agreger_paris(resolus)
    by_t = {d["type_pari"]: d for d in par_type}
    assert by_t["SIMPLE_GAGNANT"] == {"type_pari": "SIMPLE_GAGNANT", "nb": 2, "taux_reussite": 0.5}
    assert by_t["TIERCE"] == {"type_pari": "TIERCE", "nb": 1, "taux_reussite": 1.0}
    by_n = {d["niveau"]: d for d in par_niveau}
    assert by_n["eleve"]["taux_reussite"] == 1.0 and by_n["eleve"]["nb"] == 1


def test_agreger_vide():
    assert P.agreger_paris([]) == ([], [])
