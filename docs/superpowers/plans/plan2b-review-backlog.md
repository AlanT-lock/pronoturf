# Plan 2b — review backlog (deferred, non-blocking)

Final whole-branch review (Opus, `6b906c7..1042735`) verdict: **Ready to merge: Yes**,
zero Critical, zero Important blocking. Items below were triaged **defer** — none
block the merge. Ordered roughly by value.

## Worth doing before this UI grows

1. **Backend: `GET /courses/:id` omits `sexe`** (real contract miss, graceful today)
   - Plan 2b L62 lists `sexe` in the course contract; frontend `Partant` type declares
     `sexe: string | null`, so the "Sexe/Âge" column renders `—/age` (age shows, sexe never does).
   - Root cause: `sexe` lives on the `chevaux` table (migration 0001, L35); `age` is on
     `partants` and flows through `select("*")`. The chevaux enrichment select pulls only the name.
   - Fix: add `sexe` to the `chevaux` select in `_cheval_nom_par_partant` and thread it into
     `get_course` enrichment. ~small backend change; then re-verify the column renders.

2. **Keyboard a11y on the pronostic row expand** (`PronosticTable.tsx`)
   - Row expand/collapse is `onClick` on a `<tr>` with no `role="button"` / `tabIndex` /
     `onKeyDown` → not keyboard-accessible. Consistent with the codebase's current a11y bar;
     worth a pass before the UI grows.

## Minor / cosmetic (optional)

3. **`get_course` still N+1 on cotes** (`backend/app/scoring/routes.py` ~L198-208)
   - Loops `_retained_cote(client, partant["id"])` per partant though the batch helper
     `_retained_cotes_par_partant` now exists two functions away. One-line consistency win
     (N cote queries → 1). N+1 is explicitly plan-backlog, so optional.

4. **`getPronostic` catch swallows all failures** (`frontend/app/page.tsx` `loadCourse`)
   - Best-effort resume of a prior ranking swallows any non-2xx (not just 404). The primary
     action (`handleScore`) surfaces errors via `scoreError`, so a real fault is never hidden
     from the user's actual action. Could distinguish "not found" from a genuine backend error.

5. **`/score` vs `/pronostic` top-level `cote` shape asymmetry**
   - `POST /score` rows omit top-level `cote`; `GET /pronostic` rows include `cote: null`.
     `ScoreRow.cote?` is optional so both render identically. Optionally add `"cote": None`
     to the `/score` enrichment for symmetry.

6. **Progress-bar markup duplicated** (`PronosticTable.tsx`, `FactorBar` vs inline score bar)
   - ~6 lines, two visually distinct bars (signed red/green vs clamped positive). Low-value DRY.

7. **Stale-ranking cue after inline edit** (`frontend/app/page.tsx`)
   - Editing a ferrage after scoring reloads the persisted classement (last `/score`); the new
     edit isn't reflected until re-scoring, with no "recompute to reflect changes" hint. Cosmetic.

8. **Shared `error` state for course-load and terrain-save** (`frontend/app/page.tsx`)
   - A terrain-save failure renders in the top banner, far from the terrain input. Works, slightly
     disorienting. Could give terrain-save its own error slot.
