# pronoturf — Plan 1 : Schéma Supabase + ingestion PMU (import d'une course)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importer une course PMU réelle (réunion + numéro) dans Supabase : programme, partants, cotes, via un endpoint FastAPI testable de bout en bout.

**Architecture:** Service FastAPI (`backend/`) qui appelle l'API PMU non officielle (`pmu_client.py`), normalise la réponse brute en modèles Pydantic (`pmu_normalizer.py`), puis écrit dans Supabase Postgres (`supabase_writer.py`) via un endpoint `POST /courses/import`. Le schéma DB complet du projet (toutes les tables de la spec) est créé en une seule migration, même si ce plan ne peuple que les tables liées à l'ingestion (hippodromes, reunions, courses, chevaux, intervenants, partants, cotes) — les tables scoring/backtest servent aux plans suivants.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic v2, supabase-py, pytest + pytest-asyncio + respx, Supabase Postgres.

## Global Constraints

- Le service FastAPI tourne en local pour le MVP (pas de déploiement production) — voir spec `docs/superpowers/specs/2026-07-12-pronoturf-mvp-design.md`.
- Usage personnel, un seul utilisateur : pas d'auth, pas de RLS complexe. Le backend utilise la clé **service role** Supabase ; il ne doit jamais être exposé publiquement.
- Aucune récupération planifiée (cron) : tout est déclenché à la demande via l'endpoint d'import.
- Les pondérations de scoring ne font pas partie de ce plan (Plan 2).
- Toute commande `curl`/appel réseau vers l'API PMU dans les étapes manuelles doit utiliser le header `User-Agent: Mozilla/5.0` (l'API bloque parfois les requêtes sans user-agent).

## Notes de cadrage découvertes pendant la préparation du plan

Ces points ont été vérifiés par des appels réels à l'API PMU (`https://offline.turfinfo.api.pmu.fr/rest/client/61/...`) le 2026-07-12, et affinent légèrement le schéma validé dans la spec :

