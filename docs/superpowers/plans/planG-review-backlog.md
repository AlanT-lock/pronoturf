# Plan G (cron quotidien) — review backlog

Branche : `feat/plan-g-cron` (base `8c3bd95`). Final review sonnet : « With fixes » → les 3 fixes appliqués (`e917d97` garde capture-setup ; `2a83b7d` tzdata + HAIE + concurrence). Zéro Critical.

## Corrigé pendant l'exécution

1. **Important (revue T2)** : setup de l'étape capture non gardé → 500 possible du run entier. Fix : try/except global étape 1 + parse date par course + 2 tests (rouge-avant vérifiés).
2. **Important (revue finale)** : `tzdata` absent de requirements → `ZoneInfo("Europe/Paris")` pouvait lever sur le runtime Vercel (500 à chaque run). Fix : dépendance ajoutée.
3. **Découverte run réel** : PMU envoie `"HAIE"` (singulier) — absent de `_DISCIPLINE_MAP` → course perdue (KeyError). Fix : mapping + test rouge-avant.
4. **Découverte run réel** : 330s > maxDuration 300 → imports concurrents (Semaphore 6). Re-mesure : **259s**.

## Minor — DEFER

1. **Marge de durée fine (259s/300s en local)** : le goulot restant = écritures Supabase synchrones (bloquent l'event loop, ~70 upserts/course) ; la concurrence ne parallélise que les fetchs PMU. À mesurer en prod (réseau Vercel↔PMU/Supabase sans doute plus rapide). Si prod > ~250s : batcher les upserts partants/cotes ou scinder le cron.
2. Double lookup de la date de réunion (fenêtre + `capture_one_resultats`) — requête dupliquée bénigne.
3. Branche `programme:` (échec du fetch du programme entier) correcte par lecture mais non testée.
4. Erreur transient PMU avec message vide (`R4C7: `) — tronquage OK mais `str(e)` vide peu informatif ; enrichir avec `type(e).__name__` un jour.
