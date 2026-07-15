"""Évaluation pure du scoring déterministe contre les arrivées réelles.

- evaluate_course : par course, le n°1 prédit a-t-il gagné (top1) ? le vrai gagnant
  est-il dans nos 3 premiers rangs (top3) ?
- aggregate : précision top1/top3 + score de Brier de la confiance sur les courses évaluables.
- calibration_bins : courbe de fiabilité (confiance prédite vs taux de réussite réel).
"""


def evaluate_course(classement: list[dict], resultats_by_corde: dict[int, int]) -> dict:
    gagnant = next((c for c, pos in resultats_by_corde.items() if pos == 1), None)
    rang1 = next((r for r in classement if r["rang"] == 1), None)
    confiance_top1 = rang1.get("confiance") if rang1 else None
    if gagnant is None:
        return {"gagnant_reel": None, "rang_predit_du_gagnant": None,
                "top1_hit": False, "top3_hit": False, "confiance_top1": confiance_top1}
    rang_gagnant = next((r["rang"] for r in classement if r["numero_corde"] == gagnant), None)
    return {
        "gagnant_reel": gagnant,
        "rang_predit_du_gagnant": rang_gagnant,
        "top1_hit": rang1 is not None and rang1["numero_corde"] == gagnant,
        "top3_hit": rang_gagnant is not None and rang_gagnant <= 3,
        "confiance_top1": confiance_top1,
    }


def aggregate(evaluations: list[dict]) -> dict:
    evaluables = [e for e in evaluations if e["gagnant_reel"] is not None]
    if not evaluables:
        return {"nb_courses": 0, "precision_top1": None,
                "precision_top3": None, "brier_confiance": None}
    n = len(evaluables)
    top1 = sum(1 for e in evaluables if e["top1_hit"]) / n
    top3 = sum(1 for e in evaluables if e["top3_hit"]) / n
    briers = [
        (e["confiance_top1"] - (1.0 if e["top1_hit"] else 0.0)) ** 2
        for e in evaluables if e["confiance_top1"] is not None
    ]
    brier = sum(briers) / len(briers) if briers else None
    return {"nb_courses": n, "precision_top1": top1,
            "precision_top3": top3, "brier_confiance": brier}


def calibration_bins(pairs: list[tuple[float, bool]], n_bins: int = 5) -> list[dict]:
    edges = [i / n_bins for i in range(n_bins + 1)]  # [0,0.2,0.4,0.6,0.8,1.0]
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        # dernier bucket inclusif à droite pour capter confiance == 1.0
        in_bin = [
            (conf, hit) for conf, hit in pairs
            if conf is not None and (lo <= conf < hi or (i == n_bins - 1 and conf == hi))
        ]
        if not in_bin:
            continue
        m = len(in_bin)
        out.append({
            "bucket": f"{lo:.1f}–{hi:.1f}",
            "n": m,
            "confiance_moyenne": round(sum(c for c, _ in in_bin) / m, 4),
            "taux_top1_reel": round(sum(1 for _, h in in_bin if h) / m, 4),
        })
    return out
