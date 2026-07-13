"use client";

import { Fragment, useState } from "react";
import type { ScoreRow } from "@/lib/types";

type PronosticTableProps = {
  classement: ScoreRow[];
};

const FACTOR_LABELS: Record<string, string> = {
  forme: "Forme",
  taux_reussite: "Taux de réussite",
  ferrage_poids: "Ferrage/Poids",
  cote: "Cote",
  corde: "Corde",
};

function factorLabel(key: string): string {
  return FACTOR_LABELS[key] ?? key;
}

function FactorBar({ contribution, max }: { contribution: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (Math.abs(contribution) / max) * 100)) : 0;
  return (
    <div className="h-1.5 w-full rounded-full bg-slate-800">
      <div
        className={`h-1.5 rounded-full ${contribution >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function DetailRow({ row }: { row: ScoreRow }) {
  const entries = Object.entries(row.details_facteurs);
  const maxContribution = Math.max(0, ...entries.map(([, d]) => Math.abs(d.contribution)));

  return (
    <tr className="border-b border-slate-800/60 bg-slate-900/40 last:border-b-0">
      <td colSpan={5} className="px-3 py-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map(([key, detail]) => (
            <div key={key} className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
              <div className="mb-1.5 flex items-center justify-between gap-2 text-xs">
                <span className="font-medium text-slate-300">{factorLabel(key)}</span>
                <span className="font-mono tabular-nums text-slate-400">
                  {detail.valeur.toFixed(2)} × {detail.poids_effectif.toFixed(2)} ={" "}
                  {detail.contribution.toFixed(2)}
                </span>
              </div>
              <FactorBar contribution={detail.contribution} max={maxContribution} />
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}

export function PronosticTable({ classement }: PronosticTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const sorted = [...classement].sort((a, b) => a.rang - b.rang);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
            <th className="px-3 py-2">Rang</th>
            <th className="px-3 py-2">N°</th>
            <th className="px-3 py-2">Cheval</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Cote</th>
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
                  className={`cursor-pointer border-b border-slate-800/60 last:border-b-0 hover:bg-slate-800/40 ${
                    i % 2 === 1 ? "bg-slate-900/30" : ""
                  }`}
                >
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-100">{row.rang}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                    {row.numero_corde}
                  </td>
                  <td className="px-3 py-2 font-medium text-slate-100">
                    {row.nom_cheval}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      {isExpanded ? "▲" : "▼"} détail
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="w-10 font-mono tabular-nums text-slate-100">
                        {scorePct}%
                      </span>
                      <div className="h-1.5 w-24 rounded-full bg-slate-800">
                        <div
                          className="h-1.5 rounded-full bg-emerald-500"
                          style={{ width: `${Math.min(100, Math.max(0, scorePct))}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                    {row.cote ?? "—"}
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
