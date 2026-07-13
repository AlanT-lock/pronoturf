"""Pondérations de scoring : valeurs par défaut par discipline + chargement/seed depuis la DB.

Les 11 facteurs (forme, cote, taux_reussite, ferrage_poids, corde, taux_distance,
taux_discipline, taux_niveau, taux_hippodrome, jockey, entraineur) ont un poids par défaut
identique pour toutes les disciplines. La somme des poids vaut 1.0 par discipline.
"""

_POIDS_V1 = {
    "forme": 0.16, "cote": 0.18, "taux_reussite": 0.10, "ferrage_poids": 0.08, "corde": 0.08,
    "taux_distance": 0.10, "taux_discipline": 0.06, "taux_niveau": 0.06,
    "taux_hippodrome": 0.06, "jockey": 0.06, "entraineur": 0.06,
}

DEFAULT_PONDERATIONS: dict[str, dict[str, float]] = {
    "trot_attele": dict(_POIDS_V1),
    "trot_monte": dict(_POIDS_V1),
    "plat": dict(_POIDS_V1),
    "obstacle": dict(_POIDS_V1),
}


def load_active_ponderation(client, discipline: str) -> dict:
    existing = (
        client.table("ponderations_config")
        .select("id, poids")
        .eq("discipline", discipline)
        .eq("actif", True)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]
    seeded = (
        client.table("ponderations_config")
        .insert(
            {
                "discipline": discipline,
                "nom": "defaut",
                "poids": DEFAULT_PONDERATIONS[discipline],
                "actif": True,
                "version": 1,
            }
        )
        .execute()
        .data[0]
    )
    return {"id": seeded["id"], "poids": seeded["poids"]}
