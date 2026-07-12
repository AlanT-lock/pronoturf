"""Pondérations de scoring : valeurs par défaut par discipline + chargement/seed depuis la DB.

Les facteurs Geny/historique (fraicheur, couple, entraineur) ont un poids 0 au Plan 2 ;
le moteur redistribue leur poids sur les facteurs disponibles. Ils passeront > 0 en Plan 3/4.
"""

# Poids par discipline. Somme = 1.0. fraicheur/couple/entraineur à 0 (différés).
DEFAULT_PONDERATIONS: dict[str, dict[str, float]] = {
    "trot_attele": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "trot_monte": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "plat": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "obstacle": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
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
