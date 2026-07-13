# Algorithme de pronostic enrichi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrichir le scoring avec des facteurs contextuels (taux de réussite par distance / discipline / niveau / hippodrome) et jockey/entraîneur, un indice de confiance, et la vraie corde — le tout adossé à l'historique PMU stocké.

**Architecture:** À l'import, on récupère `performances-detaillees` et on persiste l'historique brut de chaque cheval (`chevaux_performances`) + les résultats pour l'entraîneur (`entraineur_resultats`). Au score, on calcule les taux par contexte depuis cet historique stocké et on agrège les stats globales jockey/entraîneur, puis on les injecte dans le moteur pondéré existant (qui redistribue déjà les poids des facteurs neutres).

**Tech Stack:** FastAPI, Pydantic v2, supabase-py, pytest (FakeStore), Next.js (App Router)/TypeScript/Tailwind côté frontend.

## Global Constraints

- **Migrations appliquées manuellement** par l'utilisateur sur son Supabase (comme pour 0001/0002). Les tests backend utilisent `FakeStore` (aucune vraie DB requise) ; seule la vérification E2E (Task 10) exige que la migration 0003 soit appliquée.
- **TDD strict** : test rouge d'abord, vérifié en échec, puis implémentation minimale.
- **Idempotence** : toute écriture PMU est un `upsert` avec `on_conflict` — ré-importer ne duplique jamais.
- **Dégradation gracieuse** : l'absence d'historique (débutant), un endpoint HS ou un payload vide ne doivent JAMAIS faire échouer l'import ni le score ; les facteurs concernés tombent en **neutre 0.5**.
- **Succès = arrivé dans les 3 premiers** (`place ∈ {1,2,3}`) ; une course courue sans succès compte au dénominateur.
- **Échantillon minimal = 3** courses dans le contexte, sinon facteur **neutre 0.5**.
- **Bandes** : distance **±10 %**, allocation **±30 %**. **Plafond de confiance** : 10 courses.
- **Normalisation** : les taux sont utilisés en **valeur absolue [0,1]** ; `cote`, `corde`, `poids` restent en **min-max relatif** à la course.
- **`numero_corde` (= `numPmu`) reste la clé/identité** d'un partant (ne pas en changer la sémantique). La **vraie corde** est un champ séparé `place_corde` (`placeCorde` PMU), utilisé uniquement par le facteur corde.
- **Poids par défaut identiques sur les 4 disciplines** pour la v1 (choix MVP assumé ; calibration fine = backtest Plan 4). Chaque vecteur somme à 1.0.
- Ne pas introduire de dépendance réseau au moment du build frontend (pas de `next/font/google`, etc.).

Réf. spec : `docs/superpowers/specs/2026-07-13-pronoturf-algo-enrichi-design.md`.

## Structure des fichiers

Backend (`backend/`) :
- `supabase/migrations/0003_algo_enrichi_schema.sql` — **créer** : tables `chevaux_performances`, `entraineur_resultats` ; colonnes `partants.place_corde`, `courses.allocation` ; désactivation des pondérations `defaut` existantes.
- `app/models.py` — **modifier** : `PartantNormalized.place_corde`, `CourseNormalized.allocation`, nouveau `PerformanceNormalized`.
- `app/pmu_client.py` — **modifier** : `fetch_performances_detaillees`.
- `app/pmu_normalizer.py` — **modifier** : `place_corde` + `allocation` dans normalize ; nouveau `normalize_performances`.
- `app/supabase_writer.py` — **modifier** : `place_corde`/`allocation` à l'upsert ; retour `cheval_id_by_corde` ; `save_performances`, `save_entraineur_resultats`.
- `app/main.py` — **modifier** : ingestion historique dans `import_course`.
- `app/scoring/context_stats.py` — **créer** : taux par contexte + succès + échantillon + confiance + constantes.
- `app/scoring/global_stats.py` — **créer** : agrégation jockey/entraîneur.
- `app/scoring/factors.py` — **modifier** : 6 nouveaux facteurs + corde via `place_corde`.
- `app/scoring/engine.py` — **modifier** : passage du contexte, confiance par partant.
- `app/scoring/ponderations.py` — **modifier** : `DEFAULT_PONDERATIONS` ~11 facteurs.
- `app/scoring/routes.py` — **modifier** : `compute_score` câble historique + stats + renvoie confiance ; `get_course` expose jockey/entraîneur.
- `tests/…` — tests par module.

Frontend (`frontend/`) :
- `lib/types.ts` — **modifier** : `ScoreRow.confiance?`, `ScoreRow.nb_courses_historique?` ; `Partant.jockey_nom?`, `Partant.entraineur_nom?`.
- `components/PronosticTable.tsx` — **modifier** : badge de confiance.
- `components/PartantsTable.tsx` — **modifier** : colonnes jockey/entraîneur.

---

### Task 1: Migration 0003 + modèles Pydantic

**Files:**
- Create: `supabase/migrations/0003_algo_enrichi_schema.sql`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models_enrichi.py`

**Interfaces:**
- Produces: `PerformanceNormalized` (champs ci-dessous) ; `PartantNormalized.place_corde: Optional[int]` ; `CourseNormalized.allocation: Optional[float]`.

- [ ] **Step 1: Écrire la migration SQL**

Create `supabase/migrations/0003_algo_enrichi_schema.sql` :

```sql
alter table partants add column place_corde int;
alter table courses add column allocation numeric;

create table chevaux_performances (
  id uuid primary key default gen_random_uuid(),
  cheval_id uuid not null references chevaux(id),
  date_course date not null,
  hippodrome text,
  discipline text,
  distance_m int,
  allocation numeric,
  nb_participants int,
  place int,
  status_arrivee text,
  raw_place text,
  jockey_nom text,
  poids_jockey numeric,
  corde int,
  oeillere text,
  unique (cheval_id, date_course, hippodrome, distance_m)
);
create index chevaux_performances_cheval_idx on chevaux_performances (cheval_id);
create index chevaux_performances_jockey_idx on chevaux_performances (jockey_nom);

create table entraineur_resultats (
  id uuid primary key default gen_random_uuid(),
  entraineur_nom text not null,
  cheval_id uuid not null references chevaux(id),
  date_course date not null,
  hippodrome text,
  discipline text,
  place int,
  status_arrivee text,
  unique (entraineur_nom, cheval_id, date_course)
);
create index entraineur_resultats_nom_idx on entraineur_resultats (entraineur_nom);

-- Réactivera les nouveaux poids par défaut (11 facteurs) au prochain load :
update ponderations_config set actif = false where nom = 'defaut';
```

- [ ] **Step 2: Écrire le test des modèles (rouge)**

Create `backend/tests/test_models_enrichi.py` :

```python
from datetime import date

from app.models import PartantNormalized, CourseNormalized, PerformanceNormalized, ReunionNormalized, HippodromeNormalized


def test_partant_has_place_corde_optional():
    p = PartantNormalized(
        numero_corde=1, nom_cheval="X", id_pmu_cheval="X-Y-Z", sexe=None,
        driver_jockey_nom=None, entraineur_nom=None, poids_kg=None,
        reduction_kilometrique=None, ferrage=None, musique=None, statut="partant", cotes=[],
    )
    assert p.place_corde is None
    p2 = p.model_copy(update={"place_corde": 8})
    assert p2.place_corde == 8


def test_course_has_allocation_optional():
    c = CourseNormalized(
        numero_course=1, discipline="plat", distance_m=1400, categorie_classe=None,
        heure_depart="2026-07-13T12:00:00+00:00", statut="a_venir",
        reunion=ReunionNormalized(
            date=date(2026, 7, 13), numero_reunion=1,
            hippodrome=HippodromeNormalized(code_pmu="DIE", nom="DIEPPE", pays="FRA"),
        ),
    )
    assert c.allocation is None


def test_performance_normalized_fields():
    perf = PerformanceNormalized(
        num_pmu=1, date_course=date(2026, 6, 1), hippodrome="DIEPPE", discipline="plat",
        distance_m=1400, allocation=20100.0, nb_participants=9, place=2,
        status_arrivee="PLACE", raw_place="2", jockey_nom="S.PASQUIER",
        poids_jockey=58.0, corde=8, oeillere="SANS_OEILLERES",
    )
    assert perf.num_pmu == 1
    assert perf.place == 2
