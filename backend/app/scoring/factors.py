"""Calcul et normalisation sur [0,1] des facteurs de scoring dans le contexte d'une course.

Chaque facteur disponible est calculé pour tous les partants d'une course, puis
normalisé relativement à la course (min-max ou inverse borné) pour être comparable.
Les facteurs de taux contextuel (distance/discipline/niveau/hippodrome) et
jockey/entraineur sont des valeurs absolues [0,1] ; ils sont OMIS pour un cheval
quand l'historique est insuffisant (le moteur redistribue alors leur poids sur les
facteurs présents), tandis que cote/corde/poids restent relatifs à la course (min-max).
"""

from app.scoring import context_stats as cs
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


def compute_factors(partants: list[dict], discipline: str, course_context: dict) -> dict[int, dict[str, float]]:
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

    # --- Corde : vraie corde (place_corde) si dispo, sinon numero_corde. Faible = mieux.
    def corde_value(p: dict) -> int:
        return p.get("place_corde") if p.get("place_corde") is not None else p["numero_corde"]
    corde_vals = [corde_value(p) for p in actifs]
    lo_n, hi_n = min(corde_vals), max(corde_vals)

    dist = course_context.get("distance_m")
    allocation = course_context.get("allocation")
    hippo = course_context.get("hippodrome")

    # Les facteurs contextuels et jockey/entraineur ne sont inclus que lorsqu'ils reposent
    # sur assez de données ; sinon on OMET la clé (on ne met pas 0.5). Le moteur redistribue
    # alors leur poids par cheval sur les facteurs présents — pas de dilution à 0.5.
    factors: dict[int, dict[str, float]] = {}
    for p in actifs:
        corde = p["numero_corde"]
        inv = inv_cotes[corde]
        perfs = p.get("performances") or []
        f: dict[str, float] = {
            "forme": forme_score(p.get("musique")),
            "taux_reussite": taux(p),
            "ferrage_poids": ferrage_poids(p),
            "cote": _minmax(inv, lo_c, hi_c),
            "corde": 1.0 - _minmax(corde_value(p), lo_n, hi_n),
        }
        td = cs.taux_distance(perfs, dist)
        if td is not None:
            f["taux_distance"] = td
        tdi = cs.taux_discipline(perfs, discipline)
        if tdi is not None:
            f["taux_discipline"] = tdi
        tn = cs.taux_niveau(perfs, allocation)
        if tn is not None:
            f["taux_niveau"] = tn
        th = cs.taux_hippodrome(perfs, hippo)
        if th is not None:
            f["taux_hippodrome"] = th
        jt = p.get("jockey_taux")
        if jt is not None:
            f["jockey"] = jt
        et = p.get("entraineur_taux")
        if et is not None:
            f["entraineur"] = et
        factors[corde] = f
    return factors
