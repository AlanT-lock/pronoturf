# Plan D — résolution des paris LLM (taux de réussite par type & niveau) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre la boucle de mesure aux paris de l'IA : résoudre (en désordre) chaque recommandation contre l'arrivée réelle, et exposer le taux de réussite par type de pari et par niveau de confiance dans `GET /backtest` + le panneau Perf.

**Architecture:** Backend — module pur `app/backtest/paris.py` (`resoudre_pari`/`resoudre_analyse`/`agreger_paris`), assemblé dans `GET /backtest` via un helper qui joint `analyses_llm` ∩ `resultats` (arrivée par corde) + le nombre de partants. Frontend — type `Backtest` étendu + section « Paris IA » read-only dans `PerfPanel`. Aucune migration, aucune persistance nouvelle, mesure seulement.

**Tech Stack :** FastAPI + Pydantic + supabase-py + pytest (FakeStore/monkeypatch) ; Next.js (App Router) + TypeScript + Tailwind v4.

**Réf. spec :** `docs/superpowers/specs/2026-07-15-pronoturf-plan-d-paris-resolution-design.md`.

## Global Constraints

- **Résolution en DÉSORDRE** sur la `selection` de la reco ; placé = top-K avec **K=3 si nb_partants ≥ 8, sinon 2**. Pas d'ordre exact, pas de fidélité PMU fine.
- Sélection trop courte pour le type, ou cheval sélectionné non arrivé → le pari **perd** (`False`), jamais d'exception. Arrivée sans gagnant (aucune position 1) → `gagnant = None` (non résolu, exclu des taux). Type hors des 9 `ANALYSABLE` → `None`.
- **Base = `selection`** (pas `base`/`tournant`).
- **Étend `GET /backtest`** avec un bloc `paris` ; pas de nouvel endpoint, **aucune migration**, aucune persistance de snapshot de paris.
- **Descriptif avec `n`** : chaque taux porte son effectif ; gracieux à `nb=0` (blocs vides, HTTP 200). Inclut les analyses `source` `llm` **et** `regles`.
- **Mesure seulement** : rien n'est appliqué (ni confiance, ni sélection de paris).
- Trio et Tiercé résolvent à l'identique en désordre (même condition sur 3) — acceptable v1.
- **Identité visuelle** : blanc, accent vert `green-600` (soft `green-50`, hover `green-700`), texte `slate-900`/`slate-500`, `font-mono tabular-nums`. Polices système.
- **Gates.** Backend : `cd backend && .venv/bin/pytest`. Frontend : `cd frontend && npm run build` (pas de suite unitaire front).
- **Ce n'est PAS le Next.js que tu connais** (`frontend/AGENTS.md`) : lire `node_modules/next/dist/docs/` avant toute construction sensible à la version.
- TDD strict côté backend.

## Structure des fichiers

Backend :
- `backend/app/backtest/paris.py` — **créer** : `resoudre_pari`, `resoudre_analyse`, `agreger_paris`, `_places_payantes`, `PLACE_MIN_RUNNERS`.
- `backend/app/backtest/routes.py` — **modifier** : helper `_paris_resolus` + bloc `paris` dans `get_backtest`.
- `backend/tests/_fake_supabase.py` — **modifier** : la table `analyses_llm` existe déjà (vide) ; les tests la seedent.
- `backend/tests/test_backtest_paris.py`, `test_backtest_routes_paris.py` — **créer**.

Frontend :
- `frontend/lib/types.ts` — **modifier** : `BetTypeStat`, `BetNiveauStat`, extension de `Backtest` (`paris`).
- `frontend/components/PerfPanel.tsx` — **modifier** : section « Paris IA ».

---

### Task 1: Module `app/backtest/paris.py` (résolution pure)

**Files:**
- Create: `backend/app/backtest/paris.py`
- Test: `backend/tests/test_backtest_paris.py`

