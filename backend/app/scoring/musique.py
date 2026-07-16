"""Parsing de la musique PMU (historique compact des performances) en score de forme.

Format : suite de perfs récente→ancienne, chaque perf = <résultat><discipline>.
Résultat : '1'..'9' = place à l'arrivée, '0' = non-placé/au-delà,
'D'/'T'/'A'/'R' = disqualifié/tombé/arrêté/rétrogradé (mauvaise perf).
Les marqueurs d'année entre parenthèses (ex '(25)') sont ignorés.
"""

import re
from typing import Optional

from app.scoring.context_stats import MIN_SAMPLE, SUCCESS_MAX_PLACE

# Un token de perf = un caractère résultat suivi d'une lettre de discipline.
_PERF_RE = re.compile(r"([0-9DTARdtar])([a-zA-Z])")

# Score par place : 1er le meilleur, décroissant ; non-placé/disqualifié = 0.
_PLACE_SCORE = {1: 1.0, 2: 0.85, 3: 0.70, 4: 0.55, 5: 0.45, 6: 0.35, 7: 0.25, 8: 0.15, 9: 0.10}


def parse_musique(musique: Optional[str]) -> list[Optional[int]]:
    if not musique:
        return []
    cleaned = re.sub(r"\([^)]*\)", "", musique)  # retire les marqueurs d'année
    places: list[Optional[int]] = []
    for match in _PERF_RE.finditer(cleaned):
        result = match.group(1).upper()
        if result.isdigit() and result != "0":
            places.append(int(result))
        else:  # '0', D, T, A, R -> non-placé
            places.append(None)
    return places


def forme_score(musique: Optional[str], n: int = 5) -> float:
    places = parse_musique(musique)[:n]
    if not places:
        return 0.0
    # Poids dégressifs : la perf la plus récente pèse le plus (n, n-1, ..., 1).
    weights = list(range(len(places), 0, -1))
    total_weight = sum(weights)
    score = 0.0
    for place, weight in zip(places, weights):
        per_race = _PLACE_SCORE.get(place, 0.0) if place is not None else 0.0
        score += per_race * weight
    return score / total_weight


# Lettre de discipline de la musique -> discipline de scoring. Lettre inconnue -> None.
_DISCIPLINE_LETTRE = {
    "a": "trot_attele", "m": "trot_monte", "p": "plat",
    "h": "obstacle", "s": "obstacle", "c": "obstacle", "o": "obstacle",
}


def parse_musique_disciplines(musique: Optional[str]) -> list[tuple[Optional[int], Optional[str]]]:
    """Comme parse_musique, mais conserve la discipline de chaque course passée."""
    if not musique:
        return []
    cleaned = re.sub(r"\([^)]*\)", "", musique)
    out: list[tuple[Optional[int], Optional[str]]] = []
    for match in _PERF_RE.finditer(cleaned):
        result = match.group(1).upper()
        place = int(result) if result.isdigit() and result != "0" else None
        out.append((place, _DISCIPLINE_LETTRE.get(match.group(2).lower())))
    return out


def taux_discipline_musique(musique: Optional[str], discipline: Optional[str]) -> Optional[float]:
    """Taux de top-3 sur les courses de la musique courues dans `discipline`.

    Mêmes règles que context_stats : None si < MIN_SAMPLE courses dans la discipline ;
    DNF (place None) compte au dénominateur, pas au numérateur.
    """
    if discipline is None:
        return None  # sans cette garde, d == discipline matcherait les lettres inconnues
    places = [p for p, d in parse_musique_disciplines(musique) if d == discipline]
    if len(places) < MIN_SAMPLE:
        return None
    succes = sum(1 for p in places if p is not None and p <= SUCCESS_MAX_PLACE)
    return succes / len(places)
