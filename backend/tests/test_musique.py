from app.scoring.musique import (
    forme_score,
    parse_musique,
    parse_musique_disciplines,
    taux_discipline_musique,
)


def test_parse_musique_extracts_places_recent_first():
    # 7aDm5a(25)6m... -> 7e, disqualifié, 5e, 6e, ...
    places = parse_musique("7aDm5a(25)6mDm9m3mDm9m")
    assert places[0] == 7
    assert places[1] is None  # D = disqualifié
    assert places[2] == 5
    assert places[3] == 6


def test_parse_musique_zero_is_unplaced():
    places = parse_musique("1a0a2a")
    assert places == [1, None, 2]


def test_parse_musique_empty_returns_empty():
    assert parse_musique("") == []
    assert parse_musique(None) == []


def test_forme_score_winner_higher_than_backmarker():
    good = forme_score("1a1a2a1a2a")
    bad = forme_score("0a0aDa9a8a")
    assert good > bad
    assert 0.0 <= good <= 1.0
    assert 0.0 <= bad <= 1.0


def test_forme_score_recent_weighted_more():
    # même perfs, ordre inversé : la bonne perf récente doit scorer plus haut
    recent_good = forme_score("1a9a9a9a9a")
    recent_bad = forme_score("9a9a9a9a1a")
    assert recent_good > recent_bad


def test_forme_score_empty_is_zero():
    assert forme_score(None) == 0.0
    assert forme_score("") == 0.0


def test_parse_disciplines_musique_reelle():
    # JAINA D'ESSARTS : 9 courses attelé, places 3,1,1,3,7 puis 3 disqualifications puis 2e.
    out = parse_musique_disciplines("3a1a1a3a7a(25)DaDaDa2a")
    assert len(out) == 9
    assert all(d == "trot_attele" for _, d in out)
    assert [p for p, _ in out] == [3, 1, 1, 3, 7, None, None, None, 2]


def test_parse_disciplines_mapping_complet():
    out = parse_musique_disciplines("1a2m3p4h5s6c7o")
    assert [d for _, d in out] == [
        "trot_attele", "trot_monte", "plat",
        "obstacle", "obstacle", "obstacle", "obstacle",
    ]


def test_parse_disciplines_lettre_inconnue_et_vide():
    assert parse_musique_disciplines("1x2a") == [(1, None), (2, "trot_attele")]
    assert parse_musique_disciplines(None) == []
    assert parse_musique_disciplines("") == []


def test_taux_discipline_musique_calcule():
    # 9 courses attelé : top-3 = 3,1,1,3,2 -> 5 succès ; Da (None) au dénominateur.
    assert abs(taux_discipline_musique("3a1a1a3a7a(25)DaDaDa2a", "trot_attele") - 5 / 9) < 1e-9


def test_taux_discipline_musique_dnf_au_denominateur():
    assert abs(taux_discipline_musique("1aDaDa", "trot_attele") - 1 / 3) < 1e-9


def test_taux_discipline_musique_gates():
    # Mauvaise discipline (0 course de plat) -> None.
    assert taux_discipline_musique("3a1a1a3a7a", "plat") is None
    # Sous MIN_SAMPLE (2 courses attelé) -> None.
    assert taux_discipline_musique("1a2a", "trot_attele") is None
    # discipline None ne matche PAS les lettres inconnues.
    assert taux_discipline_musique("1x2x3x", None) is None
    assert taux_discipline_musique(None, "plat") is None
