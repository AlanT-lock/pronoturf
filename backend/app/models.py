from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

Discipline = Literal["trot_attele", "trot_monte", "plat", "obstacle"]
StatutCourse = Literal["a_venir", "terminee"]
StatutPartant = Literal["partant", "non_partant"]
TypeCapture = Literal["reference", "direct", "finale"]


class HippodromeNormalized(BaseModel):
    code_pmu: str
    nom: str
    pays: str


class ReunionNormalized(BaseModel):
    date: date
    numero_reunion: int
    hippodrome: HippodromeNormalized


class CoteNormalized(BaseModel):
    type_capture: TypeCapture
    valeur: float
    capture_at: datetime


class CourseNormalized(BaseModel):
    numero_course: int
    discipline: Discipline
    distance_m: int
    categorie_classe: Optional[str]
    heure_depart: datetime
    statut: StatutCourse
    reunion: ReunionNormalized


class PartantNormalized(BaseModel):
    numero_corde: int
    nom_cheval: str
    id_pmu_cheval: str
    sexe: Optional[str]
    driver_jockey_nom: Optional[str]
    entraineur_nom: Optional[str]
    poids_kg: Optional[float]
    reduction_kilometrique: Optional[float]
    ferrage: Optional[str]
    musique: Optional[str]
    statut: StatutPartant
    cotes: list[CoteNormalized]
    position_arrivee: Optional[int] = None
