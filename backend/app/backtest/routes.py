"""Endpoints de la boucle de mesure : capture des arrivées + évaluation/backtest."""

from datetime import date as _date

from fastapi import APIRouter, Depends, HTTPException

from app.backtest import evaluate as ev
from app.backtest.calibration import calibrate_confidence
from app.backtest.paris import agreger_paris, resoudre_analyse
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


async def capture_one_resultats(client, course_id: str) -> dict:
    """Capture l'arrivée réelle d'une course (re-fetch PMU) ; réutilisé par l'endpoint et le cron."""
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


@router.post("/courses/{course_id}/resultats")
async def capture_resultats(course_id: str, client=Depends(get_supabase_client)) -> dict:
    return await capture_one_resultats(client, course_id)


def _corde_by_partant(client, partant_ids: list[str]) -> dict[str, int]:
    if not partant_ids:
        return {}
    rows = (
        client.table("partants").select("id, numero_corde").in_("id", partant_ids).execute().data
    )
    return {r["id"]: r["numero_corde"] for r in rows}


def _evaluations(client) -> list[dict]:
    """Assemble, par course ayant pronostic ET résultat, le classement + l'arrivée, puis évalue."""
    scores = client.table("scores_pronostic").select("*").execute().data
    resultats = client.table("resultats").select("*").execute().data
    if not scores or not resultats:
        return []
    partant_ids = list({s["partant_id"] for s in scores} | {r["partant_id"] for r in resultats})
    corde = _corde_by_partant(client, partant_ids)

    scores_by_course: dict[str, list[dict]] = {}
    for s in scores:
        scores_by_course.setdefault(s["course_id"], []).append(s)
    res_by_course: dict[str, dict[int, int]] = {}
    for r in resultats:
        c = corde.get(r["partant_id"])
        if c is not None and r["position_arrivee"] is not None:
            res_by_course.setdefault(r["course_id"], {})[c] = r["position_arrivee"]

    evaluations = []
    for course_id, rows in scores_by_course.items():
        if course_id not in res_by_course:
            continue
        classement = [
            {"numero_corde": corde.get(s["partant_id"]),
             "rang": s["rang_pronostique"], "confiance": s.get("confiance")}
            for s in rows if corde.get(s["partant_id"]) is not None
        ]
        evaluations.append(ev.evaluate_course(classement, res_by_course[course_id]))
    return evaluations


def _paris_resolus(client):
    """Résout les paris de chaque analyse dont la course a un résultat.
    Renvoie (resolus: list, nb_courses_resolues: int)."""
    analyses = client.table("analyses_llm").select("course_id, recommandations").execute().data
    resultats = client.table("resultats").select("course_id, partant_id, position_arrivee").execute().data
    if not analyses or not resultats:
        return [], 0

    corde = _corde_by_partant(client, [r["partant_id"] for r in resultats])
    arrivee_by_course: dict[str, dict[int, int]] = {}
    for r in resultats:
        c = corde.get(r["partant_id"])
        if c is not None and r["position_arrivee"] is not None:
            arrivee_by_course.setdefault(r["course_id"], {})[c] = r["position_arrivee"]

    course_ids = [a["course_id"] for a in analyses if a["course_id"] in arrivee_by_course]
    nb_partants: dict[str, int] = {}
    if course_ids:
        for p in client.table("partants").select("course_id").in_("course_id", course_ids).execute().data:
            nb_partants[p["course_id"]] = nb_partants.get(p["course_id"], 0) + 1

    resolus = []
    courses_resolues = set()
    for a in analyses:
        cid = a["course_id"]
        if cid not in arrivee_by_course:
            continue
        arrivee = arrivee_by_course[cid]
        items = resoudre_analyse(a.get("recommandations") or [], arrivee, nb_partants.get(cid, len(arrivee)))
        items = [it for it in items if it["gagnant"] is not None]
        if items:
            courses_resolues.add(cid)
        resolus.extend(items)
    return resolus, len(courses_resolues)


def _pairs(evaluations: list[dict]) -> list[tuple]:
    return [
        (e["confiance_top1"], e["top1_hit"])
        for e in evaluations
        if e["gagnant_reel"] is not None and e["confiance_top1"] is not None
    ]


@router.get("/backtest")
def get_backtest(client=Depends(get_supabase_client)) -> dict:
    evaluations = _evaluations(client)
    agg = ev.aggregate(evaluations)
    pairs = _pairs(evaluations)
    gate = calibrate_confidence(pairs)
    resolus, nb_analyses_resolues = _paris_resolus(client)
    par_type, par_niveau = agreger_paris(resolus)
    return {
        **agg,
        "calibration": ev.calibration_bins(pairs),
        "calibration_gate": {k: gate[k] for k in ("disponible", "nb_paires", "seuil") if k in gate},
        "paris": {
            "nb_analyses_resolues": nb_analyses_resolues,
            "par_type": par_type,
            "par_niveau": par_niveau,
        },
    }


@router.post("/backtest/snapshot")
def post_backtest_snapshot(client=Depends(get_supabase_client)) -> dict:
    evaluations = _evaluations(client)
    agg = ev.aggregate(evaluations)
    if agg["nb_courses"] == 0:
        raise HTTPException(status_code=400, detail="Aucune course évaluable pour un snapshot")

    pond = client.table("ponderations_config").select("id").eq("actif", True).limit(1).execute().data
    ponderation_id = pond[0]["id"] if pond else None

    # Période = dates des courses RÉELLEMENT couvertes (pronostic ET résultat),
    # pas toutes les courses scorées.
    scored = {s["course_id"] for s in client.table("scores_pronostic").select("course_id").execute().data}
    resulted = {
        r["course_id"]
        for r in client.table("resultats").select("course_id, position_arrivee").execute().data
        if r["position_arrivee"] is not None
    }
    course_ids = list(scored & resulted)
    dates = []
    if course_ids:
        courses = client.table("courses").select("reunion_id").in_("id", course_ids).execute().data
        reunion_ids = list({c["reunion_id"] for c in courses})
        if reunion_ids:
            reunions = client.table("reunions").select("date").in_("id", reunion_ids).execute().data
            dates = sorted(r["date"] for r in reunions if r.get("date"))
    periode_debut = dates[0] if dates else None
    periode_fin = dates[-1] if dates else None

    row = {
        "ponderation_config_id": ponderation_id,
        "periode_debut": periode_debut,
        "periode_fin": periode_fin,
        "nb_courses": agg["nb_courses"],
        "precision_top1": agg["precision_top1"],
        "precision_top3": agg["precision_top3"],
    }
    return client.table("backtest_resultats").insert(row).execute().data[0]
