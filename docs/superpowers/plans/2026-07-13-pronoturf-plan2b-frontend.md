# pronoturf — Plan 2b : frontend Next.js (page de travail)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Une interface web locale utilisable de bout en bout : importer une course, compléter à la main, calculer le pronostic, afficher le classement explicable.

**Architecture:** Frontend Next.js (App Router, TypeScript) dans `frontend/`, qui appelle l'API FastAPI locale (`http://localhost:8000`). Aucune lecture Supabase directe. Une tâche backend préalable unifie/enrichit les réponses des endpoints (nom du cheval + forme cohérente) et active CORS. Puis 3 tâches frontend (scaffold + client API, vue import/partants/saisie, vue scoring/pronostic). Vérification finale pilotée au navigateur (Playwright).

**Tech Stack:** Backend existant (FastAPI/Python). Frontend : Next.js 15 (App Router), React 19, TypeScript, Tailwind (via create-next-app). Pas d'auth, pas de déploiement (local only).

## Global Constraints

- **Local uniquement**, pas de Vercel. Le frontend tourne en `npm run dev` (port 3000), le backend en `uvicorn ... --port 8000`. Les deux doivent tourner pour utiliser l'app.
- Le frontend lit/écrit **uniquement via l'API FastAPI** (jamais Supabase directement). Base URL configurable via `NEXT_PUBLIC_API_URL` (défaut `http://localhost:8000`).
- Design : **propre et fonctionnel, orienté données** (bonnes tables, typographie lisible, palette sobre) — c'est un outil de test perso, pas une vitrine. Pas de sur-design.
- Backend : service-role reste côté backend, jamais exposé au frontend. CORS autorise l'origine du dev frontend.
- Ne jamais lire/afficher `backend/.env`.

## Contexte backend existant (Plan 2a)

Endpoints actuels (voir `backend/app/scoring/routes.py`, `backend/app/main.py`) :
- `POST /courses/import` body `{date:"DDMMYYYY", numero_reunion:int, numero_course:int}` → `{course_id, partant_ids}`.
- `GET /courses/{id}` → `{course, partants}` (partants avec `cote_retenue` mais **cheval_id brut, pas de nom**).
- `PATCH /courses/{id}` body `{etat_terrain?}`.
- `PATCH /partants/{id}` body `{ferrage?, poids_kg?, reduction_kilometrique?}` (+ champs_manuels).
- `POST /courses/{id}/score` → `{course_id, classement:[{numero_corde, score_total, rang, details_facteurs}]}` (**pas de nom cheval**).
- `GET /courses/{id}/pronostic` → lignes brutes `scores_pronostic` (`{partant_id, rang_pronostique, score_total, details_facteurs}` — **pas de numero_corde ni nom**).

`details_facteurs` = `{facteur: {valeur, poids_effectif, contribution}}` pour `forme, taux_reussite, ferrage_poids, cote, corde`.

## File Structure

```
backend/app/
  main.py                         # + CORSMiddleware (modifié)
  scoring/routes.py               # enrichir GET /courses, POST /score, GET /pronostic (modifié)
backend/tests/test_scoring_routes.py   # ajouts
frontend/                         # nouveau (create-next-app)
  .env.local                      # NEXT_PUBLIC_API_URL (gitignoré par défaut CNA)
  app/
    page.tsx                      # page de travail (client component)
    layout.tsx, globals.css       # générés
  lib/
    api.ts                        # client typé des endpoints
    types.ts                      # types partagés (Course, Partant, ScoreRow, ...)
  components/
    ImportForm.tsx                # saisie date/réunion/course + bouton importer
    PartantsTable.tsx             # tableau partants + saisie inline (etat_terrain, ferrage)
    PronosticTable.tsx            # classement + détail des facteurs
```

---

### Task 1: Backend — enrichir les réponses (nom cheval + forme unifiée) + CORS

**Files:**
- Modify: `backend/app/scoring/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_scoring_routes.py`

