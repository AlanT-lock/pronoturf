"""Analyse IA ancrée (Claude Opus 4.8), avec repli déterministe.

Le LLM reçoit nos signaux déterministes (scores, cotes, proba modèle, value, forme)
et produit des recommandations de paris ANCRÉES dessus, en sortie structurée.
Sans clé API ou en cas d'erreur, on bascule sur `analyse_deterministe`.
"""

import json
import os
from typing import Literal

from pydantic import BaseModel

from app import bet_types
from app.analyse.fallback import analyse_deterministe

MODELE = "claude-opus-4-8"

SYSTEM = (
    "Tu es un stratège de paris hippiques ANCRÉ, pas un oracle prédictif. "
    "Tu reçois le classement d'un modèle déterministe (scores, cotes, probabilité "
    "modèle, probabilité implicite de la cote, value) et la forme de la course. "
    "Règles : n'invente aucune donnée ; chaque sélection s'appuie sur les signaux "
    "fournis ; privilégie les value bets (value>0) pour la dimension surprise ; sois "
    "honnête sur les courses ouvertes et la faible confiance. La confiance est un "
    "indice relatif 0–100 (force de conviction), PAS une probabilité de gain. "
    "Ne propose de recommandation QUE pour les types de paris listés."
)


class Recommandation(BaseModel):
    type_pari: str
    selection: list[int]
    base: list[int] = []
    tournant: list[int] = []
    confiance: int
    niveau: Literal["faible", "moyen", "eleve"]
    avis: str


class CoupDeCoeur(BaseModel):
    numero_corde: int
    raison: str


class AnalyseLLM(BaseModel):
    lecture_globale: str
    recommandations: list[Recommandation]
    coup_de_coeur_value: CoupDeCoeur | None = None


def build_prompt(signals: dict, paris_analysables: list[str]) -> str:
    return (
        "Analyse cette course hippique et propose des paris ancrés sur les signaux.\n\n"
        f"Types de paris à analyser (uniquement ceux-ci) : {paris_analysables}\n\n"
        f"Forme de course : {json.dumps(signals['forme_course'], ensure_ascii=False)}\n\n"
        "Chevaux classés par le modèle déterministe (rang 1 = meilleur) :\n"
        + json.dumps(signals["chevaux"], ensure_ascii=False, indent=2)
    )


def _confiance_globale(recommandations: list[dict]) -> int | None:
    confs = [r["confiance"] for r in recommandations]
    return round(sum(confs) / len(confs)) if confs else None


def analyser(signals: dict, paris: list[str]) -> dict:
    paris_analysables = [p for p in paris if p in bet_types.ANALYSABLE]
    if not os.getenv("ANTHROPIC_API_KEY"):
        return analyse_deterministe(signals, paris)
    try:
        import anthropic

        client = anthropic.Anthropic()
        # effort 'high' par défaut : on l'omet (évite tout conflit avec parse()).
        resp = client.messages.parse(
            model=MODELE,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM,
            output_format=AnalyseLLM,
            messages=[{"role": "user", "content": build_prompt(signals, paris_analysables)}],
        )
        out = resp.parsed_output
        recommandations = [r.model_dump() for r in out.recommandations]
        return {
            "modele": MODELE,
            "lecture_globale": out.lecture_globale,
            "recommandations": recommandations,
            "coup_de_coeur_value": (
                out.coup_de_coeur_value.model_dump() if out.coup_de_coeur_value else None
            ),
            "confiance_globale": _confiance_globale(recommandations),
            "source": "llm",
        }
    except Exception:
        # Repli gracieux : pas de clé valide, réseau, quota, schéma… -> règles.
        return analyse_deterministe(signals, paris)
