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
