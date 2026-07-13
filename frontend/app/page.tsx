"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { Course, Partant } from "@/lib/types";
import { ImportForm } from "@/components/ImportForm";
import { PartantsTable } from "@/components/PartantsTable";

export default function Home() {
  const [courseId, setCourseId] = useState<string | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [partants, setPartants] = useState<Partant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [etatTerrain, setEtatTerrain] = useState("");
  const [savingTerrain, setSavingTerrain] = useState(false);

  const loadCourse = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCourse(id);
      setCourse(data.course);
      setPartants(data.partants);
      setEtatTerrain(data.course.etat_terrain ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors du chargement de la course.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleImported(id: string) {
    setCourseId(id);
    await loadCourse(id);
  }

  async function handleEtatTerrainBlur() {
    if (!courseId || !course) return;
    if (etatTerrain === (course.etat_terrain ?? "")) return;
    setSavingTerrain(true);
    try {
      await api.patchCourse(courseId, { etat_terrain: etatTerrain });
      setCourse({ ...course, etat_terrain: etatTerrain });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement de l'état du terrain.");
    } finally {
      setSavingTerrain(false);
    }
  }

  return (
    <div className="min-h-full bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
            pronoturf <span className="text-slate-500">—</span>{" "}
            <span className="text-emerald-400">pronostic</span>
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Import de course, saisie des partants et calcul du pronostic.
          </p>
        </header>

        <div className="flex flex-col gap-8">
          <ImportForm onImported={handleImported} />

          {error && (
            <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          {loading && <p className="text-sm text-slate-400">Chargement…</p>}

          {course && (
            <section className="flex flex-col gap-6">
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Course {course.numero_course}
                </h2>
                <div className="flex flex-wrap items-end gap-6 text-sm">
                  <div>
                    <span className="block text-xs text-slate-500">Discipline</span>
                    <span className="font-medium text-slate-100">{course.discipline}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-slate-500">Distance</span>
                    <span className="font-mono tabular-nums font-medium text-slate-100">
                      {course.distance_m} m
                    </span>
                  </div>
                  <div>
                    <span className="block text-xs text-slate-500">Statut</span>
                    <span className="font-medium text-slate-100">{course.statut}</span>
                  </div>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-slate-500">État du terrain</span>
                    <input
                      type="text"
                      value={etatTerrain}
                      onChange={(e) => setEtatTerrain(e.target.value)}
                      onBlur={handleEtatTerrainBlur}
                      disabled={savingTerrain}
                      placeholder="ex. bon, souple…"
                      className="w-40 rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-emerald-500 disabled:opacity-50"
                    />
                  </label>
                </div>
              </div>

              <div>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Partants
                </h2>
                <PartantsTable partants={partants} onPartantSaved={() => loadCourse(courseId!)} />
              </div>

              {/*
                Task 4 hook point: add "Calculer le pronostic" button here
                (calls api.scoreCourse(courseId) / api.getPronostic(courseId))
                plus the resulting classement table.
              */}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
