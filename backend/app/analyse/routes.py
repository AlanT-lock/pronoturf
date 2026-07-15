"""Endpoints d'analyse IA d'une course (get/post/force) + persistance.

- GET  /courses/{id}/analyse        -> analyse stockée (404 si aucune).
- POST /courses/{id}/analyse        -> renvoie l'existante (zéro appel LLM) sinon
                                       score -> signaux -> analyser -> persiste.
- POST /courses/{id}/analyse?force=true -> ré-analyse (archive l'ancienne).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.analyse import signals as signals_mod
from app.analyse.llm import analyser
from app.scoring.routes import _get_course_or_404, score_and_persist
from app.supabase_client import get_supabase_client

router = APIRouter()

_ARCHIVE_COLS = (
    "course_id", "modele", "source", "recommandations", "lecture_globale",
    "coup_de_coeur_value", "input_snapshot", "confiance_globale", "created_at",
)


class AnalyseRequest(BaseModel):
    paris: list[str] = []


def _existing_analyse(client, course_id: str) -> dict | None:
    rows = (
        client.table("analyses_llm").select("*").eq("course_id", course_id).limit(1).execute().data
    )
    return rows[0] if rows else None


@router.get("/courses/{course_id}/analyse")
def get_analyse(course_id: str, client=Depends(get_supabase_client)) -> dict:
    _get_course_or_404(client, course_id)
    analyse = _existing_analyse(client, course_id)
    if not analyse:
        raise HTTPException(status_code=404, detail="Aucune analyse pour cette course")
    return analyse


@router.post("/courses/{course_id}/analyse")
def post_analyse(
    course_id: str,
    body: AnalyseRequest,
    force: bool = False,
    client=Depends(get_supabase_client),
) -> dict:
    _get_course_or_404(client, course_id)
    existing = _existing_analyse(client, course_id)
    if existing and not force:
        return existing

    classement = score_and_persist(client, course_id)
    sig = signals_mod.build_signals(classement)
    result = analyser(sig, body.paris)

    if existing:
        client.table("analyses_llm_historique").insert(
            {k: existing.get(k) for k in _ARCHIVE_COLS}
        ).execute()
        client.table("analyses_llm").delete().eq("course_id", course_id).execute()

    row = {
        "course_id": course_id,
        "modele": result["modele"],
        "source": result["source"],
        "recommandations": result["recommandations"],
        "lecture_globale": result["lecture_globale"],
        "coup_de_coeur_value": result["coup_de_coeur_value"],
        "input_snapshot": {"signaux": sig, "paris": body.paris},
        "confiance_globale": result["confiance_globale"],
    }
    return client.table("analyses_llm").insert(row).execute().data[0]
