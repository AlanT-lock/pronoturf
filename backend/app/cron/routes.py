"""Job quotidien : capture des arrivées + import/score du jour + snapshot hebdo.

Déclenché par Vercel Cron (GET /cron/daily, Authorization: Bearer CRON_SECRET).
Chaque course est traitée sous try/except : une erreur PMU (course purgée, réseau)
est comptée dans `errors`, jamais fatale au run.
"""

import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException

from app.backtest.routes import capture_one_resultats, post_backtest_snapshot
from app.config import settings
from app.pmu_client import fetch_programme
from app.pmu_normalizer import normalize_programme
from app.scoring.routes import score_and_persist
from app.supabase_client import get_supabase_client

router = APIRouter()

CAPTURE_WINDOW_DAYS = 7


def _today_paris() -> date:
    """Journée hippique courante (les courses vont jusqu'à ~minuit heure de Paris)."""
    return datetime.now(ZoneInfo("Europe/Paris")).date()


@router.get("/cron/daily")
async def cron_daily(
    client=Depends(get_supabase_client),
    authorization: str | None = Header(None),
) -> dict:
    if not settings.cron_secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET non configuré")
    if not authorization or not secrets.compare_digest(
        authorization, f"Bearer {settings.cron_secret}"
    ):
        raise HTTPException(status_code=401, detail="Non autorisé")

    today = _today_paris()
    errors: list[str] = []

    # --- 1) Capture des arrivées des courses non terminées (fenêtre 7 jours). ---
    captured = 0
    try:
        courses = client.table("courses").select("id, reunion_id, numero_course, statut").execute().data
        pending = [c for c in courses if c.get("statut") != "terminee"]  # FakeStore: pas de .neq()
        dates_by_reunion: dict[str, str] = {}
        reunion_ids = list({c["reunion_id"] for c in pending})
        if reunion_ids:
            for r in client.table("reunions").select("id, date").in_("id", reunion_ids).execute().data:
                dates_by_reunion[r["id"]] = r["date"]
        cutoff = today - timedelta(days=CAPTURE_WINDOW_DAYS)
        for c in pending:
            try:
                d = dates_by_reunion.get(c["reunion_id"])
                if d is None or date.fromisoformat(d) < cutoff:
                    continue  # PMU purge les vieux programmes : on arrête de réessayer
                out = await capture_one_resultats(client, c["id"])
                if out.get("captured"):
                    captured += 1
            except Exception as e:
                errors.append(f"capture {c['id'][:8]}: {str(e)[:80]}")
    except Exception as e:
        errors.append(f"capture-setup: {str(e)[:80]}")

    # --- 2) Import + score de toutes les courses du jour (pas d'analyse LLM : coût). ---
    # Import tardif : app.main inclut ce routeur, un import module-level créerait un cycle.
    from app.main import import_one_course

    imported = scored = 0
    ddmmyyyy = today.strftime("%d%m%Y")
    try:
        programme = normalize_programme(await fetch_programme(ddmmyyyy))
        for reunion in programme["reunions"]:
            for course in reunion["courses"]:
                label = f"R{reunion['numero_reunion']}C{course['numero_course']}"
                try:
                    res = await import_one_course(
                        client, ddmmyyyy, reunion["numero_reunion"], course["numero_course"]
                    )
                    imported += 1
                    score_and_persist(client, res["course_id"])
                    scored += 1
                except Exception as e:
                    errors.append(f"{label}: {str(e)[:80]}")
    except Exception as e:
        errors.append(f"programme: {str(e)[:80]}")

    # --- 3) Snapshot backtest hebdomadaire (dimanche). ---
    snapshot = False
    if today.weekday() == 6:
        try:
            post_backtest_snapshot(client)
            snapshot = True
        except HTTPException:
            pass  # rien à évaluer -> pas un échec du cron
        except Exception as e:
            errors.append(f"snapshot: {str(e)[:80]}")

    return {"date": today.isoformat(), "captured": captured, "imported": imported,
            "scored": scored, "snapshot": snapshot, "errors": errors}
