"""Repli déterministe : analyse par règles quand le LLM est indisponible.

Produit la même forme de sortie que le chemin LLM, marquée `source="regles"` :
sélections dérivées du classement, confiance heuristique, avis gabarit.
"""

from app import bet_types

# Taille de sélection par type de pari (nombre de chevaux à retenir).
_TAILLE = {
    "SIMPLE_GAGNANT": 1, "SIMPLE_PLACE": 1,
    "COUPLE_GAGNANT": 2, "COUPLE_PLACE": 2,
    "DEUX_SUR_QUATRE": 4, "TRIO": 3, "TIERCE": 3,
    "QUARTE_PLUS": 4, "QUINTE_PLUS": 5,
}


def _niveau(confiance: int) -> str:
    if confiance >= 66:
        return "eleve"
    if confiance >= 40:
        return "moyen"
    return "faible"


def analyse_deterministe(signals: dict, paris: list[str]) -> dict:
    ordered = sorted(signals["chevaux"], key=lambda c: c["rang"])
    nums = [c["numero_corde"] for c in ordered]
    forme = signals["forme_course"]
    base_conf = 70 if forme.get("favori_ecrasant") else 45

    recommandations = []
    for code in [p for p in paris if p in bet_types.ANALYSABLE]:
        taille = _TAILLE.get(code, 1)
        selection = nums[:taille]
        confiance = max(10, base_conf - 5 * (taille - 1))
        combine = taille > 1
        recommandations.append({
            "type_pari": code,
            "selection": selection,
            "base": selection[:1] if combine else [],
            "tournant": selection[1:] if combine else [],
            "confiance": confiance,
            "niveau": _niveau(confiance),
            "avis": (
                f"Sélection dérivée du classement pour {bet_types.libelle(code)} : "
                + ", ".join(f"n°{n}" for n in selection) + "."
            ),
        })

    values = [c for c in signals["chevaux"] if c.get("value") is not None and c["value"] > 0]
    coup = None
    if values:
        best = max(values, key=lambda c: c["value"])
        coup = {
            "numero_corde": best["numero_corde"],
            "raison": f"Sous-coté par le marché (value +{best['value']:.2f}).",
        }

    tete = ordered[0]["nom_cheval"] if ordered else "—"
    lecture = (
        ("Favori qui se détache" if forme.get("favori_ecrasant") else "Course ouverte")
        + f" ; en tête du modèle : {tete}."
    )
    return {
        "modele": "regles-v1",
        "lecture_globale": lecture,
        "recommandations": recommandations,
        "coup_de_coeur_value": coup,
        "confiance_globale": base_conf,
        "source": "regles",
    }
