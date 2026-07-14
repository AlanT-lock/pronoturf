# Design — Plateforme pronoturf : découverte des courses, paris + analyse IA, refonte UI

Date : 2026-07-14
Statut : validé (brainstorming, avec maquettes visuelles), en attente de plan(s) d'implémentation.

## Objectif

Transformer pronoturf d'un import mono-course en une **vraie plateforme** de pronostic
hippique, agréable et moderne :

1. **Découverte des courses** : parcourir toutes les courses du jour (navigation
   jour par jour), voir les types de paris disponibles par course, et mettre le
   **Quinté+** en avant.
2. **Analyse IA par pari** : pour une course, produire des recommandations de paris
   (Simple G/P, Couplé G/P, 2sur4, Trio, Tiercé, Quarté+, Quinté+) avec une
   **confiance** et un **avis rédigé** par pari, via un LLM (Claude **Opus 4.8**)
   ancré sur notre scoring déterministe.
3. **Persistance + collecte de DATA** : chaque analyse est **stockée** (entrée +
   sortie) — pour la retrouver sans re-payer, et pour constituer un jeu de données
   qui améliorera les futures analyses (calibration, backtest).
4. **Refonte front** : plateforme **multi-colonnes** (dashboard 3 colonnes),
   **fond blanc** + **vert émeraude `#16A34A`** en secondaire, moderne et simple.

## Constat de faisabilité (données PMU) — vérifié