**Interfaces:**
- Produces :
  - `resoudre_pari(recommandation, arrivee, nb_partants) -> {type_pari, niveau, gagnant: bool|None}` où `arrivee` = `{numero_corde: position_arrivee}`.
  - `resoudre_analyse(recommandations, arrivee, nb_partants) -> list[dict]`.
  - `agreger_paris(resolus) -> (par_type: list, par_niveau: list)` (ignore les `gagnant is None`).
  - `_places_payantes(nb_partants) -> int` ; `PLACE_MIN_RUNNERS = 8`.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_backtest_paris.py` :

```python
from app.backtest import paris as P


def R(type_pari, selection, niveau="moyen"):
    return {"type_pari": type_pari, "selection": selection, "niveau": niveau}


# Arrivée : corde 4 gagne, puis 1, 7, 8, 3, 9 ; 10 partants -> placé top 3.
ARR = {4: 1, 1: 2, 7: 3, 8: 4, 3: 5, 9: 6}
NB = 10


def test_places_payantes_seuil():
    assert P._places_payantes(8) == 3
    assert P._places_payantes(7) == 2


def test_simple_gagnant():
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", [4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", [1]), ARR, NB)["gagnant"] is False


def test_simple_place():
    assert P.resoudre_pari(R("SIMPLE_PLACE", [7]), ARR, NB)["gagnant"] is True   # 3e, top3
    assert P.resoudre_pari(R("SIMPLE_PLACE", [8]), ARR, NB)["gagnant"] is False  # 4e


def test_simple_place_seuil_petit_peloton():
    arr = {4: 1, 1: 2, 7: 3}
    # 3 partants -> placé top 2 : le 3e (corde 7) ne paie pas.
    assert P.resoudre_pari(R("SIMPLE_PLACE", [7]), arr, 3)["gagnant"] is False
    assert P.resoudre_pari(R("SIMPLE_PLACE", [1]), arr, 3)["gagnant"] is True


def test_couple_gagnant_desordre():
    assert P.resoudre_pari(R("COUPLE_GAGNANT", [1, 4]), ARR, NB)["gagnant"] is True   # {1,4}=={top2}
    assert P.resoudre_pari(R("COUPLE_GAGNANT", [4, 7]), ARR, NB)["gagnant"] is False


def test_couple_place():
    assert P.resoudre_pari(R("COUPLE_PLACE", [1, 7]), ARR, NB)["gagnant"] is True   # tous deux top3
    assert P.resoudre_pari(R("COUPLE_PLACE", [1, 8]), ARR, NB)["gagnant"] is False  # 8 = 4e


def test_deux_sur_quatre():
    assert P.resoudre_pari(R("DEUX_SUR_QUATRE", [4, 8, 9]), ARR, NB)["gagnant"] is True  # 4(1er),8(4e) dans top4
    assert P.resoudre_pari(R("DEUX_SUR_QUATRE", [4, 3, 9]), ARR, NB)["gagnant"] is False  # seul 4 dans top4


