"""Taux de réussite globaux jockey/entraîneur, agrégés à la volée depuis les tables
d'historique (pas de compteurs maintenus). None si échantillon insuffisant."""

from app.scoring.context_stats import MIN_SAMPLE, SUCCESS_MAX_PLACE


def _taux_from_rows(rows: list[dict]) -> float | None:
    if len(rows) < MIN_SAMPLE:
        return None
    succ = sum(1 for r in rows if r.get("place") is not None and r["place"] <= SUCCESS_MAX_PLACE)
    return succ / len(rows)


def jockey_taux(client, jockey_nom: str | None) -> float | None:
    if not jockey_nom:
        return None
    rows = (
        client.table("chevaux_performances")
        .select("place")
        .eq("jockey_nom", jockey_nom)
        .execute()
        .data
    )
    return _taux_from_rows(rows)


def entraineur_taux(client, entraineur_nom: str | None) -> float | None:
    if not entraineur_nom:
        return None
    rows = (
        client.table("entraineur_resultats")
        .select("place")
        .eq("entraineur_nom", entraineur_nom)
        .execute()
        .data
    )
    return _taux_from_rows(rows)
