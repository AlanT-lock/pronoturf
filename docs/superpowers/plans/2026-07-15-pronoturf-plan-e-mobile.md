# Plan E — version mobile (liste → détail + onglets, cartes) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre pronoturf pleinement utilisable et optimisé sur mobile : parcours master-detail (liste des courses → détail avec onglets Pronostic/Analyse IA), tableaux reflow en cartes tactiles, sans toucher au dashboard desktop 3 colonnes.

**Architecture:** Pur frontend (Next.js/TS/Tailwind). Bascule à `lg` : `≥ lg` = dashboard 3 colonnes actuel (déplacé sous `hidden lg:grid`, contenu inchangé) ; `< lg` = corps mobile (`lg:hidden`) piloté par un état `mobileView`/`mobileTab` dans `Home`. Deux nouveaux composants cartes (`PronosticCards`, `PartantsCards`) ; helpers de facteurs extraits dans `components/factors.tsx` (partagés desktop/mobile). `AnalyseIA` déjà en cartes. **Aucun changement backend.**

**Tech Stack :** Next.js (App Router) + TypeScript + Tailwind v4.

**Réf. spec :** `docs/superpowers/specs/2026-07-15-pronoturf-plan-e-mobile-design.md`.

## Global Constraints

- **Bascule à `lg` (1024px)** : desktop (`≥ lg`) strictement inchangé (grid 3 colonnes déplacé sous `hidden lg:grid`, aucun contenu modifié) ; mobile (`< lg`) = nouveau corps `lg:hidden`.
- **Master-detail + onglets** : `mobileView: "list" | "detail"`, `mobileTab: "prono" | "analyse"` dans `Home`. Sélectionner une course → `detail` + `prono` ; « ‹ Retour » → `list`.
- **Reflow cartes** : `PronosticCards`/`PartantsCards` reproduisent fidèlement le dépli des facteurs (pronostic) et l'édition inline du ferrage (partants) — **mêmes appels API, même logique** que les tableaux desktop. Les tableaux desktop `PronosticTable`/`PartantsTable` gardent un **rendu identique** (seuls les helpers de facteurs sont extraits, sans changement de sortie).
- **Identité visuelle** : blanc, vert `green-600` (soft `green-50`, hover `green-700`), texte `slate-900`/`slate-500`, `font-mono tabular-nums` pour les nombres, polices système. Cibles tactiles ≥ 44px, onglets/action collants, **aucun scroll horizontal** sur mobile.
- **Gate** : `cd frontend && npm run build` (pas de suite unitaire front ; avertissement multiple-lockfiles toléré). Ne pas lancer `npm run dev` pendant le build.
- **Ce n'est PAS le Next.js que tu connais** (`frontend/AGENTS.md`) : lire `node_modules/next/dist/docs/` avant toute construction sensible à la version.
- **Aucune modification backend.**

## Structure des fichiers

- `frontend/components/factors.tsx` — **créer** : `factorLabel`, `FactorBar`, `FactorDetails` (extraits de `PronosticTable`).
- `frontend/components/PronosticTable.tsx` — **modifier** : importer les helpers depuis `factors` (rendu inchangé).
- `frontend/components/PronosticCards.tsx` — **créer** : variante mobile du pronostic (cartes + dépli facteurs).
- `frontend/components/PartantsCards.tsx` — **créer** : variante mobile des partants (cartes + édition ferrage).
- `frontend/app/page.tsx` — **modifier** : en-tête responsive + corps desktop (`hidden lg:grid`) + corps mobile (`lg:hidden`, liste/détail/onglets) + état `mobileView`/`mobileTab`.
- `frontend/components/PerfPanel.tsx` — **modifier** : popover borné pour petit écran.

---

### Task 1: Extraire les helpers de facteurs (`components/factors.tsx`)

**Files:**
- Create: `frontend/components/factors.tsx`
- Modify: `frontend/components/PronosticTable.tsx`

**Interfaces:**
- Produces : `factorLabel(key) -> string`, `FactorBar({contribution, max})`, `FactorDetails({row: ScoreRow})` (rend la grille de cartes de facteurs). Consommés par `PronosticTable` (Task 1) et `PronosticCards` (Task 2).

