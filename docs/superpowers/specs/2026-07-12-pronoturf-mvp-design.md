# pronoturf — MVP : design

Date : 2026-07-12
Statut : validé (design), en attente de plan d'implémentation

## Contexte

Application d'aide à la décision pour les pronostics de courses hippiques françaises (PMU), toutes disciplines confondues (trot attelé, trot monté, plat, obstacle). Objectif : agréger des données de course (API PMU, Geny.com, saisie manuelle), calculer un score de pronostic pondéré par cheval, afficher un classement pronostiqué comparable à la cote officielle, et comparer ce pronostic aux résultats réels pour ajuster les pondérations dans le temps.

Ce document couvre le **MVP** uniquement : le pipeline de bout en bout pour une course sélectionnée manuellement. Les sources de données supplémentaires (Letrot, France Galop/IFCE), l'automatisation (cron), le programme complet du jour et une UI riche sont des phases ultérieures (voir "Hors scope").

Usage : personnel, un seul utilisateur, pas d'authentification.

## Architecture

Deux composants séparés, un seul propriétaire de la logique métier :

```
Next.js (frontend)  ──lecture directe (supabase-js)──►  Supabase Postgres
        │                                                        ▲
        │  déclenche des actions (import, scoring, backtest)     │
        ▼                                                        │
FastAPI (Python, local pour le MVP)  ──écrit dans──────────────► ┘
        │
        ├─ ingestion/pmu.py     → API PMU non officielle (programme, partants, cotes)
        ├─ ingestion/geny.py    → scraping Geny.com (stats driver/entraîneur)
        ├─ ingestion/manuel.py  → validation des saisies manuelles
        ├─ scoring/engine.py    → calcul du score pondéré par cheval
        ├─ backtest/compare.py  → pronostic vs résultat réel, précision par config
        └─ api/routes.py        → endpoints REST appelés par le frontend
```

**Règle de séparation** : FastAPI est seul propriétaire des écritures et de toute la logique métier (ingestion, normalisation, scoring, backtest). Le frontend Next.js lit les données directement dans Supabase pour l'affichage (pas de duplication de logique de lecture), et appelle FastAPI uniquement pour déclencher des actions qui produisent ou modifient des données.

**Déploiement MVP** : FastAPI tourne en local (pas de déploiement production) puisque toute récupération de données est déclenchée à la demande, pas par un job planifié. Supabase est hébergé (cloud). Le frontend peut tourner en local ou être déployé sur Vercel en pointant vers le même Supabase — dans les deux cas, les actions qui appellent FastAPI ne fonctionnent que si le service tourne en local pendant l'usage.

### Flux pour une course

1. L'utilisateur saisit l'identifiant de la course (réunion + numéro) dans le frontend.
2. Le frontend appelle `POST /courses/import` sur FastAPI.
3. FastAPI interroge l'API PMU (programme, partants, cotes) et Geny (stats driver/entraîneur), normalise les données dans un schéma commun, et les écrit dans Supabase.
4. Le frontend affiche les partants avec un formulaire inline pour compléter les champs manquants après ingestion (ferrage confirmé, dernière minute).
5. L'utilisateur déclenche `POST /courses/{id}/score`. FastAPI calcule le score pondéré de chaque partant et écrit `scores_pronostic`.
6. Le frontend lit le classement pronostiqué directement dans Supabase et l'affiche à côté de la cote officielle.
7. Après la course, l'utilisateur saisit ou importe le résultat réel. `POST /courses/{id}/backtest` compare le classement pronostiqué au résultat et enregistre la précision.

## Schéma de base de données (Supabase Postgres)

