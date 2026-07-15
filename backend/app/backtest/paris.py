"""Résolution des paris LLM contre l'arrivée réelle (désordre, placé simplifié).

Base sur la `selection` de la reco. Placé = top-K (K=3 si nb_partants>=8 sinon 2).
`gagnant`: True/False si résolu, None si l'arrivée n'a pas de gagnant (course non
résolue) ou si le type n'est pas géré.
"""

from collections import defaultdict

PLACE_MIN_RUNNERS = 8
_SET_EQ = {"TRIO": 3, "TIERCE": 3, "QUARTE_PLUS": 4, "QUINTE_PLUS": 5}


def _places_payantes(nb_partants: int) -> int:
    return 3 if nb_partants >= PLACE_MIN_RUNNERS else 2


def resoudre_pari(recommandation: dict, arrivee: dict, nb_partants: int) -> dict:
    type_pari = recommandation["type_pari"]
    niveau = recommandation.get("niveau")
    sel = recommandation.get("selection") or []
    out = {"type_pari": type_pari, "niveau": niveau, "gagnant": None}

    if not any(p == 1 for p in arrivee.values()):
        return out  # course sans gagnant identifiable -> non résolu

    k = _places_payantes(nb_partants)
    places = {c for c, p in arrivee.items() if p is not None and p <= k}

    def topn(n: int) -> set:
        return {c for c, p in arrivee.items() if p is not None and p <= n}

    def pos(c):
        return arrivee.get(c)

    if type_pari == "SIMPLE_GAGNANT":
        res = len(sel) >= 1 and pos(sel[0]) == 1
    elif type_pari == "SIMPLE_PLACE":
        res = len(sel) >= 1 and sel[0] in places
    elif type_pari == "COUPLE_GAGNANT":
        res = len(sel) >= 2 and set(sel[:2]) == topn(2)
    elif type_pari == "COUPLE_PLACE":
        res = len(sel) >= 2 and sel[0] in places and sel[1] in places
    elif type_pari == "DEUX_SUR_QUATRE":
        res = sum(1 for c in sel if c in topn(4)) >= 2
    elif type_pari in _SET_EQ:
        n = _SET_EQ[type_pari]
        res = len(sel) >= n and set(sel[:n]) == topn(n)
    else:
        return out  # type non géré

    out["gagnant"] = bool(res)
    return out


def resoudre_analyse(recommandations: list[dict], arrivee: dict, nb_partants: int) -> list[dict]:
    return [resoudre_pari(r, arrivee, nb_partants) for r in recommandations]


def agreger_paris(resolus: list[dict]):
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])   # [nb, gagnants]
    by_niveau: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for it in resolus:
        if it.get("gagnant") is None:
            continue
        hit = 1 if it["gagnant"] else 0
        t = by_type[it["type_pari"]]
        t[0] += 1
        t[1] += hit
        niv = it.get("niveau")
        if niv:
            n = by_niveau[niv]
            n[0] += 1
            n[1] += hit
    par_type = [
        {"type_pari": k, "nb": v[0], "taux_reussite": round(v[1] / v[0], 4)}
        for k, v in sorted(by_type.items())
    ]
    par_niveau = [
        {"niveau": k, "nb": v[0], "taux_reussite": round(v[1] / v[0], 4)}
        for k, v in sorted(by_niveau.items())
    ]
    return par_type, par_niveau