- [ ] **Step 1: Créer `frontend/components/factors.tsx`**

```tsx
"use client";

import type { ScoreRow } from "@/lib/types";

const FACTOR_LABELS: Record<string, string> = {
  forme: "Forme",
  taux_reussite: "Taux de réussite",
  ferrage_poids: "Ferrage/Poids",
  cote: "Cote",
  corde: "Corde",
};

export function factorLabel(key: string): string {
  return FACTOR_LABELS[key] ?? key;
}

export function FactorBar({ contribution, max }: { contribution: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (Math.abs(contribution) / max) * 100)) : 0;
  return (
    <div className="h-1.5 w-full rounded-full bg-green-100">
      <div
        className={`h-1.5 rounded-full ${contribution >= 0 ? "bg-green-600" : "bg-red-500"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function FactorDetails({ row }: { row: ScoreRow }) {
  const entries = Object.entries(row.details_facteurs);
  const maxContribution = Math.max(0, ...entries.map(([, d]) => Math.abs(d.contribution)));
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {entries.map(([key, detail]) => (
        <div key={key} className="rounded-md border border-slate-200 bg-white p-3">
          <div className="mb-1.5 flex items-center justify-between gap-2 text-xs">
            <span className="font-medium text-slate-600">{factorLabel(key)}</span>
            <span className="font-mono tabular-nums text-slate-500">
              {detail.valeur.toFixed(2)} × {detail.poids_effectif.toFixed(2)} ={" "}
              {detail.contribution.toFixed(2)}
            </span>
          </div>
          <FactorBar contribution={detail.contribution} max={maxContribution} />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Refactor `PronosticTable.tsx` pour utiliser les helpers**

Dans `frontend/components/PronosticTable.tsx` :
- **Supprimer** les définitions locales `FACTOR_LABELS`, `factorLabel`, `FactorBar` (déplacées dans `factors.tsx`).
- Ajouter en tête : `import { FactorDetails } from "./factors";`
- **Remplacer** la fonction `DetailRow` par :

```tsx
function DetailRow({ row }: { row: ScoreRow }) {
  return (
    <tr className="border-b border-slate-100 bg-slate-50 last:border-b-0">
      <td colSpan={6} className="px-3 py-3">
        <FactorDetails row={row} />
      </td>
    </tr>
  );
}
```

(Le reste de `PronosticTable` — le `<table>` et ses lignes — est **inchangé** ; le rendu final est identique.)

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (avertissement multiple-lockfiles toléré). Aucune erreur TS (le `Fragment`/`useState` de `PronosticTable` restent utilisés).

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/factors.tsx frontend/components/PronosticTable.tsx
git commit -m "refactor(front): extraire les helpers de facteurs (partages desktop/mobile)"
```

---

### Task 2: Composant `PronosticCards` (mobile)

**Files:**
- Create: `frontend/components/PronosticCards.tsx`

**Interfaces:**
- Consumes : `ScoreRow` (types), `FactorDetails` (Task 1).
- Produces : `PronosticCards({ classement: ScoreRow[] })` — **mêmes props que `PronosticTable`**. Une carte par ligne triée par `rang` ; tap → déplie les facteurs.

- [ ] **Step 1: Créer `frontend/components/PronosticCards.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { ScoreRow } from "@/lib/types";
import { FactorDetails } from "./factors";

export function PronosticCards({ classement }: { classement: ScoreRow[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const sorted = [...classement].sort((a, b) => a.rang - b.rang);

  return (
    <div className="flex flex-col gap-2">
      {sorted.map((row) => {
        const isExpanded = expandedId === row.partant_id;
        const scorePct = Math.round(row.score_total * 100);
        return (
          <div key={row.partant_id} className="rounded-xl border border-slate-200 bg-white">
            <button
              type="button"
              onClick={() => setExpandedId(isExpanded ? null : row.partant_id)}
              className="flex w-full flex-col gap-2 p-3 text-left"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-extrabold text-slate-900">
                  <span className="font-mono tabular-nums text-green-700">#{row.rang}</span>{" "}
                  {row.nom_cheval}
                  <span className="ml-1 font-mono text-xs font-normal text-slate-400">
                    n°{row.numero_corde}
                  </span>
                </span>
                <span className="font-mono tabular-nums text-sm font-bold text-slate-900">
                  {scorePct}%
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-green-100">
                <div
                  className="h-full bg-green-600"
                  style={{ width: `${Math.min(100, Math.max(0, scorePct))}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-mono tabular-nums">cote {row.cote ?? "—"}</span>
                <span className="inline-flex items-center gap-1.5">
                  {typeof row.confiance === "number" ? (
                    <>
                      <span
                        className={`h-2 w-2 rounded-full ${
                          row.confiance >= 0.66
                            ? "bg-green-500"
                            : row.confiance >= 0.33
                            ? "bg-amber-400"
                            : "bg-red-400"
                        }`}
                      />
                      <span className="font-mono tabular-nums">{row.nb_courses_historique ?? 0} c.</span>
                    </>
                  ) : (
                    "—"
                  )}
                  <span className="ml-1 text-slate-400">{isExpanded ? "▲" : "▼"}</span>
                </span>
              </div>
            </button>
            {isExpanded && (
              <div className="border-t border-slate-100 bg-slate-50 p-3">
                <FactorDetails row={row} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (composant non encore monté ; le build valide TS/JSX).

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PronosticCards.tsx
git commit -m "feat(mobile): PronosticCards (pronostic en cartes + depli facteurs)"
```

---

### Task 3: Composant `PartantsCards` (mobile, édition ferrage)

**Files:**
- Create: `frontend/components/PartantsCards.tsx`

**Interfaces:**
- Consumes : `Partant` (types), `api.patchPartant` (existant).
- Produces : `PartantsCards({ partants: Partant[]; onPartantSaved: () => void })` — **mêmes props que `PartantsTable`**. Une carte par partant ; champ ferrage éditable (save au blur, comme `PartantsTable`).

- [ ] **Step 1: Créer `frontend/components/PartantsCards.tsx`**

```tsx
"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Partant } from "@/lib/types";

function formeSuffixe(courses: number | null, victoires: number | null, places: number | null) {
  if (courses === null && victoires === null && places === null) return "—";
  return `${courses ?? 0}c ${victoires ?? 0}v ${places ?? 0}p`;
}

function FerrageField({ partant, onSaved }: { partant: Partant; onSaved: () => void }) {
  const [value, setValue] = useState(partant.ferrage ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (value === (partant.ferrage ?? "")) return;
    setSaving(true);
    setError(null);
    try {
      await api.patchPartant(partant.partant_id, { ferrage: value });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-0.5">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        disabled={saving}
        placeholder="ferrage —"
        className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 outline-none focus:border-green-600 disabled:opacity-50"
      />
      {error && <span className="text-[10px] text-red-400">{error}</span>}
    </div>
  );
}

export function PartantsCards({
  partants,
  onPartantSaved,
}: {
  partants: Partant[];
  onPartantSaved: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      {partants.map((p) => {
        const nonPartant = p.statut === "non_partant";
        return (
          <div
            key={p.partant_id}
            className={`rounded-xl border border-slate-200 bg-white p-3 ${nonPartant ? "opacity-50" : ""}`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-bold text-slate-900">
                <span className="font-mono tabular-nums text-slate-400">n°{p.numero_corde}</span>{" "}
                {p.nom_cheval}
                {nonPartant && (
                  <span className="ml-2 text-xs font-normal text-red-500">non partant</span>
                )}
              </span>
              <span className="font-mono tabular-nums text-xs text-slate-600">
                cote {p.cote_retenue ?? "—"}
              </span>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-slate-500">
              <span className="truncate">J. {p.jockey_nom ?? "—"}</span>
              <span className="truncate">E. {p.entraineur_nom ?? "—"}</span>
              <span>
                {p.sexe ?? "—"}
                {p.age !== null ? `/${p.age}` : ""}
              </span>
              <span className="font-mono tabular-nums">
                {formeSuffixe(p.nombre_courses, p.nombre_victoires, p.nombre_places)}
              </span>
              {p.musique && <span className="col-span-2 font-mono text-slate-600">{p.musique}</span>}
              {p.poids_kg !== null && (
                <span className="font-mono tabular-nums">{p.poids_kg} kg</span>
              )}
              {p.reduction_kilometrique !== null && (
                <span className="font-mono tabular-nums">rk {p.reduction_kilometrique}</span>
              )}
            </div>
            <div className="mt-2">
              <FerrageField partant={p} onSaved={onPartantSaved} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PartantsCards.tsx
git commit -m "feat(mobile): PartantsCards (partants en cartes + edition ferrage)"
```

---

### Task 4: Coquille responsive `page.tsx` (desktop `hidden lg:grid` + corps mobile)

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes : `PronosticCards` (Task 2), `PartantsCards` (Task 3), `AnalyseIA`/`CourseBrowser`/`DayNav`/`PronosticTable`/`PartantsTable`/`PerfPanel` (existants).
- Produces : en-tête responsive ; corps desktop (`hidden lg:grid`, contenu inchangé) ; corps mobile (`lg:hidden`) liste/détail/onglets ; état `mobileView`/`mobileTab`.

- [ ] **Step 1: Réécrire `frontend/app/page.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  AnalyseIA as AnalyseIAType,
  Course,
  Partant,
  Programme,
  ProgrammeCourse,
  ProgrammeReunion,
  ScoreRow,
} from "@/lib/types";
import { addDays, toDdmmyyyy } from "@/lib/dates";
import { DayNav } from "@/components/DayNav";
import { CourseBrowser } from "@/components/CourseBrowser";
import { PartantsTable } from "@/components/PartantsTable";
import { PronosticTable } from "@/components/PronosticTable";
import { PartantsCards } from "@/components/PartantsCards";
import { PronosticCards } from "@/components/PronosticCards";
import { AnalyseIA } from "@/components/AnalyseIA";
import { PerfPanel } from "@/components/PerfPanel";

const LABEL = "text-[10px] font-extrabold uppercase tracking-wider text-slate-400";

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
  const [analyse, setAnalyse] = useState<AnalyseIAType | null>(null);
  const [analyseLoading, setAnalyseLoading] = useState(false);

  // Vues mobile (ignorées ≥ lg où tout s'affiche).
  const [mobileView, setMobileView] = useState<"list" | "detail">("list");
  const [mobileTab, setMobileTab] = useState<"prono" | "analyse">("prono");

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
    setAnalyse(null);
    try {
      const p = await api.getPronostic(id);
      setClassement(p.classement);
    } catch {
      /* pas encore de pronostic — normal */
    }
    try {
      const a = await api.getAnalyse(id);
      setAnalyse(a);
    } catch {
      /* pas encore d'analyse — normal (404) */
    }
  }, []);

  async function selectCourse(r: ProgrammeReunion, c: ProgrammeCourse) {
    setSelected({ r: r.numero_reunion, c: c.numero_course });
    setSelectedParis(c.paris);
    setMobileView("detail");
    setMobileTab("prono");
    setLoading(true);
    setError(null);
    setCourse(null);
    setPartants([]);
    setClassement(null);
    setAnalyse(null);
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

  async function runAnalyse(force: boolean) {
    if (!courseId) return;
    setAnalyseLoading(true);
    setError(null);
    try {
      const a = await api.analyseCourse(courseId, selectedParis, force);
      setAnalyse(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de l'analyse IA.");
    } finally {
      setAnalyseLoading(false);
    }
  }

  const isQuinte = selectedParis.includes("QUINTE_PLUS");

  // Bloc « Pronostic » réutilisé (mobile) : bouton + cartes pronostic + partants.
  const pronoBlock = course && (
    <section className="flex flex-col gap-4">
      <button
        type="button"
        onClick={handleScore}
        disabled={scoring}
        className="rounded-full bg-green-600 px-4 py-2.5 text-xs font-bold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
      >
        {scoring ? "Calcul en cours…" : "Calculer le pronostic"}
      </button>
      {classement && (
        <div>
          <div className={`mb-2 ${LABEL}`}>Pronostic</div>
          <PronosticCards classement={classement} />
        </div>
      )}
      <div>
        <div className={`mb-2 ${LABEL}`}>Partants</div>
        <PartantsCards partants={partants} onPartantSaved={() => courseId && loadCourse(courseId)} />
      </div>
    </section>
  );

  return (
    <div className="min-h-full bg-white text-slate-900">
      {/* Barre supérieure */}
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3 sm:px-5">
        <div className="text-[15px] font-extrabold tracking-tight text-green-700">
          pronoturf{" "}
          <span className="hidden font-bold text-slate-300 sm:inline">· le turf, en clair</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden lg:block">
            <DayNav date={date} onPrev={() => setDate((d) => addDays(d, -1))} onNext={() => setDate((d) => addDays(d, 1))} />
          </div>
          <PerfPanel />
        </div>
      </header>

      {error && (
        <p className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 sm:mx-5">
          {error}
        </p>
      )}

      {/* ===== Corps desktop (≥ lg) : dashboard 3 colonnes inchangé ===== */}
      <div className="hidden lg:grid lg:grid-cols-[240px_1fr_360px]">
        <aside className="border-slate-200 bg-slate-50/60 p-3.5 lg:border-r lg:min-h-[calc(100vh-57px)]">
          <CourseBrowser programme={programme} loading={progLoading} selected={selected} onSelect={selectCourse} />
        </aside>

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
                <div className={`mb-2 ${LABEL}`}>Partants</div>
                <PartantsTable partants={partants} onPartantSaved={() => courseId && loadCourse(courseId)} />
              </div>

              {classement && (
                <div>
                  <div className={`mb-2 ${LABEL}`}>Pronostic</div>
                  <PronosticTable classement={classement} />
                </div>
              )}
            </section>
          )}
        </main>

        <aside className="border-slate-200 bg-slate-50/40 p-4 lg:border-l">
          <div className={`mb-2 ${LABEL}`}>Analyse IA</div>
          {course ? (
            <AnalyseIA
              analyse={analyse}
              loading={analyseLoading}
              onAnalyser={() => runAnalyse(false)}
              onReanalyser={() => runAnalyse(true)}
              disabled={analyseLoading}
            />
          ) : (
            <p className="text-sm text-slate-400">—</p>
          )}
        </aside>
      </div>

      {/* ===== Corps mobile (< lg) : master-detail + onglets ===== */}
      <div className="lg:hidden">
        {mobileView === "list" ? (
          <div className="p-3.5">
            <div className="mb-3">
              <DayNav date={date} onPrev={() => setDate((d) => addDays(d, -1))} onNext={() => setDate((d) => addDays(d, 1))} />
            </div>
            <CourseBrowser programme={programme} loading={progLoading} selected={selected} onSelect={selectCourse} />
          </div>
        ) : (
          <div>
            {/* En-tête détail collant : retour + titre + onglets */}
            <div className="sticky top-0 z-10 border-b border-slate-200 bg-white">
              <div className="flex items-center gap-2 px-4 py-2.5">
                <button
                  type="button"
                  onClick={() => setMobileView("list")}
                  className="flex h-9 items-center rounded-lg border border-slate-200 px-3 text-sm font-bold text-slate-600 transition-colors hover:border-green-600 hover:text-green-700"
                >
                  ‹ Retour
                </button>
                {course && (
                  <span className="truncate text-xs font-bold text-slate-800">
                    Course {course.numero_course}
                    {isQuinte && <span className="text-green-700"> · Quinté+</span>}
                    <span className="font-medium text-slate-400"> · {course.discipline} · {course.distance_m} m</span>
                  </span>
                )}
              </div>
              <div className="flex border-t border-slate-100">
                {(["prono", "analyse"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setMobileTab(tab)}
                    className={`flex-1 border-b-2 py-2.5 text-xs font-bold transition-colors ${
                      mobileTab === tab
                        ? "border-green-600 text-green-700"
                        : "border-transparent text-slate-400"
                    }`}
                  >
                    {tab === "prono" ? "Pronostic" : "Analyse IA"}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-4">
              {loading || !course ? (
                <p className="mt-6 text-center text-sm text-slate-400">Chargement de la course…</p>
              ) : mobileTab === "prono" ? (
                pronoBlock
              ) : (
                <AnalyseIA
                  analyse={analyse}
                  loading={analyseLoading}
                  onAnalyser={() => runAnalyse(false)}
                  onReanalyser={() => runAnalyse(true)}
                  disabled={analyseLoading}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi. Aucun import inutilisé (tous les composants importés sont montés : `PronosticTable`/`PartantsTable` sur desktop, `PronosticCards`/`PartantsCards` sur mobile).

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/app/page.tsx
git commit -m "feat(mobile): coquille responsive (desktop 3-col + master-detail mobile a onglets)"
```

---

### Task 5: `PerfPanel` — popover borné sur petit écran

**Files:**
- Modify: `frontend/components/PerfPanel.tsx`

**Interfaces:** inchangées. Seul le popover est borné pour ne pas déborder du viewport mobile.

- [ ] **Step 1: Borner le popover**

Dans `frontend/components/PerfPanel.tsx`, sur le `<div>` du popover (celui avec `absolute right-0 z-10 mt-2 w-72 …`), ajouter une largeur max responsive : remplacer `w-72` par `w-72 max-w-[calc(100vw-1.5rem)]` (le popover reste à 288px sur desktop mais ne dépasse jamais la largeur de l'écran moins une marge sur mobile). Ne rien changer d'autre.

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/PerfPanel.tsx
git commit -m "fix(mobile): popper Perf borne a la largeur du viewport"
```

---

### Task 6: Vérification bout-en-bout (contrôleur) — Playwright mobile

**Files:** aucun (vérification).

Prérequis : aucune migration. Backend nécessaire (l'ouverture d'une course importe depuis PMU). Playwright MCP : `browser_navigate`/`browser_resize`/`browser_snapshot`/clics **fonctionnent** ; `browser_take_screenshot` **timeout à 5s** → utiliser `browser_snapshot` (arbre d'accessibilité/DOM), pas d'images.

- [ ] **Step 1: Lancer les deux serveurs**

Tuer tout process sur le port 8000 (`lsof -tiTCP:8000 -sTCP:LISTEN`), puis :

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # A (arrière-plan)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # B (arrière-plan)
```

- [ ] **Step 2: Piloter la vue mobile via Playwright**

Redimensionner en viewport mobile (`browser_resize` 390×844), `browser_navigate` `http://localhost:3000`, puis `browser_snapshot` :
- **Vue Liste** : vérifier la présence de `DayNav` (‹ date ›) et de la liste des courses (Quinté+ visible), et l'absence de la grille desktop (le corps `hidden lg:grid` ne doit pas apparaître dans le snapshot mobile).
- **Cliquer** une course (`browser_click` sur une puce de course) → attendre le chargement → `browser_snapshot` : vérifier la **barre Retour + titre**, les **onglets Pronostic/Analyse IA**, les **cartes** (partants ; pronostic si déjà scoré). Cliquer « Calculer le pronostic » → snapshot : cartes de pronostic présentes.
- **Cliquer** l'onglet « Analyse IA » → snapshot : le panneau `AnalyseIA` (bouton Analyser ou analyse existante).
- **Cliquer** « ‹ Retour » → snapshot : retour à la vue Liste.
- Vérifier qu'aucun débordement horizontal n'apparaît (pas de scroll-x ; les cartes occupent la largeur).

- [ ] **Step 3: Non-régression desktop**

`browser_resize` 1280×900, `browser_navigate` `http://localhost:3000`, `browser_snapshot` : la grille 3 colonnes (courses | pronostic | analyse) est présente ; le `DayNav` est dans l'en-tête. (Le corps mobile `lg:hidden` ne doit pas apparaître.)

- [ ] **Step 4: Corriger tout écart** (classes responsive, bascule, débordement) et re-vérifier. Arrêter les serveurs.

Repli si Playwright indisponible : `npm run build` vert + laisser les serveurs up pour un contrôle visuel utilisateur (devtools mode mobile), et confirmer qu'aucun appel backend n'a changé (frontend pur).

---

## Ce que ce plan produit

Sur téléphone : une vue Liste (navigation jour + courses, Quinté+ en avant), un tap ouvre le détail plein écran avec onglets Pronostic / Analyse IA, tout en cartes tactiles (aucun tableau qui déborde), bouton Retour. Sur desktop : le dashboard 3 colonnes strictement inchangé. Frontend pur, aucune régression backend.

## Hors périmètre (Plan E)

- Refonte du design system, PWA/offline, gestes avancés (swipe, pull-to-refresh), toute modification backend.