```

- [ ] **Step 3: Lancer le test (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_models_enrichi.py -q`
Expected: FAIL — `PerformanceNormalized` inexistant / `place_corde` inconnu.

- [ ] **Step 4: Modifier `app/models.py`**

Ajouter le champ `place_corde` à `PartantNormalized` (après `numero_corde`) :

```python
    place_corde: Optional[int] = None
```

Ajouter le champ `allocation` à `CourseNormalized` (après `distance_m`) :

```python
    allocation: Optional[float] = None
```

Ajouter le modèle (à la fin du fichier) :

```python
class PerformanceNormalized(BaseModel):
    num_pmu: int
    date_course: date
    hippodrome: Optional[str] = None
    discipline: Optional[str] = None
    distance_m: Optional[int] = None
    allocation: Optional[float] = None
    nb_participants: Optional[int] = None
    place: Optional[int] = None
    status_arrivee: Optional[str] = None
    raw_place: Optional[str] = None
    jockey_nom: Optional[str] = None
    poids_jockey: Optional[float] = None
    corde: Optional[int] = None
    oeillere: Optional[str] = None
```

- [ ] **Step 5: Lancer le test (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_models_enrichi.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf
git add supabase/migrations/0003_algo_enrichi_schema.sql backend/app/models.py backend/tests/test_models_enrichi.py
git commit -m "feat(algo): migration 0003 + modeles (place_corde, allocation, PerformanceNormalized)"
```

> **Note pour le contrôleur :** signaler à l'utilisateur d'appliquer `0003` sur son Supabase avant la Task 10 (E2E).

---

### Task 2: Client PMU + normalisation (performances, place_corde, allocation)

**Files:**
- Modify: `backend/app/pmu_client.py`
- Modify: `backend/app/pmu_normalizer.py`
- Test: `backend/tests/test_normalize_performances.py`

**Interfaces:**
- Consumes: `PerformanceNormalized`, `PartantNormalized.place_corde`, `CourseNormalized.allocation` (Task 1).
- Produces:
  - `fetch_performances_detaillees(date_str: str, numero_reunion: int, numero_course: int) -> dict`
  - `normalize_performances(raw_perf: dict) -> dict[int, list[PerformanceNormalized]]` (clé = `num_pmu` du jour)
  - `normalize_partants` renseigne désormais `place_corde` ; `normalize_course` renseigne `allocation`.
  - Constante `_DISCIPLINE_MAP` réutilisée pour mapper la discipline des courses passées.

- [ ] **Step 1: Écrire le test de normalisation (rouge)**

Create `backend/tests/test_normalize_performances.py` :

```python
from app.pmu_normalizer import normalize_performances


RAW_PERF = {
    "participants": [
        {
            "numPmu": 1,
            "nomCheval": "NO REMORSE",
            "coursesCourues": [
                {
                    "date": 1748772000000,
                    "timezoneOffset": 7200000,
                    "hippodrome": "DIEPPE",
                    "discipline": "PLAT",
                    "allocation": 20100,
                    "distance": 1400,
                    "nbParticipants": 9,
                    "participants": [
                        {
                            "numPmu": 3,
                            "place": {"place": 2, "rawValue": "2", "statusArrivee": "PLACE"},
                            "nomCheval": "NO REMORSE",
                            "nomJockey": "S.PASQUIER",
                            "poidsJockey": 58.0,
                            "corde": 8,
                            "itsHim": True,
                            "oeillere": "SANS_OEILLERES",
                        },
                        {"numPmu": 1, "itsHim": False, "nomCheval": "AUTRE"},
                    ],
                }
            ],
        }
    ]
}


def test_normalize_performances_keys_by_num_pmu():
    result = normalize_performances(RAW_PERF)
    assert set(result.keys()) == {1}
    perfs = result[1]
    assert len(perfs) == 1
    p = perfs[0]
    assert p.num_pmu == 1
    assert p.hippodrome == "DIEPPE"
    assert p.discipline == "plat"            # mappé
    assert p.distance_m == 1400
    assert p.allocation == 20100
    assert p.place == 2                       # depuis participant itsHim
    assert p.status_arrivee == "PLACE"
    assert p.jockey_nom == "S.PASQUIER"
    assert p.corde == 8


def test_normalize_performances_handles_missing_history():
    assert normalize_performances({"participants": []}) == {}
    assert normalize_performances({}) == {}


def test_normalize_performances_non_place():
    raw = {
        "participants": [
            {
                "numPmu": 2, "nomCheval": "X",
                "coursesCourues": [
                    {
                        "date": 1748772000000, "hippodrome": "VINCENNES",
                        "discipline": "ATTELE", "allocation": 30000, "distance": 2700, "nbParticipants": 12,
                        "participants": [
                            {"numPmu": 5, "place": {"place": None, "rawValue": "DP", "statusArrivee": "NON_PLACE"}, "itsHim": True, "nomJockey": "J.DOE"},
                        ],
                    }
                ],
            }
        ]
    }
    p = normalize_performances(raw)[2][0]
    assert p.place is None
    assert p.raw_place == "DP"
    assert p.discipline == "trot_attele"
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_normalize_performances.py -q`
Expected: FAIL — `normalize_performances` inexistant.

- [ ] **Step 3: Ajouter `fetch_performances_detaillees` dans `app/pmu_client.py`**

```python
async def fetch_performances_detaillees(date_str: str, numero_reunion: int, numero_course: int) -> dict:
    url = f"{PMU_BASE_URL}/programme/{date_str}/R{numero_reunion}/C{numero_course}/performances-detaillees/pretty"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Ajouter `normalize_performances` + place_corde + allocation dans `app/pmu_normalizer.py`**

Importer le modèle en tête du fichier (ajouter à l'import existant depuis `app.models`) : `PerformanceNormalized`.

Dans `normalize_course`, renseigner l'allocation (dans l'appel `CourseNormalized(...)`, ajouter) :

```python
        allocation=raw_course.get("montantPrix"),
```

Dans `normalize_partants`, à la construction de `PartantNormalized(...)`, ajouter :

```python
                place_corde=raw.get("placeCorde"),
```

Ajouter la fonction (fin du fichier) :

```python
def normalize_performances(raw_perf: dict) -> dict[int, list[PerformanceNormalized]]:
    result: dict[int, list[PerformanceNormalized]] = {}
    for cheval in raw_perf.get("participants", []):
        num_pmu = cheval["numPmu"]
        perfs: list[PerformanceNormalized] = []
        for course in cheval.get("coursesCourues", []):
            moi = next(
                (pp for pp in course.get("participants", []) if pp.get("itsHim")),
                None,
            )
            if moi is None:
                continue
            place_obj = moi.get("place") or {}
            raw_discipline = course.get("discipline")
            discipline = _DISCIPLINE_MAP.get(raw_discipline, raw_discipline.lower() if raw_discipline else None)
            perfs.append(
                PerformanceNormalized(
                    num_pmu=num_pmu,
                    date_course=datetime.fromtimestamp(
                        (course["date"] + course.get("timezoneOffset", 0)) / 1000, tz=timezone.utc
                    ).date(),
                    hippodrome=course.get("hippodrome"),
                    discipline=discipline,
                    distance_m=course.get("distance"),
                    allocation=course.get("allocation"),
                    nb_participants=course.get("nbParticipants"),
                    place=place_obj.get("place"),
                    status_arrivee=place_obj.get("statusArrivee"),
                    raw_place=place_obj.get("rawValue"),
                    jockey_nom=moi.get("nomJockey"),
                    poids_jockey=moi.get("poidsJockey"),
                    corde=moi.get("corde"),
                    oeillere=moi.get("oeillere"),
                )
            )
        result[num_pmu] = perfs
    return result
```

- [ ] **Step 5: Lancer le test (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_normalize_performances.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/pmu_client.py backend/app/pmu_normalizer.py backend/tests/test_normalize_performances.py
git commit -m "feat(algo): fetch+normalize performances-detaillees, place_corde, allocation"
```

---

### Task 3: Writer — chevaux_performances, entraineur_resultats, place_corde/allocation

**Files:**
- Modify: `backend/app/supabase_writer.py`
- Test: `backend/tests/test_writer_enrichi.py`

**Interfaces:**
- Consumes: `PerformanceNormalized`, `PartantNormalized.place_corde`, `CourseNormalized.allocation` (Tasks 1–2).
- Produces (méthodes de `SupabaseWriter`) :
  - `save_course_import(...)` renvoie désormais aussi `cheval_id_by_corde: dict[int, str]` (clé = `numero_corde`).
  - `save_performances(perf_by_num_pmu: dict[int, list[PerformanceNormalized]], cheval_id_by_corde: dict[int, str]) -> int` (nb lignes upsertées).
  - `save_entraineur_resultats(course: CourseNormalized, partants: list[PartantNormalized], cheval_id_by_corde: dict[int, str]) -> int`.

- [ ] **Step 1: Écrire les tests writer (rouge)**

Create `backend/tests/test_writer_enrichi.py` :

```python
from datetime import date, datetime, timezone

from app.models import (
    CourseNormalized, HippodromeNormalized, PartantNormalized,
    PerformanceNormalized, ReunionNormalized,
)


class FakeQ:
    def __init__(self, store, name):
        self.store, self.name, self.payload, self.op = store, name, None, None
    def upsert(self, payload, on_conflict=None):
        self.op, self.payload = "upsert", payload; return self
    def insert(self, payload):
        self.op, self.payload = "insert", payload; return self
    def select(self, *a, **k): self.op = "select"; return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self):
        rows = self.payload if isinstance(self.payload, list) else [self.payload]
        out = []
        for r in rows:
            nr = dict(r); nr.setdefault("id", f"{self.name}-{len(self.store.setdefault(self.name, []))+1}")
            self.store[self.name].append(nr); out.append(nr)
        class R: pass
        res = R(); res.data = out; return res


class FakeClient:
    def __init__(self): self.store = {}
    def table(self, name): return FakeQ(self.store, name)


def _course(statut="a_venir"):
    return CourseNormalized(
        numero_course=1, discipline="plat", distance_m=1400, allocation=20100.0,
        categorie_classe=None, heure_depart=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
        statut=statut,
        reunion=ReunionNormalized(
            date=date(2026, 7, 13), numero_reunion=1,
            hippodrome=HippodromeNormalized(code_pmu="DIE", nom="DIEPPE", pays="FRA"),
        ),
    )


def _partant(corde, entraineur=None, pos=None):
    return PartantNormalized(
        numero_corde=corde, nom_cheval=f"H{corde}", id_pmu_cheval=f"H{corde}-a-b", sexe=None,
        driver_jockey_nom="J.DOE", entraineur_nom=entraineur, poids_kg=58.0,
        reduction_kilometrique=None, ferrage=None, musique=None, statut="partant", cotes=[],
        position_arrivee=pos,
    )


def test_save_course_import_returns_cheval_id_by_corde():
    from app.supabase_writer import SupabaseWriter
    w = SupabaseWriter(FakeClient())
    result = w.save_course_import(_course(), [_partant(1), _partant(2)])
    assert set(result["cheval_id_by_corde"].keys()) == {1, 2}
    assert all(result["cheval_id_by_corde"].values())


def test_save_performances_writes_rows():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    perfs = {1: [PerformanceNormalized(num_pmu=1, date_course=date(2026, 6, 1),
             hippodrome="DIEPPE", discipline="plat", distance_m=1400, allocation=20100.0,
             nb_participants=9, place=2, status_arrivee="PLACE", raw_place="2",
             jockey_nom="S.PASQUIER", poids_jockey=58.0, corde=8, oeillere=None)]}
    n = w.save_performances(perfs, {1: "cheval-1"})
    assert n == 1
    row = client.store["chevaux_performances"][0]
    assert row["cheval_id"] == "cheval-1" and row["place"] == 2 and row["jockey_nom"] == "S.PASQUIER"


def test_save_performances_skips_unknown_corde():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    perfs = {9: [PerformanceNormalized(num_pmu=9, date_course=date(2026, 6, 1), distance_m=1400, hippodrome="X")]}
    assert w.save_performances(perfs, {1: "cheval-1"}) == 0
    assert client.store.get("chevaux_performances", []) == []


def test_save_entraineur_resultats_only_finished_with_place():
    from app.supabase_writer import SupabaseWriter
    client = FakeClient(); w = SupabaseWriter(client)
    partants = [_partant(1, entraineur="N.CAULLERY", pos=1), _partant(2, entraineur=None, pos=2)]
    n = w.save_entraineur_resultats(_course(statut="terminee"), partants, {1: "cheval-1", 2: "cheval-2"})
    assert n == 1
    row = client.store["entraineur_resultats"][0]
    assert row["entraineur_nom"] == "N.CAULLERY" and row["place"] == 1 and row["cheval_id"] == "cheval-1"
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_writer_enrichi.py -q`
Expected: FAIL — méthodes inexistantes / `cheval_id_by_corde` absent.

- [ ] **Step 3: Modifier `app/supabase_writer.py`**

Ajouter l'import en tête : `from app.models import CourseNormalized, PartantNormalized, PerformanceNormalized`.

Dans `save_course_import`, à l'upsert du partant, ajouter la colonne `place_corde` :

```python
                        "place_corde": partant.place_corde,
```

À l'upsert de la course, ajouter la colonne `allocation` :

```python
                    "allocation": course.allocation,
```

Construire la map corde→cheval pendant la boucle (déclarer `cheval_id_by_corde = {}` avant la boucle des partants, et dans la boucle, après l'upsert du cheval) :

```python
            cheval_id_by_corde[partant.numero_corde] = cheval_row["id"]
```

Et modifier le `return` :

```python
        return {"course_id": course_row["id"], "partant_ids": partant_ids,
                "cheval_id_by_corde": cheval_id_by_corde}
```

Ajouter les deux méthodes :

```python
    def save_performances(self, perf_by_num_pmu, cheval_id_by_corde) -> int:
        n = 0
        for num_pmu, perfs in perf_by_num_pmu.items():
            cheval_id = cheval_id_by_corde.get(num_pmu)
            if cheval_id is None:
                continue
            for perf in perfs:
                self._client.table("chevaux_performances").upsert(
                    {
                        "cheval_id": cheval_id,
                        "date_course": perf.date_course.isoformat(),
                        "hippodrome": perf.hippodrome,
                        "discipline": perf.discipline,
                        "distance_m": perf.distance_m,
                        "allocation": perf.allocation,
                        "nb_participants": perf.nb_participants,
                        "place": perf.place,
                        "status_arrivee": perf.status_arrivee,
                        "raw_place": perf.raw_place,
                        "jockey_nom": perf.jockey_nom,
                        "poids_jockey": perf.poids_jockey,
                        "corde": perf.corde,
                        "oeillere": perf.oeillere,
                    },
                    on_conflict="cheval_id,date_course,hippodrome,distance_m",
                ).execute()
                n += 1
        return n

    def save_entraineur_resultats(self, course, partants, cheval_id_by_corde) -> int:
        n = 0
        for partant in partants:
            cheval_id = cheval_id_by_corde.get(partant.numero_corde)
            if not partant.entraineur_nom or cheval_id is None:
                continue
            self._client.table("entraineur_resultats").upsert(
                {
                    "entraineur_nom": partant.entraineur_nom,
                    "cheval_id": cheval_id,
                    "date_course": course.reunion.date.isoformat(),
                    "hippodrome": course.reunion.hippodrome.nom,
                    "discipline": course.discipline,
                    "place": partant.position_arrivee,
                    "status_arrivee": None,
                },
                on_conflict="entraineur_nom,cheval_id,date_course",
            ).execute()
            n += 1
        return n
```

- [ ] **Step 4: Lancer les tests (vert) + suite writer existante**

Run: `cd backend && .venv/bin/pytest tests/test_writer_enrichi.py -q`
Expected: PASS (4 tests).
Run aussi les tests writer existants s'il y en a : `cd backend && .venv/bin/pytest -k writer -q` → tout vert.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/supabase_writer.py backend/tests/test_writer_enrichi.py
git commit -m "feat(algo): writer chevaux_performances + entraineur_resultats + place_corde/allocation"
```

---

### Task 4: Câbler l'ingestion de l'historique dans `import_course`

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_import_history.py`

**Interfaces:**
- Consumes: `fetch_performances_detaillees`, `normalize_performances` (Task 2) ; `save_performances`, `save_entraineur_resultats` (Task 3).
- Produces: `POST /courses/import` persiste l'historique en plus de la course ; réponse inchangée pour le frontend (`course_id`, `partant_ids`).

- [ ] **Step 1: Écrire le test d'intégration import (rouge)**

Le endpoint est async et appelle le réseau : on **monkeypatch** les fetch PMU et on injecte un faux writer pour vérifier le câblage (pas d'appel réseau réel).

Create `backend/tests/test_import_history.py` :

```python
import app.main as main
from fastapi.testclient import TestClient


class RecordingWriter:
    last = None
    def __init__(self, client): RecordingWriter.last = self; self.calls = []
    def save_course_import(self, course, partants):
        self.calls.append("course")
        return {"course_id": "c1", "partant_ids": ["p1"], "cheval_id_by_corde": {1: "ch1"}}
    def save_performances(self, perf, mapping):
        self.calls.append(("perf", len(perf), mapping)); return 1
    def save_entraineur_resultats(self, course, partants, mapping):
        self.calls.append("entraineur"); return 1


PROGRAMME = {"programme": {"reunions": [{
    "numOfficiel": 1, "dateReunion": 1783893600000, "timezoneOffset": 7200000,
    "pays": {"code": "FRA"},
    "hippodrome": {"code": "DIE", "libelleCourt": "DIEPPE"},
    "courses": [{"numOrdre": 1, "discipline": "PLAT", "distance": 1400,
                 "montantPrix": 20100, "heureDepart": 1783893600000,
                 "categorieParticularite": None}],
}]}}
PARTICIPANTS = {"participants": [{"numPmu": 1, "nom": "H1", "idCheval": "H1-a-b",
    "statut": "PARTANT", "placeCorde": 8}]}
PERF = {"participants": [{"numPmu": 1, "nomCheval": "H1", "coursesCourues": []}]}


def _setup(monkeypatch, perf_ok=True):
    async def fake_prog(date): return PROGRAMME
    async def fake_part(d, r, c): return PARTICIPANTS
    async def fake_perf(d, r, c):
        if not perf_ok: raise RuntimeError("PMU down")
        return PERF
    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    monkeypatch.setattr(main, "fetch_participants", fake_part)
    monkeypatch.setattr(main, "fetch_performances_detaillees", fake_perf)
    monkeypatch.setattr(main, "SupabaseWriter", RecordingWriter)
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()


def test_import_persists_history(monkeypatch):
    _setup(monkeypatch)
    try:
        r = TestClient(main.app).post("/courses/import",
            json={"date": "13072026", "numero_reunion": 1, "numero_course": 1})
        assert r.status_code == 200
        assert r.json()["course_id"] == "c1"
        calls = RecordingWriter.last.calls
        assert "course" in calls
        assert any(isinstance(c, tuple) and c[0] == "perf" for c in calls)
    finally:
        main.app.dependency_overrides.clear()


def test_import_survives_history_endpoint_failure(monkeypatch):
    _setup(monkeypatch, perf_ok=False)
    try:
        r = TestClient(main.app).post("/courses/import",
            json={"date": "13072026", "numero_reunion": 1, "numero_course": 1})
        assert r.status_code == 200          # import réussit malgré l'échec historique
        calls = RecordingWriter.last.calls
        assert "course" in calls
        assert not any(isinstance(c, tuple) and c[0] == "perf" for c in calls)
    finally:
        main.app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_import_history.py -q`
Expected: FAIL — `fetch_performances_detaillees` non importé dans `main`, historique non câblé.

- [ ] **Step 3: Modifier `app/main.py`**

Étendre l'import PMU en tête :

```python
from app.pmu_client import fetch_participants, fetch_performances_detaillees, fetch_programme
from app.pmu_normalizer import (
    find_course_in_programme, normalize_course, normalize_partants, normalize_performances,
)
```

Remplacer le corps de `import_course` après le `writer.save_course_import` :

```python
    writer = SupabaseWriter(supabase_client)
    result = writer.save_course_import(course, partants)

    try:
        raw_perf = await fetch_performances_detaillees(
            request.date, request.numero_reunion, request.numero_course
        )
        perf_by_num_pmu = normalize_performances(raw_perf)
        writer.save_performances(perf_by_num_pmu, result["cheval_id_by_corde"])
    except Exception:
        # Historique indisponible : l'import reste valide, facteurs contextuels neutres au score.
        pass

    if course.statut == "terminee":
        writer.save_entraineur_resultats(course, partants, result["cheval_id_by_corde"])

    return {"course_id": result["course_id"], "partant_ids": result["partant_ids"]}
```

- [ ] **Step 4: Lancer le test (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_import_history.py -q`
Expected: PASS (2 tests).
Run: `cd backend && .venv/bin/pytest -q` → toute la suite verte (aucune régression sur l'import existant).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/main.py backend/tests/test_import_history.py
git commit -m "feat(algo): ingest performances history on import (graceful degradation)"
```

---

### Task 5: Module `context_stats` (taux par contexte + confiance)

**Files:**
- Create: `backend/app/scoring/context_stats.py`
- Test: `backend/tests/test_context_stats.py`

**Interfaces:**
- Produces (toutes les fonctions opèrent sur des `perfs: list[dict]`, chaque dict ayant au moins `place`, `distance_m`, `discipline`, `allocation`, `hippodrome`) :
  - Constantes : `DISTANCE_BAND = 0.10`, `ALLOCATION_BAND = 0.30`, `SUCCESS_MAX_PLACE = 3`, `MIN_SAMPLE = 3`, `CONFIDENCE_FULL_AT = 10`.
  - `is_success(perf: dict) -> bool`
  - `taux_distance(perfs, distance_m) -> float | None`
  - `taux_discipline(perfs, discipline) -> float | None`
  - `taux_niveau(perfs, allocation) -> float | None`
  - `taux_hippodrome(perfs, hippodrome) -> float | None`
  - `confidence(nb_perfs: int, jockey_known: bool, entraineur_known: bool) -> float`
  - `None` = échantillon insuffisant (le moteur le traduira en neutre 0.5).

- [ ] **Step 1: Écrire les tests (rouge)**

Create `backend/tests/test_context_stats.py` :

```python
from app.scoring import context_stats as cs


def _p(place=None, distance_m=1400, discipline="plat", allocation=20000, hippodrome="DIEPPE"):
    return {"place": place, "distance_m": distance_m, "discipline": discipline,
            "allocation": allocation, "hippodrome": hippodrome}


def test_is_success_top3():
    assert cs.is_success(_p(place=1))
    assert cs.is_success(_p(place=3))
    assert not cs.is_success(_p(place=4))
    assert not cs.is_success(_p(place=None))


def test_taux_distance_within_band():
    perfs = [_p(place=1, distance_m=1400), _p(place=5, distance_m=1450),
             _p(place=2, distance_m=1350), _p(place=1, distance_m=3000)]  # 3000 hors bande
    # 3 courses dans [1260,1540] : places 1,5,2 -> 2 succès / 3
    assert cs.taux_distance(perfs, 1400) == 2 / 3


def test_taux_below_min_sample_returns_none():
    perfs = [_p(place=1, distance_m=1400), _p(place=2, distance_m=1400)]  # 2 < MIN_SAMPLE
    assert cs.taux_distance(perfs, 1400) is None


def test_taux_discipline_filters():
    perfs = [_p(place=1, discipline="plat"), _p(place=1, discipline="plat"),
             _p(place=4, discipline="plat"), _p(place=1, discipline="trot_attele")]
    assert cs.taux_discipline(perfs, "plat") == 2 / 3


def test_taux_niveau_within_band_and_skips_none_allocation():
    perfs = [_p(place=1, allocation=20000), _p(place=4, allocation=24000),
             _p(place=2, allocation=16000), _p(place=1, allocation=None)]  # None ignoré
    # bande ±30% de 20000 = [14000,26000] : 20000,24000,16000 -> places 1,4,2 -> 2/3
    assert cs.taux_niveau(perfs, 20000) == 2 / 3


def test_taux_hippodrome_filters():
    perfs = [_p(place=1, hippodrome="DIEPPE"), _p(place=2, hippodrome="DIEPPE"),
             _p(place=4, hippodrome="DIEPPE"), _p(place=1, hippodrome="VINCENNES")]
    assert cs.taux_hippodrome(perfs, "DIEPPE") == 2 / 3


def test_confidence_scales_and_clamps():
    assert cs.confidence(0, False, False) == 0.0
    assert cs.confidence(10, True, True) == 1.0
    assert cs.confidence(20, True, True) == 1.0          # plafonné
    mid = cs.confidence(5, True, True)
    assert 0.0 < mid < 1.0
    # jockey/entraineur inconnus abaissent la confiance
    assert cs.confidence(10, False, False) < cs.confidence(10, True, True)
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_context_stats.py -q`
Expected: FAIL — module `context_stats` inexistant.

- [ ] **Step 3: Créer `app/scoring/context_stats.py`**

```python
"""Taux de réussite par contexte (distance/discipline/niveau/hippodrome) + indice de confiance.

Un taux vaut None quand l'échantillon est insuffisant (< MIN_SAMPLE) — le moteur le
traduit alors en neutre 0.5. Un succès = arrivé dans les 3 premiers.
"""

DISTANCE_BAND = 0.10
ALLOCATION_BAND = 0.30
SUCCESS_MAX_PLACE = 3
MIN_SAMPLE = 3
CONFIDENCE_FULL_AT = 10


def is_success(perf: dict) -> bool:
    place = perf.get("place")
    return place is not None and place <= SUCCESS_MAX_PLACE


def _taux(subset: list[dict]) -> float | None:
    if len(subset) < MIN_SAMPLE:
        return None
    return sum(1 for p in subset if is_success(p)) / len(subset)


def taux_distance(perfs: list[dict], distance_m: int | None) -> float | None:
    if not distance_m:
        return None
    lo, hi = distance_m * (1 - DISTANCE_BAND), distance_m * (1 + DISTANCE_BAND)
    return _taux([p for p in perfs if p.get("distance_m") is not None and lo <= p["distance_m"] <= hi])


def taux_discipline(perfs: list[dict], discipline: str | None) -> float | None:
    if not discipline:
        return None
    return _taux([p for p in perfs if p.get("discipline") == discipline])


def taux_niveau(perfs: list[dict], allocation: float | None) -> float | None:
    if not allocation:
        return None
    lo, hi = allocation * (1 - ALLOCATION_BAND), allocation * (1 + ALLOCATION_BAND)
    return _taux([p for p in perfs if p.get("allocation") is not None and lo <= p["allocation"] <= hi])


def taux_hippodrome(perfs: list[dict], hippodrome: str | None) -> float | None:
    if not hippodrome:
        return None
    return _taux([p for p in perfs if p.get("hippodrome") == hippodrome])


def confidence(nb_perfs: int, jockey_known: bool, entraineur_known: bool) -> float:
    base = min(1.0, nb_perfs / CONFIDENCE_FULL_AT)
    penalty = 1.0 - 0.15 * ((not jockey_known) + (not entraineur_known))
    return round(base * penalty, 4)
```

- [ ] **Step 4: Lancer les tests (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_context_stats.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/context_stats.py backend/tests/test_context_stats.py
git commit -m "feat(algo): context_stats (taux distance/discipline/niveau/hippodrome + confiance)"
```

---

### Task 6: Module `global_stats` (agrégation jockey/entraîneur)

**Files:**
- Create: `backend/app/scoring/global_stats.py`
- Test: `backend/tests/test_global_stats.py`

**Interfaces:**
- Consumes: constantes `MIN_SAMPLE`, `SUCCESS_MAX_PLACE` de `context_stats` (Task 5).
- Produces :
  - `jockey_taux(client, jockey_nom: str) -> float | None` (depuis `chevaux_performances`).
  - `entraineur_taux(client, entraineur_nom: str) -> float | None` (depuis `entraineur_resultats`).
  - `None` si nom vide ou échantillon insuffisant.

- [ ] **Step 1: Écrire les tests (rouge)**

Create `backend/tests/test_global_stats.py` :

```python
from app.scoring import global_stats as gs


class FakeQ:
    def __init__(self, store, name): self.store, self.name, self.col, self.val = store, name, None, None
    def select(self, *a, **k): return self
    def eq(self, col, val): self.col, self.val = col, val; return self
    def execute(self):
        rows = [r for r in self.store.get(self.name, []) if r.get(self.col) == self.val]
        class R: pass
        res = R(); res.data = rows; return res


class FakeClient:
    def __init__(self, store): self.store = store
    def table(self, name): return FakeQ(self.store, name)


def test_jockey_taux_from_performances():
    store = {"chevaux_performances": [
        {"jockey_nom": "S.P", "place": 1}, {"jockey_nom": "S.P", "place": 4},
        {"jockey_nom": "S.P", "place": 2}, {"jockey_nom": "AUTRE", "place": 1},
    ]}
    assert gs.jockey_taux(FakeClient(store), "S.P") == 2 / 3


def test_jockey_taux_below_min_sample():
    store = {"chevaux_performances": [{"jockey_nom": "S.P", "place": 1}]}
    assert gs.jockey_taux(FakeClient(store), "S.P") is None


def test_jockey_taux_empty_name():
    assert gs.jockey_taux(FakeClient({}), None) is None
    assert gs.jockey_taux(FakeClient({}), "") is None


def test_entraineur_taux_from_resultats():
    store = {"entraineur_resultats": [
        {"entraineur_nom": "N.C", "place": 1}, {"entraineur_nom": "N.C", "place": 3},
        {"entraineur_nom": "N.C", "place": 8},
    ]}
    assert gs.entraineur_taux(FakeClient(store), "N.C") == 2 / 3
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_global_stats.py -q`
Expected: FAIL — module `global_stats` inexistant.

- [ ] **Step 3: Créer `app/scoring/global_stats.py`**

```python
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
```

- [ ] **Step 4: Lancer les tests (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_global_stats.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/global_stats.py backend/tests/test_global_stats.py
git commit -m "feat(algo): global_stats (agregation taux jockey/entraineur)"
```

---

### Task 7: Facteurs + pondérations (corde réelle + 6 nouveaux facteurs)

**Files:**
- Modify: `backend/app/scoring/factors.py`
- Modify: `backend/app/scoring/ponderations.py`
- Test: `backend/tests/test_factors_enrichi.py`

**Interfaces:**
- Consumes: `context_stats` (Task 5). Chaque dict partant peut contenir : `performances: list[dict]`, `jockey_taux: float|None`, `entraineur_taux: float|None`, `place_corde: int|None`, `cote_valeur`, `poids_kg`, `musique`, `numero_corde`, `statut`, `nombre_*`.
- Produces:
  - `compute_factors(partants, discipline, course_context)` où `course_context = {"distance_m", "allocation", "hippodrome"}`. Renvoie `dict[numero_corde -> dict[factor -> valeur]]` avec les 11 facteurs.
  - `DEFAULT_PONDERATIONS` couvre les 11 facteurs (somme 1.0 par discipline).

- [ ] **Step 1: Écrire les tests facteurs (rouge)**

Create `backend/tests/test_factors_enrichi.py` :

```python
from app.scoring.factors import compute_factors
from app.scoring.ponderations import DEFAULT_PONDERATIONS

CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}


def _perf(place, distance_m=1400, discipline="plat", allocation=20000, hippodrome="DIEPPE"):
    return {"place": place, "distance_m": distance_m, "discipline": discipline,
            "allocation": allocation, "hippodrome": hippodrome}


def _partant(corde, place_corde=None, perfs=None, jockey_taux=None, entraineur_taux=None):
    return {"numero_corde": corde, "statut": "partant", "cote_valeur": 5.0, "poids_kg": 56.0,
            "musique": "1p2p3p", "nombre_courses": 10, "nombre_victoires": 3, "nombre_places": 4,
            "place_corde": place_corde, "performances": perfs or [], "ferrage": None,
            "jockey_taux": jockey_taux, "entraineur_taux": entraineur_taux}


def test_new_factors_present_and_bounded():
    perfs = [_perf(1), _perf(2), _perf(5)]  # 3 courses, 2 succès -> taux 2/3 sur tous les contextes
    factors = compute_factors([_partant(1, perfs=perfs, jockey_taux=0.4, entraineur_taux=0.5)], "plat", CTX)
    f = factors[1]
    for key in ("taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"):
        assert key in f and 0.0 <= f[key] <= 1.0
    assert abs(f["taux_distance"] - 2 / 3) < 1e-9
    assert f["jockey"] == 0.4 and f["entraineur"] == 0.5


def test_neutral_when_no_history():
    factors = compute_factors([_partant(1, perfs=[])], "plat", CTX)
    f = factors[1]
    for key in ("taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"):
        assert f[key] == 0.5


def test_corde_uses_place_corde_not_numero():
    # corde 1 a une mauvaise place réelle (10), corde 2 une bonne (1) -> corde 2 mieux notée
    factors = compute_factors(
        [_partant(1, place_corde=10), _partant(2, place_corde=1)], "plat", CTX
    )
    assert factors[2]["corde"] > factors[1]["corde"]


def test_default_ponderations_sum_to_one_all_disciplines():
    keys = {"forme", "taux_reussite", "ferrage_poids", "cote", "corde",
            "taux_distance", "taux_discipline", "taux_niveau", "taux_hippodrome", "jockey", "entraineur"}
    for discipline, poids in DEFAULT_PONDERATIONS.items():
        assert set(poids.keys()) == keys, discipline
        assert abs(sum(poids.values()) - 1.0) < 1e-9, discipline
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_factors_enrichi.py -q`
Expected: FAIL — nouveaux facteurs absents, `compute_factors` n'accepte pas `course_context`, poids incomplets.

- [ ] **Step 3: Réécrire `DEFAULT_PONDERATIONS` dans `app/scoring/ponderations.py`**

Remplacer le dict `DEFAULT_PONDERATIONS` (garder `load_active_ponderation` inchangé) :

```python
_POIDS_V1 = {
    "forme": 0.16, "cote": 0.18, "taux_reussite": 0.10, "ferrage_poids": 0.08, "corde": 0.08,
    "taux_distance": 0.10, "taux_discipline": 0.06, "taux_niveau": 0.06,
    "taux_hippodrome": 0.06, "jockey": 0.06, "entraineur": 0.06,
}

DEFAULT_PONDERATIONS: dict[str, dict[str, float]] = {
    "trot_attele": dict(_POIDS_V1),
    "trot_monte": dict(_POIDS_V1),
    "plat": dict(_POIDS_V1),
    "obstacle": dict(_POIDS_V1),
}
```

Mettre à jour le docstring du module en conséquence (retirer la mention fraicheur/couple différés).

- [ ] **Step 4: Étendre `compute_factors` dans `app/scoring/factors.py`**

Ajouter l'import en tête : `from app.scoring import context_stats as cs`.

Changer la signature et compléter le calcul :

```python
def compute_factors(partants: list[dict], discipline: str, course_context: dict) -> dict[int, dict[str, float]]:
    actifs = [p for p in partants if p.get("statut") != "non_partant"]
    if not actifs:
        return {}
    is_trot = discipline in ("trot_attele", "trot_monte")

    # --- Cote : inverse (1/cote), min-max sur la course. Cote absente -> 0.
    inv_cotes = {}
    for p in actifs:
        c = p.get("cote_valeur")
        inv_cotes[p["numero_corde"]] = (1.0 / c) if c and c > 0 else 0.0
    inv_values = list(inv_cotes.values())
    lo_c, hi_c = min(inv_values), max(inv_values)

    def taux(p: dict) -> float:
        courses = p.get("nombre_courses") or 0
        if courses <= 0:
            return 0.0
        num = (p.get("nombre_victoires") or 0) + (p.get("nombre_places") or 0)
        return min(num / courses, 1.0)

    poids_values = [p.get("poids_kg") for p in actifs if p.get("poids_kg") is not None]
    lo_p = min(poids_values) if poids_values else 0.0
    hi_p = max(poids_values) if poids_values else 0.0

    def ferrage_poids(p: dict) -> float:
        if is_trot:
            return _FERRAGE_SCORE.get(p.get("ferrage"), 0.3)
        poids = p.get("poids_kg")
        if poids is None:
            return 0.5
        return 1.0 - _minmax(poids, lo_p, hi_p)

    # --- Corde : vraie corde (place_corde) si dispo, sinon numero_corde. Faible = mieux.
    def corde_value(p: dict) -> int:
        return p.get("place_corde") if p.get("place_corde") is not None else p["numero_corde"]
    corde_vals = [corde_value(p) for p in actifs]
    lo_n, hi_n = min(corde_vals), max(corde_vals)

    dist = course_context.get("distance_m")
    allocation = course_context.get("allocation")
    hippo = course_context.get("hippodrome")

    def _or_neutral(v: float | None) -> float:
        return 0.5 if v is None else v

    factors: dict[int, dict[str, float]] = {}
    for p in actifs:
        corde = p["numero_corde"]
        inv = inv_cotes[corde]
        perfs = p.get("performances") or []
        factors[corde] = {
            "forme": forme_score(p.get("musique")),
            "taux_reussite": taux(p),
            "ferrage_poids": ferrage_poids(p),
            "cote": _minmax(inv, lo_c, hi_c),
            "corde": 1.0 - _minmax(corde_value(p), lo_n, hi_n),
            "taux_distance": _or_neutral(cs.taux_distance(perfs, dist)),
            "taux_discipline": _or_neutral(cs.taux_discipline(perfs, discipline)),
            "taux_niveau": _or_neutral(cs.taux_niveau(perfs, allocation)),
            "taux_hippodrome": _or_neutral(cs.taux_hippodrome(perfs, hippo)),
            "jockey": _or_neutral(p.get("jockey_taux")),
            "entraineur": _or_neutral(p.get("entraineur_taux")),
        }
    return factors
```

- [ ] **Step 5: Mettre à jour `tests/test_factors.py` (signature changée)**

Ce fichier appelle `compute_factors(partants, "plat")` (2 args) sur 6 sites. Ajouter en tête, sous l'import :

```python
CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}
```

Puis passer `CTX` en 3ᵉ argument à **chacun** des 6 appels `compute_factors(...)`. Exemples :

```python
    factors = compute_factors([_p(1), _p(2, statut="non_partant")], "plat", CTX)
    ...
    factors = compute_factors(partants, "plat", CTX)
    ...
    plat = compute_factors([_p(1), _p(2)], "plat", CTX)
    trot = compute_factors([_p(1, rk=78.3, ferrage="DEFERRE_POSTERIEURS"), _p(2, rk=79.0, ferrage=None)], "trot_attele", CTX)
```

Le helper `_p` n'a pas besoin de changer : `compute_factors` lit `performances`/`place_corde`/`jockey_taux`/`entraineur_taux` via `.get()` (défauts → historique vide, corde = numero_corde, jockey/entraineur neutres). Les assertions existantes restent valides.

- [ ] **Step 6: Lancer les tests facteurs (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_factors.py tests/test_factors_enrichi.py -q`
Expected: PASS (les 6 tests existants + 4 nouveaux).

> Les tests `test_scoring_engine.py` et `test_scoring_routes.py` vont encore casser ici (signature `score_course` changée) — c'est attendu, ils sont corrigés en Task 8. Ne pas lancer la suite complète à cette étape.

- [ ] **Step 7: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/factors.py backend/app/scoring/ponderations.py backend/tests/test_factors_enrichi.py backend/tests/test_factors.py
git commit -m "feat(algo): 6 nouveaux facteurs + corde reelle + ponderations 11 facteurs"
```

---

### Task 8: Moteur (confiance) + câblage endpoint `compute_score`

**Files:**
- Modify: `backend/app/scoring/engine.py`
- Modify: `backend/app/scoring/routes.py`
- Test: `backend/tests/test_engine_enrichi.py`
- Test: `backend/tests/test_scoring_routes.py` (mettre à jour le `FakeStore` + assertions)

**Interfaces:**
- Consumes: `compute_factors(partants, discipline, course_context)` (Task 7), `context_stats.confidence` (Task 5), `global_stats.jockey_taux/entraineur_taux` (Task 6).
- Produces:
  - `score_course(partants, discipline, poids, course_context) -> list[dict]` ; chaque ligne gagne `confiance: float` et `nb_courses_historique: int`.
  - `POST /courses/{id}/score` renvoie ces deux champs par ligne de classement.

- [ ] **Step 1: Écrire le test moteur (rouge)**

Create `backend/tests/test_engine_enrichi.py` :

```python
from app.scoring.engine import score_course
from app.scoring.ponderations import DEFAULT_PONDERATIONS

CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}


