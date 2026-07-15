"""Endpoints de la boucle de mesure : capture des arrivées + évaluation/backtest."""

from datetime import date as _date

from fastapi import APIRouter, Depends, HTTPException

from app.pmu_client import fetch_participants, fetch_programme
from app.pmu_normalizer import find_course_in_programme, normalize_course, normalize_partants
from app.scoring.routes import _get_course_or_404
from app.supabase_client import get_supabase_client
from app.supabase_writer import SupabaseWriter

router = APIRouter()


def _reunion_of(client, course: dict) -> dict:
    rows = (
        client.table("reunions")
        .select("date, numero_reunion")
        .eq("id", course["reunion_id"])
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Réunion introuvable")
    return rows[0]


@router.post("/courses/{course_id}/resultats")
async def capture_resultats(course_id: str, client=Depends(get_supabase_client)) -> dict:
    course = _get_course_or_404(client, course_id)
    reunion = _reunion_of(client, course)
    ddmmyyyy = _date.fromisoformat(reunion["date"]).strftime("%d%m%Y")

    programme = await fetch_programme(ddmmyyyy)
    raw_reunion, raw_course = find_course_in_programme(
        programme, reunion["numero_reunion"], course["numero_course"]
    )
    course_norm = normalize_course(raw_reunion, raw_course)
    if course_norm.statut != "terminee":
        return {"course_id": course_id, "captured": False,
                "statut": course_norm.statut, "nb_resultats": 0}

    raw_participants = await fetch_participants(
        ddmmyyyy, reunion["numero_reunion"], course["numero_course"]
    )
    partants = normalize_partants(raw_participants["participants"], course_terminee=True)

    existing = (
        client.table("partants").select("id, numero_corde").eq("course_id", course_id).execute().data
    )
    partant_id_by_corde = {p["numero_corde"]: p["id"] for p in existing}

    n = SupabaseWriter(client).save_resultats(course_id, partants, partant_id_by_corde)
    client.table("courses").update({"statut": "terminee"}).eq("id", course_id).execute()
    return {"course_id": course_id, "captured": True, "statut": "terminee", "nb_resultats": n}
