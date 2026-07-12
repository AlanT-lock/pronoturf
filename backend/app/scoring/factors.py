"""Calcul et normalisation sur [0,1] des facteurs de scoring dans le contexte d'une course.

Chaque facteur disponible au Plan 2 est calculé pour tous les partants d'une course, puis
normalisé relativement à la course (min-max ou inverse borné) pour être comparable.
"""

from typing import Optional

from app.scoring.musique import forme_score

# Score de déferrage (trot) : plus déferré = léger avantage supposé.
_FERRAGE_SCORE = {
    "DEFERRE_ANTERIEURS_POSTERIEURS": 1.0,
    "DEFERRE_ANTERIEURS": 0.7,
    "DEFERRE_POSTERIEURS": 0.6,
    None: 0.3,
}


def _minmax(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return (value - lo) / (hi - lo)


def compute_factors(partants: list[dict], discipline: str) -> dict[str, dict[str, float]]:
    actifs = [p for p in partants if p.get("statut") != "non_partant"]
    if not actifs:
        return {}
    is_trot = discipline in ("trot_attele", "trot_monte")

    # --- Cote : inverse (1/cote), min-max sur la course. Cote absente -> 0.
    inv_cotes = {}
    for p in actifs:
        c = p.get("cote_valeur")
        inv_cotes[p["numero_corde"]] = (1.0 / c) if c and c > 0 else 0.0
    inv_values = list(inv_cotes.values())
    lo_c, hi_c = min(inv_values), max(inv_values)

    # --- Taux de réussite : (victoires + places) / courses, borné [0,1].
    def taux(p: dict) -> float:
        courses = p.get("nombre_courses") or 0
        if courses <= 0:
            return 0.0
        num = (p.get("nombre_victoires") or 0) + (p.get("nombre_places") or 0)
        return min(num / courses, 1.0)

    # --- ferrage_poids : trot -> déferrage ; plat -> poids relatif inversé (léger = mieux).
    poids_values = [p.get("poids_kg") for p in actifs if p.get("poids_kg") is not None]
    lo_p = min(poids_values) if poids_values else 0.0
    hi_p = max(poids_values) if poids_values else 0.0

    def ferrage_poids(p: dict) -> float:
        if is_trot:
            return _FERRAGE_SCORE.get(p.get("ferrage"), 0.3)
        poids = p.get("poids_kg")
        if poids is None:
            return 0.5
        # poids faible -> score élevé : on inverse le min-max.
        return 1.0 - _minmax(poids, lo_p, hi_p)

    # --- Corde : numéro faible = léger avantage (surtout plat). Min-max inversé.
    cordes = [p["numero_corde"] for p in actifs]
    lo_n, hi_n = min(cordes), max(cordes)

    factors: dict[str, dict[str, float]] = {}
    for p in actifs:
        corde = p["numero_corde"]
        inv = inv_cotes[corde]
        factors[corde] = {
            "forme": forme_score(p.get("musique")),
            "taux_reussite": taux(p),
            "ferrage_poids": ferrage_poids(p),
            "cote": _minmax(inv, lo_c, hi_c),
            "corde": 1.0 - _minmax(corde, lo_n, hi_n),
        }
    return factors
