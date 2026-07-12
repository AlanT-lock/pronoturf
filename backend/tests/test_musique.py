from app.scoring.musique import forme_score, parse_musique


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
