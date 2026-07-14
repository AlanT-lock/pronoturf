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
