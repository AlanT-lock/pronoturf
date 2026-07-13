# pronoturf

Application locale de pronostic hippique : importer une course, compléter les
champs manquants, calculer un classement pronostiqué **explicable** (contribution
de chaque facteur), le tout testable de bout en bout dans le navigateur.

- `backend/` — API FastAPI (import PMU, scoring). Voir [backend/README.md](backend/README.md).
- `frontend/` — interface Next.js. Voir [frontend/README.md](frontend/README.md).

## Lancer l'application en local

Deux serveurs, dans deux terminaux.

**Terminal A — backend (port 8000)**

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Prérequis backend : venv installé et `.env` renseigné (`SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`) — voir [backend/README.md](backend/README.md).

**Terminal B — frontend (port 3000)**

```bash
cd frontend
npm install   # première fois seulement
npm run dev
```

Le frontend lit l'URL du backend dans `frontend/.env.local`
(`NEXT_PUBLIC_API_URL=http://localhost:8000` par défaut).

Puis ouvrir **http://localhost:3000**.

## Parcours

1. **Importer une course** : saisir la date (`JJMMAAAA`), le numéro de réunion et
   de course, puis « Importer ». Les partants sont récupérés depuis l'API PMU.
2. **Compléter** si besoin l'état du terrain, le ferrage ou le poids des partants
   (enregistrement automatique à la sortie du champ).
3. **Calculer le pronostic** : le bouton lance le scoring et affiche le classement
   trié. Cliquer une ligne déplie le détail des facteurs
   (`valeur × poids = contribution`).
