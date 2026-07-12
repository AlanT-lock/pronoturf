from app.models import CourseNormalized, PartantNormalized


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
                },
                on_conflict="reunion_id,numero_course",
            )
            .execute()
            .data[0]
        )

        partant_ids = []
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

            driver_jockey_id = None
            if partant.driver_jockey_nom:
                driver_jockey_id = (
                    self._client.table("intervenants")
                    .upsert(
                        {"nom": partant.driver_jockey_nom, "role": "driver"},
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
                        "driver_jockey_id": driver_jockey_id,
                        "entraineur_id": entraineur_id,
                        "poids_kg": partant.poids_kg,
                        "reduction_kilometrique": partant.reduction_kilometrique,
                        "ferrage": partant.ferrage,
                        "musique": partant.musique,
                        "statut": partant.statut,
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
                    }
                ).execute()

        return {"course_id": course_row["id"], "partant_ids": partant_ids}
