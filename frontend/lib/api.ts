import type { AnalyseIA, Backtest, Course, Partant, Programme, ScoreRow } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(
      `Backend injoignable sur ${BASE}. Lance le backend : uvicorn app.main:app --port 8000`,
    );
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  importCourse: (date: string, numero_reunion: number, numero_course: number) =>
    req<{ course_id: string; partant_ids: string[] }>("/courses/import", {
      method: "POST",
      body: JSON.stringify({ date, numero_reunion, numero_course }),
    }),
  getCourse: (id: string) => req<{ course: Course; partants: Partant[] }>(`/courses/${id}`),
  patchCourse: (id: string, body: { etat_terrain?: string }) =>
    req<unknown>(`/courses/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  patchPartant: (
    id: string,
    body: { ferrage?: string; poids_kg?: number; reduction_kilometrique?: number },
  ) => req<unknown>(`/partants/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  scoreCourse: (id: string) =>
    req<{ course_id: string; classement: ScoreRow[] }>(`/courses/${id}/score`, { method: "POST" }),
  getPronostic: (id: string) =>
    req<{ course_id: string; classement: ScoreRow[] }>(`/courses/${id}/pronostic`),
  getProgramme: (date: string) => req<Programme>(`/programme/${date}`),
  getAnalyse: (id: string) => req<AnalyseIA>(`/courses/${id}/analyse`),
  analyseCourse: (id: string, paris: string[], force = false) =>
    req<AnalyseIA>(`/courses/${id}/analyse?force=${force}`, {
      method: "POST",
      body: JSON.stringify({ paris }),
    }),
  getBacktest: () => req<Backtest>("/backtest"),
  captureResultats: (id: string) =>
    req<{ course_id: string; captured: boolean; statut: string; nb_resultats: number }>(
      `/courses/${id}/resultats`,
      { method: "POST" },
    ),
};
