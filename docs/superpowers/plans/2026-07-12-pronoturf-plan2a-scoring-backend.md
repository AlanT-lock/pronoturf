# pronoturf — Plan 2a : stats PMU + moteur de scoring + endpoints (backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calculer un score de pronostic pondéré et explicable par cheval pour une course importée, et l'exposer via des endpoints FastAPI testables en local.

**Architecture:** Prolonge le pipeline du Plan 1. Migration `0002` (contrainte unique sur `cotes` + colonnes stats sur `partants`). Le normalizer/writer stockent les compteurs PMU déjà récupérés. Un module `scoring/` (parsing musique → facteurs normalisés → pondération avec redistribution → écriture `scores_pronostic`) calcule le classement. De nouveaux endpoints FastAPI exposent lecture, saisie manuelle et scoring. Le frontend Next.js est le Plan 2b (hors de ce plan).

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, supabase-py, pytest (+ respx pour les rares appels HTTP), Supabase Postgres.

## Global Constraints

- Service FastAPI **local** pour le MVP (pas de déploiement prod). Clé **service-role** côté backend uniquement, jamais exposée. Voir spec `docs/superpowers/specs/2026-07-12-pronoturf-plan2-scoring-design.md`.
- Le frontend (Plan 2b) lira **via l'API FastAPI**, pas Supabase en direct → pas de RLS à ce stade.
- Aucune récupération planifiée (cron) : tout à la demande.
- **Aucun nouvel appel à l'API PMU** dans ce plan : les stats sont extraites du payload `participants` déjà récupéré par le Plan 1. (Le facteur fraîcheur, qui nécessiterait `performances-detaillees`, est différé — poids 0.)
- Pondérations **jamais en dur dans le code** : stockées dans la table `ponderations_config`, une config `actif` par défaut par discipline.
- Scores normalisés sur `[0, 1]`. Les partants `non_partant` sont exclus du calcul et du classement.
- Env venv : `/Users/alantouati/pronoturf/backend/.venv`. Dépendances déjà installées, pins exacts dans `backend/requirements.txt` — ne pas les modifier sans raison. `pytest.ini` a `asyncio_mode = auto`.
- Le vrai `backend/.env` (credentials Supabase) existe déjà et est gitignoré : **ne jamais le lire, l'afficher ni le committer.**

## Contexte du code existant (Plan 1)

- `app/models.py` : `PartantNormalized` (numero_corde, nom_cheval, id_pmu_cheval, sexe, driver_jockey_nom, entraineur_nom, poids_kg, reduction_kilometrique, ferrage, musique, statut, cotes: list[CoteNormalized], position_arrivee), `CourseNormalized`, `CoteNormalized`, etc.
- `app/pmu_normalizer.py` : `normalize_partants(raw_participants: list[dict], course_terminee: bool) -> list[PartantNormalized]`.
- `app/supabase_writer.py` : `SupabaseWriter(client).save_course_import(course, partants) -> {"course_id": str, "partant_ids": list[str]}`. Ordre d'écriture : hippodrome → reunion → course → (par partant) cheval → intervenants → partant → cotes. Rôle rider dérivé de la discipline (`rider_role = "driver" if course.discipline == "trot_attele" else "jockey"`).
- `app/supabase_client.py` : `get_supabase_client() -> Client`.
- `app/main.py` : `GET /health`, `POST /courses/import` (body `ImportCourseRequest(date, numero_reunion, numero_course)`).
- Schéma DB (migration `0001`) : tables `hippodromes, reunions, courses, chevaux, intervenants, partants, cotes, resultats, ponderations_config, scores_pronostic, backtest_resultats`. `partants` : numero_corde, poids_kg, reduction_kilometrique, ferrage, musique, statut, champs_manuels (jsonb). `cotes` : partant_id, type_capture, valeur, capture_at (pas de contrainte unique). `ponderations_config` : discipline, nom, poids (jsonb), actif, version. `scores_pronostic` : course_id, partant_id, ponderation_config_id, score_total, rang_pronostique, details_facteurs (jsonb), calculated_at.

## Champs de stats PMU (vérifiés sur données réelles 2026-07-12)

