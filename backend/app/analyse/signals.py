"""Signaux value pour l'analyse IA, dérivés du classement déterministe.

- `proba_modele` : softmax des scores (répartit la conviction du modèle).
- `proba_implicite_cote` : 1/cote normalisée sur les cotes présentes (retire l'overround).
- `value` : proba_modele - proba_implicite -> repère les chevaux sous-cotés par le marché.
- `forme_course` : favori écrasant vs course ouverte (écart #1↔#2, dispersion).
"""

import math

_KEEP = (
    "numero_corde", "nom_cheval", "score_total", "rang", "cote",
    "confiance", "nb_courses_historique", "jockey_nom", "entraineur_nom",
    "details_facteurs",
)


def softmax(scores: list[float], temperature: float = 0.15) -> list[float]:
    if not scores:
        return []
    m = max(scores)
    exps = [math.exp((x - m) / temperature) for x in scores]
    total = sum(exps)
    if total <= 0:
        return [1 / len(scores)] * len(scores)
    return [e / total for e in exps]


def proba_implicite(cotes: list[float | None]) -> list[float | None]:
    inv = [(1.0 / c if c and c > 0 else None) for c in cotes]
    total = sum(x for x in inv if x is not None)
    if total <= 0:
        return [None] * len(cotes)
    return [(x / total if x is not None else None) for x in inv]


def course_shape(scores: list[float]) -> dict:
    if len(scores) < 2:
        return {"favori_ecrasant": False, "ecart_favori": 0.0, "dispersion": 0.0}
    ordered = sorted(scores, reverse=True)
    ecart = ordered[0] - ordered[1]
    mean = sum(scores) / len(scores)
    dispersion = math.sqrt(sum((x - mean) ** 2 for x in scores) / len(scores))
    return {
        "favori_ecrasant": ecart >= 0.12,
        "ecart_favori": round(ecart, 4),
        "dispersion": round(dispersion, 4),
    }


def build_signals(classement: list[dict]) -> dict:
    scores = [c["score_total"] for c in classement]
    cotes = [c.get("cote") for c in classement]
    probas = softmax(scores)
    implicites = proba_implicite(cotes)
    chevaux = []
    for c, pm, pi in zip(classement, probas, implicites):
        value = (pm - pi) if pi is not None else None
        row = {k: c.get(k) for k in _KEEP}
        row["proba_modele"] = round(pm, 4)
        row["proba_implicite_cote"] = round(pi, 4) if pi is not None else None
        row["value"] = round(value, 4) if value is not None else None
        chevaux.append(row)
    return {"chevaux": chevaux, "forme_course": course_shape(scores)}