def _partant(corde, nb_perfs, jockey_taux=None, entraineur_taux=None):
    perfs = [{"place": 1, "distance_m": 1400, "discipline": "plat", "allocation": 20000, "hippodrome": "DIEPPE"}] * nb_perfs
    return {"numero_corde": corde, "statut": "partant", "cote_valeur": 4.0, "poids_kg": 56.0,
            "musique": "1p1p1p", "nombre_courses": 10, "nombre_victoires": 5, "nombre_places": 3,
            "place_corde": corde, "performances": perfs,
            "jockey_taux": jockey_taux, "entraineur_taux": entraineur_taux}


def test_score_course_adds_confidence_and_history_count():
    rows = score_course([_partant(1, nb_perfs=12, jockey_taux=0.4, entraineur_taux=0.5),
                          _partant(2, nb_perfs=0)], "plat", DEFAULT_PONDERATIONS["plat"], CTX)
    by_corde = {r["numero_corde"]: r for r in rows}
    assert by_corde[1]["nb_courses_historique"] == 12
    assert by_corde[1]["confiance"] == 1.0                 # >=10 perfs, jockey+entraineur connus
    assert by_corde[2]["nb_courses_historique"] == 0
    assert by_corde[2]["confiance"] == 0.0


def test_score_course_weights_still_sum_to_one():
    rows = score_course([_partant(1, nb_perfs=5), _partant(2, nb_perfs=5)],
                        "plat", DEFAULT_PONDERATIONS["plat"], CTX)
    for r in rows:
        assert abs(sum(d["poids_effectif"] for d in r["details_facteurs"].values()) - 1.0) < 1e-9
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_engine_enrichi.py -q`
Expected: FAIL — `score_course` n'accepte pas `course_context`, `confiance` absent.

- [ ] **Step 3: Modifier `app/scoring/engine.py`**

```python
from app.scoring.context_stats import confidence
from app.scoring.factors import compute_factors


