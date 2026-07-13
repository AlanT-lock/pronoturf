# Plan 3 — review backlog (algorithme enrichi)

Final whole-branch review (Opus, `5a7b55d..e4f6171`, 12 commits) verdict:
**Ready to merge: With fixes (none blocking)**, zero Critical. Full backend
suite 80/80, frontend build clean, real-HTTP E2E passed. Items below, by priority.

## Design issue — the one worth a real decision

**Neutral context factors DILUTE the score instead of redistributing (contradicts spec intent).**
- The spec (§B1) promised: "un cheval sans historique voit le poids de ses facteurs
  contextuels redistribué sur ses facteurs connus (pas de dilution injuste)."
- Reality: `engine.py` redistribution keys on `poids > 0` (zero-WEIGHT factors), not on
  per-horse data availability. All 11 factors have weight > 0, so redistribution never
  fires. A context factor with insufficient history returns the neutral VALUE 0.5 and is
  counted at full effective weight.
- Consequence: with PMU returning ~1 past race per horse (< MIN_SAMPLE=3), the 4
  per-context factors are neutral 0.5 for nearly every horse → ~34% of every score is a
  constant 0.5 block. This compresses the score spread toward 0.5 and adds no ranking
  discrimination; the ranking is still driven by the 5 original factors, but diluted.
- **Fix (to honor the spec):** have context/jockey/entraineur factors signal "no data"
  (return `None` up to the engine) and make the engine redistribute the weight of
  no-data factors PER HORSE over that horse's factors-with-data. ~1-2 tasks. This turns
  the enrichment from "dilutes toward 0.5" into "gracefully leans on whatever data exists."
- Status: **DECISION PENDING** (fix now vs defer to Plan 4 tuning).

## Verified-safe latent risks

**Jockey name-source consistency (Important in review → verified safe here).**
- `jockey_taux` filters `chevaux_performances.jockey_nom` (from PMU `nomJockey`), while the
  score-time jockey name comes from `intervenants.nom` (from PMU `driver`). A formatting
  mismatch would silently zero the jockey factor + penalize confidence.
- **Verified on real data (R3C1 trot, 8/8 + R1C1 plat): `driver` == `nomJockey` exactly.**
  So no active bug in this dataset. Latent risk if PMU formatting ever diverges — cheap
  monitor: log when a scored jockey has 0 matching performance rows.

## Minor / cosmetic (defer)

1. **N+1 at score time** — `_partant_dict_for_scoring` does per-partant: 2 intervenant
   lookups + 2 filtered scans (jockey/entraineur taux); `get_course` also per-partant
   intervenant lookups. Indexed, fine for personal scale; batch if latency grows.
2. **`status_arrivee=None` hardcoded** in `save_entraineur_resultats` — column always NULL
   (dead field). Drop from payload or populate from `partant.statut`.
3. **Obstacle discipline matching** — `normalize_performances` maps HAIES/STEEPLE/CROSS to
   lowercased raw (`"haies"`), never equals today's `"obstacle"` → `taux_discipline` stays
   neutral for obstacle horses. Fix the mapping when a real obstacle race is available.
4. **`taux_niveau` allocation basis** — today's allocation is `montantPrix`, history uses
   the `allocation` field. Verified same value (20100) on the plat probe; worth a wider
   sanity check across disciplines.
5. **Plan-doc drift** — the plan's Task-1 SQL block wasn't updated with the two
   `scores_pronostic` columns that Task 9b's migration correctly adds. Doc only.

## Data reality (not a defect — for product expectations / Plan 4)

PMU `performances-detaillees` returns ~1 past race per horse in this dataset. Ramp:
global jockey/entraineur stats accumulate across imports and cross MIN_SAMPLE first;
per-horse context factors improve only as the same horse is imported across many dates,
or via a richer history source (Geny — future ingestion plan). The confidence index
correctly surfaces this thinness to the user.
