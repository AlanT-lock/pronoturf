# Plan C — boucle de mesure (ingestion résultats + évaluation + calibration data-gated) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fermer la boucle prédiction→résultat : capturer les arrivées réelles (`resultats`), évaluer le scoring déterministe (précision top1/top3) et la calibration de la confiance (courbe de fiabilité), le tout exposé par `GET /backtest` + un petit panneau Perf ; la calibration effective reste construite mais **data-gated**.

**Architecture :** Backend — writer `save_resultats` (rempli à l'import si course terminée + via un endpoint de rafraîchissement `POST /courses/{id}/resultats` qui backfille les courses déjà pronostiquées) ; module pur `app/backtest/` (`evaluate.py` = evaluate_course/aggregate/calibration_bins, `calibration.py` = calibrate_confidence data-gated) ; endpoints `GET /backtest` (lecture seule) + `POST /backtest/snapshot` (persiste dans `backtest_resultats`). Frontend — `PerfPanel` read-only branché sur `GET /backtest`, monté discrètement dans la barre supérieure, avec un état « données insuffisantes ».

**Tech Stack :** FastAPI + Pydantic + supabase-py + pytest (FakeStore/monkeypatch) ; Next.js (App Router) + TypeScript + Tailwind v4.

**Réf. spec :** `docs/superpowers/specs/2026-07-15-pronoturf-plan-c-backtest-design.md`.

## Global Constraints

- **Réutilise les tables existantes** `resultats (course_id, partant_id UNIQUE, position_arrivee, disqualifie, ecart, gains)` et `backtest_resultats (ponderation_config_id, periode_debut, periode_fin, nb_courses, precision_top1, precision_top3, calculated_at)` — créées au Plan 1, jamais utilisées. **Aucune migration** (colonnes déjà présentes ; vérifié).
- **Pas de nouvelle source PMU** : l'arrivée vient de `position_arrivee` = `ordreArrivee`, déjà extrait par `normalize_partants(..., course_terminee=True)`.
- **Idempotence** : `save_resultats` upsert sur `partant_id` (contrainte unique). Re-capturer ne duplique pas.
- **Thin-data / n=0 gracieux partout** : toute agrégation ou calibration renvoie un état « insuffisant » (jamais un crash, jamais un chiffre trompeur). `GET /backtest` avec zéro paire renvoie `null`/`[]` + gate `disponible:false`, HTTP 200.
- **Calibration data-gated** : `MIN_PAIRS_CALIBRATION = 50`. En-dessous, `calibrate_confidence` renvoie `disponible:false`. La confiance affichée et les poids ne sont **pas** modifiés cet incrément (mesure + exposition seulement).
- **Périmètre** : scoring déterministe + calibration de la confiance uniquement. **Pas** de résolution des paris LLM (incrément suivant).
- **Identité visuelle** : blanc, accent vert `green-600` (soft `green-50`, hover `green-700`), texte `slate-900`/`slate-500`, `font-mono tabular-nums` pour les nombres. Polices système.
- **Gates.** Backend : `cd backend && .venv/bin/pytest`. Frontend : `cd frontend && npm run build` (pas de suite unitaire front).
- **Ce n'est PAS le Next.js que tu connais** (`frontend/AGENTS.md`) : lire `node_modules/next/dist/docs/` avant toute construction sensible à la version.
- TDD strict côté backend.

## Structure des fichiers

Backend :
- `backend/app/supabase_writer.py` — **modifier** : `save_resultats(...)` + exposer `partant_id_by_corde` dans le retour de `save_course_import`.
- `backend/app/main.py` — **modifier** : appeler `save_resultats` à l'import si terminée + monter le routeur backtest.
- `backend/app/backtest/__init__.py` — **créer** (package vide).
- `backend/app/backtest/evaluate.py` — **créer** : `evaluate_course`, `aggregate`, `calibration_bins` (pur).
- `backend/app/backtest/calibration.py` — **créer** : `calibrate_confidence` + `MIN_PAIRS_CALIBRATION` (pur).
- `backend/app/backtest/routes.py` — **créer** : `POST /courses/{id}/resultats`, `GET /backtest`, `POST /backtest/snapshot`.
- `backend/tests/_fake_supabase.py` — **modifier** : tables `resultats`/`backtest_resultats` + seed d'arrivée pour les tests de route.
- `backend/tests/test_writer_resultats.py`, `test_import_resultats.py`, `test_backtest_evaluate.py`, `test_backtest_calibration.py`, `test_backtest_routes.py` — **créer**.

Frontend :
- `frontend/lib/types.ts` — **modifier** : types `CalibrationBin`, `Backtest`.
- `frontend/lib/api.ts` — **modifier** : `getBacktest()`, `captureResultats(id)`.
- `frontend/components/PerfPanel.tsx` — **créer** : panneau Perf read-only.
- `frontend/app/page.tsx` — **modifier** : monter `PerfPanel` (popover discret dans la barre supérieure).

---

### Task 1: Writer `save_resultats` + exposer `partant_id_by_corde`

**Files:**
- Modify: `backend/app/supabase_writer.py`
- Test: `backend/tests/test_writer_resultats.py`

**Interfaces:**
- Consumes : `PartantNormalized` (a `numero_corde`, `position_arrivee`).
- Produces : `SupabaseWriter.save_resultats(course_id, partants, partant_id_by_corde) -> int` (upsert des partants **arrivés** — `position_arrivee` non None — dans `resultats`, on_conflict `partant_id`, renvoie le nombre écrit) ; `save_course_import(...)` renvoie désormais aussi `partant_id_by_corde` (dict numero_corde→partant_id).

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_writer_resultats.py` :

```python
from app.models import CoteNormalized  # noqa: F401  (garde l'import du module models chargé)
from app.supabase_writer import SupabaseWriter


class FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._payload = None

    def upsert(self, payload, on_conflict=None):
        self._payload = payload
        self._store.setdefault(self._name, []).append((payload, on_conflict))
        return self

    def execute(self):
        class R:
            data = [{"id": "r1"}]
        return R()


class FakeClient:
    def __init__(self):
        self.calls = {}

    def table(self, name):
        return FakeTable(self.calls, name)


class P:
    """Partant minimal pour save_resultats (seuls numero_corde/position_arrivee comptent)."""
    def __init__(self, numero_corde, position_arrivee):
        self.numero_corde = numero_corde
        self.position_arrivee = position_arrivee


def test_save_resultats_ecrit_les_arrives_et_ignore_les_non_arrives():
    client = FakeClient()
    writer = SupabaseWriter(client)
    partants = [P(1, 3), P(2, None), P(4, 1)]  # 2 arrivés, 1 non arrivé
    pid = {1: "pa-1", 2: "pa-2", 4: "pa-4"}
    n = writer.save_resultats("course-9", partants, pid)
    assert n == 2
    rows = [payload for payload, _oc in client.calls["resultats"]]
    cordes = {r["partant_id"]: r["position_arrivee"] for r in rows}
    assert cordes == {"pa-1": 3, "pa-4": 1}
    assert all(r["course_id"] == "course-9" for r in rows)
    assert all(r["disqualifie"] is False for r in rows)
    # upsert sur partant_id (idempotence)
    assert all(oc == "partant_id" for _payload, oc in client.calls["resultats"])
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_writer_resultats.py -q`
Expected: FAIL (`AttributeError: 'SupabaseWriter' object has no attribute 'save_resultats'`).

- [ ] **Step 3: Ajouter `save_resultats` + `partant_id_by_corde`**

Dans `backend/app/supabase_writer.py`, dans `save_course_import`, à côté de `cheval_id_by_corde = {}` ajouter `partant_id_by_corde = {}` en tête de boucle, et **après** `partant_ids.append(partant_row["id"])` ajouter :

```python
            partant_id_by_corde[partant.numero_corde] = partant_row["id"]
```

puis changer le `return` final de `save_course_import` en :

```python
        return {"course_id": course_row["id"], "partant_ids": partant_ids,
                "cheval_id_by_corde": cheval_id_by_corde,
                "partant_id_by_corde": partant_id_by_corde}
```

Ajouter la méthode (à la fin de la classe) :

```python
    def save_resultats(self, course_id, partants, partant_id_by_corde) -> int:
        """Upsert l'arrivée réelle des partants arrivés (position_arrivee non None)."""
        n = 0
        for partant in partants:
            if partant.position_arrivee is None:
                continue
            partant_id = partant_id_by_corde.get(partant.numero_corde)
            if partant_id is None:
                continue
            self._client.table("resultats").upsert(
                {
                    "course_id": course_id,
                    "partant_id": partant_id,
                    "position_arrivee": partant.position_arrivee,
                    "disqualifie": False,
                },
                on_conflict="partant_id",
            ).execute()
            n += 1
        return n
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_writer_resultats.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Non-régression writer + commit**

Run: `cd backend && .venv/bin/pytest tests/test_supabase_writer.py tests/test_writer_enrichi.py -q`
Expected: PASS (le nouveau champ de retour est additif).

```bash
cd /Users/alantouati/pronoturf
git add backend/app/supabase_writer.py backend/tests/test_writer_resultats.py
git commit -m "feat(backtest): writer save_resultats + partant_id_by_corde a l'import"
```

---

### Task 2: Capture auto à l'import (course terminée)

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_import_resultats.py`

**Interfaces:**
- Consumes : `save_resultats` + `partant_id_by_corde` (Task 1).
- Produces : `import_course` écrit `resultats` quand `course.statut == "terminee"` (à côté de `save_entraineur_resultats`).

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_import_resultats.py` :

```python
import app.main as main


class _Writer:
    """Espionne SupabaseWriter pour vérifier que save_resultats est appelé si terminée."""
    def __init__(self, client):
        self.resultats_calls = []

    def save_course_import(self, course, partants):
        return {"course_id": "c-1", "partant_ids": ["pa-1"],
                "cheval_id_by_corde": {1: "ch-1"}, "partant_id_by_corde": {1: "pa-1"}}

    def save_performances(self, *a, **k):
        return 0

    def save_entraineur_resultats(self, *a, **k):
        return 0

    def save_resultats(self, course_id, partants, partant_id_by_corde):
        self.resultats_calls.append((course_id, partant_id_by_corde))
        return len(partants)


def _patch(monkeypatch, statut):
    from app.models import CourseNormalized  # type import only

    class C:
        statut = None
    course = C()
    course.statut = statut

    async def fake_prog(date):
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    monkeypatch.setattr(main, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(main, "normalize_course", lambda *a, **k: course)

    async def fake_part(*a, **k):
        return {"participants": []}

    monkeypatch.setattr(main, "fetch_participants", fake_part)
    monkeypatch.setattr(main, "normalize_partants", lambda *a, **k: ["p"])

    async def fake_perf(*a, **k):
        return {}

    monkeypatch.setattr(main, "fetch_performances_detaillees", fake_perf)
    monkeypatch.setattr(main, "normalize_performances", lambda *a, **k: {})

    writer = _Writer(None)
    monkeypatch.setattr(main, "SupabaseWriter", lambda client: writer)
    return writer


def test_import_ecrit_resultats_si_course_terminee(monkeypatch):
    from fastapi.testclient import TestClient
    writer = _patch(monkeypatch, "terminee")
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()
    try:
        r = TestClient(main.app).post(
            "/courses/import", json={"date": "15072026", "numero_reunion": 1, "numero_course": 1}
        )
        assert r.status_code == 200
        assert writer.resultats_calls == [("c-1", {1: "pa-1"})]
    finally:
        main.app.dependency_overrides.clear()


def test_import_n_ecrit_pas_resultats_si_a_venir(monkeypatch):
    from fastapi.testclient import TestClient
    writer = _patch(monkeypatch, "a_venir")
    main.app.dependency_overrides[main.get_supabase_client] = lambda: object()
    try:
        r = TestClient(main.app).post(
            "/courses/import", json={"date": "15072026", "numero_reunion": 1, "numero_course": 1}
        )
        assert r.status_code == 200
        assert writer.resultats_calls == []
    finally:
        main.app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_import_resultats.py -q`
Expected: FAIL (`save_resultats` non appelé).

- [ ] **Step 3: Câbler dans `import_course`**

Dans `backend/app/main.py`, dans `import_course`, le bloc final :

```python
    if course.statut == "terminee":
        writer.save_entraineur_resultats(course, partants, result["cheval_id_by_corde"])
```

devient :

```python
    if course.statut == "terminee":
        writer.save_entraineur_resultats(course, partants, result["cheval_id_by_corde"])
        writer.save_resultats(result["course_id"], partants, result["partant_id_by_corde"])
```

- [ ] **Step 4: Lancer (vert) + suite**

Run: `cd backend && .venv/bin/pytest tests/test_import_resultats.py tests/test_import_route.py tests/test_import_history.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/main.py backend/tests/test_import_resultats.py
git commit -m "feat(backtest): capture resultats auto a l'import si course terminee"
```

---

### Task 3: Module `app/backtest/evaluate.py` (évaluation pure)

**Files:**
- Create: `backend/app/backtest/__init__.py`, `backend/app/backtest/evaluate.py`
- Test: `backend/tests/test_backtest_evaluate.py`

**Interfaces:**
- Produces :
  - `evaluate_course(classement, resultats_by_corde) -> dict` où `classement` = liste triée de `{numero_corde, rang, confiance}` et `resultats_by_corde` = `{numero_corde: position_arrivee}`. Renvoie `{gagnant_reel, rang_predit_du_gagnant, top1_hit, top3_hit, confiance_top1}`.
  - `aggregate(evaluations) -> dict` = `{nb_courses, precision_top1, precision_top3, brier_confiance}` sur les courses évaluables (`gagnant_reel` non None).
  - `calibration_bins(pairs, n_bins=5) -> list[dict]` où `pairs` = liste de `(confiance_top1, top1_hit)`.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_backtest_evaluate.py` :

```python
from app.backtest import evaluate as ev


def _classement(triples):
    # triples: list of (numero_corde, rang, confiance)
    return [{"numero_corde": c, "rang": r, "confiance": conf} for c, r, conf in triples]


def test_evaluate_course_top1_hit():
    classement = _classement([(4, 1, 0.8), (1, 2, 0.8), (7, 3, 0.8)])
    out = ev.evaluate_course(classement, {4: 1, 1: 2, 7: 3})  # 4 gagne, on l'avait rang1
    assert out["gagnant_reel"] == 4
    assert out["rang_predit_du_gagnant"] == 1
    assert out["top1_hit"] is True
    assert out["top3_hit"] is True
    assert out["confiance_top1"] == 0.8


def test_evaluate_course_top3_hit_but_not_top1():
    classement = _classement([(4, 1, 0.5), (1, 2, 0.5), (7, 3, 0.5)])
    out = ev.evaluate_course(classement, {4: 2, 1: 3, 7: 1})  # 7 gagne, on l'avait rang3
    assert out["gagnant_reel"] == 7
    assert out["rang_predit_du_gagnant"] == 3
    assert out["top1_hit"] is False
    assert out["top3_hit"] is True


def test_evaluate_course_miss():
    classement = _classement([(4, 1, 0.5), (1, 2, 0.5), (7, 3, 0.5), (9, 4, 0.5)])
    out = ev.evaluate_course(classement, {4: 2, 1: 3, 7: 4, 9: 1})  # 9 gagne (rang4)
    assert out["top1_hit"] is False
    assert out["top3_hit"] is False


def test_evaluate_course_sans_gagnant():
    classement = _classement([(4, 1, 0.5)])
    out = ev.evaluate_course(classement, {4: 2})  # aucun position==1
    assert out["gagnant_reel"] is None


def test_aggregate_ignore_courses_sans_gagnant():
    evals = [
        {"gagnant_reel": 4, "top1_hit": True, "top3_hit": True, "confiance_top1": 0.9},
        {"gagnant_reel": 7, "top1_hit": False, "top3_hit": True, "confiance_top1": 0.5},
        {"gagnant_reel": None, "top1_hit": False, "top3_hit": False, "confiance_top1": None},
    ]
    agg = ev.aggregate(evals)
    assert agg["nb_courses"] == 2
    assert agg["precision_top1"] == 0.5
    assert agg["precision_top3"] == 1.0
    # brier = mean((0.9-1)^2, (0.5-0)^2) = mean(0.01, 0.25) = 0.13
    assert abs(agg["brier_confiance"] - 0.13) < 1e-9


def test_aggregate_vide():
    agg = ev.aggregate([])
    assert agg == {"nb_courses": 0, "precision_top1": None,
                   "precision_top3": None, "brier_confiance": None}


def test_calibration_bins_groups_and_rates():
    pairs = [(0.1, False), (0.15, True), (0.85, True), (0.9, True)]
    bins = ev.calibration_bins(pairs)
    labels = {b["bucket"]: b for b in bins}
    assert labels["0.0–0.2"]["n"] == 2
    assert labels["0.0–0.2"]["taux_top1_reel"] == 0.5
    assert labels["0.8–1.0"]["n"] == 2
    assert labels["0.8–1.0"]["taux_top1_reel"] == 1.0
    # buckets vides omis
    assert "0.2–0.4" not in labels
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_evaluate.py -q`
Expected: FAIL (module absent).

- [ ] **Step 3: Créer le package + module**

Create `backend/app/backtest/__init__.py` (vide).

Create `backend/app/backtest/evaluate.py` :

```python
"""Évaluation pure du scoring déterministe contre les arrivées réelles.

- evaluate_course : par course, le n°1 prédit a-t-il gagné (top1) ? le vrai gagnant
  est-il dans nos 3 premiers rangs (top3) ?
- aggregate : précision top1/top3 + score de Brier de la confiance sur les courses évaluables.
- calibration_bins : courbe de fiabilité (confiance prédite vs taux de réussite réel).
"""


def evaluate_course(classement: list[dict], resultats_by_corde: dict[int, int]) -> dict:
    gagnant = next((c for c, pos in resultats_by_corde.items() if pos == 1), None)
    rang1 = next((r for r in classement if r["rang"] == 1), None)
    confiance_top1 = rang1.get("confiance") if rang1 else None
    if gagnant is None:
        return {"gagnant_reel": None, "rang_predit_du_gagnant": None,
                "top1_hit": False, "top3_hit": False, "confiance_top1": confiance_top1}
    rang_gagnant = next((r["rang"] for r in classement if r["numero_corde"] == gagnant), None)
    return {
        "gagnant_reel": gagnant,
        "rang_predit_du_gagnant": rang_gagnant,
        "top1_hit": rang1 is not None and rang1["numero_corde"] == gagnant,
        "top3_hit": rang_gagnant is not None and rang_gagnant <= 3,
        "confiance_top1": confiance_top1,
    }


def aggregate(evaluations: list[dict]) -> dict:
    evaluables = [e for e in evaluations if e["gagnant_reel"] is not None]
    if not evaluables:
        return {"nb_courses": 0, "precision_top1": None,
                "precision_top3": None, "brier_confiance": None}
    n = len(evaluables)
    top1 = sum(1 for e in evaluables if e["top1_hit"]) / n
    top3 = sum(1 for e in evaluables if e["top3_hit"]) / n
    briers = [
        (e["confiance_top1"] - (1.0 if e["top1_hit"] else 0.0)) ** 2
        for e in evaluables if e["confiance_top1"] is not None
    ]
    brier = sum(briers) / len(briers) if briers else None
    return {"nb_courses": n, "precision_top1": top1,
            "precision_top3": top3, "brier_confiance": brier}


def calibration_bins(pairs: list[tuple[float, bool]], n_bins: int = 5) -> list[dict]:
    edges = [i / n_bins for i in range(n_bins + 1)]  # [0,0.2,0.4,0.6,0.8,1.0]
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        # dernier bucket inclusif à droite pour capter confiance == 1.0
        in_bin = [
            (conf, hit) for conf, hit in pairs
            if conf is not None and (lo <= conf < hi or (i == n_bins - 1 and conf == hi))
        ]
        if not in_bin:
            continue
        m = len(in_bin)
        out.append({
            "bucket": f"{lo:.1f}–{hi:.1f}",
            "n": m,
            "confiance_moyenne": round(sum(c for c, _ in in_bin) / m, 4),
            "taux_top1_reel": round(sum(1 for _, h in in_bin if h) / m, 4),
        })
    return out
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_evaluate.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/__init__.py backend/app/backtest/evaluate.py backend/tests/test_backtest_evaluate.py
git commit -m "feat(backtest): evaluation pure (top1/top3 + brier + calibration bins)"
```

---

### Task 4: Module `app/backtest/calibration.py` (data-gated)

**Files:**
- Create: `backend/app/backtest/calibration.py`
- Test: `backend/tests/test_backtest_calibration.py`

**Interfaces:**
- Consumes : `calibration_bins` (Task 3).
- Produces : `MIN_PAIRS_CALIBRATION = 50` ; `calibrate_confidence(pairs) -> dict` (`{disponible: False, raison, nb_paires, seuil}` sous le seuil ; `{disponible: True, mapping: [...bins...], nb_paires}` au-dessus).

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_backtest_calibration.py` :

```python
from app.backtest import calibration as cal


def test_gate_bloque_sous_le_seuil():
    pairs = [(0.5, True)] * 10
    out = cal.calibrate_confidence(pairs)
    assert out["disponible"] is False
    assert out["nb_paires"] == 10
    assert out["seuil"] == cal.MIN_PAIRS_CALIBRATION


def test_disponible_au_dessus_du_seuil():
    pairs = [(0.1, False)] * 30 + [(0.9, True)] * 30  # 60 >= 50
    out = cal.calibrate_confidence(pairs)
    assert out["disponible"] is True
    assert out["nb_paires"] == 60
    assert isinstance(out["mapping"], list) and out["mapping"]
    # le mapping est bien une courbe de fiabilité par bucket
    buckets = {b["bucket"] for b in out["mapping"]}
    assert "0.0–0.2" in buckets and "0.8–1.0" in buckets
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_calibration.py -q`
Expected: FAIL (module absent).

- [ ] **Step 3: Créer `app/backtest/calibration.py`**

```python
"""Calibration data-gated de l'indice de confiance.

Construit une correspondance empirique confiance -> taux de réussite réel, mais
UNIQUEMENT au-delà d'un seuil d'échantillon. En-dessous, renvoie « indisponible »
plutôt qu'une calibration bruitée. Non appliquée à la confiance affichée cet incrément.
"""

from app.backtest.evaluate import calibration_bins

MIN_PAIRS_CALIBRATION = 50


def calibrate_confidence(pairs: list[tuple[float, bool]]) -> dict:
    n = len(pairs)
    if n < MIN_PAIRS_CALIBRATION:
        return {"disponible": False, "raison": "données insuffisantes",
                "nb_paires": n, "seuil": MIN_PAIRS_CALIBRATION}
    return {"disponible": True, "nb_paires": n, "seuil": MIN_PAIRS_CALIBRATION,
            "mapping": calibration_bins(pairs)}
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_calibration.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/calibration.py backend/tests/test_backtest_calibration.py
git commit -m "feat(backtest): calibration data-gated (seuil 50 paires)"
```

---

### Task 5: Endpoint `POST /courses/{id}/resultats` (rafraîchissement/backfill)

**Files:**
- Create: `backend/app/backtest/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_backtest_routes.py` (partie « resultats »)

**Interfaces:**
- Consumes : `fetch_programme`, `find_course_in_programme`, `normalize_course`, `fetch_participants`, `normalize_partants` (existants), `save_resultats` (Task 1), `_get_course_or_404` (scoring/routes).
- Produces : `POST /courses/{id}/resultats` → re-fetch PMU ; si la course a couru, écrit `resultats` + met à jour `courses.statut='terminee'`. Réponse `{course_id, captured: bool, statut, nb_resultats}`.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_backtest_routes.py` :

```python
import app.backtest.routes as br
from fastapi.testclient import TestClient
from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


class _Course:
    def __init__(self, statut):
        self.statut = statut


def test_post_resultats_capture_si_course_courue(monkeypatch):
    store = FakeStore()
    _override(store)

    async def fake_prog(date):
        assert date == "13072026"  # reunion date 2026-07-13 -> JJMMAAAA
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(br, "fetch_programme", fake_prog)
    monkeypatch.setattr(br, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(br, "normalize_course", lambda *a, **k: _Course("terminee"))

    async def fake_part(date, r, c):
        return {"participants": []}

    monkeypatch.setattr(br, "fetch_participants", fake_part)

    class P:
        def __init__(self, corde, pos):
            self.numero_corde = corde
            self.position_arrivee = pos

    monkeypatch.setattr(br, "normalize_partants", lambda parts, course_terminee: [P(1, 1), P(2, 2)])
    try:
        r = TestClient(app).post("/courses/course-1/resultats")
        assert r.status_code == 200
        body = r.json()
        assert body["captured"] is True
        assert body["statut"] == "terminee"
        assert body["nb_resultats"] == 2
        assert len(store.tables["resultats"]) == 2  # p1, p2 (cordes 1,2 -> partant_ids)
    finally:
        app.dependency_overrides.clear()


def test_post_resultats_pas_encore_courue(monkeypatch):
    store = FakeStore()
    _override(store)

    async def fake_prog(date):
        return {"programme": {"reunions": []}}

    monkeypatch.setattr(br, "fetch_programme", fake_prog)
    monkeypatch.setattr(br, "find_course_in_programme", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(br, "normalize_course", lambda *a, **k: _Course("a_venir"))
    try:
        r = TestClient(app).post("/courses/course-1/resultats")
        assert r.status_code == 200
        body = r.json()
        assert body["captured"] is False and body["statut"] == "a_venir"
        assert body["nb_resultats"] == 0
        assert store.tables["resultats"] == []
    finally:
        app.dependency_overrides.clear()


def test_post_resultats_404_course_absente():
    store = FakeStore()
    _override(store)
    try:
        assert TestClient(app).post("/courses/inconnue/resultats").status_code == 404
    finally:
        app.dependency_overrides.clear()
```

Also, **modifier** `backend/tests/_fake_supabase.py` : dans `FakeStore.__init__`, ajouter aux `self.tables` (après `"scores_pronostic": [],`) :

```python
            "resultats": [],
            "backtest_resultats": [],
```

et vérifier que la table `reunions` existante contient une `date` (elle en a une : `"2026-07-13"`).

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes.py -q`
Expected: FAIL (route absente / module `app.backtest.routes` inexistant).

- [ ] **Step 3: Créer `app/backtest/routes.py` (endpoint resultats) + monter le routeur**

Create `backend/app/backtest/routes.py` :

```python
"""Endpoints de la boucle de mesure : capture des arrivées + évaluation/backtest."""

from datetime import date as _date

from fastapi import APIRouter, Depends, HTTPException

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


@router.post("/courses/{course_id}/resultats")
async def capture_resultats(course_id: str, client=Depends(get_supabase_client)) -> dict:
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
```

Dans `backend/app/main.py`, après `from app.analyse.routes import router as analyse_router`, ajouter :

```python
from app.backtest.routes import router as backtest_router
```

et après `app.include_router(analyse_router)`, ajouter :

```python
app.include_router(backtest_router)
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/routes.py backend/app/main.py backend/tests/_fake_supabase.py backend/tests/test_backtest_routes.py
git commit -m "feat(backtest): endpoint POST /courses/{id}/resultats (refresh/backfill)"
```

---

### Task 6: Endpoints `GET /backtest` + `POST /backtest/snapshot`

**Files:**
- Modify: `backend/app/backtest/routes.py`
- Test: `backend/tests/test_backtest_routes.py` (partie « backtest »)

**Interfaces:**
- Consumes : `evaluate.evaluate_course/aggregate/calibration_bins` (Task 3), `calibration.calibrate_confidence` (Task 4).
- Produces :
  - `GET /backtest` → `{nb_courses, precision_top1, precision_top3, brier_confiance, calibration: [...], calibration_gate: {...}}`.
  - `POST /backtest/snapshot` → persiste une ligne dans `backtest_resultats` (config active, période min/max des dates de réunion couvertes, nb_courses, precision_top1/top3) et la renvoie.

- [ ] **Step 1: Écrire le test rouge (ajouter à `test_backtest_routes.py`)**

```python
def _seed_scored_course_with_result(store):
    """La FakeStore a course-1 (p1 corde1, p2 corde2). On ajoute pronostic + arrivée :
    p1 rang1 (corde1), p2 rang2 (corde2) ; arrivée: corde1 gagne (top1_hit=True)."""
    store.tables["scores_pronostic"] = [
        {"id": "s1", "course_id": "course-1", "partant_id": "p1", "ponderation_config_id": "pond-1",
         "score_total": 0.8, "rang_pronostique": 1, "details_facteurs": {}, "confiance": 0.9,
         "nb_courses_historique": 3},
        {"id": "s2", "course_id": "course-1", "partant_id": "p2", "ponderation_config_id": "pond-1",
         "score_total": 0.4, "rang_pronostique": 2, "details_facteurs": {}, "confiance": 0.9,
         "nb_courses_historique": 3},
    ]
    store.tables["resultats"] = [
        {"id": "r1", "course_id": "course-1", "partant_id": "p1", "position_arrivee": 1, "disqualifie": False},
        {"id": "r2", "course_id": "course-1", "partant_id": "p2", "position_arrivee": 2, "disqualifie": False},
    ]


def test_get_backtest_vide_gracieux():
    store = FakeStore()
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["nb_courses"] == 0
        assert body["precision_top1"] is None and body["precision_top3"] is None
        assert body["calibration"] == []
        assert body["calibration_gate"]["disponible"] is False
    finally:
        app.dependency_overrides.clear()


def test_get_backtest_calcule_precision():
    store = FakeStore()
    _seed_scored_course_with_result(store)
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["nb_courses"] == 1
        assert body["precision_top1"] == 1.0  # corde1 (rang1) a gagné
        assert body["precision_top3"] == 1.0
        assert body["calibration_gate"]["disponible"] is False  # 1 < 50
        assert body["calibration_gate"]["nb_paires"] == 1
    finally:
        app.dependency_overrides.clear()


def test_post_backtest_snapshot_persiste():
    store = FakeStore()
    _seed_scored_course_with_result(store)
    _override(store)
    try:
        r = TestClient(app).post("/backtest/snapshot")
        assert r.status_code == 200
        assert len(store.tables["backtest_resultats"]) == 1
        row = store.tables["backtest_resultats"][0]
        assert row["nb_courses"] == 1
        assert row["precision_top1"] == 1.0
        assert row["ponderation_config_id"] == "pond-1"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes.py -q`
Expected: FAIL (routes `GET /backtest` / `POST /backtest/snapshot` absentes).

- [ ] **Step 3: Ajouter les endpoints dans `app/backtest/routes.py`**

Étendre les imports en tête du fichier :

```python
from app.backtest import evaluate as ev
from app.backtest.calibration import calibrate_confidence
```

Ajouter (à la fin du fichier) :

```python
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
    return {
        **agg,
        "calibration": ev.calibration_bins(pairs),
        "calibration_gate": {k: gate[k] for k in ("disponible", "nb_paires", "seuil") if k in gate},
    }


@router.post("/backtest/snapshot")
def post_backtest_snapshot(client=Depends(get_supabase_client)) -> dict:
    evaluations = _evaluations(client)
    agg = ev.aggregate(evaluations)
    if agg["nb_courses"] == 0:
        raise HTTPException(status_code=400, detail="Aucune course évaluable pour un snapshot")

    pond = client.table("ponderations_config").select("id").eq("actif", True).limit(1).execute().data
    ponderation_id = pond[0]["id"] if pond else None

    # Période : min/max des dates de réunion des courses couvertes.
    course_ids = list({s["course_id"] for s in client.table("scores_pronostic").select("course_id").execute().data})
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
```

- [ ] **Step 4: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes.py -q`
Expected: PASS.
Run: `cd backend && .venv/bin/pytest -q`
Expected: toute la suite verte.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/routes.py backend/tests/test_backtest_routes.py
git commit -m "feat(backtest): GET /backtest + POST /backtest/snapshot"
```

---

### Task 7: Frontend — types + client API

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api.ts`

**Interfaces:**
- Produces : types `CalibrationBin`, `Backtest` ; `api.getBacktest()`, `api.captureResultats(id)`.

- [ ] **Step 1: Types — `frontend/lib/types.ts`**

Ajouter à la fin :

```typescript
export type CalibrationBin = {
  bucket: string;
  n: number;
  confiance_moyenne: number;
  taux_top1_reel: number;
};

export type Backtest = {
  nb_courses: number;
  precision_top1: number | null;
  precision_top3: number | null;
  brier_confiance: number | null;
  calibration: CalibrationBin[];
  calibration_gate: { disponible: boolean; nb_paires: number; seuil: number };
};
```

- [ ] **Step 2: Client — `frontend/lib/api.ts`**

Étendre l'import de types en tête pour inclure `Backtest`, puis dans l'objet `api` ajouter :

```typescript
  getBacktest: () => req<Backtest>("/backtest"),
  captureResultats: (id: string) =>
    req<{ course_id: string; captured: boolean; statut: string; nb_resultats: number }>(
      `/courses/${id}/resultats`,
      { method: "POST" },
    ),
```

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (avertissement multiple-lockfiles toléré).

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(plateforme): types Backtest + client getBacktest/captureResultats"
```

---

### Task 8: Frontend — composant `PerfPanel` + montage discret

**Files:**
- Create: `frontend/components/PerfPanel.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes : `api.getBacktest` + type `Backtest`/`CalibrationBin` (Task 7).
- Produces : `PerfPanel` (popover repliable dans la barre supérieure) ; état « données insuffisantes » tant que `nb_courses` faible / gate indisponible.

- [ ] **Step 1: Créer `frontend/components/PerfPanel.tsx`**

```tsx
"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Backtest } from "@/lib/types";

function pct(x: number | null): string {
  return x === null ? "—" : `${Math.round(x * 100)}%`;
}

export function PerfPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Backtest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !data) {
      setLoading(true);
      setError(null);
      try {
        setData(await api.getBacktest());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Perf indisponible.");
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition-colors hover:border-green-600 hover:text-green-700"
      >
        Perf
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
          {loading && <p className="text-sm text-slate-400">Chargement…</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          {data && !loading && !error && (
            <div className="flex flex-col gap-3">
              <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                Performance · {data.nb_courses} course{data.nb_courses > 1 ? "s" : ""} évaluée
                {data.nb_courses > 1 ? "s" : ""}
              </div>
              {data.nb_courses === 0 ? (
                <p className="text-sm text-slate-400">
                  Données insuffisantes — aucune arrivée capturée pour l'instant.
                </p>
              ) : (
                <>
                  <div className="flex gap-4">
                    <div>
                      <div className="font-mono text-lg font-bold tabular-nums text-green-700">
                        {pct(data.precision_top1)}
                      </div>
                      <div className="text-[10px] text-slate-500">précision top 1</div>
                    </div>
                    <div>
                      <div className="font-mono text-lg font-bold tabular-nums text-green-700">
                        {pct(data.precision_top3)}
                      </div>
                      <div className="text-[10px] text-slate-500">précision top 3</div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                      Calibration confiance
                    </div>
                    {data.calibration_gate.disponible ? (
                      <div className="flex flex-col gap-1">
                        {data.calibration.map((b) => (
                          <div key={b.bucket} className="flex items-center gap-2 text-[11px]">
                            <span className="w-16 font-mono tabular-nums text-slate-500">{b.bucket}</span>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-green-100">
                              <div className="h-full bg-green-600" style={{ width: `${b.taux_top1_reel * 100}%` }} />
                            </div>
                            <span className="w-8 text-right font-mono tabular-nums text-slate-600">
                              {pct(b.taux_top1_reel)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">
                        Données insuffisantes ({data.calibration_gate.nb_paires}/
                        {data.calibration_gate.seuil} paires) — la calibration s'activera en accumulant des résultats.
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Monter dans la barre supérieure — `frontend/app/page.tsx`**

Ajouter l'import (à côté des autres composants) :

```tsx
import { PerfPanel } from "@/components/PerfPanel";
```

Dans le `<header>` (la barre supérieure contenant le logo et le `DayNav`), envelopper le `DayNav` et `PerfPanel` dans un conteneur à droite. Remplacer le bloc :

```tsx
        <DayNav date={date} onPrev={() => setDate((d) => addDays(d, -1))} onNext={() => setDate((d) => addDays(d, 1))} />
```

par :

```tsx
        <div className="flex items-center gap-3">
          <DayNav date={date} onPrev={() => setDate((d) => addDays(d, -1))} onNext={() => setDate((d) => addDays(d, 1))} />
          <PerfPanel />
        </div>
```

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PerfPanel.tsx frontend/app/page.tsx
git commit -m "feat(plateforme): panneau Perf (precision + calibration data-gated)"
```

---

### Task 9: Vérification bout-en-bout (contrôleur)

**Files:** aucun (vérification).

Prérequis : aucune migration (tables `resultats`/`backtest_resultats` déjà présentes). La clé Anthropic n'est pas nécessaire ici (Plan C n'appelle pas le LLM).

- [ ] **Step 1: Lancer les deux serveurs**

Avant de démarrer, tuer tout process squattant le port 8000 (`lsof -tiTCP:8000 -sTCP:LISTEN`).

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # A (arrière-plan)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # B (arrière-plan)
```

- [ ] **Step 2: Backfill + contrat HTTP réel**

Pour quelques courses **déjà pronostiquées et désormais courues** (ex. celles de la veille) : `POST /courses/{id}/resultats` → vérifier `captured:true`, `nb_resultats>0`, et que `resultats` se remplit dans Supabase (idempotent si rappelé). Pour une course non courue → `captured:false, statut:"a_venir"`.
Puis `GET /backtest` (avec `Origin: http://localhost:3000` pour CORS) → `nb_courses>0`, `precision_top1`/`precision_top3` cohérents, `calibration_gate.disponible:false` (bien en-dessous de 50 paires) avec `nb_paires` correct. `POST /backtest/snapshot` → une ligne dans `backtest_resultats`.
Vérifier aussi le cas vide au départ : sur une base sans `resultats`, `GET /backtest` renvoie `nb_courses:0` sans erreur.

- [ ] **Step 3: Vérifier le rendu** (contrôle visuel utilisateur — pas d'outil navigateur dans l'env)

Ouvrir http://localhost:3000 : bouton **Perf** dans la barre supérieure → panneau avec précision top1/top3 et l'état de calibration **« données insuffisantes (n/50) »**. Après un backfill, `n` reflète les courses évaluées. Vérifier que la page n'est pas une page d'erreur.

- [ ] **Step 4: Corriger tout écart** (câblage, CORS, forme des données, conversion de date JJMMAAAA) et re-vérifier. Arrêter les serveurs.

---

## Ce que ce plan produit

La boucle prédiction→résultat est fermée : on capture les arrivées réelles (auto à l'import + backfill à la demande), on mesure la précision du scoring (top1/top3) et on expose la courbe de calibration de la confiance, le tout dans un petit panneau Perf. La calibration effective est en place mais **data-gated** — elle s'activera d'elle-même quand ≥50 paires (prédiction, résultat) seront accumulées, sans rien réécrire aujourd'hui. Le jeu de données `resultats` + `backtest_resultats` commence à se constituer pour les incréments suivants.

## Hors périmètre (Plan C — cet incrément)

- Résolution/évaluation des **paris LLM** (Simple/Couplé/Tiercé… gagnés) → incrément suivant.
- Application live de la calibration à la confiance affichée + réglage automatique des pondérations → plan futur (une fois la data au-dessus du seuil).
- `ecart`/`gains` dans `resultats` (laissés NULL en v1).