def score_course(partants: list[dict], discipline: str, poids: dict[str, float],
                 course_context: dict) -> list[dict]:
    factors_by_corde = compute_factors(partants, discipline, course_context)
    if not factors_by_corde:
        return []

    partant_by_corde = {p["numero_corde"]: p for p in partants}

    any_corde = next(iter(factors_by_corde.values()))
    available = [f for f in any_corde.keys() if poids.get(f, 0.0) > 0.0]
    weight_sum = sum(poids[f] for f in available)
    if weight_sum <= 0:
        effective = {f: 1.0 / len(any_corde) for f in any_corde}
    else:
        effective = {f: poids[f] / weight_sum for f in available}

    scored = []
    for corde, factor_values in factors_by_corde.items():
        details = {}
        total = 0.0
        for f, eff in effective.items():
            value = factor_values.get(f, 0.0)
            contribution = eff * value
            details[f] = {"valeur": value, "poids_effectif": eff, "contribution": contribution}
            total += contribution
        p = partant_by_corde.get(corde, {})
        perfs = p.get("performances") or []
        conf = confidence(len(perfs), p.get("jockey_taux") is not None, p.get("entraineur_taux") is not None)
        scored.append({
            "numero_corde": corde, "score_total": total, "details_facteurs": details,
            "confiance": conf, "nb_courses_historique": len(perfs),
        })

    scored.sort(key=lambda r: r["score_total"], reverse=True)
    for rang, row in enumerate(scored, start=1):
        row["rang"] = rang
    return scored
