# Design — Plan E : version mobile (liste → détail + onglets, cartes)

Date : 2026-07-15
Statut : validé (brainstorming, avec maquettes ASCII), en attente de plan d'implémentation.

## Objectif

Rendre pronoturf **entièrement adapté et optimisé pour mobile**, sans dégrader le desktop.
Le dashboard 3 colonnes ne convient pas à un téléphone (aujourd'hui il s'empile : toute la
liste des courses, puis le pronostic, puis l'analyse — long scroll, tableaux qui débordent).
On introduit un **parcours mobile master-detail** (liste des courses → détail d'une course
avec onglets) et un **reflow des tableaux en cartes**. **Pur frontend, aucun changement
backend.**

## Décisions (validées au brainstorming)

1. **Bascule à `lg` (1024px)** : `≥ lg` = dashboard 3 colonnes **inchangé** ; `< lg` = expérience
   mobile. Même composant `Home`, même état/logique, deux rendus (`hidden lg:grid` /
   `lg:hidden`).
2. **Navigation mobile master-detail + onglets** : vue **Liste** ⇄ vue **Détail** (bouton
   Retour), le détail portant des onglets **Pronostic | Analyse IA**.
3. **Reflow complet des tableaux en cartes** sur mobile (partants ET pronostic) : pas de scroll
   horizontal, cibles tactiles, tap pour déplier les facteurs / éditer. Les tableaux desktop
   restent intacts.
4. Identité visuelle inchangée : blanc, vert `green-600` (soft `green-50`, hover `green-700`),
   texte `slate-900`/`slate-500`, `font-mono tabular-nums` pour les nombres, polices système.

## Architecture (frontend)

### A. Coquille responsive + état — `frontend/app/page.tsx`

- Ajouter deux états dans `Home` : `mobileView: "list" | "detail"` (défaut `"list"`) et
  `mobileTab: "prono" | "analyse"` (défaut `"prono"`).
- `selectCourse` : à la sélection, passer `mobileView = "detail"` et `mobileTab = "prono"` (sans
  effet sur desktop). Un handler `backToList()` remet `mobileView = "list"`.
- **En-tête** (`<header>`, partagé, responsive) : logo (compact `< lg`) + groupe droite. Le
  `DayNav` est **dans l'en-tête sur desktop uniquement** (`hidden lg:flex`) ; `PerfPanel`
  toujours visible. Sur mobile le `DayNav` vit dans la vue Liste.
- **Corps desktop** (`hidden lg:grid ...`) : le grid 3 colonnes **actuel**, déplacé tel quel
  sous ce wrapper (aucune modif de contenu).
- **Corps mobile** (`lg:hidden`) :
  - **Vue Liste** (`mobileView === "list"`) : barre `DayNav` (‹ date ›) + `CourseBrowser`
    (réutilisé). `onSelect` déclenche `selectCourse` (qui bascule en détail).
  - **Vue Détail** (`mobileView === "detail"`) : barre **‹ Retour** + titre course (R/C ·
    Quinté+ si `est_quinte` · discipline · distance) ; **onglets collants**
    `[ Pronostic | Analyse IA ]` ; contenu de l'onglet actif :
    - **Pronostic** : bouton « Calculer le pronostic » (réutilise `handleScore`), puis
      `<PronosticCards>` si `classement`, puis un sous-bloc « Partants » `<PartantsCards>`
      (secondaire).
    - **Analyse IA** : le composant `AnalyseIA` existant (déjà en cartes) avec
      Analyser/Ré-analyser.
  - États de chargement/erreur repris de l'existant (`loading`, `analyseLoading`, `error`).

> Le corps mobile réutilise `CourseBrowser` et `AnalyseIA` tels quels ; seules les vues
> tabulaires ont besoin de variantes cartes.

### B. Nouveaux composants cartes (mobile)

- `frontend/components/PronosticCards.tsx` — **même props que `PronosticTable`**
  (`{ classement: ScoreRow[] }`). Une carte par ligne triée par `rang` : n° rang + nom_cheval ;
  barre de score (score_total ×100, `green-600` sur `green-100`) ; cote + badge de confiance
  coloré (reprend le mapping niveau→couleur de `PronosticTable`) ; **tap → déplie les facteurs**
  (`details_facteurs` : libellé, `valeur×poids_effectif=contribution`, mini-barres +/-),
  réutilisant la même logique d'affichage que `PronosticTable` (pas de mutation de tableau,
  `role="button"`/`tabIndex`/`onKeyDown` pour l'accessibilité clavier).
- `frontend/components/PartantsCards.tsx` — **même props que `PartantsTable`**
  (`{ partants: Partant[]; onPartantSaved: () => void }`). Une carte par partant : n° corde +
  nom_cheval + jockey/entraîneur + cote + musique ; champs éditables ferrage/poids/RK au tap
  (réutilise `api.patchPartant` puis `onPartantSaved`, comme `PartantsTable`) ; marqueur non
  partant.
- Les composants desktop `PronosticTable`/`PartantsTable` restent **inchangés**. Le corps
  mobile monte les *Cards*, le corps desktop monte les *Table* (jamais les deux en même temps —
  séparation `lg:hidden` / `hidden lg:block` au niveau du corps).

### C. Ergonomie mobile

- Cibles tactiles ≥ 44px (lignes de course, onglets, boutons).
- Onglets et bouton d'action collants en haut du détail (`sticky top-…`).
- Aucun scroll horizontal (les cartes remplacent les tableaux).
- `PerfPanel` : le popover `w-72` peut déborder sur petit écran → largeur max responsive
  (`max-w-[calc(100vw-…)]`) ou ancrage plein-largeur ; le bouton « Perf » reste dans l'en-tête.
- Transitions douces existantes conservées.

### D. Verticalité `min-h`

- Corps desktop garde `lg:min-h-[calc(100vh-57px)]`. Corps mobile : hauteur naturelle
  (scroll vertical simple par vue).

## Ce que ce plan produit

Sur téléphone : une vue Liste (navigation jour + courses, Quinté+ en avant), un tap ouvre le
détail plein écran avec onglets Pronostic / Analyse IA, tout en **cartes tactiles** (aucun
tableau qui déborde), avec un bouton Retour. Sur desktop : le dashboard 3 colonnes **strictement
inchangé**. Aucune régression backend (frontend pur).

## Découpage prévisionnel (un seul plan, ~5-6 tâches)

1. `PronosticCards` (variante mobile du pronostic) — build gate.
2. `PartantsCards` (variante mobile des partants, édition inline) — build gate.
3. Coquille responsive `page.tsx` : en-tête responsive + corps desktop (`hidden lg:grid`) +
   corps mobile (liste/détail/onglets), état `mobileView`/`mobileTab` — build gate.
4. Ajustement `PerfPanel` pour petit écran — build gate.
5. Vérification (contrôleur) : build + **captures Playwright en viewport mobile** si l'outil
   répond, sinon contrôle visuel utilisateur + contrat HTTP inchangé.

## Vérification

- **Gate** : `cd frontend && npm run build` (pas de suite unitaire front).
- **Rendu mobile** : tenter des captures Playwright (MCP) en viewport mobile (ex. 390×844) sur
  la vue Liste puis Détail (les 2 onglets) — vérifier l'absence de débordement horizontal, la
  bascule liste↔détail, les cartes. La mémoire [frontend-e2e-verification] indiquait « pas
  d'outil navigateur » ; **à re-vérifier en exécution** (les outils Playwright MCP semblent
  désormais listés). Repli : build vert + contrôle visuel par l'utilisateur (devtools/phone) +
  confirmation que le contrat HTTP est inchangé (aucune modif backend).
- **Non-régression desktop** : le grid `≥ lg` est déplacé sans changement de contenu ; vérifier
  qu'il rend à l'identique (`hidden lg:grid`).

## Hors périmètre (Plan E)

- Refonte visuelle / nouveau design system (on garde blanc/vert existant).
- PWA / installable / offline.
- Gestes avancés (swipe entre onglets, pull-to-refresh).
- Toute modification backend.

## Prérequis & risques

- **Duplication maîtrisée** : deux rendus (mobile/desktop) partagent l'état de `Home` et les
  composants lourds (`CourseBrowser`, `AnalyseIA`) ; seules les vues tabulaires ont une variante
  cartes. `page.tsx` grossit — acceptable ; extraire des sous-composants si un fichier devient
  trop gros.
- **Parité d'interaction** : `PronosticCards`/`PartantsCards` doivent reproduire fidèlement le
  dépli des facteurs et l'édition inline des tableaux desktop (mêmes appels API, même logique),
  sans régresser le comportement.
- **Vérif navigateur** possiblement indisponible (cf. §Vérification) — repli documenté.
