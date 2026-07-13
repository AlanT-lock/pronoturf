from app.models import CourseNormalized, PartantNormalized, PerformanceNormalized


class SupabaseWriter:
    def __init__(self, client):
        self._client = client

    def save_course_import(self, course: CourseNormalized, partants: list[PartantNormalized]) -> dict:
        hippodrome_row = (
            self._client.table("hippodromes")
            .upsert(
                {
                    "code_pmu": course.reunion.hippodrome.code_pmu,
                    "nom": course.reunion.hippodrome.nom,
                    "pays": course.reunion.hippodrome.pays,
                },
                on_conflict="code_pmu",
            )
            .execute()
            .data[0]
        )

        reunion_row = (
            self._client.table("reunions")
            .upsert(
                {
                    "date": course.reunion.date.isoformat(),
                    "hippodrome_id": hippodrome_row["id"],
                    "numero_reunion": course.reunion.numero_reunion,
                },
                on_conflict="date,numero_reunion",
            )
            .execute()
            .data[0]
        )

        course_row = (
            self._client.table("courses")
            .upsert(
                {
                    "reunion_id": reunion_row["id"],
                    "numero_course": course.numero_course,
                    "discipline": course.discipline,
                    "distance_m": course.distance_m,
                    "categorie_classe": course.categorie_classe,
                    "heure_depart": course.heure_depart.isoformat(),
                    "statut": course.statut,
                    "allocation": course.allocation,
                },
                on_conflict="reunion_id,numero_course",
            )
            .execute()
            .data[0]
        )

        rider_role = "driver" if course.discipline == "trot_attele" else "jockey"

        partant_ids = []
        cheval_id_by_corde = {}
        for partant in partants:
            cheval_row = (
                self._client.table("chevaux")
                .upsert(
                    {
                        "nom": partant.nom_cheval,
                        "sexe": partant.sexe,
                        "id_pmu": partant.id_pmu_cheval,
                    },
                    on_conflict="id_pmu",
                )
                .execute()
                .data[0]
            )

            cheval_id_by_corde[partant.numero_corde] = cheval_row["id"]

            driver_jockey_id = None
            if partant.driver_jockey_nom:
                driver_jockey_id = (
                    self._client.table("intervenants")
                    .upsert(
                        {"nom": partant.driver_jockey_nom, "role": rider_role},
                        on_conflict="nom,role",
                    )
                    .execute()
                    .data[0]["id"]
                )

            entraineur_id = None
            if partant.entraineur_nom:
                entraineur_id = (
                    self._client.table("intervenants")
                    .upsert(
                        {"nom": partant.entraineur_nom, "role": "entraineur"},
                        on_conflict="nom,role",
                    )
                    .execute()
                    .data[0]["id"]
                )

            partant_row = (
                self._client.table("partants")
                .upsert(
                    {
                        "course_id": course_row["id"],
                        "cheval_id": cheval_row["id"],
                        "numero_corde": partant.numero_corde,
                        "place_corde": partant.place_corde,
                        "driver_jockey_id": driver_jockey_id,
                        "entraineur_id": entraineur_id,
                        "poids_kg": partant.poids_kg,
                        "reduction_kilometrique": partant.reduction_kilometrique,
                        "ferrage": partant.ferrage,
                        "musique": partant.musique,
                        "statut": partant.statut,
                        "age": partant.age,
                        "nombre_courses": partant.nombre_courses,
                        "nombre_victoires": partant.nombre_victoires,
                        "nombre_places": partant.nombre_places,
                        "gains_carriere": partant.gains_carriere,
                        "gains_annee_en_cours": partant.gains_annee_en_cours,
                    },
                    on_conflict="course_id,numero_corde",
                )
                .execute()
                .data[0]
            )
            partant_ids.append(partant_row["id"])

            for cote in partant.cotes:
                self._client.table("cotes").upsert(
                    {
                        "partant_id": partant_row["id"],
                        "type_capture": cote.type_capture,
                        "valeur": cote.valeur,
                        "capture_at": cote.capture_at.isoformat(),
                    },
                    on_conflict="partant_id,type_capture",
                ).execute()

        return {"course_id": course_row["id"], "partant_ids": partant_ids,
                "cheval_id_by_corde": cheval_id_by_corde}

    def save_performances(self, perf_by_num_pmu, cheval_id_by_corde) -> int:
        n = 0
        for num_pmu, perfs in perf_by_num_pmu.items():
            cheval_id = cheval_id_by_corde.get(num_pmu)
            if cheval_id is None:
                continue
            for perf in perfs:
                self._client.table("chevaux_performances").upsert(
                    {
                        "cheval_id": cheval_id,
                        "date_course": perf.date_course.isoformat(),
                        "hippodrome": perf.hippodrome,
                        "discipline": perf.discipline,
                        "distance_m": perf.distance_m,
                        "allocation": perf.allocation,
                        "nb_participants": perf.nb_participants,
                        "place": perf.place,
                        "status_arrivee": perf.status_arrivee,
                        "raw_place": perf.raw_place,
                        "jockey_nom": perf.jockey_nom,
                        "poids_jockey": perf.poids_jockey,
                        "corde": perf.corde,
                        "oeillere": perf.oeillere,
                    },
                    on_conflict="cheval_id,date_course,hippodrome,distance_m",
                ).execute()
                n += 1
        return n

    def save_entraineur_resultats(self, course, partants, cheval_id_by_corde) -> int:
        n = 0
        for partant in partants:
            cheval_id = cheval_id_by_corde.get(partant.numero_corde)
            if not partant.entraineur_nom or cheval_id is None:
                continue
            self._client.table("entraineur_resultats").upsert(
                {
                    "entraineur_nom": partant.entraineur_nom,
                    "cheval_id": cheval_id,
                    "date_course": course.reunion.date.isoformat(),
                    "hippodrome": course.reunion.hippodrome.nom,
                    "discipline": course.discipline,
                    "place": partant.position_arrivee,
                    "status_arrivee": None,
                },
                on_conflict="entraineur_nom,cheval_id,date_course",
            ).execute()
            n += 1
        return n