```

- [ ] **Step 4: Modifier `compute_score` dans `app/scoring/routes.py`**

Ajouter les imports en tête : `from app.scoring import global_stats`.

Ajouter un helper de contexte + d'historique (après les helpers existants) :

```python
def _course_context(client, course: dict) -> dict:
    hippodrome_nom = None
    reunion = (
        client.table("reunions").select("hippodrome_id").eq("id", course["reunion_id"]).limit(1).execute().data
    )
    if reunion:
        hippo = (
            client.table("hippodromes").select("nom").eq("id", reunion[0]["hippodrome_id"]).limit(1).execute().data
        )
        if hippo:
            hippodrome_nom = hippo[0]["nom"]
    return {"distance_m": course.get("distance_m"), "allocation": course.get("allocation"),
            "hippodrome": hippodrome_nom}


def _performances_par_cheval(client, cheval_ids: list[str]) -> dict[str, list[dict]]:
    if not cheval_ids:
        return {}
    rows = client.table("chevaux_performances").select("*").in_("cheval_id", cheval_ids).execute().data
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["cheval_id"], []).append(r)
    return out


def _jockey_entraineur_noms(client, partant: dict) -> tuple[str | None, str | None]:
    def nom(interv_id):
        if not interv_id:
            return None
        rows = client.table("intervenants").select("nom").eq("id", interv_id).limit(1).execute().data
        return rows[0]["nom"] if rows else None
    return nom(partant.get("driver_jockey_id")), nom(partant.get("entraineur_id"))
