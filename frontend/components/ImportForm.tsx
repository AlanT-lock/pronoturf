"use client";

import { useState } from "react";
import { api } from "@/lib/api";

function todayAsDdmmyyyy(): string {
  const now = new Date();
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const yyyy = now.getFullYear();
  return `${dd}${mm}${yyyy}`;
}

type ImportFormProps = {
  onImported: (courseId: string) => void;
};

export function ImportForm({ onImported }: ImportFormProps) {
  const [date, setDate] = useState(todayAsDdmmyyyy());
  const [numeroReunion, setNumeroReunion] = useState("1");
  const [numeroCourse, setNumeroCourse] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const reunion = Number(numeroReunion);
      const course = Number(numeroCourse);
      const { course_id } = await api.importCourse(date, reunion, course);
      onImported(course_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue lors de l'import.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Importer une course
      </h2>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-400">Date (JJMMAAAA)</span>
          <input
            type="text"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            placeholder="12072026"
            pattern="\d{8}"
            required
            className="w-32 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm tabular-nums text-slate-100 outline-none focus:border-emerald-500"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-400">Réunion</span>
          <input
            type="number"
            min={1}
            value={numeroReunion}
            onChange={(e) => setNumeroReunion(e.target.value)}
            required
            className="w-20 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm tabular-nums text-slate-100 outline-none focus:border-emerald-500"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-400">Course</span>
          <input
            type="number"
            min={1}
            value={numeroCourse}
            onChange={(e) => setNumeroCourse(e.target.value)}
            required
            className="w-20 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm tabular-nums text-slate-100 outline-none focus:border-emerald-500"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Import en cours…" : "Importer"}
        </button>
      </form>
      {error && (
        <p className="mt-3 rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}
