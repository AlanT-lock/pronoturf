"""Point d'entrée Vercel : expose l'app ASGI FastAPI pour le runtime Python.

Toutes les routes sont redirigées vers cette fonction via `vercel.json` (rewrites),
et FastAPI route ensuite sur le chemin d'origine (/health, /programme/…, /courses/…).
"""

from app.main import app

__all__ = ["app"]
