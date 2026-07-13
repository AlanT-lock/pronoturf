"""Moteur de scoring : combine les facteurs normalisés et les poids en un score classé.

La redistribution des poids est faite PAR CHEVAL : seuls les facteurs présents pour ce
cheval (les 5 de base + ceux dont l'historique suffit) et de poids > 0 sont retenus, et
leurs poids sont renormalisés pour sommer à 1. Un cheval sans données contextuelles
s'appuie donc pleinement sur les facteurs qu'il possède, sans bloc neutre 0.5 qui diluerait.
"""

from app.scoring.context_stats import confidence
from app.scoring.factors import compute_factors


def score_course(partants: list[dict], discipline: str, poids: dict[str, float],
                 course_context: dict) -> list[dict]:
    factors_by_corde = compute_factors(partants, discipline, course_context)
    if not factors_by_corde:
        return []

    partant_by_corde = {p["numero_corde"]: p for p in partants}

    scored = []
    for corde, factor_values in factors_by_corde.items():
        # Par cheval : uniquement les facteurs présents (dans factor_values) ET de poids > 0.
        available = [f for f in factor_values if poids.get(f, 0.0) > 0.0]
        weight_sum = sum(poids[f] for f in available)
        details = {}
        total = 0.0
        if weight_sum > 0:
            for f in available:
                eff = poids[f] / weight_sum
                value = factor_values[f]
                contribution = eff * value
                details[f] = {"valeur": value, "poids_effectif": eff, "contribution": contribution}
                total += contribution
        else:
            # Dégénéré : aucun facteur pondéré présent -> répartition uniforme sur les facteurs calculés.
            present = list(factor_values.keys())
            if present:
                eff = 1.0 / len(present)
                for f in present:
                    value = factor_values[f]
                    details[f] = {"valeur": value, "poids_effectif": eff, "contribution": eff * value}
                    total += eff * value

        p = partant_by_corde.get(corde, {})
        perfs = p.get("performances") or []
        conf = confidence(len(perfs), p.get("jockey_taux") is not None, p.get("entraineur_taux") is not None)
        scored.append({
            "numero_corde": corde, "score_total": total, "details_facteurs": details,
            "confiance": conf, "nb_courses_historique": len(perfs),
        })

    scored.sort(key=lambda r: r["score_total"], reverse=True)
    for rang, row in enumerate(scored, start=1):
        row["rang"] = rang
    return scored