Endpoint `GET /programme/{date}` (déjà utilisé pour l'import) fournit **tout** le
nécessaire, sans import lourd :

- Toutes les **réunions → courses** du jour : `numOrdre`, `hippodrome.libelleCourt`,
  `specialite`/`discipline`, `heureDepart`, `montantPrix`, `nombreDeclaresPartants`,
  statut (`arriveeDefinitive`).
- **Types de paris par course** : tableau `paris`, chaque entrée a un `typePari`.
  Vocabulaire observé (hors préfixe `E_` = versions en ligne) : `SIMPLE_GAGNANT`,
  `SIMPLE_PLACE`, `COUPLE_GAGNANT`, `COUPLE_PLACE`, `COUPLE_ORDRE`,
  `DEUX_SUR_QUATRE`, `TRIO`, `TRIO_ORDRE`, `TIERCE`, `QUARTE_PLUS`, `QUINTE_PLUS`,
  `MULTI`, `MINI_MULTI`, `SUPER_QUATRE`, `PICK5`, `REPORT_PLUS`.
- **Quinté+ du jour** = la course dont les `paris` contiennent `QUINTE_PLUS`
  (vérifié : 14/07 → R1C3 ParisLongchamp). Pas de flag de course dédié ; on le dérive
  du tableau `paris`.

## Architecture des données

### A. Découverte (léger, sans écriture)

Nouvel endpoint backend `GET /programme/{date}` (date `JJMMAAAA`) qui **normalise et
renvoie** le programme du jour, sans rien importer en base :

```
{ "date": "...", "reunions": [
    { "numero_reunion", "hippodrome", "pays",
      "courses": [
        { "numero_course", "discipline", "distance_m", "heure_depart",
          "statut", "nombre_partants", "allocation",
          "paris": ["SIMPLE_GAGNANT","COUPLE_PLACE",...],  // mappés/dédupliqués
          "est_quinte": true|false }
      ] } ] }
```

- **Navigation par jour** = appeler cet endpoint avec une autre date (le frontend gère
  précédent/suivant + date courante).
- Ne touche pas la DB : c'est un proxy normalisé du programme PMU.

### B. Mapping des paris

Module `bet_types` (backend) : codes PMU `typePari` → identifiants internes + libellés
FR lisibles, en dédupliquant les variantes `E_` (online) avec leur base. Marque le
sous-ensemble « analysable par l'IA » (voir décisions). `est_quinte` dérivé de la
présence de `QUINTE_PLUS`.

### C. Ouverture d'une course

À l'ouverture d'une course dans l'UI, on déclenche l'**import existant** (programme +
participants + performances-detaillees → `courses`/`partants`/`chevaux`/`cotes`/
`chevaux_performances`) puis le **scoring enrichi** (11 facteurs, confiance) déjà en
place. C'est la base sur laquelle l'IA s'appuie.

### D. Persistance des analyses IA (migration `0004`)

Nouvelle table **`analyses_llm`** :

| colonne | type | rôle |
|---|---|---|
| `id` | uuid pk | |
| `course_id` | uuid fk courses | la course analysée |
| `modele` | text | ex. `claude-opus-4-8` |
| `recommandations` | jsonb | par type de pari : `{type_pari, selection[], base[], tournant[], confiance (0-100), niveau (faible/moyen/eleve), avis}` |
| `lecture_globale` | text | lecture d'ensemble de la course |
| `coup_de_coeur_value` | jsonb | le « value bet » : `{numero_corde, raison}` (nullable) |
| `input_snapshot` | jsonb | ce qui a été envoyé au LLM (classement + facteurs + cotes + signaux value) — pour audit & DATA |
| `confiance_globale` | numeric | indice agrégé (optionnel) |
| `created_at` | timestamptz default now() | |

Contrainte d'unicité `(course_id)` : **une analyse « courante » par course**. La
ré-analyse (`force=true`) **remplace** la ligne courante ; l'ancienne est **archivée**
dans une table jumelle `analyses_llm_historique` (mêmes colonnes + `archived_at`), pour
conserver la DATA longitudinale (évolution des avis quand les cotes bougent) sans
alourdir la lecture courante.

### E. Endpoints d'analyse

- `POST /courses/{id}/analyse` :
  - si une analyse existe → **la renvoie telle quelle (zéro appel LLM, zéro coût)** ;
  - sinon : score la course → construit les signaux (voir contrat LLM) → appelle
    Opus 4.8 → **persiste** → renvoie.
- `POST /courses/{id}/analyse?force=true` (bouton « Ré-analyser ») : refait un appel
  LLM payant (utile si les cotes ont bougé), remplace l'analyse courante (archive
  l'ancienne).
- `GET /courses/{id}/analyse` : renvoie l'analyse stockée (ou 404 si aucune).

## Contrat LLM (Opus 4.8)

**Rôle : stratège de paris ancré, PAS oracle prédictif.** Le LLM reçoit nos signaux
déterministes et doit s'appuyer dessus.

**Entrée (JSON structuré construit par le backend)** :
- Contexte course : discipline, distance, allocation, hippodrome, nombre de partants,
  type de course (Quinté+ ou non), paris disponibles.
- Chevaux classés : `numero_corde`, `nom`, `jockey`, `entraineur`, `score_total`,
  `rang`, `details_facteurs` (contributions), `cote`, `confiance`,
  `nb_courses_historique`.
- **Signaux value** (calculés backend) : par cheval, `proba_modele` (softmax des
  scores), `proba_implicite_cote`, `value = proba_modele − proba_implicite` → repère
  les chevaux sous-cotés par le marché.
- Forme de course : favori écrasant vs course ouverte (écart #1↔peloton, dispersion).

**Sortie (schéma imposé)** — via `messages.parse()` (Pydantic) / `output_config.format` :
- `lecture_globale` (str).
- `recommandations` : liste, un item par type de pari **analysable** dispo sur la
  course. Chaque item : `type_pari`, `selection` (numéros), `base`/`tournant` (pour les
  combinés), `confiance` (0–100), `niveau` (faible/moyen/élevé), `avis` (str, cite les
  facteurs + risques).
- `coup_de_coeur_value` (nullable) : `{numero_corde, raison}`.

**Réglages** : `thinking:{type:"adaptive"}` + `output_config.effort:"high"`.
**Ancrage** : le prompt interdit d'inventer ; chaque sélection doit s'appuyer sur les
signaux fournis ; privilégier les value bets pour la dimension « surprise » ; être
honnête sur les courses ouvertes / faible confiance.

**Confiance** : indice **relatif 0–100 + niveau**, présenté comme une *force de
conviction*, **pas** une probabilité de gain (pas de calibration tant que le backtest
n'existe pas — Plan futur).

**Coût / robustesse** :
- Un appel par course, **mis en cache via la persistance** (pas de rappel à
  l'affichage). Coût ~fraction de centime par course (Opus 4.8 5$/25$ / 1M).
- Repli gracieux : pas de clé API ou erreur LLM → l'endpoint renvoie une analyse
  **déterministe par règles** (sélections dérivées du classement + value, avis
  gabarit) et le marque comme tel, plutôt que d'échouer.
- Prérequis : `ANTHROPIC_API_KEY` dans `backend/.env` ; SDK `anthropic` (Python).

## Frontend — refonte (Layout A validé)

**Identité** : fond **blanc**, secondaire **émeraude `#16A34A`** (accents, Quinté+,
barres, confiance), texte ardoise, polices système (contrainte offline conservée),
cartes arrondies, ombres subtiles, `font-mono tabular-nums` pour les nombres.

**Dashboard 3 colonnes** (une seule page, pas de sections empilées) :
1. **Barre supérieure** : logo, **navigation par jour** (‹ date ›), recherche
   (cheval/jockey — best-effort, peut arriver plus tard).
2. **Colonne gauche — Courses du jour** : liste groupée par réunion (hippodrome +
   discipline), chaque course = puce cliquable (heure, discipline) ; la course
   **Quinté+ surlignée** en émeraude avec badge. Sélectionner une course charge le
   centre + la droite.
3. **Colonne centre — Pronostic** : entête course (R/C, hippodrome, type, distance,
   discipline, heure) + bouton « Analyser cette course » ; tableau classé (rang,
   cheval, jockey, barre de score, cote, indice de confiance coloré). Réutilise le
   scoring existant.
4. **Colonne droite — Analyse IA** : une **carte par pari** (Quinté+ en tête), avec
   sélection de chevaux (base pleine / tournant en pointillés), **confiance 0–100 +
   niveau**, **avis rédigé**, barre de confiance, tag **Value** pour la surprise
   fondée. Mention « analyse enregistrée » quand elle est persistée. Si aucune analyse
   → état vide + CTA « Analyser » ; « Ré-analyser » disponible sur une analyse
   existante.

**Responsive** : les 3 colonnes s'empilent proprement sous une largeur seuil (le
multi-colonnes est la cible desktop).

**Récupération de l'analyse** : à l'ouverture d'une course, le front appelle
`GET /courses/{id}/analyse` ; si présente, l'affiche (aucun coût). Sinon, panneau
vide + bouton d'analyse.

**Refonte** : on **reprend entièrement** l'existant (`ImportForm` disparaît au profit
du navigateur de courses ; `PartantsTable`/`PronosticTable` sont réintégrés dans la
colonne centre ; nouveau composant `AnalyseIA`).

## Décisions clés (validées)

1. **Affichage vs analyse des paris** : on **affiche tous** les paris dispo par course
   (info) ; le **LLM ne stratège que sur** Simple G/P, Couplé G/P, 2sur4, Trio,
   Tiercé, Quarté+, Quinté+. Les autres (Multi, Pick5, Super Quatre, Report+…) restent
   affichés mais non analysés en v1.
2. **Persistance = vue par défaut** ; la **ré-analyse est explicite et payante**.
3. **LLM = stratège ancré** (reçoit scores/cotes/value, produit sélections + avis) —
   choix utilisateur assumé, mitigé par l'ancrage sur nos signaux déterministes.
4. **Confiance = indice relatif 0–100 + niveau**, pas une probabilité de gain.
5. **Modèle = Claude Opus 4.8** (`claude-opus-4-8`), sorties structurées, thinking
   adaptatif, effort `high`.
6. **DATA** : on stocke entrée (`input_snapshot`) **et** sortie complète du LLM.

## Découpage prévisionnel (plans successifs)

Grosse fonctionnalité → plusieurs incréments, chacun livrable et testable :

- **Plan A — Découverte des courses (backend + front)** : endpoint `GET /programme/{date}`
  + mapping paris + détection Quinté+ ; côté front, la refonte du shell (dashboard 3
  colonnes, navigation jour, colonne gauche courses, Quinté+ en avant), branché sur le
  pronostic existant au centre. Pas encore d'IA. *(Livrable : on navigue et on
  pronostique dans la nouvelle plateforme.)*
- **Plan B — Analyse IA + persistance** : migration `0004` (`analyses_llm`) ; client
  Opus 4.8 + construction des signaux value ; endpoints analyse (get/post/force) ;
  colonne droite `AnalyseIA` + récupération persistée. *(Livrable : paris + avis +
  confiance, stockés et retrouvés sans coût.)*
- **(Futur) Plan C — Calibration/backtest** : exploiter la DATA collectée + résultats
  réels pour calibrer confiance et pondérations.

Chaque plan aura son propre cycle spec(ce doc)→plan→exécution.

## Hors périmètre (v1)

- Calibration statistique de la confiance / vraies probabilités (Plan futur / backtest).
- Analyse IA des paris hors sous-ensemble (Multi, Pick5, Super Quatre…).
- Prise de pari réelle / intégration compte PMU (pas un objectif ; app d'analyse).
- Sources de données tierces (Aspiturf/Geny) — cf. `2026-07-14-aspiturf-feasibility.md`.
- Auth / multi-utilisateur / déploiement.

## Prérequis & risques

- **`ANTHROPIC_API_KEY`** dans `backend/.env` (sinon repli déterministe).
- **Migration `0004`** appliquée manuellement par l'utilisateur (comme 0001–0003).
- **Coût LLM** maîtrisé par la persistance (un appel par course, ré-analyse explicite).
- **Contrainte Next.js** : « ce n'est pas le Next.js que tu connais » (lire
  `node_modules/next/dist/docs/`), et **pas de fetch réseau au build** (polices
  système only) — déjà des acquis du projet.
- **Vérif E2E navigateur** limitée par l'absence d'outil de pilotage — on vérifie au
  niveau contrat HTTP + build, cf. mémoire projet.
