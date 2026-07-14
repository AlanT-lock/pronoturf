# Plateforme pronoturf — Plan A (découverte des courses + refonte du shell) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la saisie manuelle réunion/course par une plateforme : navigation jour par jour, liste des courses du jour (Quinté+ en avant), et pronostic enrichi affiché dans un dashboard 3 colonnes blanc + vert.

**Architecture:** Backend expose `GET /programme/{date}` (proxy normalisé du programme PMU : réunions→courses + paris + Quinté+), sans écriture DB. Frontend refondu en dashboard 3 colonnes (blanc/vert `#16A34A`) : navigation jour en haut, navigateur de courses à gauche, pronostic au centre (import + scoring existants), colonne droite réservée à l'Analyse IA (Plan B, placeholder). Aucune IA en Plan A.

**Tech Stack:** FastAPI + Pydantic + supabase-py + pytest (FakeStore/monkeypatch) ; Next.js (App Router) + TypeScript + Tailwind v4.

**Réf. spec :** `docs/superpowers/specs/2026-07-14-pronoturf-plateforme-paris-ia-design.md`.

## Global Constraints

- **Découverte = zéro écriture DB.** `GET /programme/{date}` ne fait que fetch + normaliser le programme PMU. L'import lourd (course/partants/historique) reste déclenché à l'ouverture d'une course, via l'endpoint existant `POST /courses/import`.
- **Quinté+ dérivé** de la présence du pari `QUINTE_PLUS` dans le tableau `paris` de la course (pas de flag PMU dédié).
- **Variantes en ligne `E_`** dédupliquées avec leur base (`E_SIMPLE_GAGNANT` == `SIMPLE_GAGNANT`).
- **Identité visuelle** : fond **blanc**, accent **vert `#16A34A` = classe Tailwind `green-600`** (soft `green-50`, hover `green-700`). Texte `slate-900`/`slate-500`. **Polices système uniquement** (pas de `next/font/google` — le build est offline). `font-mono tabular-nums` pour les nombres.
- **Layout cible** : dashboard **3 colonnes** (courses | pronostic | analyse IA), pas de sections empilées ; responsive (empilement propre en dessous d'un seuil).
- **Gate frontend** = `cd frontend && npm run build` (pas de suite unitaire front). Gate backend = `cd backend && .venv/bin/pytest`.
- **Ce n'est PAS le Next.js que tu connais** (`frontend/AGENTS.md`) : lire `node_modules/next/dist/docs/` avant toute construction sensible à la version.
- TDD strict côté backend ; idempotence non concernée (lecture seule).

## Structure des fichiers

Backend :
- `backend/app/bet_types.py` — **créer** : mapping `typePari` PMU → codes internes + libellés + set analysable.
- `backend/app/pmu_normalizer.py` — **modifier** : `normalize_programme`.
- `backend/app/main.py` — **modifier** : endpoint `GET /programme/{date}`.
- `backend/tests/test_bet_types.py`, `test_normalize_programme.py`, `test_programme_endpoint.py` — **créer**.

Frontend :
- `frontend/lib/types.ts` — **modifier** : types `Programme`, `ProgrammeReunion`, `ProgrammeCourse`.
- `frontend/lib/api.ts` — **modifier** : `getProgramme(date)`.
- `frontend/lib/dates.ts` — **créer** : helpers date (DDMMYYYY, +/- jours, libellé FR).
- `frontend/lib/paris.ts` — **créer** : libellés FR des codes de paris (côté client).
- `frontend/components/DayNav.tsx` — **créer** : barre de navigation jour.
- `frontend/components/CourseBrowser.tsx` — **créer** : colonne gauche (courses groupées par réunion, Quinté+ en avant).
- `frontend/components/PartantsTable.tsx`, `PronosticTable.tsx` — **modifier** : restyle sombre → blanc/vert.
- `frontend/app/globals.css`, `frontend/app/layout.tsx` — **modifier** : thème clair.
- `frontend/app/page.tsx` — **réécrire** : dashboard 3 colonnes.

---

### Task 1: Module `bet_types` (mapping des paris)

**Files:**
- Create: `backend/app/bet_types.py`
- Test: `backend/tests/test_bet_types.py`

**Interfaces:**
- Produces : `map_paris(raw_types) -> list[str]` (codes internes triés, dédupliqués, sans préfixe `E_`) ; `est_quinte(codes) -> bool` ; `libelle(code) -> str` ; constante `ANALYSABLE: set[str]`.

- [ ] **Step 1: Test rouge**

Create `backend/tests/test_bet_types.py` :

```python
from app import bet_types as bt


def test_map_paris_dedupes_online_variants():
    raw = ["SIMPLE_GAGNANT", "E_SIMPLE_GAGNANT", "SIMPLE_PLACE", "E_SIMPLE_PLACE", "QUINTE_PLUS"]
    assert bt.map_paris(raw) == ["QUINTE_PLUS", "SIMPLE_GAGNANT", "SIMPLE_PLACE"]


def test_map_paris_ignores_none():
    assert bt.map_paris(["TRIO", None, "E_TRIO"]) == ["TRIO"]


def test_est_quinte():
    assert bt.est_quinte(["SIMPLE_GAGNANT", "QUINTE_PLUS"]) is True
    assert bt.est_quinte(["SIMPLE_GAGNANT", "TRIO"]) is False


def test_libelle_known_and_fallback():
    assert bt.libelle("QUINTE_PLUS") == "Quinté+"
    assert bt.libelle("SIMPLE_GAGNANT") == "Simple Gagnant"
    assert bt.libelle("INCONNU_XYZ") == "INCONNU_XYZ"


def test_analysable_subset():
    assert "QUINTE_PLUS" in bt.ANALYSABLE
    assert "COUPLE_ORDRE" not in bt.ANALYSABLE  # affiché mais pas analysé
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_bet_types.py -q` → FAIL (module absent).

- [ ] **Step 3: Créer `app/bet_types.py`**

```python
"""Mapping des types de paris PMU vers des identifiants internes lisibles.

Les variantes en ligne sont préfixées `E_` (E_SIMPLE_GAGNANT == SIMPLE_GAGNANT).
`ANALYSABLE` = sous-ensemble stratégié par l'IA au Plan B ; les autres paris sont
affichés dans l'UI mais non analysés.
"""

ANALYSABLE = {
    "SIMPLE_GAGNANT", "SIMPLE_PLACE", "COUPLE_GAGNANT", "COUPLE_PLACE",
    "DEUX_SUR_QUATRE", "TRIO", "TIERCE", "QUARTE_PLUS", "QUINTE_PLUS",
}

LABELS = {
    "SIMPLE_GAGNANT": "Simple Gagnant", "SIMPLE_PLACE": "Simple Placé",
    "COUPLE_GAGNANT": "Couplé Gagnant", "COUPLE_PLACE": "Couplé Placé",
    "COUPLE_ORDRE": "Couplé Ordre", "DEUX_SUR_QUATRE": "2 sur 4",
    "TRIO": "Trio", "TRIO_ORDRE": "Trio Ordre", "TIERCE": "Tiercé",
    "QUARTE_PLUS": "Quarté+", "QUINTE_PLUS": "Quinté+", "MULTI": "Multi",
    "MINI_MULTI": "Mini Multi", "SUPER_QUATRE": "Super Quatre",
    "PICK5": "Pick 5", "REPORT_PLUS": "Report+",
}


def _base_code(type_pari: str) -> str:
    return type_pari[2:] if type_pari.startswith("E_") else type_pari


def map_paris(raw_types) -> list[str]:
    return sorted({_base_code(t) for t in raw_types if t})


def est_quinte(codes) -> bool:
    return "QUINTE_PLUS" in codes


def libelle(code: str) -> str:
    return LABELS.get(code, code)
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_bet_types.py -q` → PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/bet_types.py backend/tests/test_bet_types.py
git commit -m "feat(plateforme): module bet_types (mapping paris PMU + Quinte+)"
```

---

### Task 2: `normalize_programme` (normalisation du programme du jour)

**Files:**
- Modify: `backend/app/pmu_normalizer.py`
- Test: `backend/tests/test_normalize_programme.py`

**Interfaces:**
- Consumes : `bet_types.map_paris`/`est_quinte` (Task 1), `_DISCIPLINE_MAP` (existant).
- Produces : `normalize_programme(programme: dict) -> dict` → `{"reunions": [{numero_reunion, hippodrome, pays, courses:[{numero_course, discipline, distance_m, heure_depart(ISO), statut, nombre_partants, allocation, paris:[codes], est_quinte}]}]}`.

- [ ] **Step 1: Test rouge**

Create `backend/tests/test_normalize_programme.py` :

```python
from app.pmu_normalizer import normalize_programme

PROG = {"programme": {"reunions": [
    {"numOfficiel": 1, "pays": {"code": "FRA"},
     "hippodrome": {"code": "PLC", "libelleCourt": "ParisLongchamp"},
     "courses": [
        {"numOrdre": 1, "discipline": "PLAT", "distance": 1400, "montantPrix": 25000,
         "heureDepart": 1784030100000, "nombreDeclaresPartants": 12,
         "paris": [{"typePari": "SIMPLE_GAGNANT"}, {"typePari": "E_SIMPLE_GAGNANT"}, {"typePari": "TRIO"}]},
        {"numOrdre": 3, "discipline": "PLAT", "distance": 2400, "montantPrix": 90000,
         "heureDepart": 1784032500000, "nombreDeclaresPartants": 16, "arriveeDefinitive": False,
         "paris": [{"typePari": "QUINTE_PLUS"}, {"typePari": "TIERCE"}, {"typePari": "SIMPLE_GAGNANT"}]},
     ]},
]}}


def test_normalize_programme_structure():
    out = normalize_programme(PROG)
    assert len(out["reunions"]) == 1
    r = out["reunions"][0]
    assert r["numero_reunion"] == 1 and r["hippodrome"] == "ParisLongchamp" and r["pays"] == "FRA"
    assert len(r["courses"]) == 2


def test_course_fields_and_paris_deduped():
    c = normalize_programme(PROG)["reunions"][0]["courses"][0]
    assert c["numero_course"] == 1
    assert c["discipline"] == "plat"
    assert c["distance_m"] == 1400
    assert c["allocation"] == 25000
    assert c["nombre_partants"] == 12
    assert c["statut"] == "a_venir"
    assert c["paris"] == ["SIMPLE_GAGNANT", "TRIO"]   # E_ dédupliqué
    assert c["est_quinte"] is False
    assert c["heure_depart"].startswith("2026-")       # ISO


def test_quinte_flagged():
    c3 = normalize_programme(PROG)["reunions"][0]["courses"][1]
    assert c3["est_quinte"] is True
    assert "QUINTE_PLUS" in c3["paris"]
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_normalize_programme.py -q` → FAIL (fonction absente).

- [ ] **Step 3: Ajouter `normalize_programme` dans `app/pmu_normalizer.py`**

Ajouter l'import en tête : `from app import bet_types`. Puis, à la fin du fichier :

```python
def normalize_programme(programme: dict) -> dict:
    reunions = []
    for r in programme["programme"]["reunions"]:
        courses = []
        for c in r.get("courses", []):
            codes = bet_types.map_paris([p.get("typePari") for p in c.get("paris", [])])
            raw_disc = c.get("discipline")
            heure = c.get("heureDepart")
            courses.append({
                "numero_course": c["numOrdre"],
                "discipline": _DISCIPLINE_MAP.get(raw_disc, raw_disc.lower() if raw_disc else None),
                "distance_m": c.get("distance"),
                "heure_depart": (
                    datetime.fromtimestamp(heure / 1000, tz=timezone.utc).isoformat()
                    if heure is not None else None
                ),
                "statut": "terminee" if c.get("arriveeDefinitive") else "a_venir",
                "nombre_partants": c.get("nombreDeclaresPartants"),
                "allocation": c.get("montantPrix"),
                "paris": codes,
                "est_quinte": bet_types.est_quinte(codes),
            })
        reunions.append({
            "numero_reunion": r["numOfficiel"],
            "hippodrome": r["hippodrome"]["libelleCourt"],
            "pays": r["pays"]["code"],
            "courses": courses,
        })
    return {"reunions": reunions}
```

(`datetime`, `timezone` et `_DISCIPLINE_MAP` sont déjà importés/définis dans ce fichier.)

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_normalize_programme.py -q` → PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/pmu_normalizer.py backend/tests/test_normalize_programme.py
git commit -m "feat(plateforme): normalize_programme (reunions/courses + paris + Quinte)"
```

---

### Task 3: Endpoint `GET /programme/{date}`

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_programme_endpoint.py`

**Interfaces:**
- Consumes : `fetch_programme` (existant), `normalize_programme` (Task 2).
- Produces : `GET /programme/{date}` (date `JJMMAAAA`) → `{"date", "reunions":[...]}`.

- [ ] **Step 1: Test rouge**

Create `backend/tests/test_programme_endpoint.py` :

```python
import app.main as main
from fastapi.testclient import TestClient

PROG = {"programme": {"reunions": [
    {"numOfficiel": 1, "pays": {"code": "FRA"},
     "hippodrome": {"code": "PLC", "libelleCourt": "ParisLongchamp"},
     "courses": [
        {"numOrdre": 3, "discipline": "PLAT", "distance": 2400, "montantPrix": 90000,
         "heureDepart": 1784032500000, "nombreDeclaresPartants": 16,
         "paris": [{"typePari": "QUINTE_PLUS"}, {"typePari": "SIMPLE_GAGNANT"}]},
     ]},
]}}


def test_get_programme_returns_normalized(monkeypatch):
    async def fake_prog(date):
        assert date == "14072026"
        return PROG
    monkeypatch.setattr(main, "fetch_programme", fake_prog)
    r = TestClient(main.app).get("/programme/14072026")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "14072026"
    c = body["reunions"][0]["courses"][0]
    assert c["est_quinte"] is True
    assert body["reunions"][0]["hippodrome"] == "ParisLongchamp"
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_programme_endpoint.py -q` → FAIL (route 404).

- [ ] **Step 3: Ajouter la route dans `app/main.py`**

Étendre l'import du normalizer :

```python
from app.pmu_normalizer import (
    find_course_in_programme, normalize_course, normalize_partants,
    normalize_performances, normalize_programme,
)
```

Ajouter la route (après `health_check`, avant `import_course`). **Pas de dépendance
Supabase** : la découverte est en lecture seule sur PMU, aucune DB requise (ça garde
aussi le test simple, sans override de dépendance).

```python
@app.get("/programme/{date}")
async def get_programme(date: str) -> dict:
    programme = await fetch_programme(date)
    return {"date": date, **normalize_programme(programme)}
```

(CORS localhost:3000 est déjà configuré.)

- [ ] **Step 4: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_programme_endpoint.py -q` → PASS.
Run: `cd backend && .venv/bin/pytest -q` → toute la suite verte.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/main.py backend/tests/test_programme_endpoint.py
git commit -m "feat(plateforme): endpoint GET /programme/{date}"
```

---

### Task 4: Frontend — types, client API, helpers date/paris, thème clair

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/app/globals.css`, `frontend/app/layout.tsx`
- Create: `frontend/lib/dates.ts`, `frontend/lib/paris.ts`

**Interfaces:**
- Produces : types `Programme`/`ProgrammeReunion`/`ProgrammeCourse` ; `api.getProgramme(date)` ; helpers `toDdmmyyyy`/`addDays`/`labelFr` ; `libellePari(code)`.

- [ ] **Step 1: Types — `frontend/lib/types.ts`**

Ajouter :

```typescript
export type ProgrammeCourse = {
  numero_course: number;
  discipline: string | null;
  distance_m: number | null;
  heure_depart: string | null;
  statut: string;
  nombre_partants: number | null;
  allocation: number | null;
  paris: string[];
  est_quinte: boolean;
};

export type ProgrammeReunion = {
  numero_reunion: number;
  hippodrome: string;
  pays: string;
  courses: ProgrammeCourse[];
};

export type Programme = { date: string; reunions: ProgrammeReunion[] };
```

- [ ] **Step 2: Client — `frontend/lib/api.ts`**

Ajouter `Programme` à l'import de types en tête, puis dans l'objet `api` :

```typescript
  getProgramme: (date: string) => req<Programme>(`/programme/${date}`),
```

- [ ] **Step 3: Helpers date — `frontend/lib/dates.ts`**

```typescript
export function toDdmmyyyy(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}${mm}${d.getFullYear()}`;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export function labelFr(d: Date): string {
  const s = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}
```

- [ ] **Step 4: Libellés paris — `frontend/lib/paris.ts`**

```typescript
const LABELS: Record<string, string> = {
  SIMPLE_GAGNANT: "Simple Gagnant", SIMPLE_PLACE: "Simple Placé",
  COUPLE_GAGNANT: "Couplé Gagnant", COUPLE_PLACE: "Couplé Placé",
  COUPLE_ORDRE: "Couplé Ordre", DEUX_SUR_QUATRE: "2 sur 4",
  TRIO: "Trio", TRIO_ORDRE: "Trio Ordre", TIERCE: "Tiercé",
  QUARTE_PLUS: "Quarté+", QUINTE_PLUS: "Quinté+", MULTI: "Multi",
  MINI_MULTI: "Mini Multi", SUPER_QUATRE: "Super Quatre",
  PICK5: "Pick 5", REPORT_PLUS: "Report+",
};

export function libellePari(code: string): string {
  return LABELS[code] ?? code;
}
```

- [ ] **Step 5: Thème clair — `frontend/app/globals.css`**

Le fichier est déjà en base blanche (Tailwind v4). Confirmer/forcer le fond blanc et un texte ardoise par défaut ; ajouter une couleur d'accent de marque. Remplacer le bloc `:root` + `body` par :

```css
:root {
  --background: #ffffff;
  --foreground: #0f172a;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Menlo", "Consolas", monospace;
}

body {
  font-family: var(--font-sans);
  background: var(--background);
  color: var(--foreground);
}
```

- [ ] **Step 6: `frontend/app/layout.tsx`**

Mettre à jour le `metadata.title` et garder la base claire :

```tsx
export const metadata: Metadata = {
  title: "pronoturf — le turf, en clair",
  description: "Plateforme locale de pronostic hippique",
};
```

et la classe body : `className="min-h-full bg-white text-slate-900"`.

- [ ] **Step 7: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build` → build réussi (seul l'avertissement pré-existant multiple-lockfiles est toléré).

- [ ] **Step 8: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/dates.ts frontend/lib/paris.ts frontend/app/globals.css frontend/app/layout.tsx
git commit -m "feat(plateforme): types Programme + getProgramme + helpers + theme clair"
```

---

### Task 5: Frontend — composants `DayNav` et `CourseBrowser`

**Files:**
- Create: `frontend/components/DayNav.tsx`, `frontend/components/CourseBrowser.tsx`

**Interfaces:**
- Consumes : types `Programme`/`ProgrammeReunion`/`ProgrammeCourse` (Task 4), `libellePari`, `labelFr`.
- Produces :
  - `DayNav({ date, onPrev, onNext })` où `date: Date`.
  - `CourseBrowser({ programme, loading, selected, onSelect })` où `selected: {r:number,c:number}|null` et `onSelect(reunion, course)`.

- [ ] **Step 1: `frontend/components/DayNav.tsx`**

```tsx
"use client";

import { labelFr } from "@/lib/dates";

type Props = { date: Date; onPrev: () => void; onNext: () => void };

export function DayNav({ date, onPrev, onNext }: Props) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onPrev}
        aria-label="Jour précédent"
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-green-600 hover:text-green-700"
      >
        ‹
      </button>
      <span className="rounded-full border border-green-200 bg-green-50 px-3 py-1.5 text-sm font-bold text-green-700">
        {labelFr(date)}
      </span>
      <button
        type="button"
        onClick={onNext}
        aria-label="Jour suivant"
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-green-600 hover:text-green-700"
      >
        ›
      </button>
    </div>
  );
}
```

- [ ] **Step 2: `frontend/components/CourseBrowser.tsx`**

```tsx
"use client";

import type { Programme, ProgrammeCourse, ProgrammeReunion } from "@/lib/types";

type Props = {
  programme: Programme | null;
  loading: boolean;
  selected: { r: number; c: number } | null;
  onSelect: (reunion: ProgrammeReunion, course: ProgrammeCourse) => void;
};

function heure(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

export function CourseBrowser({ programme, loading, selected, onSelect }: Props) {
  if (loading) return <p className="p-3 text-sm text-slate-400">Chargement du programme…</p>;
  if (!programme || programme.reunions.length === 0)
    return <p className="p-3 text-sm text-slate-400">Aucune course ce jour-là.</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        Courses du jour · {programme.reunions.length} réunions
      </div>
      {programme.reunions.map((r) => (
        <div key={r.numero_reunion}>
          <div className="mb-1.5 flex items-center gap-2 text-xs font-extrabold text-slate-800">
            R{r.numero_reunion} · {r.hippodrome}
          </div>
          <div className="flex flex-col gap-1.5">
            {r.courses.map((c) => {
              const on = selected?.r === r.numero_reunion && selected?.c === c.numero_course;
              return (
                <button
                  key={c.numero_course}
                  type="button"
                  onClick={() => onSelect(r, c)}
                  className={`flex items-center justify-between rounded-lg border px-2.5 py-2 text-left text-xs transition-colors ${
                    c.est_quinte
                      ? "border-green-600 bg-green-50"
                      : on
                      ? "border-green-600 bg-white shadow-[0_0_0_2px_rgba(22,163,74,0.12)]"
                      : "border-slate-200 bg-white hover:border-green-300"
                  }`}
                >
                  <span className="text-slate-800">
                    <b className="font-bold">C{c.numero_course}</b>
                    <span className="ml-1 text-slate-400">· {heure(c.heure_depart)}</span>
                  </span>
                  {c.est_quinte ? (
                    <span className="rounded-full bg-green-600 px-2 py-0.5 text-[9px] font-extrabold tracking-wide text-white">
                      QUINTÉ+
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-bold text-slate-500">
                      {c.discipline ?? "—"}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build` → réussi.
(Les composants ne sont pas encore montés ; le build valide juste TS/JSX.)

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/DayNav.tsx frontend/components/CourseBrowser.tsx
git commit -m "feat(plateforme): composants DayNav + CourseBrowser"
```

---

### Task 6: Frontend — restyle `PartantsTable` et `PronosticTable` en blanc/vert

**Files:**
- Modify: `frontend/components/PartantsTable.tsx`, `frontend/components/PronosticTable.tsx`

**Interfaces:** inchangées (mêmes props). Seul le style change (sombre `slate-900/800/emerald` → blanc/`slate`/`green-600`).

- [ ] **Step 1: `PartantsTable.tsx` — passage au thème clair**

Remplacer les classes sombres par leurs équivalents clairs, sans changer la logique ni la structure. Correspondances à appliquer partout dans le fichier :
- conteneur : `border-slate-800` → `border-slate-200` ; `overflow-x-auto rounded-lg`.
- entête `thead tr` : `border-slate-800 bg-slate-900/80 text-slate-400` → `border-slate-200 bg-slate-50 text-slate-500`.
- lignes `tbody tr` : `border-slate-800/60` → `border-slate-100` ; zébrure `bg-slate-900/30` → `bg-slate-50/60`.
- textes : `text-slate-300`/`text-slate-100` → `text-slate-600`/`text-slate-900` ; `text-slate-500` conservé.
- inputs (FerrageCell + autres) : `border-slate-700 bg-slate-950 text-slate-100 focus:border-emerald-500` → `border-slate-300 bg-white text-slate-900 focus:border-green-600`.
- accents `emerald-*` → `green-600`.
- marqueur « non partant » : `text-red-400` → `text-red-500`.

Vérifier qu'aucune classe `slate-9xx`/`emerald` ne subsiste (`grep -n "slate-9\|emerald\|bg-slate-950" frontend/components/PartantsTable.tsx` → vide).

- [ ] **Step 2: `PronosticTable.tsx` — passage au thème clair**

Mêmes correspondances. En particulier :
- barres de score / badges de confiance : fond `emerald`/`slate` → `green-600` sur piste `green-100` ; pastilles confiance : vert `bg-green-500`, orange `bg-amber-400`, rouge `bg-red-400` (inchangé pour amber/red).
- lignes dépliées `details_facteurs` : fonds sombres → `bg-slate-50` ; textes clairs.
- conserver le `colSpan` et l'itération générique sur `details_facteurs`.

Vérifier `grep -n "slate-9\|emerald\|bg-slate-950" frontend/components/PronosticTable.tsx` → vide.

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build` → réussi.

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PartantsTable.tsx frontend/components/PronosticTable.tsx
git commit -m "feat(plateforme): restyle PartantsTable + PronosticTable en blanc/vert"
```

---

### Task 7: Frontend — dashboard 3 colonnes (`page.tsx`)

**Files:**
- Rewrite: `frontend/app/page.tsx`

**Interfaces:**
- Consumes : `api.getProgramme` + `api.importCourse` + `api.getCourse` + `api.getPronostic` + `api.scoreCourse` ; `DayNav`, `CourseBrowser`, `PartantsTable`, `PronosticTable` ; helpers dates ; `libellePari`.
- Produces : la page plateforme (dashboard 3 colonnes) ; l'`ImportForm` n'est plus utilisé dans le flux principal.

- [ ] **Step 1: Réécrire `frontend/app/page.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Course, Partant, Programme, ProgrammeCourse, ProgrammeReunion, ScoreRow } from "@/lib/types";
import { addDays, toDdmmyyyy } from "@/lib/dates";
import { libellePari } from "@/lib/paris";
import { DayNav } from "@/components/DayNav";
import { CourseBrowser } from "@/components/CourseBrowser";
import { PartantsTable } from "@/components/PartantsTable";
import { PronosticTable } from "@/components/PronosticTable";

