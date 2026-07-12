from datetime import datetime, timezone

from app.models import (
    CourseNormalized,
    CoteNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)

_DISCIPLINE_MAP = {
    "PLAT": "plat",
    "ATTELE": "trot_attele",
    "MONTE": "trot_monte",
    # Mapping non vérifié en conditions réelles (aucune course obstacle
    # disponible au moment du test) — à confirmer dès une vraie course d'obstacle.
    "OBSTACLE": "obstacle",
    "STEEPLE-CHASE": "obstacle",
    "HAIES": "obstacle",
    "CROSS": "obstacle",
}


def find_course_in_programme(programme: dict, numero_reunion: int, numero_course: int) -> tuple[dict, dict]:
    for raw_reunion in programme["programme"]["reunions"]:
        if raw_reunion["numOfficiel"] != numero_reunion:
            continue
        for raw_course in raw_reunion["courses"]:
            if raw_course["numOrdre"] == numero_course:
                return raw_reunion, raw_course
    raise ValueError(f"Course R{numero_reunion}C{numero_course} introuvable dans le programme")


def normalize_course(raw_reunion: dict, raw_course: dict) -> CourseNormalized:
    hippodrome = HippodromeNormalized(
        code_pmu=raw_reunion["hippodrome"]["code"],
        nom=raw_reunion["hippodrome"]["libelleCourt"],
        pays=raw_reunion["pays"]["code"],
    )
    reunion = ReunionNormalized(
        date=datetime.fromtimestamp(raw_reunion["dateReunion"] / 1000, tz=timezone.utc).date(),
        numero_reunion=raw_reunion["numOfficiel"],
        hippodrome=hippodrome,
    )
    return CourseNormalized(
        numero_course=raw_course["numOrdre"],
        discipline=_DISCIPLINE_MAP[raw_course["discipline"]],
        distance_m=raw_course["distance"],
        categorie_classe=raw_course.get("categorieParticularite"),
        heure_depart=datetime.fromtimestamp(raw_course["heureDepart"] / 1000, tz=timezone.utc),
        statut="terminee" if raw_course.get("arriveeDefinitive") else "a_venir",
        reunion=reunion,
    )


def normalize_partants(raw_participants: list[dict], course_terminee: bool) -> list[PartantNormalized]:
    partants = []
    for raw in raw_participants:
        cotes = []
        if raw.get("dernierRapportReference") is not None:
            cotes.append(
                CoteNormalized(
                    type_capture="reference",
                    valeur=raw["dernierRapportReference"]["rapport"],
                    capture_at=datetime.now(tz=timezone.utc),
                )
            )
        if raw.get("dernierRapportDirect") is not None:
            cotes.append(
                CoteNormalized(
                    type_capture="finale" if course_terminee else "direct",
                    valeur=raw["dernierRapportDirect"]["rapport"],
                    capture_at=datetime.now(tz=timezone.utc),
                )
            )
        reduction = raw.get("reductionKilometrique")
        poids = raw.get("handicapPoids")
        partants.append(
            PartantNormalized(
                numero_corde=raw["numPmu"],
                nom_cheval=raw["nom"],
                id_pmu_cheval=raw["idCheval"],
                sexe=raw.get("sexe"),
                driver_jockey_nom=raw.get("driver"),
                entraineur_nom=raw.get("entraineur"),
                poids_kg=(poids / 10.0) if poids is not None else None,
                reduction_kilometrique=(reduction / 1000.0) if reduction is not None else None,
                ferrage=raw.get("deferre"),
                musique=raw.get("musique"),
                statut="partant" if raw["statut"] == "PARTANT" else "non_partant",
                cotes=cotes,
                position_arrivee=raw.get("ordreArrivee"),
            )
        )
    return partants
