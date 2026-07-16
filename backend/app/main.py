from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.pmu_client import fetch_participants, fetch_performances_detaillees, fetch_programme
from app.pmu_normalizer import (
    find_course_in_programme, normalize_course, normalize_partants,
    normalize_performances, normalize_programme,
)
from app.config import settings
from app.scoring.routes import router as scoring_router
from app.analyse.routes import router as analyse_router
from app.backtest.routes import router as backtest_router
from app.cron.routes import router as cron_router
from app.supabase_client import get_supabase_client
from app.supabase_writer import SupabaseWriter

app = FastAPI(title="pronoturf")
app.include_router(scoring_router)
app.include_router(analyse_router)
app.include_router(backtest_router)
app.include_router(cron_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/programme/{date}")
async def get_programme(date: str) -> dict:
    programme = await fetch_programme(date)
    return {"date": date, **normalize_programme(programme)}


class ImportCourseRequest(BaseModel):
    date: str
    numero_reunion: int
    numero_course: int


async def import_one_course(supabase_client, date_str: str, numero_reunion: int, numero_course: int) -> dict:
    """Importe une course (programme+participants+historique) ; réutilisé par l'endpoint et le cron."""
    programme = await fetch_programme(date_str)
    raw_reunion, raw_course = find_course_in_programme(programme, numero_reunion, numero_course)
    course = normalize_course(raw_reunion, raw_course)

    raw_participants = await fetch_participants(date_str, numero_reunion, numero_course)
    partants = normalize_partants(raw_participants["participants"], course_terminee=course.statut == "terminee")

    writer = SupabaseWriter(supabase_client)
    result = writer.save_course_import(course, partants)

    try:
        raw_perf = await fetch_performances_detaillees(date_str, numero_reunion, numero_course)
        perf_by_num_pmu = normalize_performances(raw_perf)
        writer.save_performances(perf_by_num_pmu, result["cheval_id_by_corde"])
    except Exception:
        # Historique indisponible : l'import reste valide, facteurs contextuels neutres au score.
        pass

    if course.statut == "terminee":
        writer.save_entraineur_resultats(course, partants, result["cheval_id_by_corde"])
        writer.save_resultats(result["course_id"], partants, result["partant_id_by_corde"])

    return {"course_id": result["course_id"], "partant_ids": result["partant_ids"]}


@app.post("/courses/import")
async def import_course(request: ImportCourseRequest, supabase_client=Depends(get_supabase_client)) -> dict:
    return await import_one_course(supabase_client, request.date, request.numero_reunion, request.numero_course)