export default function Home() {
  const [date, setDate] = useState<Date>(() => new Date());
  const [programme, setProgramme] = useState<Programme | null>(null);
  const [progLoading, setProgLoading] = useState(false);
  const [selected, setSelected] = useState<{ r: number; c: number } | null>(null);

  const [courseId, setCourseId] = useState<string | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [partants, setPartants] = useState<Partant[]>([]);
  const [classement, setClassement] = useState<ScoreRow[] | null>(null);
  const [selectedParis, setSelectedParis] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Charge le programme du jour à chaque changement de date.
  useEffect(() => {
    let cancelled = false;
    setProgLoading(true);
    setProgramme(null);
    api
      .getProgramme(toDdmmyyyy(date))
      .then((p) => !cancelled && setProgramme(p))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Programme indisponible."))
      .finally(() => !cancelled && setProgLoading(false));
    return () => {
      cancelled = true;
    };
  }, [date]);

  const loadCourse = useCallback(async (id: string) => {
    const data = await api.getCourse(id);
    setCourse(data.course);
    setPartants(data.partants);
    setClassement(null);
    try {
      const p = await api.getPronostic(id);
      setClassement(p.classement);
    } catch {
      /* pas encore de pronostic — normal */
    }
  }, []);

  async function selectCourse(r: ProgrammeReunion, c: ProgrammeCourse) {
    setSelected({ r: r.numero_reunion, c: c.numero_course });
    setSelectedParis(c.paris);
    setLoading(true);
    setError(null);
    setCourse(null);
    setPartants([]);
    setClassement(null);
    try {
      const { course_id } = await api.importCourse(toDdmmyyyy(date), r.numero_reunion, c.numero_course);
      setCourseId(course_id);
      await loadCourse(course_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur au chargement de la course.");
    } finally {
      setLoading(false);
    }
  }

  async function handleScore() {
    if (!courseId) return;
    setScoring(true);
    setError(null);
    try {
      const data = await api.scoreCourse(courseId);
      setClassement(data.classement);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors du calcul du pronostic.");
    } finally {
      setScoring(false);
    }
  }

  return (
    <div className="min-h-full bg-white text-slate-900">
      {/* Barre supérieure */}
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
        <div className="text-[15px] font-extrabold tracking-tight text-green-700">
          pronoturf <span className="font-bold text-slate-300">· le turf, en clair</span>
        </div>
        <DayNav date={date} onPrev={() => setDate((d) => addDays(d, -1))} onNext={() => setDate((d) => addDays(d, 1))} />
      </header>

      {error && (
        <p className="mx-5 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {/* Dashboard 3 colonnes */}
      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_360px]">
        {/* Colonne gauche : courses */}
        <aside className="border-b border-slate-200 bg-slate-50/60 p-3.5 lg:border-b-0 lg:border-r lg:min-h-[calc(100vh-57px)]">
          <CourseBrowser programme={programme} loading={progLoading} selected={selected} onSelect={selectCourse} />
        </aside>

        {/* Colonne centre : pronostic */}
        <main className="p-4">
          {!course && !loading && (
            <p className="mt-10 text-center text-sm text-slate-400">
              Sélectionne une course à gauche pour voir le pronostic.
            </p>
          )}
          {loading && <p className="mt-10 text-center text-sm text-slate-400">Chargement de la course…</p>}
          {course && (
            <section className="flex flex-col gap-5">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-sm font-extrabold text-slate-900">
                  Course {course.numero_course}
                  <span className="ml-2 font-medium text-slate-500">
                    · {course.discipline} · {course.distance_m} m
                  </span>
                </h2>
                <button
                  type="button"
                  onClick={handleScore}
                  disabled={scoring}
                  className="rounded-full bg-green-600 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                >
                  {scoring ? "Calcul en cours…" : "Calculer le pronostic"}
                </button>
              </div>

              <div>
                <div className="mb-2 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Partants</div>
                <PartantsTable partants={partants} onPartantSaved={() => courseId && loadCourse(courseId)} />
              </div>

              {classement && (
                <div>
                  <div className="mb-2 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Pronostic</div>
                  <PronosticTable classement={classement} />
                </div>
              )}
            </section>
          )}
        </main>

        {/* Colonne droite : analyse IA (Plan B) */}
        <aside className="border-t border-slate-200 bg-slate-50/40 p-4 lg:border-t-0 lg:border-l">
          <div className="mb-2 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Analyse IA</div>
          {course ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-400">
              L'analyse IA (paris, confiance, avis) arrive au prochain incrément.
              {selectedParis.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {selectedParis.map((p) => (
                    <span
                      key={p}
                      className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                        p === "QUINTE_PLUS" ? "bg-green-600 text-white" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {libellePari(p)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">—</p>
          )}
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build` → build réussi.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/app/page.tsx
git commit -m "feat(plateforme): dashboard 3 colonnes (nav jour + courses + pronostic + placeholder IA)"
```

> Note : `frontend/components/ImportForm.tsx` n'est plus référencé. Le laisser en place (mort) pour l'instant ; sa suppression sera un nettoyage sans risque en fin de plan si souhaité.

---

### Task 8: Vérification bout-en-bout (contrôleur)

**Files:** aucun (vérification).

- [ ] **Step 1: Lancer les deux serveurs**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # A (arrière-plan)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # B (arrière-plan)
```

Avant de démarrer, vérifier qu'aucun process ne squatte déjà le port 8000 (`lsof -tiTCP:8000 -sTCP:LISTEN` ; tuer si besoin — piège déjà rencontré).

- [ ] **Step 2: Vérifier le contrat HTTP réel (ce que le front appelle)**

`GET /programme/14072026` (avec `Origin: http://localhost:3000` pour CORS) → structure réunions/courses ; au moins une course `est_quinte:true`. Puis simuler la sélection : `POST /courses/import` (date+R+C d'une course listée) → course_id ; `GET /courses/:id` → partants ; `POST /courses/:id/score` → classement 11 facteurs. (Prérequis réel : migration 0003 déjà appliquée.)

- [ ] **Step 3: Vérifier le rendu** (contrôle visuel utilisateur — pas d'outil navigateur dans l'env)

Ouvrir http://localhost:3000 : dashboard blanc/vert, navigation jour (‹ / ›) qui recharge la liste, colonne gauche des courses avec Quinté+ surligné, clic sur une course → pronostic au centre, colonne droite = placeholder Analyse IA avec les puces de paris (Quinté+ en vert). Vérifier que le build servi n'est pas une page d'erreur.

- [ ] **Step 4: Corriger tout écart** (câblage, CORS, forme des données) et re-vérifier. Arrêter les serveurs.

---

## Ce que ce plan produit

Une plateforme utilisable : on navigue de jour en jour, on voit toutes les courses du jour avec le Quinté+ mis en avant, on clique une course et on obtient le pronostic enrichi — le tout dans un dashboard 3 colonnes blanc/vert moderne. La colonne Analyse IA est en place (placeholder) et sera branchée au **Plan B** (analyse Opus 4.8 + persistance).

## Hors périmètre (Plan A)

- Toute l'**analyse IA** (paris, confiance, avis, persistance) → **Plan B**.
- Recherche cheval/jockey (best-effort, plus tard).
- Suppression de `ImportForm` (nettoyage optionnel).
- Édition inline avancée / saisie manuelle au-delà de l'existant.
