"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Partant } from "@/lib/types";

function formeSuffixe(courses: number | null, victoires: number | null, places: number | null) {
  if (courses === null && victoires === null && places === null) return "—";
  return `${courses ?? 0}c ${victoires ?? 0}v ${places ?? 0}p`;
}

function FerrageField({ partant, onSaved }: { partant: Partant; onSaved: () => void }) {
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
        placeholder="ferrage —"
        className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 outline-none focus:border-green-600 disabled:opacity-50"
      />
      {error && <span className="text-[10px] text-red-400">{error}</span>}
    </div>
  );
}

export function PartantsCards({
  partants,
  onPartantSaved,
}: {
  partants: Partant[];
  onPartantSaved: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      {partants.map((p) => {
        const nonPartant = p.statut === "non_partant";
        return (
          <div
            key={p.partant_id}
            className={`rounded-xl border border-slate-200 bg-white p-3 ${nonPartant ? "opacity-50" : ""}`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-bold text-slate-900">
                <span className="font-mono tabular-nums text-slate-400">n°{p.numero_corde}</span>{" "}
                {p.nom_cheval}
                {nonPartant && (
                  <span className="ml-2 text-xs font-normal text-red-500">non partant</span>
                )}
              </span>
              <span className="font-mono tabular-nums text-xs text-slate-600">
                cote {p.cote_retenue ?? "—"}
              </span>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-slate-500">
              <span className="truncate">J. {p.jockey_nom ?? "—"}</span>
              <span className="truncate">E. {p.entraineur_nom ?? "—"}</span>
              <span>
                {p.sexe ?? "—"}
                {p.age !== null ? `/${p.age}` : ""}
              </span>
              <span className="font-mono tabular-nums">
                {formeSuffixe(p.nombre_courses, p.nombre_victoires, p.nombre_places)}
              </span>
              {p.musique && <span className="col-span-2 font-mono text-slate-600">{p.musique}</span>}
              {p.poids_kg !== null && (
                <span className="font-mono tabular-nums">{p.poids_kg} kg</span>
              )}
              {p.reduction_kilometrique !== null && (
                <span className="font-mono tabular-nums">rk {p.reduction_kilometrique}</span>
              )}
            </div>
            <div className="mt-2">
              <FerrageField partant={p} onSaved={onPartantSaved} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
