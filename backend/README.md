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
