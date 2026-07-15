"use client";

import type { AnalyseIA as Analyse, Recommandation } from "@/lib/types";
import { libellePari } from "@/lib/paris";

type Props = {
  analyse: Analyse | null;
  loading: boolean;
  onAnalyser: () => void;
  onReanalyser: () => void;
  disabled: boolean;
};

function niveauClasse(niveau: string): string {
  if (niveau === "eleve") return "bg-green-500";
  if (niveau === "moyen") return "bg-amber-400";
  return "bg-red-400";
}

function Puce({ n, base }: { n: number; base: boolean }) {
  return (
    <span
      className={`inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-xs font-bold tabular-nums ${
        base
          ? "bg-green-600 text-white"
          : "border border-dashed border-green-500 text-green-700"
      }`}
    >
      {n}
    </span>
  );
}

function Carte({ reco }: { reco: Recommandation }) {
  const combine = reco.base.length > 0 || reco.tournant.length > 0;
  const puces = combine
    ? [...reco.base.map((n) => ({ n, base: true })), ...reco.tournant.map((n) => ({ n, base: false }))]
    : reco.selection.map((n) => ({ n, base: true }));
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-extrabold text-slate-900">{libellePari(reco.type_pari)}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-500">
          {reco.niveau}
        </span>
      </div>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {puces.map((p, i) => (
          <Puce key={i} n={p.n} base={p.base} />
        ))}
      </div>
      <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-green-100">
        <div className={`h-full ${niveauClasse(reco.niveau)}`} style={{ width: `${reco.confiance}%` }} />
      </div>
      <p className="text-xs leading-relaxed text-slate-600">{reco.avis}</p>
    </div>
  );
}

export function AnalyseIA({ analyse, loading, onAnalyser, onReanalyser, disabled }: Props) {
  if (loading) {
    return <p className="text-sm text-slate-400">Analyse en cours…</p>;
  }

  if (!analyse) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-4">
        <p className="mb-3 text-sm text-slate-400">Pas encore d'analyse pour cette course.</p>
        <button
          type="button"
          onClick={onAnalyser}
          disabled={disabled}
          className="rounded-full bg-green-600 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
        >
          Analyser cette course
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
            analyse.source === "llm" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {analyse.source === "llm" ? "analyse enregistrée" : "analyse par règles"}
        </span>
        <button
          type="button"
          onClick={onReanalyser}
          disabled={disabled}
          className="text-[11px] font-bold text-slate-500 transition-colors hover:text-green-700 disabled:opacity-50"
        >
          Ré-analyser
        </button>
      </div>

      {analyse.lecture_globale && (
        <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
          {analyse.lecture_globale}
        </p>
      )}

      {analyse.coup_de_coeur_value && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-xs text-green-800">
          <span className="font-extrabold">Value · n°{analyse.coup_de_coeur_value.numero_corde}</span>{" "}
          {analyse.coup_de_coeur_value.raison}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {analyse.recommandations.map((reco) => (
          <Carte key={reco.type_pari} reco={reco} />
        ))}
      </div>
    </div>
  );
}
