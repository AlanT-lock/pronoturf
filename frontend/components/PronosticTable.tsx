"use client";

import { Fragment, useState } from "react";
import type { ScoreRow } from "@/lib/types";
import { FactorDetails } from "./factors";

type PronosticTableProps = {
  classement: ScoreRow[];
};

function DetailRow({ row }: { row: ScoreRow }) {
  return (
    <tr className="border-b border-slate-100 bg-slate-50 last:border-b-0">
      <td colSpan={6} className="px-3 py-3">
        <FactorDetails row={row} />
      </td>
    </tr>
  );
}

export function PronosticTable({ classement }: PronosticTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const sorted = [...classement].sort((a, b) => a.rang - b.rang);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2">Rang</th>
            <th className="px-3 py-2">N°</th>
            <th className="px-3 py-2">Cheval</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Cote</th>
            <th className="px-3 py-2">Confiance</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => {
            const isExpanded = expandedId === row.partant_id;
            const scorePct = Math.round(row.score_total * 100);
            return (
              <Fragment key={row.partant_id}>
                <tr
                  onClick={() => setExpandedId(isExpanded ? null : row.partant_id)}
                  className={`cursor-pointer border-b border-slate-100 last:border-b-0 hover:bg-slate-100/60 ${
                    i % 2 === 1 ? "bg-slate-50/60" : ""
                  }`}
                >
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-900">{row.rang}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-600">
                    {row.numero_corde}
                  </td>
                  <td className="px-3 py-2 font-medium text-slate-900">
                    {row.nom_cheval}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      {isExpanded ? "▲" : "▼"} détail
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="w-10 font-mono tabular-nums text-slate-900">
                        {scorePct}%
                      </span>
                      <div className="h-1.5 w-24 rounded-full bg-green-100">
                        <div
                          className="h-1.5 rounded-full bg-green-600"
                          style={{ width: `${Math.min(100, Math.max(0, scorePct))}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-600">
                    {row.cote ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {typeof row.confiance === "number" ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className={`h-2 w-2 rounded-full ${
                            row.confiance >= 0.66 ? "bg-green-500" : row.confiance >= 0.33 ? "bg-amber-400" : "bg-red-400"
                          }`}
                        />
                        <span className="font-mono tabular-nums text-xs text-slate-500">
                          {row.nb_courses_historique ?? 0} c.
                        </span>
                      </span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                </tr>
                {isExpanded && <DetailRow row={row} />}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