- **`chevaux.id_pmu`** (nouvelle colonne, texte, unique) : PMU fournit un identifiant naturel stable par cheval dans `idCheval` (ex: `"MAJNOUN-MALICIEUSE-WOOTTON BASSETT"`, combinaison cheval-mère-père). On l'utilise comme clé d'upsert plutôt que `source_ids` jsonb, parce que PostgREST (utilisé par Supabase pour les upserts) exige une contrainte unique sur des colonnes simples, pas sur une expression jsonb.
- **`intervenants`** : PMU ne fournit pas d'identifiant stable pour driver/jockey/entraîneur, seulement un nom texte (ex: `"M.BARZALONA"`). La clé d'upsert reste `unique(nom, role)` — limitation connue : deux intervenants homonymes de même rôle seraient fusionnés à tort. Acceptable pour un usage personnel MVP.
- **`cotes.type_capture`** : la spec prévoyait `h2h`/`h30`/`finale`, qui suppose un polling à heures fixes (hors scope MVP, réservé à une phase avec cron). Comme l'import est ponctuel et à la demande, on capture ce que l'API expose réellement à l'instant T : `dernierRapportDirect` (cote courante) et `dernierRapportReference` (cote de référence/ouverture). Le type_capture devient donc `('reference', 'direct', 'finale')` : `reference` et `direct` sont capturés à chaque import ; `direct` est réécrit en `finale` si la course est terminée au moment de l'import (`course.statut == 'terminee'`).
- **Mapping discipline** : confirmé par l'API — `PLAT`→`plat`, `ATTELE`→`trot_attele`, `MONTE`→`trot_monte`. Aucune course obstacle n'était au programme le jour du test ; le mapping `OBSTACLE`/`STEEPLE-CHASE`/`HAIES`/`CROSS`→`obstacle` est basé sur la documentation publique de l'API PMU et **doit être vérifié** dès qu'une vraie course d'obstacle est importée (voir Tâche 8).
- **`numero_corde`** : mappé depuis le champ `numPmu` du partant (présent dans toutes les disciplines testées), pas `placeCorde` (absent en trot). `numPmu` correspond au numéro de départ affiché au public dans les deux cas.
- **Poids (plat)** : `handicapPoids` est exprimé en dixièmes de kg (`580` → 58.0 kg) — confirmé par comparaison avec `poidsConditionMonte`.
- **Réduction kilométrique (trot)** : `reductionKilometrique` est exprimée en millièmes de seconde par km (`78300` → 78.3 s/km, soit une réduction kilométrique de 1'18"3) — confirmé par cohérence avec `tempsObtenu`/distance.

## File Structure

```
pronoturf/
  backend/
    requirements.txt
    pytest.ini
    app/
      __init__.py
      config.py            # Settings (env vars)
      supabase_client.py    # get_supabase_client()
      main.py                # FastAPI app + routes
      models.py              # modèles Pydantic normalisés
      pmu_client.py          # appels HTTP bruts à l'API PMU
      pmu_normalizer.py      # raw dict -> modèles normalisés
      supabase_writer.py     # modèles normalisés -> upserts Supabase
    tests/
      __init__.py
      conftest.py
      fixtures/
        pmu_programme_sample.json
        pmu_participants_plat_sample.json
        pmu_participants_trot_sample.json
      test_pmu_client.py
      test_pmu_normalizer.py
      test_supabase_writer.py
      test_main.py
  supabase/
    migrations/
      0001_init_schema.sql
```

---

### Task 1: Scaffolding backend + health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_main.py`

**Interfaces:**
- Produces: `app.main.app` (instance FastAPI), route `GET /health` → `{"status": "ok"}`.

- [ ] **Step 1: Créer la structure de dossiers et `requirements.txt`**

```bash
mkdir -p /Users/alantouati/pronoturf/backend/app /Users/alantouati/pronoturf/backend/tests/fixtures
```

`backend/requirements.txt` :
```
fastapi==0.115.0
uvicorn==0.32.0
httpx==0.27.2
pydantic==2.9.2
pydantic-settings==2.5.2
supabase==2.9.1
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

`backend/pytest.ini` :
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: Créer l'environnement virtuel et installer les dépendances**

```bash
cd /Users/alantouati/pronoturf/backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Expected: installation sans erreur.

- [ ] **Step 3: Écrire le test du health check (échoue d'abord)**

`backend/tests/__init__.py` : fichier vide.

`backend/tests/test_main.py` :
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_main.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (ou `app` n'existe pas encore).

- [ ] **Step 5: Implémenter `app/main.py` minimal**

`backend/app/__init__.py` : fichier vide.

`backend/app/main.py` :
```python
from fastapi import FastAPI

app = FastAPI(title="pronoturf")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_main.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/requirements.txt backend/pytest.ini backend/app backend/tests && git commit -m "feat(backend): scaffold FastAPI app with health check"
```

---

### Task 2: Schéma Supabase complet

**Files:**
- Create: `supabase/migrations/0001_init_schema.sql`

**Interfaces:**
- Produces: tables Postgres `hippodromes, reunions, courses, chevaux, intervenants, partants, cotes, resultats, ponderations_config, scores_pronostic, backtest_resultats` dans le projet Supabase `pronoturf`.

- [ ] **Step 1: Écrire la migration SQL**

`supabase/migrations/0001_init_schema.sql` :
```sql
create table hippodromes (
  id uuid primary key default gen_random_uuid(),
  code_pmu text unique not null,
  nom text not null,
  pays text not null,
  sens_corde text
);

create table reunions (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  hippodrome_id uuid not null references hippodromes(id),
  numero_reunion int not null,
  source_ids jsonb not null default '{}'::jsonb,
  unique (date, numero_reunion)
);

create table courses (
  id uuid primary key default gen_random_uuid(),
  reunion_id uuid not null references reunions(id),
  numero_course int not null,
  discipline text not null check (discipline in ('trot_attele','trot_monte','plat','obstacle')),
  distance_m int not null,
  etat_terrain text,
  categorie_classe text,
  heure_depart timestamptz not null,
  statut text not null default 'a_venir' check (statut in ('a_venir','terminee')),
  source_ids jsonb not null default '{}'::jsonb,
  unique (reunion_id, numero_course)
);

create table chevaux (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  sexe text,
  date_naissance date,
  id_pmu text unique not null,
  id_geny text
);

create table intervenants (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  role text not null check (role in ('driver','jockey','entraineur')),
  unique (nom, role)
);

create table partants (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  cheval_id uuid not null references chevaux(id),
  numero_corde int not null,
  driver_jockey_id uuid references intervenants(id),
  entraineur_id uuid references intervenants(id),
  poids_kg numeric,
  reduction_kilometrique numeric,
  ferrage text,
  musique text,
  statut text not null default 'partant' check (statut in ('partant','non_partant')),
  champs_manuels jsonb not null default '[]'::jsonb,
  unique (course_id, numero_corde)
);

create table cotes (
  id uuid primary key default gen_random_uuid(),
  partant_id uuid not null references partants(id),
  type_capture text not null check (type_capture in ('reference','direct','finale')),
  valeur numeric not null,
  capture_at timestamptz not null
);

create table resultats (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  partant_id uuid not null references partants(id) unique,
  position_arrivee int,
  disqualifie boolean not null default false,
  ecart text,
  gains numeric
);

create table ponderations_config (
  id uuid primary key default gen_random_uuid(),
  discipline text not null check (discipline in ('trot_attele','trot_monte','plat','obstacle')),
  nom text not null,
  poids jsonb not null,
  actif boolean not null default true,
  version int not null default 1,
  created_at timestamptz not null default now()
);

create table scores_pronostic (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  partant_id uuid not null references partants(id),
  ponderation_config_id uuid not null references ponderations_config(id),
  score_total numeric not null,
  rang_pronostique int not null,
  details_facteurs jsonb not null default '{}'::jsonb,
  calculated_at timestamptz not null default now()
);

create table backtest_resultats (
  id uuid primary key default gen_random_uuid(),
  ponderation_config_id uuid not null references ponderations_config(id),
  periode_debut date not null,
  periode_fin date not null,
  nb_courses int not null,
  precision_top1 numeric,
  precision_top3 numeric,
  calculated_at timestamptz not null default now()
);
```

- [ ] **Step 2: Créer le projet Supabase `pronoturf`**

Demander confirmation à l'utilisateur avant de créer un projet cloud facturable. Une fois confirmé, utiliser l'outil MCP `mcp__plugin_supabase_supabase__create_project` avec :
- `name`: `"pronoturf"`
- `organization_id`: `"qqyykwpqguivbiplqcfi"` (organisation existante de l'utilisateur, cf. `list_projects`)
- `region`: `"eu-west-3"` (cohérent avec les autres projets Supabase de l'utilisateur : LockHACCP, E-learning)

Noter le `project_id` retourné — il sera réutilisé dans toutes les étapes Supabase suivantes et dans `backend/.env` (Task 3).

- [ ] **Step 3: Appliquer la migration**

Utiliser l'outil MCP `mcp__plugin_supabase_supabase__apply_migration` avec le `project_id` obtenu, `name: "init_schema"`, et le contenu SQL de `supabase/migrations/0001_init_schema.sql`.

- [ ] **Step 4: Vérifier que les tables existent**

Utiliser l'outil MCP `mcp__plugin_supabase_supabase__list_tables` avec le `project_id`.
Expected: la liste contient les 11 tables créées à l'étape 1.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add supabase/migrations/0001_init_schema.sql && git commit -m "feat(db): initial Supabase schema for pronoturf"
```

---

### Task 3: Configuration et client Supabase

**Files:**
- Create: `backend/.env.example`
- Create: `backend/app/config.py`
- Create: `backend/app/supabase_client.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: `project_id` Supabase de la Task 2 (l'URL du projet et la clé service role, récupérables via `mcp__plugin_supabase_supabase__get_project_url` et le dashboard Supabase → Settings → API).
- Produces: `app.config.settings` (instance `Settings`), `app.supabase_client.get_supabase_client() -> Client`.

- [ ] **Step 1: Écrire le test de config (échoue d'abord)**

`backend/tests/test_config.py` :
```python
import os
from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
    settings = Settings()
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_service_key == "test-key"
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Implémenter `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str


settings = Settings()
```

`backend/.env.example` :
```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_config.py -v
```
Expected: PASS.

- [ ] **Step 5: Créer `backend/.env` réel (non committé) avec les vraies valeurs**

Copier `.env.example` vers `.env`, remplir `SUPABASE_URL` avec l'URL du projet créé en Task 2 (`mcp__plugin_supabase_supabase__get_project_url`) et `SUPABASE_SERVICE_KEY` avec la clé service role (dashboard Supabase → Settings → API → service_role secret).

Ajouter `.env` à `.gitignore` :
```bash
cd /Users/alantouati/pronoturf && printf "backend/.venv/\nbackend/.env\n__pycache__/\n*.pyc\n" > .gitignore
```

- [ ] **Step 6: Implémenter `app/supabase_client.py`**

```python
from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)
```

- [ ] **Step 7: Commit**

```bash
cd /Users/alantouati/pronoturf && git add .gitignore backend/.env.example backend/app/config.py backend/app/supabase_client.py backend/tests/test_config.py && git commit -m "feat(backend): add settings and Supabase client"
```

---

### Task 4: Modèles Pydantic normalisés

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `HippodromeNormalized`, `ReunionNormalized`, `CourseNormalized`, `CoteNormalized`, `PartantNormalized` (tous `pydantic.BaseModel`), types `Discipline`, `StatutPartant`, `TypeCapture`.

- [ ] **Step 1: Écrire le test des modèles (échoue d'abord)**

`backend/tests/test_models.py` :
```python
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    CourseNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)


def test_course_normalized_rejects_invalid_discipline():
    hippodrome = HippodromeNormalized(code_pmu="DEA", nom="DEAUVILLE", pays="FRA")
    reunion = ReunionNormalized(date=date(2026, 7, 12), numero_reunion=1, hippodrome=hippodrome)
    with pytest.raises(ValidationError):
        CourseNormalized(
            numero_course=1,
            discipline="GALOP",  # invalide
            distance_m=1200,
            categorie_classe="COURSE_A_CONDITIONS",
            heure_depart=datetime(2026, 7, 12, 14, 30),
            statut="a_venir",
            reunion=reunion,
        )


def test_partant_normalized_accepts_minimal_fields():
    partant = PartantNormalized(
        numero_corde=1,
        nom_cheval="MAJNOUN",
        id_pmu_cheval="MAJNOUN-MALICIEUSE-WOOTTON BASSETT",
        sexe="MALES",
        driver_jockey_nom="M.BARZALONA",
        entraineur_nom="FH.GRAFFARD (S)",
        poids_kg=58.0,
        reduction_kilometrique=None,
        ferrage=None,
        musique=None,
        statut="partant",
        cotes=[],
    )
    assert partant.numero_corde == 1
    assert partant.poids_kg == 58.0
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implémenter `app/models.py`**

```python
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
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_models.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/models.py backend/tests/test_models.py && git commit -m "feat(backend): add normalized Pydantic models"
```

---

### Task 5: Client PMU (appels HTTP bruts)

**Files:**
- Create: `backend/app/pmu_client.py`
- Create: `backend/tests/fixtures/pmu_programme_sample.json`
- Create: `backend/tests/fixtures/pmu_participants_plat_sample.json`
- Test: `backend/tests/test_pmu_client.py`

**Interfaces:**
- Produces: `async def fetch_programme(date_str: str) -> dict`, `async def fetch_participants(date_str: str, numero_reunion: int, numero_course: int) -> dict`. `date_str` au format `"DDMMYYYY"` (ex: `"12072026"`).

- [ ] **Step 1: Créer les fixtures JSON (données réelles capturées le 2026-07-12)**

`backend/tests/fixtures/pmu_programme_sample.json` :
```json
{
  "programme": {
    "reunions": [
      {
        "numOfficiel": 1,
        "dateReunion": 1783807200000,
        "hippodrome": {"code": "DEA", "libelleCourt": "DEAUVILLE", "libelleLong": "HIPPODROME DE DEAUVILLE"},
        "pays": {"code": "FRA", "libelle": "FRANCE"},
        "courses": [
          {
            "numOrdre": 1,
            "heureDepart": 1783858620000,
            "libelle": "HARAS DE FRESNAY-LE-BUFFARD PRIX DE TANCARVILLE",
            "distance": 1200,
            "discipline": "PLAT",
            "specialite": "PLAT",
            "categorieParticularite": "COURSE_A_CONDITIONS",
            "arriveeDefinitive": true
          }
        ]
      }
    ]
  }
}
```

`backend/tests/fixtures/pmu_participants_plat_sample.json` :
```json
{
  "participants": [
    {
      "idCheval": "MAJNOUN-MALICIEUSE-WOOTTON BASSETT",
      "nom": "MAJNOUN",
      "numPmu": 1,
      "sexe": "MALES",
      "statut": "PARTANT",
      "entraineur": "FH.GRAFFARD (S)",
      "driver": "M.BARZALONA",
      "handicapPoids": 580,
      "dernierRapportDirect": {"rapport": 2.3, "typeRapport": "DIRECT"},
      "dernierRapportReference": {"rapport": 1.4, "typeRapport": "REFERENCE"},
      "ordreArrivee": 3
    },
    {
      "idCheval": "TRIPOLITAIN-SYMPOSIUM-BLUE POINT",
      "nom": "TRIPOLITAIN",
      "numPmu": 2,
      "sexe": "MALES",
      "statut": "PARTANT",
      "entraineur": "H.GHABRI",
      "driver": "C.LECOEUVRE",
      "handicapPoids": 580,
      "dernierRapportDirect": {"rapport": 5.7, "typeRapport": "DIRECT"},
      "dernierRapportReference": {"rapport": 4.9, "typeRapport": "REFERENCE"},
      "ordreArrivee": 5
    }
  ]
}
```

- [ ] **Step 2: Écrire le test du client PMU (échoue d'abord)**

`backend/tests/conftest.py` :
```python
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def pmu_programme_sample() -> dict:
    return json.loads((FIXTURES_DIR / "pmu_programme_sample.json").read_text())


@pytest.fixture
def pmu_participants_plat_sample() -> dict:
    return json.loads((FIXTURES_DIR / "pmu_participants_plat_sample.json").read_text())
```

`backend/tests/test_pmu_client.py` :
```python
import httpx
import respx

from app.pmu_client import PMU_BASE_URL, fetch_participants, fetch_programme


@respx.mock
async def test_fetch_programme_calls_expected_url(pmu_programme_sample):
    route = respx.get(f"{PMU_BASE_URL}/programme/12072026").mock(
        return_value=httpx.Response(200, json=pmu_programme_sample)
    )
    result = await fetch_programme("12072026")
    assert route.called
    assert result == pmu_programme_sample


@respx.mock
async def test_fetch_participants_calls_expected_url(pmu_participants_plat_sample):
    route = respx.get(f"{PMU_BASE_URL}/programme/12072026/R1/C1/participants").mock(
        return_value=httpx.Response(200, json=pmu_participants_plat_sample)
    )
    result = await fetch_participants("12072026", 1, 1)
    assert route.called
    assert result == pmu_participants_plat_sample
```

- [ ] **Step 3: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pmu_client'`.

- [ ] **Step 4: Implémenter `app/pmu_client.py`**

```python
import httpx

PMU_BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/61"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


async def fetch_programme(date_str: str) -> dict:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(f"{PMU_BASE_URL}/programme/{date_str}")
        response.raise_for_status()
        return response.json()


async def fetch_participants(date_str: str, numero_reunion: int, numero_course: int) -> dict:
    url = f"{PMU_BASE_URL}/programme/{date_str}/R{numero_reunion}/C{numero_course}/participants"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 5: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_client.py -v
```
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/pmu_client.py backend/tests/conftest.py backend/tests/fixtures backend/tests/test_pmu_client.py && git commit -m "feat(ingestion): add PMU API client with mocked tests"
```

---

### Task 6: Normalisation des données PMU

**Files:**
- Create: `backend/app/pmu_normalizer.py`
- Create: `backend/tests/fixtures/pmu_participants_trot_sample.json`
- Test: `backend/tests/test_pmu_normalizer.py`

**Interfaces:**
- Consumes: `HippodromeNormalized`, `ReunionNormalized`, `CourseNormalized`, `CoteNormalized`, `PartantNormalized` (Task 4).
- Produces: `def find_course_in_programme(programme: dict, numero_reunion: int, numero_course: int) -> tuple[dict, dict]`, `def normalize_course(raw_reunion: dict, raw_course: dict) -> CourseNormalized`, `def normalize_partants(raw_participants: list[dict], course_terminee: bool) -> list[PartantNormalized]`.

- [ ] **Step 1: Créer la fixture trot (données réelles capturées le 2026-07-12, course déjà terminée)**

`backend/tests/fixtures/pmu_participants_trot_sample.json` :
```json
{
  "participants": [
    {
      "idCheval": "IGOR THEPOL-LA DIVA DE RIEZ-URIEL SPEED",
      "nom": "IGOR THEPOL",
      "numPmu": 1,
      "sexe": "HONGRES",
      "statut": "PARTANT",
      "entraineur": "P. BILLON",
      "driver": "D. RABILLER",
      "deferre": "DEFERRE_POSTERIEURS",
      "musique": "7aDm5a(25)6mDm9m3mDm9m",
      "reductionKilometrique": 78300,
      "ordreArrivee": 2,
      "dernierRapportDirect": {"rapport": 62.0, "typeRapport": "DIRECT"},
      "dernierRapportReference": {"rapport": 45.0, "typeRapport": "REFERENCE"}
    },
    {
      "idCheval": "JAZZ KERODA-ULTIMA KERODA-SAXO DE VANDEL",
      "nom": "JAZZ KERODA",
      "numPmu": 2,
      "sexe": "HONGRES",
      "statut": "PARTANT",
      "entraineur": "A. DAVID",
      "driver": "C. BATY",
      "deferre": "DEFERRE_POSTERIEURS",
      "musique": "(25)0a0a5a(24)7a3a1a4a2a",
      "reductionKilometrique": 78400,
      "ordreArrivee": 4,
      "dernierRapportDirect": {"rapport": 11.0, "typeRapport": "DIRECT"},
      "dernierRapportReference": {"rapport": 25.0, "typeRapport": "REFERENCE"}
    }
  ]
}
```

Ajouter la fixture dans `conftest.py` :
```python
@pytest.fixture
def pmu_participants_trot_sample() -> dict:
    return json.loads((FIXTURES_DIR / "pmu_participants_trot_sample.json").read_text())
```
(Insérer cette fonction dans `backend/tests/conftest.py` en la faisant suivre à `pmu_participants_plat_sample`.)

- [ ] **Step 2: Écrire les tests de normalisation (échouent d'abord)**

`backend/tests/test_pmu_normalizer.py` :
```python
from app.pmu_normalizer import (
    find_course_in_programme,
    normalize_course,
    normalize_partants,
)


def test_find_course_in_programme_returns_reunion_and_course(pmu_programme_sample):
    raw_reunion, raw_course = find_course_in_programme(pmu_programme_sample, 1, 1)
    assert raw_reunion["numOfficiel"] == 1
    assert raw_course["numOrdre"] == 1


def test_normalize_course_maps_plat_discipline(pmu_programme_sample):
    raw_reunion, raw_course = find_course_in_programme(pmu_programme_sample, 1, 1)
    course = normalize_course(raw_reunion, raw_course)
    assert course.discipline == "plat"
    assert course.statut == "terminee"
    assert course.distance_m == 1200
    assert course.reunion.hippodrome.code_pmu == "DEA"


def test_normalize_partants_plat_maps_poids_and_cotes(pmu_participants_plat_sample):
    partants = normalize_partants(pmu_participants_plat_sample["participants"], course_terminee=True)
    majnoun = next(p for p in partants if p.nom_cheval == "MAJNOUN")
    assert majnoun.numero_corde == 1
    assert majnoun.poids_kg == 58.0
    assert majnoun.position_arrivee == 3
    valeurs_par_type = {c.type_capture: c.valeur for c in majnoun.cotes}
    assert valeurs_par_type["reference"] == 1.4
    assert valeurs_par_type["finale"] == 2.3
    assert "direct" not in valeurs_par_type  # course terminée -> direct devient finale


def test_normalize_partants_trot_maps_deferre_and_reduction(pmu_participants_trot_sample):
    partants = normalize_partants(pmu_participants_trot_sample["participants"], course_terminee=True)
    igor = next(p for p in partants if p.nom_cheval == "IGOR THEPOL")
    assert igor.ferrage == "DEFERRE_POSTERIEURS"
    assert igor.reduction_kilometrique == 78.3
    assert igor.poids_kg is None
    assert igor.musique == "7aDm5a(25)6mDm9m3mDm9m"
```

- [ ] **Step 3: Lancer les tests pour vérifier qu'ils échouent**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_normalizer.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pmu_normalizer'`.

- [ ] **Step 4: Implémenter `app/pmu_normalizer.py`**

```python
from datetime import datetime, timezone

from app.models import (
    CourseNormalized,
    CoteNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)

_DISCIPLINE_MAP = {
    "PLAT": "plat",
    "ATTELE": "trot_attele",
    "MONTE": "trot_monte",
    # Mapping non vérifié en conditions réelles (aucune course obstacle
    # disponible au moment du test) — à confirmer dès une vraie course d'obstacle.
    "OBSTACLE": "obstacle",
    "STEEPLE-CHASE": "obstacle",
    "HAIES": "obstacle",
    "CROSS": "obstacle",
}


def find_course_in_programme(programme: dict, numero_reunion: int, numero_course: int) -> tuple[dict, dict]:
    for raw_reunion in programme["programme"]["reunions"]:
        if raw_reunion["numOfficiel"] != numero_reunion:
            continue
        for raw_course in raw_reunion["courses"]:
            if raw_course["numOrdre"] == numero_course:
                return raw_reunion, raw_course
    raise ValueError(f"Course R{numero_reunion}C{numero_course} introuvable dans le programme")


def normalize_course(raw_reunion: dict, raw_course: dict) -> CourseNormalized:
    hippodrome = HippodromeNormalized(
        code_pmu=raw_reunion["hippodrome"]["code"],
        nom=raw_reunion["hippodrome"]["libelleCourt"],
        pays=raw_reunion["pays"]["code"],
    )
    reunion = ReunionNormalized(
        date=datetime.fromtimestamp(raw_reunion["dateReunion"] / 1000, tz=timezone.utc).date(),
        numero_reunion=raw_reunion["numOfficiel"],
        hippodrome=hippodrome,
    )
    return CourseNormalized(
        numero_course=raw_course["numOrdre"],
        discipline=_DISCIPLINE_MAP[raw_course["discipline"]],
        distance_m=raw_course["distance"],
        categorie_classe=raw_course.get("categorieParticularite"),
        heure_depart=datetime.fromtimestamp(raw_course["heureDepart"] / 1000, tz=timezone.utc),
        statut="terminee" if raw_course.get("arriveeDefinitive") else "a_venir",
        reunion=reunion,
    )


def normalize_partants(raw_participants: list[dict], course_terminee: bool) -> list[PartantNormalized]:
    partants = []
    for raw in raw_participants:
        cotes = []
        if raw.get("dernierRapportReference") is not None:
            cotes.append(
                CoteNormalized(
                    type_capture="reference",
                    valeur=raw["dernierRapportReference"]["rapport"],
                    capture_at=datetime.now(tz=timezone.utc),
                )
            )
        if raw.get("dernierRapportDirect") is not None:
            cotes.append(
                CoteNormalized(
                    type_capture="finale" if course_terminee else "direct",
                    valeur=raw["dernierRapportDirect"]["rapport"],
                    capture_at=datetime.now(tz=timezone.utc),
                )
            )
        reduction = raw.get("reductionKilometrique")
        poids = raw.get("handicapPoids")
        partants.append(
            PartantNormalized(
                numero_corde=raw["numPmu"],
                nom_cheval=raw["nom"],
                id_pmu_cheval=raw["idCheval"],
                sexe=raw.get("sexe"),
                driver_jockey_nom=raw.get("driver"),
                entraineur_nom=raw.get("entraineur"),
                poids_kg=(poids / 10.0) if poids is not None else None,
                reduction_kilometrique=(reduction / 1000.0) if reduction is not None else None,
                ferrage=raw.get("deferre"),
                musique=raw.get("musique"),
                statut="partant" if raw["statut"] == "PARTANT" else "non_partant",
                cotes=cotes,
                position_arrivee=raw.get("ordreArrivee"),
            )
        )
    return partants
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_normalizer.py -v
```
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/pmu_normalizer.py backend/tests/fixtures/pmu_participants_trot_sample.json backend/tests/conftest.py backend/tests/test_pmu_normalizer.py && git commit -m "feat(ingestion): normalize raw PMU data into domain models"
```

---

### Task 7: Écriture Supabase (upserts)

**Files:**
- Create: `backend/app/supabase_writer.py`
- Test: `backend/tests/test_supabase_writer.py`

**Interfaces:**
- Consumes: `CourseNormalized`, `PartantNormalized` (Task 4/6).
- Produces: `class SupabaseWriter`, méthode `def save_course_import(self, course: CourseNormalized, partants: list[PartantNormalized]) -> dict` → `{"course_id": str, "partant_ids": list[str]}`.

- [ ] **Step 1: Écrire le test avec un faux client Supabase (échoue d'abord)**

`backend/tests/test_supabase_writer.py` :
```python
from datetime import date, datetime, timezone

from app.models import (
    CourseNormalized,
    CoteNormalized,
    HippodromeNormalized,
    PartantNormalized,
    ReunionNormalized,
)
from app.supabase_writer import SupabaseWriter


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self._client = client
        self._name = name
        self._payload = None

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        return self

    def execute(self):
        row = dict(self._payload)
        row["id"] = f"fake-id-{self._name}-{row.get('numero_course') or row.get('numero_corde') or row.get('code_pmu') or row.get('nom') or row.get('id_pmu')}"
        self._client.calls.append((self._name, dict(row)))
        return FakeResponse([row])


class FakeSupabaseClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return FakeTable(self, name)


def _sample_course() -> CourseNormalized:
    hippodrome = HippodromeNormalized(code_pmu="DEA", nom="DEAUVILLE", pays="FRA")
    reunion = ReunionNormalized(date=date(2026, 7, 12), numero_reunion=1, hippodrome=hippodrome)
    return CourseNormalized(
        numero_course=1,
        discipline="plat",
        distance_m=1200,
        categorie_classe="COURSE_A_CONDITIONS",
        heure_depart=datetime(2026, 7, 12, 14, 30, tzinfo=timezone.utc),
        statut="terminee",
        reunion=reunion,
    )


def _sample_partants() -> list[PartantNormalized]:
    return [
        PartantNormalized(
            numero_corde=1,
            nom_cheval="MAJNOUN",
            id_pmu_cheval="MAJNOUN-MALICIEUSE-WOOTTON BASSETT",
            sexe="MALES",
            driver_jockey_nom="M.BARZALONA",
            entraineur_nom="FH.GRAFFARD (S)",
            poids_kg=58.0,
            reduction_kilometrique=None,
            ferrage=None,
            musique=None,
            statut="partant",
            cotes=[CoteNormalized(type_capture="finale", valeur=2.3, capture_at=datetime.now(tz=timezone.utc))],
            position_arrivee=3,
        )
    ]


def test_save_course_import_writes_all_tables_and_returns_ids():
    fake_client = FakeSupabaseClient()
    writer = SupabaseWriter(fake_client)

    result = writer.save_course_import(_sample_course(), _sample_partants())

    table_names_called = [name for name, _ in fake_client.calls]
    assert table_names_called == [
        "hippodromes",
        "reunions",
        "courses",
        "chevaux",
        "intervenants",
        "intervenants",
        "partants",
        "cotes",
    ]
    assert result["course_id"] is not None
    assert len(result["partant_ids"]) == 1
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_supabase_writer.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.supabase_writer'`.

- [ ] **Step 3: Implémenter `app/supabase_writer.py`**

```python
from app.models import CourseNormalized, PartantNormalized


class SupabaseWriter:
    def __init__(self, client):
        self._client = client

    def save_course_import(self, course: CourseNormalized, partants: list[PartantNormalized]) -> dict:
        hippodrome_row = (
            self._client.table("hippodromes")
            .upsert(
                {
                    "code_pmu": course.reunion.hippodrome.code_pmu,
                    "nom": course.reunion.hippodrome.nom,
                    "pays": course.reunion.hippodrome.pays,
                },
                on_conflict="code_pmu",
            )
            .execute()
            .data[0]
        )

        reunion_row = (
            self._client.table("reunions")
            .upsert(
                {
                    "date": course.reunion.date.isoformat(),
                    "hippodrome_id": hippodrome_row["id"],
                    "numero_reunion": course.reunion.numero_reunion,
                },
                on_conflict="date,numero_reunion",
            )
            .execute()
            .data[0]
        )

        course_row = (
            self._client.table("courses")
            .upsert(
                {
                    "reunion_id": reunion_row["id"],
                    "numero_course": course.numero_course,
                    "discipline": course.discipline,
                    "distance_m": course.distance_m,
                    "categorie_classe": course.categorie_classe,
                    "heure_depart": course.heure_depart.isoformat(),
                    "statut": course.statut,
                },
                on_conflict="reunion_id,numero_course",
            )
            .execute()
            .data[0]
        )

        partant_ids = []
        for partant in partants:
            cheval_row = (
                self._client.table("chevaux")
                .upsert(
                    {
                        "nom": partant.nom_cheval,
                        "sexe": partant.sexe,
                        "id_pmu": partant.id_pmu_cheval,
                    },
                    on_conflict="id_pmu",
                )
                .execute()
                .data[0]
            )

            driver_jockey_id = None
            if partant.driver_jockey_nom:
                driver_jockey_id = (
                    self._client.table("intervenants")
                    .upsert(
                        {"nom": partant.driver_jockey_nom, "role": "driver"},
                        on_conflict="nom,role",
                    )
                    .execute()
                    .data[0]["id"]
                )

            entraineur_id = None
            if partant.entraineur_nom:
                entraineur_id = (
                    self._client.table("intervenants")
                    .upsert(
                        {"nom": partant.entraineur_nom, "role": "entraineur"},
                        on_conflict="nom,role",
                    )
                    .execute()
                    .data[0]["id"]
                )

            partant_row = (
                self._client.table("partants")
                .upsert(
                    {
                        "course_id": course_row["id"],
                        "cheval_id": cheval_row["id"],
                        "numero_corde": partant.numero_corde,
                        "driver_jockey_id": driver_jockey_id,
                        "entraineur_id": entraineur_id,
                        "poids_kg": partant.poids_kg,
                        "reduction_kilometrique": partant.reduction_kilometrique,
                        "ferrage": partant.ferrage,
                        "musique": partant.musique,
                        "statut": partant.statut,
                    },
                    on_conflict="course_id,numero_corde",
                )
                .execute()
                .data[0]
            )
            partant_ids.append(partant_row["id"])

            for cote in partant.cotes:
                self._client.table("cotes").upsert(
                    {
                        "partant_id": partant_row["id"],
                        "type_capture": cote.type_capture,
                        "valeur": cote.valeur,
                        "capture_at": cote.capture_at.isoformat(),
                    }
                ).execute()

        return {"course_id": course_row["id"], "partant_ids": partant_ids}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_supabase_writer.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/supabase_writer.py backend/tests/test_supabase_writer.py && git commit -m "feat(ingestion): write normalized course data to Supabase"
```

---

### Task 8: Endpoint `POST /courses/import` + vérification manuelle réelle

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_import_route.py`

**Interfaces:**
- Consumes: `fetch_programme`, `fetch_participants` (Task 5), `find_course_in_programme`, `normalize_course`, `normalize_partants` (Task 6), `SupabaseWriter.save_course_import` (Task 7), `get_supabase_client` (Task 3).
- Produces: `POST /courses/import` avec corps `{"date": "12072026", "numero_reunion": 1, "numero_course": 1}` → `{"course_id": "...", "partant_ids": ["..."]}`.

- [ ] **Step 1: Écrire le test de l'endpoint avec mocks (échoue d'abord)**

`backend/tests/test_import_route.py` :
```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self._client = client
        self._name = name
        self._payload = None

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        return self

    def execute(self):
        row = dict(self._payload)
        row["id"] = f"fake-id-{self._name}-{len(self._client.calls)}"
        self._client.calls.append((self._name, dict(row)))
        return FakeResponse([row])


class FakeSupabaseClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return FakeTable(self, name)


client = TestClient(app)


def test_import_course_returns_course_and_partant_ids(pmu_programme_sample, pmu_participants_plat_sample):
    app.dependency_overrides[get_supabase_client] = lambda: FakeSupabaseClient()
    try:
        with patch("app.main.fetch_programme", new=AsyncMock(return_value=pmu_programme_sample)), patch(
            "app.main.fetch_participants", new=AsyncMock(return_value=pmu_participants_plat_sample)
        ):
            response = client.post(
                "/courses/import",
                json={"date": "12072026", "numero_reunion": 1, "numero_course": 1},
            )
        assert response.status_code == 200
        body = response.json()
        assert "course_id" in body
        assert len(body["partant_ids"]) == 2
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_import_route.py -v
```
Expected: FAIL — `404 Not Found` (route inexistante) ou `AttributeError` sur `app.main.fetch_programme`.

- [ ] **Step 3: Implémenter la route dans `app/main.py`**

```python
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
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_import_route.py -v
```
Expected: PASS.

- [ ] **Step 5: Lancer toute la suite de tests**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest -v
```
Expected: PASS (tous les tests précédents + celui-ci, aucun test réseau réel).

- [ ] **Step 6: Vérification manuelle contre l'API PMU réelle et le vrai Supabase**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

Dans un autre terminal, trouver une réunion/course du jour :
```bash
curl -sS "https://offline.turfinfo.api.pmu.fr/rest/client/61/programme/$(date +%d%m%Y)" -H "User-Agent: Mozilla/5.0" | python3 -c "
import json,sys
d = json.load(sys.stdin)
for r in d['programme']['reunions'][:3]:
    for c in r['courses'][:2]:
        print(r['numOfficiel'], c['numOrdre'], c['discipline'], r['hippodrome']['libelleCourt'])
"
```

Puis appeler l'endpoint d'import avec une réunion/course réelle affichée ci-dessus :
```bash
curl -sS -X POST http://localhost:8000/courses/import \
  -H "Content-Type: application/json" \
  -d "{\"date\": \"$(date +%d%m%Y)\", \"numero_reunion\": 1, \"numero_course\": 1}"
```
Expected: réponse JSON `{"course_id": "...", "partant_ids": [...]}`.

Vérifier les données en base avec l'outil MCP `mcp__plugin_supabase_supabase__execute_sql` (project_id de la Task 2) :
```sql
select c.numero_course, c.discipline, p.numero_corde, ch.nom, p.poids_kg, p.reduction_kilometrique
from courses c
join partants p on p.course_id = c.id
join chevaux ch on ch.id = p.cheval_id
order by p.numero_corde;
```
Expected : une ligne par partant importé, avec les bonnes valeurs.

**Si la réunion/course testée est une course d'obstacle** : vérifier que `discipline` normalisé correspond bien à `"obstacle"` et ajuster `_DISCIPLINE_MAP` dans `app/pmu_normalizer.py` si la valeur brute PMU diffère de `OBSTACLE`/`STEEPLE-CHASE`/`HAIES`/`CROSS` (voir note de cadrage en tête de plan).

- [ ] **Step 7: Écrire un README minimal**

`backend/README.md` :
```markdown
# pronoturf backend

## Setup

\`\`\`bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # puis renseigner SUPABASE_URL et SUPABASE_SERVICE_KEY
\`\`\`

## Lancer les tests

\`\`\`bash
.venv/bin/pytest -v
\`\`\`

## Lancer le serveur

\`\`\`bash
.venv/bin/uvicorn app.main:app --reload --port 8000
\`\`\`

## Importer une course

\`\`\`bash
curl -X POST http://localhost:8000/courses/import \
  -H "Content-Type: application/json" \
  -d '{"date": "12072026", "numero_reunion": 1, "numero_course": 1}'
\`\`\`
```

- [ ] **Step 8: Commit final**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/main.py backend/tests/test_import_route.py backend/README.md && git commit -m "feat(api): add POST /courses/import end-to-end route"
```

---

## Ce que ce plan produit

À la fin de ce plan : un service FastAPI local capable d'importer n'importe quelle course PMU du jour (réunion + numéro), toutes disciplines, avec ses partants et ses cotes, dans un vrai projet Supabase — vérifiable par une requête SQL. C'est la fondation sur laquelle branchent le moteur de scoring (Plan 2, avec la saisie manuelle et le frontend Next.js), l'ingestion Geny (Plan 3), et le backtest (Plan 4).

## Hors scope de ce plan (plans suivants)

- **Plan 2** : formulaire de saisie manuelle des champs manquants, moteur de scoring pondéré, endpoint `POST /courses/{id}/score`, frontend Next.js (sélection de course, affichage du classement pronostiqué).
- **Plan 3** : ingestion Geny.com (stats driver/entraîneur).
- **Plan 4** : import des résultats réels post-course, endpoint `POST /courses/{id}/backtest`, calcul de précision top1/top3.