def test_trio_et_tierce_desordre():
    assert P.resoudre_pari(R("TRIO", [7, 4, 1]), ARR, NB)["gagnant"] is True      # {4,1,7}=={top3}
    assert P.resoudre_pari(R("TIERCE", [1, 7, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("TIERCE", [1, 7, 8]), ARR, NB)["gagnant"] is False


def test_quarte_quinte_desordre():
    assert P.resoudre_pari(R("QUARTE_PLUS", [8, 7, 1, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("QUINTE_PLUS", [3, 8, 7, 1, 4]), ARR, NB)["gagnant"] is True
    assert P.resoudre_pari(R("QUINTE_PLUS", [9, 8, 7, 1, 4]), ARR, NB)["gagnant"] is False  # 9=6e


def test_selection_trop_courte_perd():
    assert P.resoudre_pari(R("TIERCE", [4, 1]), ARR, NB)["gagnant"] is False
    assert P.resoudre_pari(R("SIMPLE_GAGNANT", []), ARR, NB)["gagnant"] is False


def test_arrivee_sans_gagnant_non_resolu():
    out = P.resoudre_pari(R("SIMPLE_GAGNANT", [4]), {4: 2, 1: 3}, NB)
    assert out["gagnant"] is None


def test_niveau_propage():
    out = P.resoudre_pari(R("SIMPLE_GAGNANT", [4], niveau="eleve"), ARR, NB)
    assert out["niveau"] == "eleve" and out["type_pari"] == "SIMPLE_GAGNANT"


def test_resoudre_analyse_liste():
    recos = [R("SIMPLE_GAGNANT", [4]), R("TIERCE", [1, 7, 4])]
    out = P.resoudre_analyse(recos, ARR, NB)
    assert [o["gagnant"] for o in out] == [True, True]


def test_agreger_paris_par_type_et_niveau():
    resolus = [
        {"type_pari": "SIMPLE_GAGNANT", "niveau": "eleve", "gagnant": True},
        {"type_pari": "SIMPLE_GAGNANT", "niveau": "moyen", "gagnant": False},
        {"type_pari": "TIERCE", "niveau": "faible", "gagnant": True},
        {"type_pari": "TIERCE", "niveau": "faible", "gagnant": None},  # ignoré
    ]
    par_type, par_niveau = P.agreger_paris(resolus)
    by_t = {d["type_pari"]: d for d in par_type}
    assert by_t["SIMPLE_GAGNANT"] == {"type_pari": "SIMPLE_GAGNANT", "nb": 2, "taux_reussite": 0.5}
    assert by_t["TIERCE"] == {"type_pari": "TIERCE", "nb": 1, "taux_reussite": 1.0}
    by_n = {d["niveau"]: d for d in par_niveau}
    assert by_n["eleve"]["taux_reussite"] == 1.0 and by_n["eleve"]["nb"] == 1


def test_agreger_vide():
    assert P.agreger_paris([]) == ([], [])
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_paris.py -q`
Expected: FAIL (module absent).

- [ ] **Step 3: Créer `app/backtest/paris.py`**

```python
"""Résolution des paris LLM contre l'arrivée réelle (désordre, placé simplifié).

Base sur la `selection` de la reco. Placé = top-K (K=3 si nb_partants>=8 sinon 2).
`gagnant`: True/False si résolu, None si l'arrivée n'a pas de gagnant (course non
résolue) ou si le type n'est pas géré.
"""

from collections import defaultdict

PLACE_MIN_RUNNERS = 8
_SET_EQ = {"TRIO": 3, "TIERCE": 3, "QUARTE_PLUS": 4, "QUINTE_PLUS": 5}


def _places_payantes(nb_partants: int) -> int:
    return 3 if nb_partants >= PLACE_MIN_RUNNERS else 2


def resoudre_pari(recommandation: dict, arrivee: dict, nb_partants: int) -> dict:
    type_pari = recommandation["type_pari"]
    niveau = recommandation.get("niveau")
    sel = recommandation.get("selection") or []
    out = {"type_pari": type_pari, "niveau": niveau, "gagnant": None}

    if not any(p == 1 for p in arrivee.values()):
        return out  # course sans gagnant identifiable -> non résolu

    k = _places_payantes(nb_partants)
    places = {c for c, p in arrivee.items() if p is not None and p <= k}

    def topn(n: int) -> set:
        return {c for c, p in arrivee.items() if p is not None and p <= n}

    def pos(c):
        return arrivee.get(c)

    if type_pari == "SIMPLE_GAGNANT":
        res = len(sel) >= 1 and pos(sel[0]) == 1
    elif type_pari == "SIMPLE_PLACE":
        res = len(sel) >= 1 and sel[0] in places
    elif type_pari == "COUPLE_GAGNANT":
        res = len(sel) >= 2 and set(sel[:2]) == topn(2)
    elif type_pari == "COUPLE_PLACE":
        res = len(sel) >= 2 and sel[0] in places and sel[1] in places
    elif type_pari == "DEUX_SUR_QUATRE":
        res = sum(1 for c in sel if c in topn(4)) >= 2
    elif type_pari in _SET_EQ:
        n = _SET_EQ[type_pari]
        res = len(sel) >= n and set(sel[:n]) == topn(n)
    else:
        return out  # type non géré

    out["gagnant"] = bool(res)
    return out


def resoudre_analyse(recommandations: list[dict], arrivee: dict, nb_partants: int) -> list[dict]:
    return [resoudre_pari(r, arrivee, nb_partants) for r in recommandations]


def agreger_paris(resolus: list[dict]):
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])   # [nb, gagnants]
    by_niveau: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for it in resolus:
        if it.get("gagnant") is None:
            continue
        hit = 1 if it["gagnant"] else 0
        t = by_type[it["type_pari"]]
        t[0] += 1
        t[1] += hit
        niv = it.get("niveau")
        if niv:
            n = by_niveau[niv]
            n[0] += 1
            n[1] += hit
    par_type = [
        {"type_pari": k, "nb": v[0], "taux_reussite": round(v[1] / v[0], 4)}
        for k, v in sorted(by_type.items())
    ]
    par_niveau = [
        {"niveau": k, "nb": v[0], "taux_reussite": round(v[1] / v[0], 4)}
        for k, v in sorted(by_niveau.items())
    ]
    return par_type, par_niveau
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_paris.py -q`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/paris.py backend/tests/test_backtest_paris.py
git commit -m "feat(backtest): resolution des paris LLM (desordre) + agregat par type/niveau"
```

---

### Task 2: Bloc `paris` dans `GET /backtest`

**Files:**
- Modify: `backend/app/backtest/routes.py`
- Test: `backend/tests/test_backtest_routes_paris.py`

**Interfaces:**
- Consumes : `resoudre_analyse`, `agreger_paris` (Task 1), `_corde_by_partant` (existant, Task C6).
- Produces : `GET /backtest` renvoie en plus `"paris": {nb_analyses_resolues, par_type, par_niveau}`. Bloc vide gracieux quand aucune analyse résolue.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_backtest_routes_paris.py` :

```python
from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def _seed(store):
    """course-1 (p1 corde1, p2 corde2) : arrivée corde1 1er, corde2 2e ;
    analyse llm : SIMPLE_GAGNANT [1] (gagne), SIMPLE_PLACE [2] (2 partants -> top2, gagne)."""
    store.tables["resultats"] = [
        {"id": "r1", "course_id": "course-1", "partant_id": "p1", "position_arrivee": 1, "disqualifie": False},
        {"id": "r2", "course_id": "course-1", "partant_id": "p2", "position_arrivee": 2, "disqualifie": False},
    ]
    store.tables["analyses_llm"] = [
        {"id": "a1", "course_id": "course-1", "modele": "claude-opus-4-8", "source": "llm",
         "recommandations": [
             {"type_pari": "SIMPLE_GAGNANT", "selection": [1], "base": [], "tournant": [],
              "confiance": 70, "niveau": "eleve", "avis": "x"},
             {"type_pari": "SIMPLE_PLACE", "selection": [2], "base": [], "tournant": [],
              "confiance": 60, "niveau": "moyen", "avis": "y"},
         ],
         "lecture_globale": "z", "coup_de_coeur_value": None, "input_snapshot": {},
         "confiance_globale": 65},
    ]


def test_backtest_paris_vide_gracieux():
    store = FakeStore()
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        assert body["paris"] == {"nb_analyses_resolues": 0, "par_type": [], "par_niveau": []}
    finally:
        app.dependency_overrides.clear()


def test_backtest_paris_calcule_taux():
    store = FakeStore()
    _seed(store)
    _override(store)
    try:
        body = TestClient(app).get("/backtest").json()
        paris = body["paris"]
        assert paris["nb_analyses_resolues"] == 1
        by_type = {d["type_pari"]: d for d in paris["par_type"]}
        assert by_type["SIMPLE_GAGNANT"]["nb"] == 1 and by_type["SIMPLE_GAGNANT"]["taux_reussite"] == 1.0
        assert by_type["SIMPLE_PLACE"]["taux_reussite"] == 1.0
        by_niv = {d["niveau"]: d for d in paris["par_niveau"]}
        assert by_niv["eleve"]["nb"] == 1 and by_niv["moyen"]["nb"] == 1
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes_paris.py -q`
Expected: FAIL (`KeyError: 'paris'`).

- [ ] **Step 3: Ajouter l'assemblage + le bloc dans `routes.py`**

Étendre l'import backtest en tête de `app/backtest/routes.py` :

```python
from app.backtest.paris import agreger_paris, resoudre_analyse
```

Ajouter le helper (près de `_evaluations`) :

```python
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
```

Dans `get_backtest`, avant le `return`, calculer le bloc et l'ajouter :

```python
    resolus, nb_analyses_resolues = _paris_resolus(client)
    par_type, par_niveau = agreger_paris(resolus)
```

et remplacer le `return { ... }` par (ajout de la clé `paris`) :

```python
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
```

- [ ] **Step 4: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_backtest_routes_paris.py -q`
Expected: PASS (2 tests).
Run: `cd backend && .venv/bin/pytest -q`
Expected: toute la suite verte (les tests `test_backtest_routes.py` existants voient une clé `paris` en plus — additive, ils testent des sous-ensembles, pas d'égalité stricte du dict complet).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/backtest/routes.py backend/tests/test_backtest_routes_paris.py
git commit -m "feat(backtest): bloc paris (taux par type/niveau) dans GET /backtest"
```

---

### Task 3: Frontend — type `Backtest` étendu

**Files:**
- Modify: `frontend/lib/types.ts`

**Interfaces:**
- Produces : types `BetTypeStat`, `BetNiveauStat` ; champ `paris` sur `Backtest`.

- [ ] **Step 1: Étendre `frontend/lib/types.ts`**

Ajouter les deux nouveaux types à la fin :

```typescript
export type BetTypeStat = { type_pari: string; nb: number; taux_reussite: number };
export type BetNiveauStat = { niveau: string; nb: number; taux_reussite: number };
```

et **ajouter le champ `paris`** au type `Backtest` existant (juste après `calibration_gate`) :

```typescript
  paris: {
    nb_analyses_resolues: number;
    par_type: BetTypeStat[];
    par_niveau: BetNiveauStat[];
  };
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (avertissement multiple-lockfiles toléré).

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/lib/types.ts
git commit -m "feat(plateforme): type Backtest.paris (stats paris IA)"
```

---

### Task 4: Frontend — section « Paris IA » dans `PerfPanel`

**Files:**
- Modify: `frontend/components/PerfPanel.tsx`

**Interfaces:**
- Consumes : `Backtest.paris` (Task 3), `libellePari` (`@/lib/paris`), `pct` (helper existant dans `PerfPanel`).
- Produces : une section « Paris IA » sous la calibration : taux par type (libellé) + par niveau, chaque ligne avec son `n` ; état « aucune analyse résultée » quand `nb_analyses_resolues == 0`.

- [ ] **Step 1: Modifier `frontend/components/PerfPanel.tsx`**

Ajouter l'import de `libellePari` en tête (à côté des autres imports) :

```tsx
import { libellePari } from "@/lib/paris";
```

Dans le rendu, **après** le bloc `<div>` de la « Calibration confiance » (et avant la fermeture du conteneur `data && !loading && !error`), insérer la section Paris IA :

```tsx
                  <div>
                    <div className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                      Paris IA · {data.paris.nb_analyses_resolues} analyse
                      {data.paris.nb_analyses_resolues > 1 ? "s" : ""} résolue
                      {data.paris.nb_analyses_resolues > 1 ? "s" : ""}
                    </div>
                    {data.paris.nb_analyses_resolues === 0 ? (
                      <p className="text-xs text-slate-400">
                        Aucune analyse dont la course a un résultat pour l'instant.
                      </p>
                    ) : (
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-col gap-1">
                          {data.paris.par_type.map((s) => (
                            <div key={s.type_pari} className="flex items-center gap-2 text-[11px]">
                              <span className="w-24 truncate text-slate-600">{libellePari(s.type_pari)}</span>
                              <div className="h-2 flex-1 overflow-hidden rounded-full bg-green-100">
                                <div className="h-full bg-green-600" style={{ width: `${s.taux_reussite * 100}%` }} />
                              </div>
                              <span className="w-14 text-right font-mono tabular-nums text-slate-600">
                                {pct(s.taux_reussite)} · n{s.nb}
                              </span>
                            </div>
                          ))}
                        </div>
                        <div className="flex flex-wrap gap-2 text-[10px] text-slate-500">
                          {data.paris.par_niveau.map((s) => (
                            <span key={s.niveau} className="rounded-md bg-slate-100 px-2 py-0.5 font-mono tabular-nums">
                              {s.niveau} {pct(s.taux_reussite)} (n{s.nb})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
```

(Note : `pct` accepte `number | null` ; `taux_reussite` est toujours un nombre ici, donc l'affichage est un pourcentage.)

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PerfPanel.tsx
git commit -m "feat(plateforme): section Paris IA dans le panneau Perf"
```

---

### Task 5: Vérification bout-en-bout (contrôleur)

**Files:** aucun (vérification).

Prérequis : aucune migration. Clé Anthropic présente (backend/.env) pour produire une analyse `llm` réelle, sinon le repli `regles` suffit à peupler des paris.

- [ ] **Step 1: Lancer les deux serveurs**

Tuer tout process squattant le port 8000 (`lsof -tiTCP:8000 -sTCP:LISTEN`), puis :

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # A (arrière-plan)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # B (arrière-plan)
```

- [ ] **Step 2: Créer une paire (analyse, résultat) puis vérifier le contrat**

Sur une course **déjà courue** (ex. une réunion de la veille) : `POST /courses/import` (date+R+C) → `course_id` ; `POST /courses/{id}/analyse` (corps `{"paris":[...]}`) → analyse persistée ; `POST /courses/{id}/resultats` → `captured:true`. Puis `GET /backtest` (avec `Origin: http://localhost:3000`) → le bloc `paris` a `nb_analyses_resolues ≥ 1`, `par_type` avec des `taux_reussite ∈ [0,1]` et `n`, `par_niveau` cohérent. Vérifier aussi le cas vide (base sans analyse résolue) → `paris` vides sans erreur.

- [ ] **Step 3: Vérifier le rendu** (contrôle visuel utilisateur — pas d'outil navigateur dans l'env)

Ouvrir http://localhost:3000 → bouton **Perf** → la section « Paris IA » affiche les taux par type + par niveau avec les `n`, ou « aucune analyse résultée » si vide. Pas de page d'erreur.

- [ ] **Step 4: Corriger tout écart** (câblage, CORS, forme des données) et re-vérifier. Arrêter les serveurs.

---

## Ce que ce plan produit

La boucle de mesure couvre désormais les **paris de l'IA** : on résout chaque recommandation contre l'arrivée réelle (désordre) et on expose le taux de réussite par type de pari et par niveau de confiance dans `GET /backtest` + le panneau Perf. Comme le reste de la mesure, c'est descriptif avec l'effectif `n` affiché, honnête sur la finesse de l'échantillon, et le jeu de données grossit à mesure que des analyses portent sur des courses résultées.

## Hors périmètre (Plan D — cet incrément)

- Fidélité PMU complète (ordre exact, règles de placé fines, non-partants, rapports/ROI) → plan futur.
- Persistance de snapshots de paris + filtre par source llm/regles.
- Application (proposer automatiquement les paris les plus rentables).
