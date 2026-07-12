"""Moteur de scoring : combine les facteurs normalisés et les poids en un score classé.

Les facteurs dont le poids est 0 ou qui ne sont pas calculés (indisponibles au Plan 2)
voient leur poids redistribué proportionnellement sur les facteurs disponibles, de sorte
que la somme des poids effectifs vaille toujours 1.
"""

from app.scoring.factors import compute_factors


def score_course(partants: list[dict], discipline: str, poids: dict[str, float]) -> list[dict]:
    factors_by_corde = compute_factors(partants, discipline)
    if not factors_by_corde:
        return []

    # Facteurs réellement disponibles = ceux calculés ET de poids > 0.
    any_corde = next(iter(factors_by_corde.values()))
    available = [f for f in any_corde.keys() if poids.get(f, 0.0) > 0.0]
    weight_sum = sum(poids[f] for f in available)
    if weight_sum <= 0:
        # Aucun poids exploitable : répartition uniforme sur les facteurs calculés.
        effective = {f: 1.0 / len(any_corde) for f in any_corde}
    else:
        effective = {f: poids[f] / weight_sum for f in available}

    scored = []
    for corde, factor_values in factors_by_corde.items():
        details = {}
        total = 0.0
        for f, eff in effective.items():
            value = factor_values.get(f, 0.0)
            contribution = eff * value
            details[f] = {"valeur": value, "poids_effectif": eff, "contribution": contribution}
            total += contribution
        scored.append({"numero_corde": corde, "score_total": total, "details_facteurs": details})

    scored.sort(key=lambda r: r["score_total"], reverse=True)
    for rang, row in enumerate(scored, start=1):
        row["rang"] = rang
    return scored
