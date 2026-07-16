# Plan F (taux_discipline via musique) — review backlog

Branche : `feat/plan-f-musique-discipline` (base `74a00d2`, 2 commits).
Final review : sonnet — « Ready to merge: Yes », zéro Critical/Important. Regex vérifiée adversarialement (spans identiques ancien/nouveau, pas de token fantôme autour des `(25)`). E2E live : 14/14 chevaux portent le facteur, JAINA = 0.556 == 5/9 calculé à la main.

## Minor — DEFER

1. `parse_musique_disciplines` duplique la logique de parsing de `parse_musique` (même `re.sub`, même logique place/DNF) — choix délibéré du plan (« parse_musique inchangé, risque minimal »). Cleanup futur : faire déléguer `parse_musique` à `parse_musique_disciplines` (`return [p for p, _ in ...]`) pour rendre l'invariant structurel.

## Notes

- `context_stats.taux_discipline` volontairement conservé (plus appelé par le scoring) — resservira si `chevaux_performances` s'enrichit via Aspiturf.
