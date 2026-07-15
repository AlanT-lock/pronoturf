"""Calibration data-gated de l'indice de confiance.

Construit une correspondance empirique confiance -> taux de réussite réel, mais
UNIQUEMENT au-delà d'un seuil d'échantillon. En-dessous, renvoie « indisponible »
plutôt qu'une calibration bruitée. Non appliquée à la confiance affichée cet incrément.
"""

from app.backtest.evaluate import calibration_bins

MIN_PAIRS_CALIBRATION = 50


def calibrate_confidence(pairs: list[tuple[float, bool]]) -> dict:
    n = len(pairs)
    if n < MIN_PAIRS_CALIBRATION:
        return {"disponible": False, "raison": "données insuffisantes",
                "nb_paires": n, "seuil": MIN_PAIRS_CALIBRATION}
    return {"disponible": True, "nb_paires": n, "seuil": MIN_PAIRS_CALIBRATION,
            "mapping": calibration_bins(pairs)}
