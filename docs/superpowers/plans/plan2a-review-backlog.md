# Plan 2a — Backlog issu de la revue finale (à traiter en Plan 2b / Plan 4)

Revue finale de branche (Opus) sur `3242b3f..89c7beb`. Verdict : **prêt à merger, aucun problème critique.** Chaîne de scoring vérifiée correcte de bout en bout (clés de facteurs cohérentes musique→factors→engine→routes→DB, aucun facteur inversé, mapping `numero_corde`→`partant_id` sûr grâce à `unique(course_id, numero_corde)`, migration 0002 cohérente avec le writer, pas de surface d'injection — tout passe par `.eq()` PostgREST). 43 tests verts + vérif bout-en-bout réelle réussie.

## À traiter en priorité au début du Plan 2b

1. **Unifier la forme des réponses `POST /score` et `GET /pronostic` + renvoyer le nom du cheval.** (le plus fort levier)
   - `POST /score` renvoie `[{numero_corde, score_total, rang, details_facteurs}]` (a la corde, pas de partant_id, pas de nom).
   - `GET /pronostic` renvoie les lignes brutes `scores_pronostic` `[{partant_id, rang_pronostique, score_total, details_facteurs, ...}]` (a partant_id, pas de numero_corde, pas de nom, et le champ de rang s'appelle `rang_pronostique` ≠ `rang`).
   - **Aucun endpoint ne renvoie le nom du cheval à côté d'un score** — le nom vit dans `chevaux`, `GET /courses` ne renvoie que `cheval_id`.
   - Fix (≈20 min backend) : enrichir `GET /pronostic` avec `numero_corde` + nom du cheval (jointure partant→cheval), aligner le champ de rang (`rang`) et la forme globale sur `POST /score`. Un petit helper partagé par les deux endpoints. À faire au début du Plan 2b, avant de brancher le frontend dessus.

## À porter dans le brief de tuning du Plan 4

2. **Asymétrie de normalisation : les facteurs min-max (`cote`, `corde`) ont structurellement plus de pouvoir discriminant que les facteurs absolus (`forme`, `taux_reussite`, `ferrage_poids` trot).**
   - `cote`/`corde` sont min-max sur la course → dans chaque course un cheval est forcé à 1.0 et un à 0.0 (pleine amplitude). `forme`/`taux`/`ferrage_poids` sont des scores absolus [0,1] qui en pratique se resserrent (ex. tout le monde entre 0.35 et 0.55). Résultat : le classement s'appuie en réalité plus sur la cote et la corde que ce que suggèrent les poids 20%/15%.
   - Conforme à la spec (cote « normalisée sur la course », forme = score de place absolu) → pas un bug, mais c'est la raison la plus probable qu'un backtest tuné (Plan 4) paraisse décalé. Décision à prendre en Plan 4 : soit min-max aussi les facteurs absolus (amplitude cohérente), soit garder tel quel et en tenir compte au tuning. À minima, documenté ici.

3. **`nombre_places` double-compte peut-être les victoires dans `taux_reussite`.** `(victoires + places)/courses` (`factors.py`) suppose que le `nombrePlaces` de PMU exclut les victoires. Sémantique PMU à vérifier (données réelles ambiguës : IGOR THEPOL 46 courses, 2 victoires, 24 places, dont 2ᵉ=2 / 3ᵉ=1). Si `nombrePlaces` inclut les victoires, retirer le `+ victoires`. Impact borné (min à 1.0), à trancher empiriquement au backtest du Plan 4.

4. **Poids identiques entre les 4 disciplines** (simplification assumée du plan). `trot_monte`/`obstacle` sont des placeholders non tunés — ne pas les prendre pour des valeurs validées. À tuner via backtest en Plan 4.

## Durcissement (quand la latence/robustesse comptera)

5. **Requêtes N+1 sur `cotes`** (`routes.py`, une requête par partant dans `get_course` et le scoring). OK en local ; batcher en une requête filtrée par les partant_ids de la course si le Plan 2b devient sensible à la latence.

6. **`delete`-puis-`insert` de `scores_pronostic` non transactionnel** (`routes.py`) : une panne entre les deux laisse la course sans scores jusqu'au re-score. OK pour un MVP local ; passer par une RPC/transaction si ça tourne un jour côté serveur.

7. **Seed `load_active_ponderation` = check-then-insert sans garde d'unicité** (`ponderations.py`) : deux premiers scores concurrents sur la même discipline peuvent insérer deux configs `actif=true`. Inoffensif en mono-utilisateur local (défauts identiques). Un index partiel `unique(discipline) where actif` ou un upsert le fermerait.

8. **Dédup migration 0002 échoue sur des `capture_at` strictement égaux** (`0002_scoring_schema.sql`) : `capture_at < capture_at` garde les deux lignes en cas d'égalité exacte → l'`ADD CONSTRAINT unique` échouerait alors. Déjà appliqué proprement sur la vraie DB (donc sans effet ici), mais si on rejoue ailleurs, ajouter un tie-breaker `or (capture_at = capture_at and c.id < c2.id)`.

9. **Branches dégénérées non testées** (correctes par traçage) : fallback `weight_sum <= 0` (`engine.py`), course à un seul partant (min-max→0.5), toutes cotes absentes. Quelques tests unitaires bon marché les verrouilleraient.

10. **Débutants (pas de musique, 0 course)** : `forme=0` et `taux=0` → plancher sur les deux facteurs de forme. Acceptable (la cote parle encore pour eux) mais à garder en tête : les inédits ressortent bas.

## Note sécurité (rappel)

Les endpoints sont non authentifiés et utilisent le client service-role — conforme à la contrainte « MVP local, pas de RLS », mais **ce backend ne doit jamais être exposé tel quel**. RLS + auth requis avant tout déploiement.