```

Étendre `_partant_dict_for_scoring` pour ajouter les champs historiques (nouvelle signature avec `perfs` + noms + client) :

```python
def _partant_dict_for_scoring(client, partant: dict, perfs: list[dict]) -> dict:
    jockey_nom, entraineur_nom = _jockey_entraineur_noms(client, partant)
    return {
        "numero_corde": partant["numero_corde"],
        "place_corde": partant.get("place_corde"),
        "musique": partant.get("musique"),
        "nombre_courses": partant.get("nombre_courses"),
        "nombre_victoires": partant.get("nombre_victoires"),
        "nombre_places": partant.get("nombre_places"),
        "cote_valeur": _retained_cote(client, partant["id"]),
        "poids_kg": partant.get("poids_kg"),
        "reduction_kilometrique": partant.get("reduction_kilometrique"),
        "ferrage": partant.get("ferrage"),
        "statut": partant.get("statut"),
        "performances": perfs,
        "jockey_taux": global_stats.jockey_taux(client, jockey_nom),
        "entraineur_taux": global_stats.entraineur_taux(client, entraineur_nom),
    }
```

Dans `compute_score`, remplacer la construction des `partant_dicts` et l'appel `score_course` :

```python
    perfs_par_cheval = _performances_par_cheval(client, [p["cheval_id"] for p in partants])
    partant_dicts = [
        _partant_dict_for_scoring(client, p, perfs_par_cheval.get(p["cheval_id"], []))
        for p in partants
    ]
    context = _course_context(client, course)

    ponderation = load_active_ponderation(client, course["discipline"])
    classement = score_course(partant_dicts, course["discipline"], ponderation["poids"], context)