Dans chaque `participants[i]` : `age` (int), `nombreCourses` (int), `nombreVictoires` (int), `nombrePlaces` (int, nombre de fois placé au sens PMU), `nombrePlacesSecond`, `nombrePlacesTroisieme`, `gainsParticipant.gainsCarriere` (int, centimes d'euro), `gainsParticipant.gainsAnneeEnCours` (int, centimes). Absents chez un « inédit » (0 course) mais les compteurs valent alors 0.

## File Structure

```
supabase/migrations/
  0002_scoring_schema.sql          # unique cotes + colonnes stats partants
backend/app/
  models.py                        # + champs stats sur PartantNormalized (modifié)
  pmu_normalizer.py                # + peuplement stats (modifié)
  supabase_writer.py               # + écriture stats + on_conflict cotes (modifié)
  main.py                          # inclut le router scoring (modifié)
  scoring/
    __init__.py
    musique.py                     # parsing musique -> score de forme
    factors.py                     # calcul + normalisation des facteurs par course
    engine.py                      # pondération + redistribution -> scores_pronostic
    ponderations.py                # config de pondération par défaut + chargement/seed
    routes.py                      # GET/PATCH/POST endpoints scoring & lecture
backend/tests/
  test_musique.py
  test_factors.py
  test_scoring_engine.py
  test_ponderations.py
  test_scoring_routes.py
```

---

### Task 1: Migration 0002 — unique cotes + colonnes stats

**Files:**
- Create: `supabase/migrations/0002_scoring_schema.sql`

**Interfaces:**
- Produces: contrainte `cotes_partant_type_unique`, colonnes `partants.age/nombre_courses/nombre_victoires/nombre_places/gains_carriere/gains_annee_en_cours`.

- [ ] **Step 1: Écrire la migration**

`supabase/migrations/0002_scoring_schema.sql` :
```sql
-- Dédoublonnage éventuel des cotes avant d'ajouter la contrainte unique :
-- garde la ligne la plus récente par (partant_id, type_capture).
delete from cotes c
using cotes c2
where c.partant_id = c2.partant_id
  and c.type_capture = c2.type_capture
  and c.capture_at < c2.capture_at;

alter table cotes
  add constraint cotes_partant_type_unique unique (partant_id, type_capture);

alter table partants
  add column age int,
  add column nombre_courses int,
  add column nombre_victoires int,
  add column nombre_places int,
  add column gains_carriere numeric,
  add column gains_annee_en_cours numeric;
```

- [ ] **Step 2: Appliquer la migration**

L'utilisateur applique le SQL dans le dashboard Supabase (le projet est sur son compte, pas accessible via MCP). Le contrôleur fournit le contenu du fichier à coller et attend confirmation avant de continuer.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf && git add supabase/migrations/0002_scoring_schema.sql && git commit -m "feat(db): unique cotes constraint + partant stat columns"
```

---

### Task 2: Étendre les modèles + normalizer pour les stats PMU

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/pmu_normalizer.py`
- Test: `backend/tests/test_pmu_normalizer.py` (ajout)

**Interfaces:**
- Consumes: payload `participants` PMU.
- Produces: `PartantNormalized` avec `age, nombre_courses, nombre_victoires, nombre_places, gains_carriere, gains_annee_en_cours` (tous `Optional`, défaut `None`).

- [ ] **Step 1: Écrire le test (échoue d'abord)**

Ajouter à `backend/tests/test_pmu_normalizer.py` :
```python
def test_normalize_partants_trot_maps_stats(pmu_participants_trot_sample):
    partants = normalize_partants(pmu_participants_trot_sample["participants"], course_terminee=True)
    igor = next(p for p in partants if p.nom_cheval == "IGOR THEPOL")
    assert igor.age == 8
    assert igor.nombre_courses == 46
    assert igor.nombre_victoires == 2
    assert igor.nombre_places == 24
    assert igor.gains_carriere == 3416500
    assert igor.gains_annee_en_cours == 33000
```

Prérequis fixture : le fichier `backend/tests/fixtures/pmu_participants_trot_sample.json` doit contenir ces champs pour IGOR THEPOL. Ajouter dans son objet (à côté de `musique`/`reductionKilometrique`) : `"age": 8, "nombreCourses": 46, "nombreVictoires": 2, "nombrePlaces": 24, "gainsParticipant": {"gainsCarriere": 3416500, "gainsAnneeEnCours": 33000}`. (Valeurs réelles capturées le 2026-07-12.)

- [ ] **Step 2: Lancer le test → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_normalizer.py::test_normalize_partants_trot_maps_stats -v`
Expected: FAIL (`AttributeError: 'PartantNormalized' object has no attribute 'age'`).

- [ ] **Step 3: Étendre `PartantNormalized`**

Dans `backend/app/models.py`, ajouter à la fin de `PartantNormalized` (après `position_arrivee`) :
```python
    age: Optional[int] = None
    nombre_courses: Optional[int] = None
    nombre_victoires: Optional[int] = None
    nombre_places: Optional[int] = None
    gains_carriere: Optional[float] = None
    gains_annee_en_cours: Optional[float] = None
```

- [ ] **Step 4: Peupler dans le normalizer**

Dans `backend/app/pmu_normalizer.py`, `normalize_partants`, à la construction de chaque `PartantNormalized`, ajouter ces arguments (le dict `gains` peut être absent — `.get(...) or {}`) :
```python
                age=raw.get("age"),
                nombre_courses=raw.get("nombreCourses"),
                nombre_victoires=raw.get("nombreVictoires"),
                nombre_places=raw.get("nombrePlaces"),
                gains_carriere=(raw.get("gainsParticipant") or {}).get("gainsCarriere"),
                gains_annee_en_cours=(raw.get("gainsParticipant") or {}).get("gainsAnneeEnCours"),
```

- [ ] **Step 5: Lancer les tests → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_pmu_normalizer.py -v`
Expected: PASS (tous, dont le nouveau).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/models.py backend/app/pmu_normalizer.py backend/tests/test_pmu_normalizer.py backend/tests/fixtures/pmu_participants_trot_sample.json && git commit -m "feat(ingestion): normalize PMU horse stats (age, wins, places, gains)"
```

---

### Task 3: Écrire les stats + on_conflict cotes dans le writer

**Files:**
- Modify: `backend/app/supabase_writer.py`
- Test: `backend/tests/test_supabase_writer.py` (ajout)

**Interfaces:**
- Consumes: `PartantNormalized` (avec stats).
- Produces: le payload d'upsert `partants` inclut les 6 colonnes stats ; l'upsert `cotes` utilise `on_conflict="partant_id,type_capture"`.

- [ ] **Step 1: Écrire le test (échoue d'abord)**

Ajouter à `backend/tests/test_supabase_writer.py` (le `_sample_partants()` existant doit inclure des stats — ajouter `age=8, nombre_courses=46, nombre_victoires=2, nombre_places=24, gains_carriere=3416500, gains_annee_en_cours=33000` à la construction du `PartantNormalized` de test) :
```python
def test_save_course_import_writes_partant_stats_and_cote_on_conflict():
    fake_client = FakeSupabaseClient()
    writer = SupabaseWriter(fake_client)
    writer.save_course_import(_sample_course(), _sample_partants())

    partant_payload = next(row for name, row in fake_client.calls if name == "partants")
    assert partant_payload["nombre_victoires"] == 2
    assert partant_payload["gains_carriere"] == 3416500

    cote_calls = [row for name, row in fake_client.calls if name == "cotes"]
    assert cote_calls, "au moins une cote écrite"
    assert fake_client.last_on_conflict["cotes"] == "partant_id,type_capture"
```

Le `FakeTable`/`FakeSupabaseClient` existant doit enregistrer le `on_conflict` reçu. Modifier `FakeTable.upsert` pour stocker `on_conflict` et l'exposer via le client :
```python
    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        self._client.last_on_conflict[self._name] = on_conflict
        return self
```
et initialiser `self.last_on_conflict = {}` dans `FakeSupabaseClient.__init__`. (Cette amélioration corrige aussi une lacune identifiée à la revue du Plan 1 : le double de test ignorait `on_conflict`.)

- [ ] **Step 2: Lancer le test → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_supabase_writer.py::test_save_course_import_writes_partant_stats_and_cote_on_conflict -v`
Expected: FAIL (stats absentes du payload ou `on_conflict` cotes à `None`).

- [ ] **Step 3: Étendre le writer**

Dans `backend/app/supabase_writer.py`, dans l'upsert `partants`, ajouter au dict les 6 colonnes :
```python
                        "age": partant.age,
                        "nombre_courses": partant.nombre_courses,
                        "nombre_victoires": partant.nombre_victoires,
                        "nombre_places": partant.nombre_places,
                        "gains_carriere": partant.gains_carriere,
                        "gains_annee_en_cours": partant.gains_annee_en_cours,
```
Et pour l'upsert `cotes`, ajouter l'argument `on_conflict` :
```python
                self._client.table("cotes").upsert(
                    {
                        "partant_id": partant_row["id"],
                        "type_capture": cote.type_capture,
                        "valeur": cote.valeur,
                        "capture_at": cote.capture_at.isoformat(),
                    },
                    on_conflict="partant_id,type_capture",
                ).execute()
```

- [ ] **Step 4: Lancer les tests → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_supabase_writer.py -v`
Expected: PASS (tous).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/supabase_writer.py backend/tests/test_supabase_writer.py && git commit -m "feat(ingestion): persist horse stats and upsert cotes on conflict"
```

---

### Task 4: Parsing de la musique → score de forme

**Files:**
- Create: `backend/app/scoring/__init__.py`
- Create: `backend/app/scoring/musique.py`
- Test: `backend/tests/test_musique.py`

**Interfaces:**
- Produces: `parse_musique(musique: str) -> list[Optional[int]]` (place par perf récente→ancienne ; `None` = non-placé/disqualifié/tombé/arrêté ou `0`), `forme_score(musique: Optional[str], n: int = 5) -> float` sur `[0, 1]` (`0.0` si musique vide/None).

- [ ] **Step 1: Écrire les tests (échouent d'abord)**

`backend/tests/test_musique.py` :
```python
import pytest

from app.scoring.musique import forme_score, parse_musique


def test_parse_musique_extracts_places_recent_first():
    # 7aDm5a(25)6m... -> 7e, disqualifié, 5e, 6e, ...
    places = parse_musique("7aDm5a(25)6mDm9m3mDm9m")
    assert places[0] == 7
    assert places[1] is None  # D = disqualifié
    assert places[2] == 5
    assert places[3] == 6


def test_parse_musique_zero_is_unplaced():
    places = parse_musique("1a0a2a")
    assert places == [1, None, 2]


def test_parse_musique_empty_returns_empty():
    assert parse_musique("") == []
    assert parse_musique(None) == []


def test_forme_score_winner_higher_than_backmarker():
    good = forme_score("1a1a2a1a2a")
    bad = forme_score("0a0aDa9a8a")
    assert good > bad
    assert 0.0 <= good <= 1.0
    assert 0.0 <= bad <= 1.0


def test_forme_score_recent_weighted_more():
    # même perfs, ordre inversé : la bonne perf récente doit scorer plus haut
    recent_good = forme_score("1a9a9a9a9a")
    recent_bad = forme_score("9a9a9a9a1a")
    assert recent_good > recent_bad


def test_forme_score_empty_is_zero():
    assert forme_score(None) == 0.0
    assert forme_score("") == 0.0
```

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_musique.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.scoring'`).

- [ ] **Step 3: Implémenter**

`backend/app/scoring/__init__.py` : fichier vide.

`backend/app/scoring/musique.py` :
```python
"""Parsing de la musique PMU (historique compact des performances) en score de forme.

Format : suite de perfs récente→ancienne, chaque perf = <résultat><discipline>.
Résultat : '1'..'9' = place à l'arrivée, '0' = non-placé/au-delà,
'D'/'T'/'A'/'R' = disqualifié/tombé/arrêté/rétrogradé (mauvaise perf).
Les marqueurs d'année entre parenthèses (ex '(25)') sont ignorés.
"""

import re
from typing import Optional

# Un token de perf = un caractère résultat suivi d'une lettre de discipline.
_PERF_RE = re.compile(r"([0-9DTARdtar])[a-zA-Z]")

# Score par place : 1er le meilleur, décroissant ; non-placé/disqualifié = 0.
_PLACE_SCORE = {1: 1.0, 2: 0.85, 3: 0.70, 4: 0.55, 5: 0.45, 6: 0.35, 7: 0.25, 8: 0.15, 9: 0.10}


def parse_musique(musique: Optional[str]) -> list[Optional[int]]:
    if not musique:
        return []
    cleaned = re.sub(r"\([^)]*\)", "", musique)  # retire les marqueurs d'année
    places: list[Optional[int]] = []
    for match in _PERF_RE.finditer(cleaned):
        result = match.group(1).upper()
        if result.isdigit() and result != "0":
            places.append(int(result))
        else:  # '0', D, T, A, R -> non-placé
            places.append(None)
    return places


def forme_score(musique: Optional[str], n: int = 5) -> float:
    places = parse_musique(musique)[:n]
    if not places:
        return 0.0
    # Poids dégressifs : la perf la plus récente pèse le plus (n, n-1, ..., 1).
    weights = list(range(len(places), 0, -1))
    total_weight = sum(weights)
    score = 0.0
    for place, weight in zip(places, weights):
        per_race = _PLACE_SCORE.get(place, 0.0) if place is not None else 0.0
        score += per_race * weight
    return score / total_weight
```

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_musique.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/__init__.py backend/app/scoring/musique.py backend/tests/test_musique.py && git commit -m "feat(scoring): parse musique into recency-weighted form score"
```

---

### Task 5: Config de pondération par défaut (chargement + seed)

**Files:**
- Create: `backend/app/scoring/ponderations.py`
- Test: `backend/tests/test_ponderations.py`

**Interfaces:**
- Produces: `DEFAULT_PONDERATIONS: dict[str, dict[str, float]]` (par discipline → {facteur: poids}), `def load_active_ponderation(client, discipline: str) -> dict` (renvoie `{"id": ..., "poids": {...}}`, en seedant la config par défaut si aucune active n'existe pour la discipline).

Les clés de facteurs (partagées par tout le module scoring) : `"forme"`, `"taux_reussite"`, `"ferrage_poids"`, `"cote"`, `"corde"`, `"fraicheur"`, `"couple"`, `"entraineur"`.

- [ ] **Step 1: Écrire les tests (échouent d'abord)**

`backend/tests/test_ponderations.py` :
```python
from app.scoring.ponderations import DEFAULT_PONDERATIONS, load_active_ponderation


def test_default_ponderations_sum_to_one_per_discipline():
    for discipline, poids in DEFAULT_PONDERATIONS.items():
        assert abs(sum(poids.values()) - 1.0) < 1e-9, discipline


def test_default_ponderations_cover_all_disciplines():
    assert set(DEFAULT_PONDERATIONS) == {"trot_attele", "trot_monte", "plat", "obstacle"}


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table):
        self._table = table

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeResult(self._table.rows)

    def insert(self, payload):
        row = dict(payload)
        row["id"] = "seeded-id"
        self._table.rows = [row]
        return self


class _FakeTable:
    def __init__(self):
        self.rows = []


class _FakeClient:
    def __init__(self):
        self._tables = {}

    def table(self, name):
        self._tables.setdefault(name, _FakeTable())
        return _FakeQuery(self._tables[name])


def test_load_active_ponderation_seeds_when_absent():
    client = _FakeClient()
    result = load_active_ponderation(client, "plat")
    assert result["poids"] == DEFAULT_PONDERATIONS["plat"]
    assert result["id"] == "seeded-id"
```

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_ponderations.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter**

`backend/app/scoring/ponderations.py` :
```python
"""Pondérations de scoring : valeurs par défaut par discipline + chargement/seed depuis la DB.

Les facteurs Geny/historique (fraicheur, couple, entraineur) ont un poids 0 au Plan 2 ;
le moteur redistribue leur poids sur les facteurs disponibles. Ils passeront > 0 en Plan 3/4.
"""

# Poids par discipline. Somme = 1.0. fraicheur/couple/entraineur à 0 (différés).
DEFAULT_PONDERATIONS: dict[str, dict[str, float]] = {
    "trot_attele": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "trot_monte": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "plat": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
    "obstacle": {
        "forme": 0.30, "taux_reussite": 0.20, "ferrage_poids": 0.15,
        "cote": 0.20, "corde": 0.15, "fraicheur": 0.0, "couple": 0.0, "entraineur": 0.0,
    },
}


def load_active_ponderation(client, discipline: str) -> dict:
    existing = (
        client.table("ponderations_config")
        .select("id, poids")
        .eq("discipline", discipline)
        .eq("actif", True)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]
    seeded = (
        client.table("ponderations_config")
        .insert(
            {
                "discipline": discipline,
                "nom": "defaut",
                "poids": DEFAULT_PONDERATIONS[discipline],
                "actif": True,
                "version": 1,
            }
        )
        .execute()
        .data[0]
    )
    return {"id": seeded["id"], "poids": seeded["poids"]}
```

> Note d'implémentation : le vrai client supabase-py chaîne `.insert(...).execute()`. Le `_FakeQuery` du test modélise ce chaînage. Vérifier lors de la vérification manuelle (Task 8) que le seed réel fonctionne.

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_ponderations.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/ponderations.py backend/tests/test_ponderations.py && git commit -m "feat(scoring): default weight config per discipline with DB seed"
```

---

### Task 6: Calcul et normalisation des facteurs par course

**Files:**
- Create: `backend/app/scoring/factors.py`
- Test: `backend/tests/test_factors.py`

**Interfaces:**
- Consumes: liste de dicts partants (lus depuis Supabase : `numero_corde, poids_kg, reduction_kilometrique, ferrage, musique, statut, nombre_courses, nombre_victoires, nombre_places`, plus `cote_valeur` : la cote retenue, finale sinon reference sinon None), la `discipline`.
- Produces: `def compute_factors(partants: list[dict], discipline: str) -> dict[str, dict[str, float]]` → `{numero_corde: {facteur: valeur_normalisée_0_1}}` pour les facteurs disponibles (`forme, taux_reussite, ferrage_poids, cote, corde`). Chaque facteur est normalisé sur `[0,1]` dans le contexte de la course.

- [ ] **Step 1: Écrire les tests (échouent d'abord)**

`backend/tests/test_factors.py` :
```python
from app.scoring.factors import compute_factors


def _p(corde, musique="1a1a1a", courses=10, victoires=5, places=8, cote=3.0, poids=58.0, rk=None, ferrage=None, statut="partant"):
    return {
        "numero_corde": corde, "musique": musique, "nombre_courses": courses,
        "nombre_victoires": victoires, "nombre_places": places, "cote_valeur": cote,
        "poids_kg": poids, "reduction_kilometrique": rk, "ferrage": ferrage, "statut": statut,
    }


def test_compute_factors_excludes_non_partants():
    factors = compute_factors([_p(1), _p(2, statut="non_partant")], "plat")
    assert 1 in factors
    assert 2 not in factors


def test_compute_factors_all_in_unit_range():
    partants = [_p(1, cote=2.0, victoires=8), _p(2, cote=15.0, victoires=1), _p(3, cote=6.0, victoires=4)]
    factors = compute_factors(partants, "plat")
    for corde_factors in factors.values():
        for key, value in corde_factors.items():
            assert 0.0 <= value <= 1.0, (key, value)


def test_cote_factor_favours_low_odds():
    partants = [_p(1, cote=2.0), _p(2, cote=20.0)]
    factors = compute_factors(partants, "plat")
    assert factors[1]["cote"] > factors[2]["cote"]


def test_taux_reussite_favours_more_wins():
    partants = [_p(1, courses=10, victoires=8, places=9), _p(2, courses=10, victoires=0, places=1)]
    factors = compute_factors(partants, "plat")
    assert factors[1]["taux_reussite"] > factors[2]["taux_reussite"]


def test_plat_has_corde_factor_trot_uses_reduction():
    plat = compute_factors([_p(1), _p(2)], "plat")
    assert "corde" in plat[1]
    # en trot attelé, ferrage_poids s'appuie sur le déferrage / réduction, corde reste calculée sur numero_corde
    trot = compute_factors([_p(1, rk=78.3, ferrage="DEFERRE_POSTERIEURS"), _p(2, rk=79.0, ferrage=None)], "trot_attele")
    assert 0.0 <= trot[1]["ferrage_poids"] <= 1.0
```

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_factors.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter**

`backend/app/scoring/factors.py` :
```python
"""Calcul et normalisation sur [0,1] des facteurs de scoring dans le contexte d'une course.

Chaque facteur disponible au Plan 2 est calculé pour tous les partants d'une course, puis
normalisé relativement à la course (min-max ou inverse borné) pour être comparable.
"""

from typing import Optional

from app.scoring.musique import forme_score

# Score de déferrage (trot) : plus déferré = léger avantage supposé.
_FERRAGE_SCORE = {
    "DEFERRE_ANTERIEURS_POSTERIEURS": 1.0,
    "DEFERRE_ANTERIEURS": 0.7,
    "DEFERRE_POSTERIEURS": 0.6,
    None: 0.3,
}


def _minmax(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return (value - lo) / (hi - lo)


def compute_factors(partants: list[dict], discipline: str) -> dict[str, dict[str, float]]:
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

    # --- Taux de réussite : (victoires + places) / courses, borné [0,1].
    def taux(p: dict) -> float:
        courses = p.get("nombre_courses") or 0
        if courses <= 0:
            return 0.0
        num = (p.get("nombre_victoires") or 0) + (p.get("nombre_places") or 0)
        return min(num / courses, 1.0)

    # --- ferrage_poids : trot -> déferrage ; plat -> poids relatif inversé (léger = mieux).
    poids_values = [p.get("poids_kg") for p in actifs if p.get("poids_kg") is not None]
    lo_p = min(poids_values) if poids_values else 0.0
    hi_p = max(poids_values) if poids_values else 0.0

    def ferrage_poids(p: dict) -> float:
        if is_trot:
            return _FERRAGE_SCORE.get(p.get("ferrage"), 0.3)
        poids = p.get("poids_kg")
        if poids is None:
            return 0.5
        # poids faible -> score élevé : on inverse le min-max.
        return 1.0 - _minmax(poids, lo_p, hi_p)

    # --- Corde : numéro faible = léger avantage (surtout plat). Min-max inversé.
    cordes = [p["numero_corde"] for p in actifs]
    lo_n, hi_n = min(cordes), max(cordes)

    factors: dict[str, dict[str, float]] = {}
    for p in actifs:
        corde = p["numero_corde"]
        inv = inv_cotes[corde]
        factors[corde] = {
            "forme": forme_score(p.get("musique")),
            "taux_reussite": taux(p),
            "ferrage_poids": ferrage_poids(p),
            "cote": _minmax(inv, lo_c, hi_c),
            "corde": 1.0 - _minmax(corde, lo_n, hi_n),
        }
    return factors
```

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_factors.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/factors.py backend/tests/test_factors.py && git commit -m "feat(scoring): compute and normalize per-course factors"
```

---

### Task 7: Moteur de scoring (pondération + redistribution + classement)

**Files:**
- Create: `backend/app/scoring/engine.py`
- Test: `backend/tests/test_scoring_engine.py`

**Interfaces:**
- Consumes: `compute_factors` (Task 6), `load_active_ponderation` (Task 5).
- Produces: `def score_course(partants: list[dict], discipline: str, poids: dict[str, float]) -> list[dict]` → une liste triée par score décroissant : `[{numero_corde, score_total, rang, details_facteurs}]`. `details_facteurs` = `{facteur: {valeur, poids_effectif, contribution}}`. Redistribue proportionnellement le poids des facteurs indisponibles (non calculés par `compute_factors`, p.ex. fraicheur/couple/entraineur, ou poids 0) sur les facteurs disponibles.

- [ ] **Step 1: Écrire les tests (échouent d'abord)**

`backend/tests/test_scoring_engine.py` :
```python
from app.scoring.engine import score_course
from app.scoring.ponderations import DEFAULT_PONDERATIONS


def _p(corde, musique="1a1a1a", courses=10, victoires=5, places=8, cote=3.0, poids=58.0, statut="partant"):
    return {
        "numero_corde": corde, "musique": musique, "nombre_courses": courses,
        "nombre_victoires": victoires, "nombre_places": places, "cote_valeur": cote,
        "poids_kg": poids, "reduction_kilometrique": None, "ferrage": None, "statut": statut,
    }


def test_score_course_ranks_by_score_desc():
    partants = [
        _p(1, musique="9a9a9a", victoires=0, places=1, cote=25.0),
        _p(2, musique="1a1a2a", victoires=8, places=9, cote=2.0),
        _p(3, musique="5a4a6a", victoires=3, places=5, cote=6.0),
    ]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    assert [r["numero_corde"] for r in ranked] == sorted(
        [r["numero_corde"] for r in ranked], key=lambda c: -next(x["score_total"] for x in ranked if x["numero_corde"] == c)
    )
    assert ranked[0]["numero_corde"] == 2  # le meilleur profil gagne
    assert ranked[0]["rang"] == 1
    assert ranked[-1]["numero_corde"] == 1


def test_effective_weights_sum_to_one_after_redistribution():
    partants = [_p(1), _p(2)]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    for r in ranked:
        total = sum(f["poids_effectif"] for f in r["details_facteurs"].values())
        assert abs(total - 1.0) < 1e-9


def test_score_in_unit_range_and_details_consistent():
    partants = [_p(1, cote=2.0), _p(2, cote=10.0)]
    ranked = score_course(partants, "plat", DEFAULT_PONDERATIONS["plat"])
    for r in ranked:
        assert 0.0 <= r["score_total"] <= 1.0
        recomputed = sum(f["contribution"] for f in r["details_facteurs"].values())
        assert abs(recomputed - r["score_total"]) < 1e-9


def test_non_partant_excluded_from_ranking():
    ranked = score_course([_p(1), _p(2, statut="non_partant")], "plat", DEFAULT_PONDERATIONS["plat"])
    assert [r["numero_corde"] for r in ranked] == [1]
```

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_scoring_engine.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter**

`backend/app/scoring/engine.py` :
```python
"""Moteur de scoring : combine les facteurs normalisés et les poids en un score classé.

Les facteurs dont le poids est 0 ou qui ne sont pas calculés (indisponibles au Plan 2)
voient leur poids redistribué proportionnellement sur les facteurs disponibles, de sorte
que la somme des poids effectifs vaille toujours 1.
"""

from app.scoring.factors import compute_factors


def score_course(partants: list[dict], discipline: str, poids: dict[str, float]) -> list[dict]:
    factors_by_corde = compute_factors(partants, discipline)
    if not factors_by_corde:
        return []

    # Facteurs réellement disponibles = ceux calculés ET de poids > 0.
    any_corde = next(iter(factors_by_corde.values()))
    available = [f for f in any_corde.keys() if poids.get(f, 0.0) > 0.0]
    weight_sum = sum(poids[f] for f in available)
    if weight_sum <= 0:
        # Aucun poids exploitable : répartition uniforme sur les facteurs calculés.
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
        scored.append({"numero_corde": corde, "score_total": total, "details_facteurs": details})

    scored.sort(key=lambda r: r["score_total"], reverse=True)
    for rang, row in enumerate(scored, start=1):
        row["rang"] = rang
    return scored
```

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_scoring_engine.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/engine.py backend/tests/test_scoring_engine.py && git commit -m "feat(scoring): weighted scoring engine with weight redistribution"
```

---

### Task 8: Endpoints lecture / saisie / scoring + vérification bout-en-bout

**Files:**
- Create: `backend/app/scoring/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_scoring_routes.py`

**Interfaces:**
- Consumes: `get_supabase_client` (Plan 1), `load_active_ponderation` (Task 5), `score_course` (Task 7).
- Produces (router monté sur l'app FastAPI) :
  - `GET /courses/{course_id}` → `{course, partants (avec stats + cote retenue)}`
  - `PATCH /courses/{course_id}` body `{etat_terrain?: str}` → course mise à jour
  - `PATCH /partants/{partant_id}` body `{ferrage?, poids_kg?, reduction_kilometrique?}` → partant mis à jour + champs ajoutés à `champs_manuels`
  - `POST /courses/{course_id}/score` → calcule, écrit `scores_pronostic` (supprime les scores existants de la course d'abord), renvoie le classement
  - `GET /courses/{course_id}/pronostic` → classement lu depuis `scores_pronostic`

- [ ] **Step 1: Écrire le test (échoue d'abord)**

`backend/tests/test_scoring_routes.py` : teste `POST /courses/{id}/score` avec un faux client Supabase qui renvoie une course + partants prédéfinis, en surchargeant `get_supabase_client` via `app.dependency_overrides`. Le faux client doit :
- répondre `select` sur `courses` (par id) → 1 course plat,
- `select` sur `partants` (par course_id, avec join implicite simulé) → 2 partants avec stats + une cote,
- capturer les `insert`/`delete`/`upsert` sur `scores_pronostic`,
- répondre au `load_active_ponderation` (select ponderations_config → renvoyer une config active).

```python
from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from app.scoring.ponderations import DEFAULT_PONDERATIONS


class FakeResult:
    def __init__(self, data): self.data = data


class FakeQuery:
    def __init__(self, store, name):
        self._store, self._name, self._filters = store, name, {}
    def select(self, *a, **k): return self
    def eq(self, col, val): self._filters[col] = val; return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self
    def execute(self):
        return FakeResult(self._store.rows_for(self._name, self._filters))
    def insert(self, payload):
        self._store.inserted.setdefault(self._name, []).append(payload); return self
    def delete(self): self._store.deleted.append(self._name); return self
    def upsert(self, payload, on_conflict=None):
        self._store.inserted.setdefault(self._name, []).append(payload); return self


class FakeStore:
    def __init__(self):
        self.inserted, self.deleted = {}, []
        self.course_id = "course-1"
        self._courses = [{"id": "course-1", "numero_course": 1, "discipline": "plat", "statut": "terminee", "distance_m": 1200, "reunion_id": "r1"}]
        self._partants = [
            {"id": "p1", "numero_corde": 1, "musique": "1a1a2a", "nombre_courses": 10, "nombre_victoires": 8, "nombre_places": 9, "poids_kg": 56.0, "reduction_kilometrique": None, "ferrage": None, "statut": "partant"},
            {"id": "p2", "numero_corde": 2, "musique": "9a9a0a", "nombre_courses": 10, "nombre_victoires": 0, "nombre_places": 1, "poids_kg": 60.0, "reduction_kilometrique": None, "ferrage": None, "statut": "partant"},
        ]
        self._cotes = [
            {"partant_id": "p1", "type_capture": "finale", "valeur": 2.0},
            {"partant_id": "p2", "type_capture": "finale", "valeur": 18.0},
        ]
        self._ponderations = [{"id": "pond-1", "poids": DEFAULT_PONDERATIONS["plat"], "discipline": "plat", "actif": True}]
    def rows_for(self, name, filters):
        if name == "courses": return [c for c in self._courses if c["id"] == filters.get("id", c["id"])]
        if name == "partants": return [p for p in self._partants if filters.get("course_id") in (None, "course-1")]
        if name == "cotes":
            return [c for c in self._cotes if c["partant_id"] == filters.get("partant_id")]
        if name == "ponderations_config": return self._ponderations
        if name == "scores_pronostic": return self.inserted.get("scores_pronostic", [])
        return []


class FakeClient:
    def __init__(self, store): self._store = store
    def table(self, name): return FakeQuery(self._store, name)


def test_score_endpoint_returns_ranked_pronostic():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        resp = client.post("/courses/course-1/score")
        assert resp.status_code == 200
        body = resp.json()
        assert body["classement"][0]["numero_corde"] == 1  # meilleur profil
        assert body["classement"][0]["rang"] == 1
        assert store.inserted.get("scores_pronostic")
    finally:
        app.dependency_overrides.clear()
```

> Note : la forme exacte du faux client dépend de la façon dont `routes.py` lit les données (voir Step 3). L'implémenteur ajuste le faux client pour correspondre aux appels réels (`select().eq().execute()`, une requête cotes par partant, etc.), tant que le test vérifie bien : status 200, classement trié (corde 1 en tête), et écriture dans `scores_pronostic`.

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_scoring_routes.py -v`
Expected: FAIL (route inexistante → 404, ou ImportError sur `app.scoring.routes`).

- [ ] **Step 3: Implémenter le router**

`backend/app/scoring/routes.py` — implémenter les 5 endpoints. Pour `POST /courses/{course_id}/score` :
1. Lire la course (`courses` par id) → 404 si absente ; récupérer `discipline`.
2. Lire les partants de la course (`partants` par `course_id`).
3. Pour chaque partant, récupérer sa cote retenue : `finale` sinon `reference` sinon `None` (une requête `cotes` par partant, ou une requête groupée puis sélection en Python).
4. Construire les dicts partants attendus par `score_course` (avec `cote_valeur`).
5. `poids = load_active_ponderation(client, discipline)["poids"]` ; `pond_id = ...["id"]`.
6. `classement = score_course(partants_dicts, discipline, poids)`.
7. Supprimer les `scores_pronostic` existants de la course (`delete().eq("course_id", ...)`), puis insérer une ligne par partant classé (`course_id, partant_id, ponderation_config_id, score_total, rang_pronostique, details_facteurs`).
8. Renvoyer `{"course_id": ..., "classement": [...]}`.

Utiliser un `APIRouter`. `GET /courses/{id}`, `GET /courses/{id}/pronostic`, `PATCH /courses/{id}`, `PATCH /partants/{id}` suivent le même style (lecture/écriture simples). Pour `PATCH /partants/{id}` : mettre à jour les champs fournis (non-null) et ajouter leurs noms à `champs_manuels` (lire l'existant, union, réécrire). Gérer proprement l'absence (404) et renvoyer des `HTTPException` claires.

Dans `backend/app/main.py`, monter le router :
```python
from app.scoring.routes import router as scoring_router
app.include_router(scoring_router)
```

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_scoring_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Lancer toute la suite**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest -v`
Expected: PASS (tous les tests Plan 1 + Plan 2a).

- [ ] **Step 6: Vérification manuelle bout-en-bout (contre PMU réel + Supabase réel)**

Prérequis : la migration `0002` (Task 1) doit être appliquée sur le Supabase de l'utilisateur.

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000
```
Dans un autre terminal — importer une course du jour, la scorer, lire le pronostic :
```bash
D=$(date +%d%m%Y)
curl -sS -X POST http://localhost:8000/courses/import -H "Content-Type: application/json" -d "{\"date\":\"$D\",\"numero_reunion\":1,\"numero_course\":1}"
# récupérer le course_id renvoyé, puis :
curl -sS -X POST http://localhost:8000/courses/<course_id>/score | python3 -m json.tool | head -40
curl -sS http://localhost:8000/courses/<course_id>/pronostic | python3 -m json.tool | head -40
```
Vérifier : le classement est trié par score décroissant, chaque ligne a un `details_facteurs` cohérent (somme des contributions = score_total), les favoris à la cote (cote basse) ne sont pas systématiquement derniers. **Important — redémarrer uvicorn après tout changement de code** (pas de `--reload` → le process garde l'ancien code en mémoire ; leçon du Plan 1).

- [ ] **Step 7: Mettre à jour le README**

Ajouter à `backend/README.md` une section « Scoring » documentant les endpoints (`GET /courses/{id}`, `POST /courses/{id}/score`, `GET /courses/{id}/pronostic`, les deux `PATCH`) avec un exemple curl.

- [ ] **Step 8: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/routes.py backend/app/main.py backend/tests/test_scoring_routes.py backend/README.md && git commit -m "feat(api): scoring, read and manual-entry endpoints"
```

---

## Ce que ce plan produit

Un backend qui, pour n'importe quelle course importée, calcule un score de pronostic pondéré et **explicable** par cheval (détail par facteur), et l'expose via des endpoints testables en local au curl. Base pour le frontend (Plan 2b).

## Hors scope de ce plan

- **Plan 2b** : frontend Next.js (page de travail : import → saisie → score → affichage du classement).
- **Plan 3** : ingestion Geny (active les facteurs `couple`, `entraineur`) + facteur `fraicheur` via `performances-detaillees`.
- **Plan 4** : résultats réels + backtest (précision top1/top3).

## Notes de suivi (backlog revue Plan 1, cf. `plan1-review-backlog.md`)

Traités par ce plan : contrainte unique cotes (#1), `FakeTable` enregistre `on_conflict` (#6). À traiter en Plan 2b ou ultérieurement : gestion d'erreur route → 404/502 (#3, partiellement adressée par les `HTTPException` des nouveaux endpoints), guard `KeyError` sur clés PMU (#4), `_DISCIPLINE_MAP` en `.get()` (#5), index FK (#6), settings lazy pour CI (#9), RLS si le frontend passe un jour en lecture directe.