**Interfaces produites (contrat que le frontend consommera) :**
- `GET /courses/{id}` → `{course: {...}, partants: [{partant_id, numero_corde, nom_cheval, sexe, age, musique, nombre_courses, nombre_victoires, nombre_places, poids_kg, reduction_kilometrique, ferrage, statut, cote_retenue}]}`
- `POST /courses/{id}/score` → `{course_id, classement: [{partant_id, numero_corde, nom_cheval, score_total, rang, details_facteurs}]}`
- `GET /courses/{id}/pronostic` → **même forme que POST score** : `{course_id, classement: [{partant_id, numero_corde, nom_cheval, score_total, rang, details_facteurs, cote}]}` (champ de rang nommé `rang`, pas `rang_pronostique`).

- [ ] **Step 1: Écrire/étendre les tests (échouent d'abord)**

Dans `backend/tests/test_scoring_routes.py`, étendre le `FakeStore` pour inclure une table `chevaux` (jointure via `partants.cheval_id`), puis ajouter :
```python
def test_score_response_includes_nom_cheval_and_corde():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        body = client.post("/courses/course-1/score").json()
        top = body["classement"][0]
        assert "nom_cheval" in top and top["nom_cheval"]
        assert "numero_corde" in top
        assert "rang" in top
    finally:
        app.dependency_overrides.clear()


def test_pronostic_shape_matches_score_shape():
    store = FakeStore()
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)
    try:
        client = TestClient(app)
        client.post("/courses/course-1/score")
        body = client.get("/courses/course-1/pronostic").json()
        row = body["classement"][0]
        assert {"partant_id", "numero_corde", "nom_cheval", "score_total", "rang", "details_facteurs"} <= set(row)
    finally:
        app.dependency_overrides.clear()
```
Le `FakeStore` doit exposer `chevaux` (`id`, `nom`) et lier `partants[i].cheval_id`.

- [ ] **Step 2: Lancer → échec**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest tests/test_scoring_routes.py -v`
Expected: FAIL (nom_cheval absent, ou forme pronostic différente).

- [ ] **Step 3: Implémenter l'enrichissement**

Dans `routes.py` :
- Helper `_cheval_nom_par_partant(client, partant_ids) -> dict[str, tuple[numero_corde, nom]]` : lit `partants` (id, numero_corde, cheval_id) puis `chevaux` (id, nom) pour ces ids, en **une requête chacune** (`.in_(...)`), et renvoie la map partant_id → (numero_corde, nom). Évite le N+1.
- `POST /score` : après `score_course`, enrichir chaque ligne du classement avec `partant_id` (déjà mappé), `nom_cheval` (via la map). Renvoyer `{course_id, classement}`.
- `GET /pronostic` : lire `scores_pronostic` (order by rang_pronostique), puis pour chaque ligne renvoyer `{partant_id, numero_corde, nom_cheval, score_total, rang: rang_pronostique, details_facteurs, cote}` (cote = cote retenue du partant, ou None). Récupérer numero_corde/nom via la même map ; récupérer les cotes en une requête `.in_(partant_ids)`.
- `GET /courses/{id}` : enrichir chaque partant avec `nom_cheval` (map cheval_id→nom en une requête).

Dans `main.py`, ajouter CORS :
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Lancer → passent**

Run: `cd /Users/alantouati/pronoturf/backend && .venv/bin/pytest -v`
Expected: PASS (tous, dont les 2 nouveaux).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add backend/app/scoring/routes.py backend/app/main.py backend/tests/test_scoring_routes.py && git commit -m "feat(api): enrich score/pronostic/course responses with horse name + CORS"
```

---

### Task 2: Frontend — scaffold Next.js + client API typé

**Files:**
- Create: `frontend/` (via create-next-app)
- Create: `frontend/lib/types.ts`, `frontend/lib/api.ts`
- Create: `frontend/.env.local`

**Interfaces produites:** fonctions `api.importCourse(date, r, c)`, `api.getCourse(id)`, `api.patchCourse(id, body)`, `api.patchPartant(id, body)`, `api.scoreCourse(id)`, `api.getPronostic(id)` ; types `Course, Partant, ScoreRow, FactorDetail`.

- [ ] **Step 1: Scaffolder Next.js**

```bash
cd /Users/alantouati/pronoturf && npx --yes create-next-app@latest frontend --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm
```
Attendu : projet `frontend/` créé, `npm install` effectué par CNA.

- [ ] **Step 2: `.env.local`**

`frontend/.env.local` :
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Types**

`frontend/lib/types.ts` :
```typescript
export type FactorDetail = { valeur: number; poids_effectif: number; contribution: number };
export type Partant = {
  partant_id: string;
  numero_corde: number;
  nom_cheval: string;
  sexe: string | null;
  age: number | null;
  musique: string | null;
  nombre_courses: number | null;
  nombre_victoires: number | null;
  nombre_places: number | null;
  poids_kg: number | null;
  reduction_kilometrique: number | null;
  ferrage: string | null;
  statut: string;
  cote_retenue: number | null;
};
export type Course = {
  id: string;
  numero_course: number;
  discipline: string;
  distance_m: number;
  statut: string;
  etat_terrain: string | null;
};
export type ScoreRow = {
  partant_id: string;
  numero_corde: number;
  nom_cheval: string;
  score_total: number;
  rang: number;
  details_facteurs: Record<string, FactorDetail>;
  cote?: number | null;
};
```

- [ ] **Step 4: Client API**

`frontend/lib/api.ts` :
```typescript
import type { Course, Partant, ScoreRow } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  importCourse: (date: string, numero_reunion: number, numero_course: number) =>
    req<{ course_id: string; partant_ids: string[] }>("/courses/import", {
      method: "POST",
      body: JSON.stringify({ date, numero_reunion, numero_course }),
    }),
  getCourse: (id: string) => req<{ course: Course; partants: Partant[] }>(`/courses/${id}`),
  patchCourse: (id: string, body: { etat_terrain?: string }) =>
    req<unknown>(`/courses/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  patchPartant: (id: string, body: { ferrage?: string; poids_kg?: number; reduction_kilometrique?: number }) =>
    req<unknown>(`/partants/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  scoreCourse: (id: string) =>
    req<{ course_id: string; classement: ScoreRow[] }>(`/courses/${id}/score`, { method: "POST" }),
  getPronostic: (id: string) =>
    req<{ course_id: string; classement: ScoreRow[] }>(`/courses/${id}/pronostic`),
};
```

- [ ] **Step 5: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (pas d'erreur TS). (La page par défaut de CNA suffit à cette étape.)

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf && git add frontend && git commit -m "feat(frontend): scaffold Next.js app with typed API client"
```

> Note : create-next-app génère un `.gitignore` dans `frontend/` qui exclut `node_modules/`, `.next/`, `.env*`. Vérifier que `frontend/node_modules` et `frontend/.next` ne sont pas ajoutés au commit.

---

### Task 3: Frontend — page de travail : import + partants + saisie manuelle

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/ImportForm.tsx`, `frontend/components/PartantsTable.tsx`
- Modify: `frontend/app/globals.css` si besoin (styles utilitaires légers)

**Interfaces:** `page.tsx` est un client component (`"use client"`) qui orchestre l'état (course courante, partants, classement) et rend les composants.

- [ ] **Step 1: `ImportForm`**

`frontend/components/ImportForm.tsx` : formulaire avec 3 champs (date `DDMMYYYY` — défaut aujourd'hui au format PMU, numéro de réunion, numéro de course) et un bouton « Importer ». `onImport(courseId)` callback appelé après `api.importCourse`. Afficher l'erreur si l'appel échoue (ex. backend éteint → message clair « Backend injoignable, lance uvicorn sur le port 8000 »).

- [ ] **Step 2: `PartantsTable`**

`frontend/components/PartantsTable.tsx` : reçoit `partants: Partant[]` et rend un tableau (numéro, nom, sexe/âge, musique, courses/victoires/places, poids ou réduction km selon dispo, ferrage, cote retenue). Les non-partants grisés. Champs éditables inline : `ferrage` (par partant, `PATCH /partants/{id}`) et `etat_terrain` (niveau course, `PATCH /courses/{id}`, un champ au-dessus du tableau). Un bouton « Enregistrer les saisies » ou sauvegarde au blur.

- [ ] **Step 3: `page.tsx` orchestration (partie 1)**

`frontend/app/page.tsx` : `"use client"`, état `courseId`, `course`, `partants`. Au retour d'import, appeler `api.getCourse(courseId)` pour peupler `course` + `partants`. Rendre `ImportForm` puis, si course chargée, l'entête course (discipline, distance, état terrain éditable) + `PartantsTable`. Titre de page « pronoturf — pronostic ».

- [ ] **Step 4: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf && git add frontend/app/page.tsx frontend/components frontend/app/globals.css && git commit -m "feat(frontend): course import + partants table with manual entry"
```

---

### Task 4: Frontend — scoring + tableau de pronostic explicable

**Files:**
- Create: `frontend/components/PronosticTable.tsx`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: `PronosticTable`**

`frontend/components/PronosticTable.tsx` : reçoit `classement: ScoreRow[]`. Tableau trié par rang : rang, numéro, nom cheval, score (barre ou %), cote. Colonne/expand « détail » montrant la contribution de chaque facteur (`forme, taux_reussite, ferrage_poids, cote, corde`) — ex. mini-barres ou valeurs `valeur × poids = contribution`. Rendre le score lisible (ex. `score_total` ×100 arrondi).

- [ ] **Step 2: `page.tsx` orchestration (partie 2)**

Ajouter un bouton « Calculer le pronostic » (visible quand une course est chargée) → `api.scoreCourse(courseId)` → stocker `classement` → rendre `PronosticTable`. Gérer l'état de chargement et les erreurs. Au chargement d'une course déjà scorée, optionnellement `api.getPronostic` pour réafficher un classement existant.

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf && git add frontend/app/page.tsx frontend/components/PronosticTable.tsx && git commit -m "feat(frontend): scoring trigger + explainable pronostic table"
```

---

### Task 5: Vérification bout-en-bout au navigateur (contrôleur)

Non déléguée — le contrôleur exécute cette vérification avec les deux serveurs lancés et Playwright.

- [ ] **Step 1: Lancer backend + frontend**

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # terminal A (background)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # terminal B (background)
```

- [ ] **Step 2: Piloter au navigateur (Playwright)**

Naviguer sur `http://localhost:3000`, importer une vraie course du jour (réunion/numéro valides), vérifier l'affichage des partants (noms, stats, cotes), déclencher « Calculer le pronostic », vérifier le tableau de classement (trié, noms visibles, détail des facteurs cohérent). Prendre une capture d'écran.

- [ ] **Step 3: Corriger tout écart** constaté (câblage frontend/backend, CORS, forme des données) et re-vérifier.

- [ ] **Step 4: Documenter le lancement**

Ajouter à un `README.md` racine (ou compléter `backend/README.md`) : comment lancer les deux serveurs et ouvrir l'app. Commit.

---

## Ce que ce plan produit

Une app web locale utilisable : l'utilisateur importe une course, complète les champs manquants, clique pour calculer, et voit un classement pronostiqué explicable — testable de bout en bout dans le navigateur.

## Hors scope

- Résultats réels + précision du pronostic (Plan 4).
- Ingestion Geny + fraîcheur (Plan 3).
- Déploiement (Vercel/prod), auth, RLS.
- Points du backlog `plan2a-review-backlog.md` non liés à l'affichage (N+1, transactions, tuning des poids).
