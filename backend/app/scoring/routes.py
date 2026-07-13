"""Endpoints lecture / saisie manuelle / scoring pour une course.

Expose la lecture d'une course avec ses partants (stats + cote retenue), la saisie
manuelle de champs (état du terrain, ferrage/poids/RK d'un partant), le calcul du
pronostic (écrit dans scores_pronostic) et sa lecture.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.scoring import global_stats
from app.scoring.engine import score_course
from app.scoring.ponderations import load_active_ponderation
from app.supabase_client import get_supabase_client

router = APIRouter()


def _get_course_or_404(client, course_id: str) -> dict:
    rows = client.table("courses").select("*").eq("id", course_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Course introuvable")
    return rows[0]


def _get_partant_or_404(client, partant_id: str) -> dict:
    rows = client.table("partants").select("*").eq("id", partant_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Partant introuvable")
    return rows[0]


def _get_partants_for_course(client, course_id: str) -> list[dict]:
    return client.table("partants").select("*").eq("course_id", course_id).execute().data


def _retained_cote(client, partant_id: str) -> float | None:
    """Cote retenue pour un partant : finale si présente, sinon reference, sinon None."""
    cotes = client.table("cotes").select("*").eq("partant_id", partant_id).execute().data
    by_type = {c["type_capture"]: c["valeur"] for c in cotes}
    if "finale" in by_type:
        return by_type["finale"]
    return by_type.get("reference")


def _cheval_nom_par_partant(
    client, partant_ids: list[str]
) -> dict[str, tuple[int, str | None, str | None]]:
    """Map partant_id -> (numero_corde, nom_cheval, sexe), batché (une requête `partants`, une `chevaux`)."""
    if not partant_ids:
        return {}
    partants = (
        client.table("partants")
        .select("id, numero_corde, cheval_id")
        .in_("id", partant_ids)
        .execute()
        .data
    )
    cheval_ids = [p["cheval_id"] for p in partants if p.get("cheval_id")]
    chevaux = (
        client.table("chevaux").select("id, nom, sexe").in_("id", cheval_ids).execute().data
        if cheval_ids
        else []
    )
    cheval_by_id = {c["id"]: c for c in chevaux}
    return {
        p["id"]: (
            p["numero_corde"],
            (cheval_by_id.get(p["cheval_id"]) or {}).get("nom"),
            (cheval_by_id.get(p["cheval_id"]) or {}).get("sexe"),
        )
        for p in partants
    }


def _retained_cotes_par_partant(client, partant_ids: list[str]) -> dict[str, float | None]:
    """Cote retenue par partant (finale sinon reference sinon None), batché en une requête."""
    if not partant_ids:
        return {}
    cotes = client.table("cotes").select("*").in_("partant_id", partant_ids).execute().data
    by_partant: dict[str, dict[str, float]] = {}
    for c in cotes:
        by_partant.setdefault(c["partant_id"], {})[c["type_capture"]] = c["valeur"]
    return {
        partant_id: (types.get("finale") if "finale" in types else types.get("reference"))
        for partant_id, types in by_partant.items()
    }


def _course_context(client, course: dict) -> dict:
    hippodrome_nom = None
    reunion = (
        client.table("reunions").select("hippodrome_id").eq("id", course["reunion_id"]).limit(1).execute().data
    )
    if reunion:
        hippo = (
            client.table("hippodromes").select("nom").eq("id", reunion[0]["hippodrome_id"]).limit(1).execute().data
        )
        if hippo:
            hippodrome_nom = hippo[0]["nom"]
    return {"distance_m": course.get("distance_m"), "allocation": course.get("allocation"),
            "hippodrome": hippodrome_nom}


def _performances_par_cheval(client, cheval_ids: list[str]) -> dict[str, list[dict]]:
    if not cheval_ids:
        return {}
    rows = client.table("chevaux_performances").select("*").in_("cheval_id", cheval_ids).execute().data
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["cheval_id"], []).append(r)
    return out


def _jockey_entraineur_noms(client, partant: dict) -> tuple[str | None, str | None]:
    def nom(interv_id):
        if not interv_id:
            return None
        rows = client.table("intervenants").select("nom").eq("id", interv_id).limit(1).execute().data
        return rows[0]["nom"] if rows else None
    return nom(partant.get("driver_jockey_id")), nom(partant.get("entraineur_id"))


def _partant_dict_for_scoring(client, partant: dict, perfs: list[dict]) -> dict:
    jockey_nom, entraineur_nom = _jockey_entraineur_noms(client, partant)
    return {
        "numero_corde": partant["numero_corde"],
        "place_corde": partant.get("place_corde"),
        "musique": partant.get("musique"),
        "nombre_courses": partant.get("nombre_courses"),
        "nombre_victoires": partant.get("nombre_victoires"),
        "nombre_places": partant.get("nombre_places"),
        "cote_valeur": _retained_cote(client, partant["id"]),
        "poids_kg": partant.get("poids_kg"),
        "reduction_kilometrique": partant.get("reduction_kilometrique"),
        "ferrage": partant.get("ferrage"),
        "statut": partant.get("statut"),
        "performances": perfs,
        "jockey_taux": global_stats.jockey_taux(client, jockey_nom),
        "entraineur_taux": global_stats.entraineur_taux(client, entraineur_nom),
    }


@router.get("/courses/{course_id}")
def get_course(course_id: str, client=Depends(get_supabase_client)) -> dict:
    course = _get_course_or_404(client, course_id)
    partants = _get_partants_for_course(client, course_id)
    cheval_map = _cheval_nom_par_partant(client, [p["id"] for p in partants])
    enriched = []
    for partant in partants:
        jockey_nom, entraineur_nom = _jockey_entraineur_noms(client, partant)
        enriched.append({
            **partant,
            "partant_id": partant["id"],
            "cote_retenue": _retained_cote(client, partant["id"]),
            "nom_cheval": cheval_map.get(partant["id"], (None, None, None))[1],
            "sexe": cheval_map.get(partant["id"], (None, None, None))[2],
            "jockey_nom": jockey_nom,
            "entraineur_nom": entraineur_nom,
        })
    return {"course": course, "partants": enriched}


class CoursePatch(BaseModel):
    etat_terrain: str | None = None


@router.patch("/courses/{course_id}")
def patch_course(course_id: str, body: CoursePatch, client=Depends(get_supabase_client)) -> dict:
    course = _get_course_or_404(client, course_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return course
    return client.table("courses").update(updates).eq("id", course_id).execute().data[0]


class PartantPatch(BaseModel):
    ferrage: str | None = None
    poids_kg: float | None = None
    reduction_kilometrique: float | None = None


@router.patch("/partants/{partant_id}")
def patch_partant(partant_id: str, body: PartantPatch, client=Depends(get_supabase_client)) -> dict:
    existing = _get_partant_or_404(client, partant_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return existing

    champs_manuels = set(existing.get("champs_manuels") or [])
    champs_manuels |= set(updates.keys())
    updates["champs_manuels"] = sorted(champs_manuels)

    return client.table("partants").update(updates).eq("id", partant_id).execute().data[0]


@router.post("/courses/{course_id}/score")
def compute_score(course_id: str, client=Depends(get_supabase_client)) -> dict:
    course = _get_course_or_404(client, course_id)
    partants = _get_partants_for_course(client, course_id)
    partant_id_by_corde = {p["numero_corde"]: p["id"] for p in partants}
    perfs_par_cheval = _performances_par_cheval(client, [p["cheval_id"] for p in partants])
    partant_dicts = [
        _partant_dict_for_scoring(client, p, perfs_par_cheval.get(p["cheval_id"], []))
        for p in partants
    ]
    context = _course_context(client, course)

    ponderation = load_active_ponderation(client, course["discipline"])
    classement = score_course(partant_dicts, course["discipline"], ponderation["poids"], context)

    client.table("scores_pronostic").delete().eq("course_id", course_id).execute()

    if classement:
        rows = [
            {
                "course_id": course_id,
                "partant_id": partant_id_by_corde[row["numero_corde"]],
                "ponderation_config_id": ponderation["id"],
                "score_total": row["score_total"],
                "rang_pronostique": row["rang"],
                "details_facteurs": row["details_facteurs"],
            }
            for row in classement
        ]
        client.table("scores_pronostic").insert(rows).execute()

    cheval_map = _cheval_nom_par_partant(client, list(partant_id_by_corde.values()))
    enriched_classement = [
        {
            **row,
            "partant_id": partant_id_by_corde[row["numero_corde"]],
            "nom_cheval": cheval_map.get(
                partant_id_by_corde[row["numero_corde"]], (None, None, None)
            )[1],
        }
        for row in classement
    ]

    return {"course_id": course_id, "classement": enriched_classement}


@router.get("/courses/{course_id}/pronostic")
def get_pronostic(course_id: str, client=Depends(get_supabase_client)) -> dict:
    _get_course_or_404(client, course_id)
    rows = (
        client.table("scores_pronostic")
        .select("*")
        .eq("course_id", course_id)
        .order("rang_pronostique")
        .execute()
        .data
    )
    partant_ids = [r["partant_id"] for r in rows]
    cheval_map = _cheval_nom_par_partant(client, partant_ids)
    cote_map = _retained_cotes_par_partant(client, partant_ids)
    classement = [
        {
            "partant_id": r["partant_id"],
            "numero_corde": cheval_map.get(r["partant_id"], (None, None, None))[0],
            "nom_cheval": cheval_map.get(r["partant_id"], (None, None, None))[1],
            "score_total": r["score_total"],
            "rang": r["rang_pronostique"],
            "details_facteurs": r["details_facteurs"],
            "cote": cote_map.get(r["partant_id"]),
        }
        for r in rows
    ]
    return {"course_id": course_id, "classement": classement}
