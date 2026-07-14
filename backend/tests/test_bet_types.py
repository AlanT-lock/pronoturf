from app import bet_types as bt


def test_map_paris_dedupes_online_variants():
    raw = ["SIMPLE_GAGNANT", "E_SIMPLE_GAGNANT", "SIMPLE_PLACE", "E_SIMPLE_PLACE", "QUINTE_PLUS"]
    assert bt.map_paris(raw) == ["QUINTE_PLUS", "SIMPLE_GAGNANT", "SIMPLE_PLACE"]


def test_map_paris_ignores_none():
    assert bt.map_paris(["TRIO", None, "E_TRIO"]) == ["TRIO"]


def test_est_quinte():
    assert bt.est_quinte(["SIMPLE_GAGNANT", "QUINTE_PLUS"]) is True
    assert bt.est_quinte(["SIMPLE_GAGNANT", "TRIO"]) is False


def test_libelle_known_and_fallback():
    assert bt.libelle("QUINTE_PLUS") == "Quinté+"
    assert bt.libelle("SIMPLE_GAGNANT") == "Simple Gagnant"
    assert bt.libelle("INCONNU_XYZ") == "INCONNU_XYZ"


def test_analysable_subset():
    assert "QUINTE_PLUS" in bt.ANALYSABLE
    assert "COUPLE_ORDRE" not in bt.ANALYSABLE  # affiché mais pas analysé
