# Design — Plan F : facteur `taux_discipline` depuis la musique (quick-win historique)

Date : 2026-07-15
Statut : validé (brainstorming), en attente de plan.
Réf. : investigation des sources d'historique (cette session) ; [[pmu-history-limitation]] ; `docs/superpowers/specs/2026-07-14-aspiturf-feasibility.md`.

## Objectif

Débloquer **1 des 4 facteurs contextuels** du scoring — `taux_discipline` — sans source
externe, en l'alimentant depuis la **musique** (profonde : ~10-15 courses passées) au lieu de
`chevaux_performances` (superficielle : ~1 course via PMU `performances-detaillees`, confirmé
en direct). La musique encode, par course passée, la **place** ET la **discipline** ; on
n'exploitait que la place (facteur « forme »). Les 3 autres facteurs contextuels
(distance/hippodrome/niveau) exigent une source structurée profonde et restent en attente
d'Aspiturf.

## Contexte technique (vérifié)

- `app/scoring/musique.py` : `_PERF_RE = r"([0-9DTARdtar])[a-zA-Z]"` capture le **résultat**
  (place ou DNF) et matche — **sans la capturer** — la **lettre de discipline**. `parse_musique`
  renvoie une liste de places ; `forme_score` s'en sert.
- `app/scoring/context_stats.py` : `taux_discipline(perfs, discipline)` = taux de top-3 sur les
  `perfs` de la discipline, `None` si `< MIN_SAMPLE` (3). `SUCCESS_MAX_PLACE = 3`.
- `app/scoring/factors.py` : `compute_factors(...)` fait `tdi = cs.taux_discipline(perfs, discipline)`
  puis `f["taux_discipline"] = tdi` seulement si `tdi is not None` (déjà omis → redistribué quand
  pas de données, cf. correction de dilution du Plan 3).
- Disciplines de scoring (via `_DISCIPLINE_MAP`) : `plat`, `trot_attele`, `trot_monte`, `obstacle`.

## Architecture

### A. Parser musique étendu — `app/scoring/musique.py`

- Capturer la lettre de discipline : `_PERF_RE = r"([0-9DTARdtar])([a-zA-Z])"`.
- Mapping lettre → enum : `a`→`trot_attele`, `m`→`trot_monte`, `p`→`plat`,
  `h`/`s`/`c`/`o`→`obstacle` (haies/steeple/cross/obstacle), toute autre lettre → `None`
  (course exclue du calcul par discipline). Lettre lue en minuscule.
- Nouvelle fonction `parse_musique_disciplines(musique) -> list[tuple[int | None, str | None]]` :
  `(place, discipline_enum)` par course (place `int` 1-9, `None` pour `0`/D/T/A/R ; discipline
  `None` si lettre inconnue). `parse_musique` (places seules) et `forme_score` **inchangés**.
- `taux_discipline_musique(musique, discipline) -> float | None` : sur les courses de la
  musique dont la discipline == `discipline`, taux = (nb place ≤ `SUCCESS_MAX_PLACE`) / (nb
  courses de cette discipline) ; `None` si `< MIN_SAMPLE`. DNF (place `None`) compte au
  dénominateur, pas au numérateur — **mêmes règles** que `context_stats` (réutiliser
  `SUCCESS_MAX_PLACE`/`MIN_SAMPLE` importés de `context_stats`). Taux **simple** (pas de
  pondération par récence).

### B. Re-branchement du facteur — `app/scoring/factors.py`

- Remplacer `tdi = cs.taux_discipline(perfs, discipline)` par
  `tdi = musique.taux_discipline_musique(<musique du partant>, discipline)`.
- La musique du partant est déjà dans le dict de partant (`p["musique"]`, utilisée pour la
  forme). Le reste de `compute_factors` (omission si `None` → redistribution) est **inchangé**.
- `context_stats.taux_discipline` n'est plus appelé par le scoring (laissé en place, il peut
  redevenir utile si `chevaux_performances` s'enrichit un jour via Aspiturf).

## Décisions clés (validées)

1. **Remplacer** la source de `taux_discipline` (chevaux_performances → musique). Strictement
   meilleur (musique ~10-15 vs ~1) ; garder un fallback serait équivalent en pratique mais plus
   complexe.
2. **Mapping** : a/m/p→trot_attele/trot_monte/plat ; h/s/c/o→obstacle ; autre→ignoré.
3. **Seuils inchangés** (top-3 = succès, min 3 courses dans la discipline), taux simple.
4. **Pur backend, aucune migration.** `parse_musique`/`forme_score` inchangés.

## Découpage prévisionnel (~3 tâches TDD)

1. Étendre `musique.py` (`parse_musique_disciplines` + `taux_discipline_musique`) — pur, TDD.
2. Re-brancher `factors.py` sur `taux_discipline_musique` + non-régression (`test_factors*`, `test_scoring_*`).
3. Vérification E2E (contrôleur) : sur une course réelle, `POST /score` → `taux_discipline`
   présent et non-neutre pour les chevaux à musique fournie (ex. R1C8, chevaux trot avec ~9
   courses attelé), redistribution des poids correcte, valeurs ∈ [0,1].

## Hors périmètre

- Facteurs `taux_distance` / `taux_hippodrome` / `taux_niveau` (nécessitent une source
  structurée profonde → Aspiturf, incrément futur).
- Pondération par récence du taux discipline (possible plus tard).
- Toute source externe / migration.