```

Dans la construction de `rows` (insert scores_pronostic), les colonnes existantes suffisent (confiance/nb non stockés en base — renvoyés au frontend seulement). Dans `enriched_classement`, propager les deux champs :

```python
    enriched_classement = [
        {
            **row,
            "partant_id": partant_id_by_corde[row["numero_corde"]],
            "nom_cheval": cheval_map.get(partant_id_by_corde[row["numero_corde"]], (None, None, None))[1],
        }
        for row in classement
    ]
```

> `row` contient déjà `confiance` et `nb_courses_historique` (issus de `score_course`), donc `**row` les propage automatiquement dans la réponse.

- [ ] **Step 5: Mettre à jour `tests/test_scoring_engine.py` (signature changée)**

Ce fichier appelle `score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])` (3 args) sur 4 sites. Ajouter en tête, sous les imports :

```python
CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}
```

Puis passer `CTX` en 4ᵉ argument à **chacun** des 4 appels `score_course(...)`. Exemple :

```python
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"], CTX)
```

Le helper `_p` n'a pas besoin de changer (défauts via `.get()`). Les assertions existantes (classement, poids = 1, score ∈ [0,1], détails cohérents, non-partant exclu) restent valides.

- [ ] **Step 6: Mettre à jour `tests/test_scoring_routes.py`**

Le `FakeStore` doit connaître les nouvelles tables et colonnes. Dans `FakeStore.__init__`, ajouter aux `tables` :

```python
            "chevaux_performances": [],
            "entraineur_resultats": [],
            "reunions": [{"id": "r1", "hippodrome_id": "h1", "date": "2026-07-13", "numero_reunion": 1}],
            "hippodromes": [{"id": "h1", "nom": "DIEPPE", "code_pmu": "DIE", "pays": "FRA"}],
            "intervenants": [],
