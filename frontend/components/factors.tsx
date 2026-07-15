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
