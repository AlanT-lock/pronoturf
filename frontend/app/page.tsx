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