```

Ajouter `"allocation": 20000` et `"reunion_id": "r1"` à la ligne `courses`. Sur les deux partants `p1`/`p2`, ajouter les colonnes lues par le nouveau code si elles manquent : `"place_corde": 1` (resp. 2), `"driver_jockey_id": None`, `"entraineur_id": None` (le `cheval_id` est déjà présent : `"ch1"`/`"ch2"`).

Ajouter une assertion dans `test_score_endpoint_returns_ranked_pronostic` :

```python
        assert "confiance" in body["classement"][0]
        assert "nb_courses_historique" in body["classement"][0]
```

- [ ] **Step 7: Lancer les tests (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_engine_enrichi.py tests/test_scoring_engine.py tests/test_scoring_routes.py -q`
Expected: PASS.
Run: `cd backend && .venv/bin/pytest -q` → **toute la suite verte** (le changement de signature `score_course` est bien répercuté partout).

- [ ] **Step 8: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/engine.py backend/app/scoring/routes.py backend/tests/test_engine_enrichi.py backend/tests/test_scoring_engine.py backend/tests/test_scoring_routes.py
git commit -m "feat(algo): moteur confiance + cablage compute_score (historique + stats globales)"
```

---

### Task 9: Frontend — confiance + jockey/entraîneur + enrichissement GET /courses

**Files:**
- Modify: `backend/app/scoring/routes.py` (enrichir `get_course` avec noms jockey/entraîneur)
- Modify: `backend/tests/test_scoring_routes.py`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/PronosticTable.tsx`
- Modify: `frontend/components/PartantsTable.tsx`

**Interfaces:**
- Consumes: `ScoreRow.confiance`, `ScoreRow.nb_courses_historique` (Task 8) ; helper `_jockey_entraineur_noms` (Task 8).
- Produces: `GET /courses/:id` expose `jockey_nom`/`entraineur_nom` par partant ; types TS étendus ; UI confiance + colonnes.

- [ ] **Step 1: Test backend (rouge) — noms jockey/entraîneur sur GET /courses**

Dans `backend/tests/test_scoring_routes.py`, d'abord garnir le FakeStore : ajouter deux intervenants et référencer-les sur un partant. Dans `tables["intervenants"]` mettre :

```python
            "intervenants": [
                {"id": "iv1", "nom": "S.PASQUIER", "role": "jockey"},
                {"id": "iv2", "nom": "N.CAULLERY", "role": "entraineur"},
            ],
```

et sur le partant `p1`, poser `"driver_jockey_id": "iv1", "entraineur_id": "iv2"`.

Ajouter le test :

```python
def test_get_course_partants_expose_jockey_entraineur():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.get("/courses/course-1").json()
        p1 = next(p for p in body["partants"] if p["numero_corde"] == 1)
        assert p1["jockey_nom"] == "S.PASQUIER"
        assert p1["entraineur_nom"] == "N.CAULLERY"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_scoring_routes.py::test_get_course_partants_expose_jockey_entraineur -q`
Expected: FAIL — `jockey_nom` absent.

- [ ] **Step 3: Enrichir `get_course` dans `app/scoring/routes.py`**

Dans la compréhension `enriched` de `get_course`, ajouter les deux noms via le helper existant `_jockey_entraineur_noms` :

```python
    enriched = []
    for partant in partants:
        jockey_nom, entraineur_nom = _jockey_entraineur_noms(client, partant)
        enriched.append({
            **partant,
            "partant_id": partant["id"],
            "cote_retenue": _retained_cote(client, partant["id"]),
            "nom_cheval": cheval_map.get(partant["id"], (None, None, None))[1],
            "sexe": cheval_map.get(partant["id"], (None, None, None))[2],
            "jockey_nom": jockey_nom,
            "entraineur_nom": entraineur_nom,
        })
```

- [ ] **Step 4: Lancer (vert) + suite backend**

Run: `cd backend && .venv/bin/pytest -q`
Expected: toute la suite verte.

- [ ] **Step 5: Étendre les types TS `frontend/lib/types.ts`**

Sur `Partant`, ajouter :

```typescript
  jockey_nom: string | null;
  entraineur_nom: string | null;
```

Sur `ScoreRow`, ajouter :

```typescript
  confiance?: number;
  nb_courses_historique?: number;
```

- [ ] **Step 6: Badge de confiance dans `frontend/components/PronosticTable.tsx`**

Ajouter une colonne « Confiance » dans l'en-tête (après « Cote »), et par ligne un badge. Insérer, dans la ligne principale, une cellule :

```tsx
<td className="px-3 py-2">
  {typeof row.confiance === "number" ? (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`h-2 w-2 rounded-full ${
          row.confiance >= 0.66 ? "bg-emerald-400" : row.confiance >= 0.33 ? "bg-amber-400" : "bg-red-400"
        }`}
      />
      <span className="font-mono tabular-nums text-xs text-slate-400">
        {row.nb_courses_historique ?? 0} c.
      </span>
    </span>
  ) : (
    <span className="text-slate-600">—</span>
  )}
</td>
```

Adapter le `colSpan` de la ligne de détail dépliée (incrémenter de 1 pour la nouvelle colonne).

- [ ] **Step 7: Colonnes jockey/entraîneur dans `frontend/components/PartantsTable.tsx`**

Ajouter deux `<th>` (« Jockey », « Entraîneur ») après « Cheval », et par ligne deux `<td>` :

```tsx
<td className="px-3 py-2 text-slate-300">{p.jockey_nom ?? "—"}</td>
<td className="px-3 py-2 text-slate-300">{p.entraineur_nom ?? "—"}</td>
```

- [ ] **Step 8: Vérifier le build frontend**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (seul l'avertissement pré-existant multiple-lockfiles est toléré).

- [ ] **Step 9: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/routes.py backend/tests/test_scoring_routes.py frontend/lib/types.ts frontend/components/PronosticTable.tsx frontend/components/PartantsTable.tsx
git commit -m "feat(algo): frontend confiance + jockey/entraineur + enrich GET /courses"
```

---

### Task 10: Vérification bout-en-bout (contrôleur)

**Files:** aucun (vérification). Prérequis : **migration 0003 appliquée** sur le Supabase de l'utilisateur.

- [ ] **Step 1: Confirmer l'application de la migration 0003**

Demander à l'utilisateur d'appliquer `supabase/migrations/0003_algo_enrichi_schema.sql` sur son Supabase (comme 0001/0002). Sans ça, l'import écrira dans des tables inexistantes.

- [ ] **Step 2: Lancer le backend et importer une vraie course**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # background
```

Importer via HTTP (contrat exact appelé par le frontend) une course du jour, ex. R1C1 :

```bash
curl -s -X POST http://localhost:8000/courses/import \
  -H "Content-Type: application/json" \
  -d '{"date":"13072026","numero_reunion":1,"numero_course":1}'
```

- [ ] **Step 3: Vérifier l'historique peuplé + le score enrichi**

`GET /courses/<id>` → vérifier `jockey_nom`/`entraineur_nom` non nuls.
`POST /courses/<id>/score` → vérifier que chaque ligne contient les 6 nouveaux facteurs dans `details_facteurs`, `confiance` et `nb_courses_historique` cohérents (chevaux avec historique → confiance > 0 ; débutants → facteurs contextuels à 0.5, confiance basse), `Σ contributions == score_total`, poids effectifs sommant à 1.0.

- [ ] **Step 4: Vérifier le frontend**

`cd frontend && npm run dev`, ouvrir http://localhost:3000, importer, vérifier colonnes jockey/entraîneur dans les partants, et badge de confiance dans le classement après « Calculer le pronostic ». (Contrôle visuel par l'utilisateur si aucun outil navigateur n'est disponible.)

- [ ] **Step 5: Corriger tout écart** constaté et re-vérifier. Arrêter les serveurs.

---

## Ce que ce plan produit

Un scoring enrichi de 11 facteurs adossés à l'historique PMU stocké : taux de réussite par distance / discipline / niveau / hippodrome, taux jockey/entraîneur, corde réelle, et un indice de confiance par cheval — affiché dans une interface qui montre où le pronostic est solide. L'historique brut se capitalise à chaque import, ouvrant la voie au backtest (Plan 4).

## Hors périmètre

- Calibration des poids par backtest (Plan 4) — poids par défaut fixes en v1.
- Scraping Geny (Plan 3).
- Reformatage cosmétique des libellés sexe (M/F/H) — backlog Plan 2b.
- Optimisations N+1 au score (lookups intervenants/cotes par partant) — acceptables à l'échelle personnelle, backlog.
