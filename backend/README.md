# pronoturf backend

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # puis renseigner SUPABASE_URL et SUPABASE_SERVICE_KEY
```

## Lancer les tests

```bash
.venv/bin/pytest -v
```

## Lancer le serveur

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## Importer une course

```bash
curl -X POST http://localhost:8000/courses/import \
  -H "Content-Type: application/json" \
  -d '{"date": "12072026", "numero_reunion": 1, "numero_course": 1}'
```

## Scoring

Une fois une course importée (le `course_id` renvoyé par `/courses/import`), ces endpoints
permettent de la relire, de saisir des corrections manuelles, de calculer le pronostic et de
le relire.

- `GET /courses/{course_id}` — la course + ses partants, chacun enrichi de sa `cote_retenue`
  (cote `finale` si disponible, sinon `reference`, sinon `null`).
- `PATCH /courses/{course_id}` body `{"etat_terrain": "souple"}` — met à jour la course.
- `PATCH /partants/{partant_id}` body `{"ferrage"?, "poids_kg"?, "reduction_kilometrique"?}` —
  met à jour les champs fournis et les ajoute à `champs_manuels` du partant (traçabilité des
  corrections manuelles).
- `POST /courses/{course_id}/score` — calcule le score de chaque partant (facteurs pondérés
  par la pondération active de la discipline), remplace les lignes `scores_pronostic`
  existantes de la course par le nouveau classement, et le renvoie.
- `GET /courses/{course_id}/pronostic` — relit le classement déjà calculé depuis
  `scores_pronostic` (sans recalculer).

Chaque endpoint renvoie `404` si la course ou le partant n'existe pas.

```bash
curl -X GET http://localhost:8000/courses/<course_id>

curl -X PATCH http://localhost:8000/partants/<partant_id> \
  -H "Content-Type: application/json" \
  -d '{"ferrage": "DEFERRE_ANTERIEURS"}'

curl -X POST http://localhost:8000/courses/<course_id>/score

curl -X GET http://localhost:8000/courses/<course_id>/pronostic
```
