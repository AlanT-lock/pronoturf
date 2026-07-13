"""Taux de réussite par contexte (distance/discipline/niveau/hippodrome) + indice de confiance.

Un taux vaut None quand l'échantillon est insuffisant (< MIN_SAMPLE) — le facteur est
alors OMIS pour ce cheval et le moteur redistribue son poids sur les facteurs présents
(pas de neutralisation à 0.5). Un succès = arrivé dans les 3 premiers.
"""

DISTANCE_BAND = 0.10
ALLOCATION_BAND = 0.30
SUCCESS_MAX_PLACE = 3
MIN_SAMPLE = 3
CONFIDENCE_FULL_AT = 10


def is_success(perf: dict) -> bool:
    place = perf.get("place")
    return place is not None and place <= SUCCESS_MAX_PLACE


def _taux(subset: list[dict]) -> float | None:
    if len(subset) < MIN_SAMPLE:
        return None
    return sum(1 for p in subset if is_success(p)) / len(subset)


def taux_distance(perfs: list[dict], distance_m: int | None) -> float | None:
    if not distance_m:
        return None
    lo, hi = distance_m * (1 - DISTANCE_BAND), distance_m * (1 + DISTANCE_BAND)
    return _taux([p for p in perfs if p.get("distance_m") is not None and lo <= p["distance_m"] <= hi])


def taux_discipline(perfs: list[dict], discipline: str | None) -> float | None:
    if not discipline:
        return None
    return _taux([p for p in perfs if p.get("discipline") == discipline])


def taux_niveau(perfs: list[dict], allocation: float | None) -> float | None:
    if not allocation:
        return None
    lo, hi = allocation * (1 - ALLOCATION_BAND), allocation * (1 + ALLOCATION_BAND)
    return _taux([p for p in perfs if p.get("allocation") is not None and lo <= p["allocation"] <= hi])


def taux_hippodrome(perfs: list[dict], hippodrome: str | None) -> float | None:
    if not hippodrome:
        return None
    return _taux([p for p in perfs if p.get("hippodrome") == hippodrome])


def confidence(nb_perfs: int, jockey_known: bool, entraineur_known: bool) -> float:
    base = min(1.0, nb_perfs / CONFIDENCE_FULL_AT)
    penalty = 1.0 - 0.15 * ((not jockey_known) + (not entraineur_known))
    return round(base * penalty, 4)