- **chevaux** — id, nom, sexe, date_naissance, source_ids (jsonb: `{pmu, geny}`)
- **intervenants** — id, nom, role (`driver` / `jockey` / `entraineur`), source_ids
- **hippodromes** — id, nom, pays, sens_corde (sens de la piste : droite/gauche — distinct de `partants.numero_corde`, qui est le numéro de départ du cheval)
- **reunions** — id, date, hippodrome_id, numero_reunion, source_ids
- **courses** — id, reunion_id, numero_course, discipline (`trot_attele` / `trot_monte` / `plat` / `obstacle`), distance_m, etat_terrain, categorie_classe, heure_depart, statut (`a_venir` / `terminee`), source_ids
- **partants** — id, course_id, cheval_id, numero_corde, driver_jockey_id, entraineur_id, poids_kg, reduction_kilometrique, ferrage, musique, statut (`partant` / `non_partant`), champs_manuels (jsonb — liste des champs saisis manuellement plutôt qu'importés)
- **cotes** — id, partant_id, type_capture (`h2h` / `h30` / `finale`), valeur, capture_at
- **resultats** — id, course_id, partant_id, position_arrivee, disqualifie, ecart, gains (gains perçus pour cette course précise, pas un cumul carrière)
- **ponderations_config** — id, discipline, nom, poids (jsonb), actif, version, created_at
- **scores_pronostic** — id, course_id, partant_id, ponderation_config_id, score_total, rang_pronostique, details_facteurs (jsonb), calculated_at
- **backtest_resultats** — id, ponderation_config_id, periode_debut, periode_fin, nb_courses, precision_top1, precision_top3, calculated_at

Pas d'authentification ni de RLS complexe (usage personnel, un seul utilisateur) : le frontend lit avec la clé anon (lecture seule), FastAPI écrit avec la clé service role.

## Moteur de scoring

Les pondérations sont stockées en base (`ponderations_config`), jamais en dur dans le code, avec un jeu de poids par défaut par discipline (trot et plat ne pondèrent pas les mêmes facteurs).

Facteurs du MVP et poids par défaut :

| Facteur | Trot (attelé/monté) | Plat |
|---|---|---|
| Forme récente (musique, 10 dernières courses) | 25% | 25% |
| Taux de victoire/place, 12 derniers mois | 15% | 15% |
| Fraîcheur (jours depuis dernière course) | 10% | 10% |
| Couple cheval/driver-jockey | 15% | 10% |
| Entraîneur (forme du mois) | 10% | 10% |
| Ferrage (trot) / poids porté (plat) | 10% | 10% |
| Cote marché (signal pondéré, pas vérité absolue) | 15% | 15% |
| Corde / numéro de départ | — | 5% |

Chaque score calculé est stocké avec le détail par facteur (`details_facteurs`), pour rester explicable (voir pourquoi un cheval est classé où il est, pas seulement le score final).

Si un facteur n'est pas renseigné pour un partant (ex : ferrage non confirmé), son poids est redistribué proportionnellement sur les autres facteurs renseignés plutôt que de bloquer le calcul.

## Backtest

Le module `backtest/compare.py` confronte `rang_pronostique` (scores_pronostic) à `position_arrivee` (resultats) pour une période et une config de pondération donnée, et calcule :
- précision top1 (le cheval classé 1er par le pronostic a-t-il gagné ?)
- précision top3 (le podium pronostiqué correspond-il au podium réel ?)

Les résultats sont stockés dans `backtest_resultats`, par config de pondération, pour permettre de comparer différents jeux de poids dans le temps. L'ajustement des poids eux-mêmes (à la main ou automatisé) est hors scope du MVP — le MVP se limite à mesurer la précision, pas à l'optimiser automatiquement.

## Frontend (Next.js)

Une seule page de travail pour le MVP :
1. Saisie de l'identifiant de course (réunion + numéro) → déclenche l'import.
2. Affichage des partants importés avec formulaire inline pour les champs manquants.
3. Bouton "Calculer le pronostic" → tableau de classement pronostiqué (rang, cheval, score, cote officielle en regard).
4. Après la course : champ de saisie/import du résultat réel, affichage de la précision du pronostic.

## Gestion des erreurs et cas limites

- **API PMU ou Geny indisponible ou format de réponse changé** : erreur explicite affichée à l'utilisateur ; le formulaire manuel reste utilisable comme fallback complet (l'app doit rester utilisable même si aucune API ne répond).
- **Non-partant** (cheval retiré de la course) : exclu du calcul de score, affiché grisé dans la liste.
- **Champ manquant après ingestion** : mis en évidence dans le formulaire manuel ; le score reste calculable avec redistribution du poids du facteur manquant (voir Moteur de scoring).

## Hors scope MVP (phases ultérieures)

- Sources de données Letrot.com, France Galop/IFCE.
- Récupération automatique planifiée (cron) — le MVP est déclenché à la demande.
- Programme complet du jour (liste de toutes les réunions/courses) — le MVP sélectionne une course à la fois.
- Authentification multi-utilisateurs.
- Déploiement production du service FastAPI.
- UI riche (graphiques d'historique, comparaison visuelle de plusieurs configs de pondération, ajustement automatique des poids via backtest).

## Note

Cet outil est une aide à la décision basée sur des statistiques historiques — il ne garantit aucun résultat. Les paris hippiques comportent une part de hasard irréductible.
