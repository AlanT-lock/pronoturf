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
