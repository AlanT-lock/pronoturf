from datetime import datetime, timezone

from app import bet_types
from app.models import (
    CourseNormalized,
    CoteNormalized,
    HippodromeNormalized,
    PartantNormalized,
    PerformanceNormalized,
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
        date=datetime.fromtimestamp(
            (raw_reunion["dateReunion"] + raw_reunion.get("timezoneOffset", 0)) / 1000,
            tz=timezone.utc,
        ).date(),
        numero_reunion=raw_reunion["numOfficiel"],
        hippodrome=hippodrome,
    )
    return CourseNormalized(
        numero_course=raw_course["numOrdre"],
        discipline=_DISCIPLINE_MAP[raw_course["discipline"]],
        distance_m=raw_course["distance"],
        allocation=raw_course.get("montantPrix"),
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
                place_corde=raw.get("placeCorde"),
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
                age=raw.get("age"),
                nombre_courses=raw.get("nombreCourses"),
                nombre_victoires=raw.get("nombreVictoires"),
                nombre_places=raw.get("nombrePlaces"),
                gains_carriere=(raw.get("gainsParticipant") or {}).get("gainsCarriere"),
                gains_annee_en_cours=(raw.get("gainsParticipant") or {}).get("gainsAnneeEnCours"),
            )
        )
    return partants


def normalize_performances(raw_perf: dict) -> dict[int, list[PerformanceNormalized]]:
    result: dict[int, list[PerformanceNormalized]] = {}
    for cheval in raw_perf.get("participants", []):
        num_pmu = cheval["numPmu"]
        perfs: list[PerformanceNormalized] = []
        for course in cheval.get("coursesCourues", []):
            moi = next(
                (pp for pp in course.get("participants", []) if pp.get("itsHim")),
                None,
            )
            if moi is None:
                continue
            place_obj = moi.get("place") or {}
            raw_discipline = course.get("discipline")
            discipline = _DISCIPLINE_MAP.get(raw_discipline, raw_discipline.lower() if raw_discipline else None)
            perfs.append(
                PerformanceNormalized(
                    num_pmu=num_pmu,
                    date_course=datetime.fromtimestamp(
                        (course["date"] + course.get("timezoneOffset", 0)) / 1000, tz=timezone.utc
                    ).date(),
                    hippodrome=course.get("hippodrome"),
                    discipline=discipline,
                    distance_m=course.get("distance"),
                    allocation=course.get("allocation"),
                    nb_participants=course.get("nbParticipants"),
                    place=place_obj.get("place"),
                    status_arrivee=place_obj.get("statusArrivee"),
                    raw_place=place_obj.get("rawValue"),
                    jockey_nom=moi.get("nomJockey"),
                    poids_jockey=moi.get("poidsJockey"),
                    corde=moi.get("corde"),
                    oeillere=moi.get("oeillere"),
                )
            )
        result[num_pmu] = perfs
    return result


def normalize_programme(programme: dict) -> dict:
    reunions = []
    for r in programme["programme"]["reunions"]:
        courses = []
        for c in r.get("courses", []):
            codes = bet_types.map_paris([p.get("typePari") for p in c.get("paris", [])])
            raw_disc = c.get("discipline")
            heure = c.get("heureDepart")
            courses.append({
                "numero_course": c["numOrdre"],
                "discipline": _DISCIPLINE_MAP.get(raw_disc, raw_disc.lower() if raw_disc else None),
                "distance_m": c.get("distance"),
                "heure_depart": (
                    datetime.fromtimestamp(heure / 1000, tz=timezone.utc).isoformat()
                    if heure is not None else None
                ),
                "statut": "terminee" if c.get("arriveeDefinitive") else "a_venir",
                "nombre_partants": c.get("nombreDeclaresPartants"),
                "allocation": c.get("montantPrix"),
                "paris": codes,
                "est_quinte": bet_types.est_quinte(codes),
            })
        reunions.append({
            "numero_reunion": r["numOfficiel"],
            "hippodrome": r["hippodrome"]["libelleCourt"],
            "pays": r["pays"]["code"],
            "courses": courses,
        })
    return {"reunions": reunions}
