"""Mapping des types de paris PMU vers des identifiants internes lisibles.

Les variantes en ligne sont préfixées `E_` (E_SIMPLE_GAGNANT == SIMPLE_GAGNANT).
`ANALYSABLE` = sous-ensemble stratégié par l'IA au Plan B ; les autres paris sont
affichés dans l'UI mais non analysés.
"""

ANALYSABLE = {
    "SIMPLE_GAGNANT", "SIMPLE_PLACE", "COUPLE_GAGNANT", "COUPLE_PLACE",
    "DEUX_SUR_QUATRE", "TRIO", "TIERCE", "QUARTE_PLUS", "QUINTE_PLUS",
}

LABELS = {
    "SIMPLE_GAGNANT": "Simple Gagnant", "SIMPLE_PLACE": "Simple Placé",
    "COUPLE_GAGNANT": "Couplé Gagnant", "COUPLE_PLACE": "Couplé Placé",
    "COUPLE_ORDRE": "Couplé Ordre", "DEUX_SUR_QUATRE": "2 sur 4",
    "TRIO": "Trio", "TRIO_ORDRE": "Trio Ordre", "TIERCE": "Tiercé",
    "QUARTE_PLUS": "Quarté+", "QUINTE_PLUS": "Quinté+", "MULTI": "Multi",
    "MINI_MULTI": "Mini Multi", "SUPER_QUATRE": "Super Quatre",
    "PICK5": "Pick 5", "REPORT_PLUS": "Report+",
}


def _base_code(type_pari: str) -> str:
    return type_pari[2:] if type_pari.startswith("E_") else type_pari


def map_paris(raw_types) -> list[str]:
    return sorted({_base_code(t) for t in raw_types if t})


def est_quinte(codes) -> bool:
    return "QUINTE_PLUS" in codes


def libelle(code: str) -> str:
    return LABELS.get(code, code)
