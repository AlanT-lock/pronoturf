"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Partant } from "@/lib/types";

type PartantsTableProps = {
  partants: Partant[];
  onPartantSaved: () => void;
};

function formeSuffixe(courses: number | null, victoires: number | null, places: number | null) {
  if (courses === null && victoires === null && places === null) return "—";
  return `${courses ?? 0}c ${victoires ?? 0}v ${places ?? 0}p`;
}

function FerrageCell({ partant, onSaved }: { partant: Partant; onSaved: () => void }) {
  const [value, setValue] = useState(partant.ferrage ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (value === (partant.ferrage ?? "")) return;
    setSaving(true);
    setError(null);
    try {
      await api.patchPartant(partant.partant_id, { ferrage: value });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-0.5">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        disabled={saving}
        placeholder="—"
        className="w-20 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100 outline-none focus:border-emerald-500 disabled:opacity-50"
      />
      {error && <span className="text-[10px] text-red-400">{error}</span>}
    </div>
  );
}

export function PartantsTable({ partants, onPartantSaved }: PartantsTableProps) {
  const showPoids = partants.some((p) => p.poids_kg !== null);
  const showReduction = partants.some((p) => p.reduction_kilometrique !== null);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
            <th className="px-3 py-2">N°</th>
            <th className="px-3 py-2">Cheval</th>
            <th className="px-3 py-2">Jockey</th>
            <th className="px-3 py-2">Entraîneur</th>
            <th className="px-3 py-2">Sexe/Âge</th>
            <th className="px-3 py-2">Musique</th>
            <th className="px-3 py-2">Forme</th>
            {showPoids && <th className="px-3 py-2">Poids</th>}
            {showReduction && <th className="px-3 py-2">Réd. km</th>}
            <th className="px-3 py-2">Ferrage</th>
            <th className="px-3 py-2">Cote</th>
          </tr>
        </thead>
        <tbody>
          {partants.map((p, i) => {
            const nonPartant = p.statut === "non_partant";
            return (
              <tr
                key={p.partant_id}
                className={`border-b border-slate-800/60 last:border-b-0 ${
                  i % 2 === 1 ? "bg-slate-900/30" : ""
                } ${nonPartant ? "opacity-50" : ""}`}
              >
                <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                  {p.numero_corde}
                </td>
                <td className="px-3 py-2 font-medium text-slate-100">
                  {p.nom_cheval}
                  {nonPartant && (
                    <span className="ml-2 text-xs font-normal text-red-400">non partant</span>
                  )}
                </td>
                <td className="px-3 py-2 text-slate-300">{p.jockey_nom ?? "—"}</td>
                <td className="px-3 py-2 text-slate-300">{p.entraineur_nom ?? "—"}</td>
                <td className="px-3 py-2 text-slate-300">
                  {p.sexe ?? "—"}
                  {p.age !== null ? `/${p.age}` : ""}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-300">{p.musique ?? "—"}</td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs text-slate-300">
                  {formeSuffixe(p.nombre_courses, p.nombre_victoires, p.nombre_places)}
                </td>
                {showPoids && (
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                    {p.poids_kg !== null ? `${p.poids_kg} kg` : "—"}
                  </td>
                )}
                {showReduction && (
                  <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                    {p.reduction_kilometrique !== null ? p.reduction_kilometrique : "—"}
                  </td>
                )}
                <td className="px-3 py-2">
                  <FerrageCell partant={p} onSaved={onPartantSaved} />
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-slate-300">
                  {p.cote_retenue !== null ? p.cote_retenue : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
