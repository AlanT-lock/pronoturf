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
