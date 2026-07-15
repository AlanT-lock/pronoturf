# Plan E (version mobile) — review backlog

Plan : `docs/superpowers/plans/2026-07-15-pronoturf-plan-e-mobile.md`
Branche : `feat/plan-e-mobile` (base `921c256`). Pur frontend, aucune modif backend.
Final review : Opus, `921c256..048d474` (6 commits) — verdict « Ready to merge: YES », zéro Critical, zéro Important.

## Vérifié en profondeur (RAS)

- **Non-régression desktop** : le corps `hidden lg:grid` rend un contenu identique (seules des classes de bordure déjà neutralisées à `lg` ont été simplifiées) — course header + `PartantsTable` + `PronosticTable` + `AnalyseIA`. Un seul `DayNav` à chaque breakpoint (header `hidden lg:block` / liste mobile `lg:hidden`).
- **Extraction `factors.tsx`** fidèle : `factorLabel`/`FactorBar`/`FactorDetails` identiques aux originaux ; `PronosticTable.DetailRow` enveloppe `<FactorDetails>` dans le même `<tr><td colSpan=6>` ; pas de code mort / pas d'import inutilisé.
- **Cartes** : `PronosticCards` copie avant tri, barre de score/cote/confiance/dépli fidèles, en-tête `<button>` (accessible clavier) ; `PartantsCards` reproduit le save-on-blur du ferrage (`api.patchPartant`→`onSaved`) + marqueur non-partant, reste en display-only ; aucune mutation des props.
- **État mobile** (`mobileView`/`mobileTab`) inerte sur desktop (corps CSS-caché) ; spinner de chargement au tap ; titre gardé sur `course`.

## Vérification E2E LIVE (Task 6 — Playwright)

Réels serveurs + Playwright MCP. Mobile 390×844 : liste (header, DayNav, 10 réunions, R1C8 QUINTÉ+, pas de grille desktop) → tap C8 → détail immédiat + spinner → chargé : ‹ Retour + « Course 8 · Quinté+ · trot_attele · 2675 m » + onglets ; **Pronostic** = 14 cartes pronostic + 14 cartes partants (ferrage éditable) ; **Analyse IA** = composant AnalyseIA (analyse enregistrée + 8 cartes de paris) ; ‹ Retour → liste. Desktop 1280×900 : tagline visible, DayNav dans l'en-tête, grille 3 colonnes avec **tableaux** + colonne Analyse IA, état persistant. Aucun débordement horizontal. (`browser_take_screenshot` timeout 5s → vérif via `browser_snapshot`.)

## Minor — CORRIGÉ

- Popover **Perf** (`z-10`) pouvait être partiellement recouvert par le sous-en-tête collant du détail mobile (`sticky top-0 z-10`) quand Perf est ouvert en vue détail. **Fix** : popover passé à `z-20`.

## Notes (pas des défauts)

- Onglet « Pronostic » mobile ordonne Pronostic puis Partants (inverse du desktop) — choix de priorité mobile assumé.
- Affichage poids/rk par carte (`!== null` par ligne) vs colonnes all-or-nothing du tableau — adapté aux cartes, display-only.

## Hors périmètre (rappel)

Refonte design system, PWA/offline, gestes (swipe, pull-to-refresh), toute modif backend.
