from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.pmu_client import fetch_participants, fetch_programme
from app.pmu_normalizer import find_course_in_programme, normalize_course, normalize_partants
from app.supabase_client import get_supabase_client
from app.supabase_writer import SupabaseWriter

app = FastAPI(title="pronoturf")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


class ImportCourseRequest(BaseModel):
    date: str
    numero_reunion: int
    numero_course: int


@app.post("/courses/import")
async def import_course(request: ImportCourseRequest, supabase_client=Depends(get_supabase_client)) -> dict:
    programme = await fetch_programme(request.date)
    raw_reunion, raw_course = find_course_in_programme(programme, request.numero_reunion, request.numero_course)
    course = normalize_course(raw_reunion, raw_course)

    raw_participants = await fetch_participants(request.date, request.numero_reunion, request.numero_course)
    partants = normalize_partants(raw_participants["participants"], course_terminee=course.statut == "terminee")

    writer = SupabaseWriter(supabase_client)
    return writer.save_course_import(course, partants)
