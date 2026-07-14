"use client";

import { labelFr } from "@/lib/dates";

type Props = { date: Date; onPrev: () => void; onNext: () => void };

export function DayNav({ date, onPrev, onNext }: Props) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onPrev}
        aria-label="Jour précédent"
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-green-600 hover:text-green-700"
      >
        ‹
      </button>
      <span className="rounded-full border border-green-200 bg-green-50 px-3 py-1.5 text-sm font-bold text-green-700">
        {labelFr(date)}
      </span>
      <button
        type="button"
        onClick={onNext}
        aria-label="Jour suivant"
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-green-600 hover:text-green-700"
      >
        ›
      </button>
    </div>
  );
}
