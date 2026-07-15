# Plateforme pronoturf — Plan B (analyse IA + persistance) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher la colonne « Analyse IA » : produire des recommandations de paris (sélection + confiance + avis) par course, ancrées sur le scoring déterministe, via Claude Opus 4.8, avec repli déterministe et persistance (retrouver sans re-payer).

**Architecture :** Backend — un module `app/analyse/` qui (1) construit des **signaux value** (softmax des scores → proba modèle, proba implicite des cotes, value, forme de course) à partir du classement existant, (2) appelle **Opus 4.8** en sortie structurée pour produire l'analyse OU, sans clé/en cas d'erreur, un **repli déterministe par règles**, (3) persiste l'analyse (table `analyses_llm`, unicité `course_id`, archivage sur ré-analyse). Endpoints `GET/POST /courses/{id}/analyse` (+ `?force=true`). Frontend — nouveau composant `AnalyseIA` monté dans la colonne droite, récupération persistée à l'ouverture d'une course.

**Tech Stack :** FastAPI + Pydantic + supabase-py + pytest (FakeStore/monkeypatch) + SDK `anthropic` (Python) ; Next.js (App Router) + TypeScript + Tailwind v4.

**Réf. spec :** `docs/superpowers/specs/2026-07-14-pronoturf-plateforme-paris-ia-design.md` (§D, §E, §Contrat LLM, §Frontend colonne droite).

## Global Constraints

- **Décision de session : on construit SANS clé Anthropic pour l'instant.** Le chemin LLM complet est codé, mais la **vérification E2E s'appuie sur le repli déterministe**. Le vrai appel Opus 4.8 se testera quand la clé sera ajoutée. Concrètement : `analyser()` bascule sur le repli déterministe si `ANTHROPIC_API_KEY` est absente **ou** si l'appel LLM lève.
- **Modèle = `claude-opus-4-8`** exactement (jamais de suffixe de date). Sortie structurée via `client.messages.parse(output_format=<Pydantic>)`. Thinking adaptatif `{"type": "adaptive"}`. **Ne PAS passer `output_config`/`effort`** : l'effort `high` est le défaut — l'omettre évite tout conflit avec `parse()`. Pas de `temperature`/`top_p`/`budget_tokens` (rejetés en 400 sur Opus 4.8).
- **Persistance = vue par défaut** ; POST sans `force` renvoie l'analyse existante **sans appel LLM**. `?force=true` refait l'analyse et **archive** l'ancienne dans `analyses_llm_historique`.
- **Analyse restreinte** au sous-ensemble `bet_types.ANALYSABLE` ; les paris hors sous-ensemble sont ignorés par l'IA (affichés côté front, non analysés).
- **Confiance = indice relatif 0–100 + niveau** (`faible`/`moyen`/`eleve`), présentée comme force de conviction, PAS une probabilité de gain.
- **Migration `0004` appliquée manuellement** par l'utilisateur (comme 0001–0003) — ne pas tenter de l'appliquer depuis le code.
- **Identité visuelle** (rappel Plan A) : fond blanc, accent vert `green-600` (soft `green-50`, hover `green-700`), texte `slate-900`/`slate-500`, `font-mono tabular-nums` pour les nombres. Polices système uniquement.
- **Gates.** Backend : `cd backend && .venv/bin/pytest`. Frontend : `cd frontend && npm run build` (pas de suite unitaire front).
- **Ce n'est PAS le Next.js que tu connais** (`frontend/AGENTS.md`) : lire `node_modules/next/dist/docs/` avant toute construction sensible à la version.
- TDD strict côté backend.

## Structure des fichiers

Backend (nouveau package `app/analyse/`) :
- `backend/app/analyse/__init__.py` — **créer** (package vide).
- `backend/app/analyse/signals.py` — **créer** : fonctions pures (softmax, proba implicite, value, forme de course, `build_signals`).
- `backend/app/analyse/fallback.py` — **créer** : `analyse_deterministe(signals, paris)` (analyse par règles).
- `backend/app/analyse/llm.py` — **créer** : schémas Pydantic de sortie, `build_prompt`, `analyser(signals, paris)` (Opus 4.8 + repli).
- `backend/app/analyse/routes.py` — **créer** : `GET/POST /courses/{id}/analyse` + persistance/archivage.
- `backend/app/scoring/routes.py` — **modifier** : extraire `score_and_persist(client, course_id) -> list[dict]` (enrichi jockey/entraîneur), réutilisé par `compute_score` et l'analyse.
- `backend/app/main.py` — **modifier** : monter le routeur analyse.
- `backend/requirements.txt` — **modifier** : ajouter `anthropic`.
- `backend/tests/_fake_supabase.py` — **créer** : `FakeStore`/`FakeClient`/`FakeQuery`/`FakeResult` partagés (extraits de `test_scoring_routes.py`), + tables `analyses_llm`/`analyses_llm_historique`.
- `backend/tests/test_scoring_routes.py` — **modifier** : importer les fakes depuis `_fake_supabase`.
- `backend/tests/test_analyse_signals.py`, `test_analyse_fallback.py`, `test_analyse_llm.py`, `test_analyse_routes.py` — **créer**.

Base de données :
- `supabase/migrations/0004_analyses_llm_schema.sql` — **créer**.

Frontend :
- `frontend/lib/types.ts` — **modifier** : types `Recommandation`, `CoupDeCoeur`, `AnalyseIA`.
- `frontend/lib/api.ts` — **modifier** : `getAnalyse(id)`, `analyseCourse(id, paris, force)`.
- `frontend/components/AnalyseIA.tsx` — **créer** : rendu de l'analyse (cartes par pari, confiance, value, source).
- `frontend/app/page.tsx` — **modifier** : monter `AnalyseIA` dans la colonne droite + câblage (récupération persistée + boutons Analyser/Ré-analyser).

---

### Task 1: Migration `0004` (tables `analyses_llm` + historique)

**Files:**
- Create: `supabase/migrations/0004_analyses_llm_schema.sql`

**Interfaces:**
- Produces : table `analyses_llm` (unicité `course_id`) et `analyses_llm_historique`. Colonnes consommées par `app/analyse/routes.py` (Task 6).

- [ ] **Step 1: Écrire la migration**

Create `supabase/migrations/0004_analyses_llm_schema.sql` :

```sql
-- Analyse IA par course (une analyse « courante » par course).
create table analyses_llm (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  modele text not null,
  source text not null default 'llm',          -- 'llm' | 'regles' (repli déterministe)
  recommandations jsonb not null default '[]'::jsonb,
  lecture_globale text,
  coup_de_coeur_value jsonb,                    -- { numero_corde, raison } | null
  input_snapshot jsonb,                         -- signaux envoyés + paris (audit & DATA)
  confiance_globale numeric,
  created_at timestamptz not null default now(),
  unique (course_id)
);
create index analyses_llm_course_idx on analyses_llm (course_id);

-- Table jumelle : conserve la DATA longitudinale lors d'une ré-analyse (force=true).
create table analyses_llm_historique (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  modele text not null,
  source text,
  recommandations jsonb,
  lecture_globale text,
  coup_de_coeur_value jsonb,
  input_snapshot jsonb,
  confiance_globale numeric,
  created_at timestamptz,
  archived_at timestamptz not null default now()
);
create index analyses_llm_historique_course_idx on analyses_llm_historique (course_id);
```

- [ ] **Step 2: Demander l'application manuelle**

La migration est appliquée **par l'utilisateur** dans Supabase (comme 0001–0003). Signaler : « Applique `supabase/migrations/0004_analyses_llm_schema.sql` avant la vérification E2E de la Task 10. » Aucune commande de migration à lancer depuis le code.

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add supabase/migrations/0004_analyses_llm_schema.sql
git commit -m "feat(plateforme): migration 0004 (analyses_llm + historique)"
```

---

### Task 2: `app/analyse/signals.py` (signaux value)

**Files:**
- Create: `backend/app/analyse/__init__.py`, `backend/app/analyse/signals.py`
- Test: `backend/tests/test_analyse_signals.py`

**Interfaces:**
- Consumes : un `classement` = liste de dicts triés par `rang`, chacun avec au minimum `numero_corde`, `nom_cheval`, `score_total`, `rang`, `cote` (float|None), `confiance`, `nb_courses_historique`, `details_facteurs`, et optionnellement `jockey_nom`/`entraineur_nom`.
- Produces : `build_signals(classement) -> {"chevaux": [...], "forme_course": {...}}`. Chaque cheval enrichi de `proba_modele`, `proba_implicite_cote` (float|None), `value` (float|None). `forme_course` = `{"favori_ecrasant": bool, "ecart_favori": float, "dispersion": float}`.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_analyse_signals.py` :

```python
from app.analyse import signals as s


def test_softmax_sums_to_one_and_ranks():
    out = s.softmax([0.8, 0.5, 0.2])
    assert abs(sum(out) - 1.0) < 1e-9
    assert out[0] > out[1] > out[2]


def test_softmax_empty():
    assert s.softmax([]) == []


def test_proba_implicite_normalise_et_ignore_none():
    # cotes 2.0 et 4.0 -> inv 0.5 et 0.25 -> total 0.75 -> 0.666.., 0.333..
    out = s.proba_implicite([2.0, 4.0, None])
    assert abs(out[0] - 2 / 3) < 1e-6
    assert abs(out[1] - 1 / 3) < 1e-6
    assert out[2] is None


def test_course_shape_favori_ecrasant():
    forme = s.course_shape([0.9, 0.5, 0.45, 0.4])
    assert forme["favori_ecrasant"] is True
    assert forme["ecart_favori"] > 0


def test_course_shape_ouverte():
    forme = s.course_shape([0.55, 0.54, 0.53, 0.52])
    assert forme["favori_ecrasant"] is False


def test_build_signals_shape_and_value():
    classement = [
        {"numero_corde": 4, "nom_cheval": "A", "score_total": 0.8, "rang": 1,
         "cote": 5.0, "confiance": 0.5, "nb_courses_historique": 3, "details_facteurs": {}},
        {"numero_corde": 1, "nom_cheval": "B", "score_total": 0.4, "rang": 2,
         "cote": 2.0, "confiance": 0.5, "nb_courses_historique": 3, "details_facteurs": {}},
    ]
    out = s.build_signals(classement)
    assert set(out) == {"chevaux", "forme_course"}
    ch = out["chevaux"][0]
    assert {"proba_modele", "proba_implicite_cote", "value"} <= set(ch)
    # A a un meilleur score mais une cote plus haute -> value probablement positive
    assert ch["numero_corde"] == 4
    assert ch["value"] is not None


def test_build_signals_cote_absente_donne_value_none():
    classement = [
        {"numero_corde": 4, "nom_cheval": "A", "score_total": 0.8, "rang": 1,
         "cote": None, "confiance": 0.5, "nb_courses_historique": 1, "details_facteurs": {}},
    ]
    ch = s.build_signals(classement)["chevaux"][0]
    assert ch["proba_implicite_cote"] is None
    assert ch["value"] is None
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_signals.py -q`
Expected: FAIL (module `app.analyse.signals` absent).

- [ ] **Step 3: Créer le package et le module**

Create `backend/app/analyse/__init__.py` (vide).

Create `backend/app/analyse/signals.py` :

```python
"""Signaux value pour l'analyse IA, dérivés du classement déterministe.

- `proba_modele` : softmax des scores (répartit la conviction du modèle).
- `proba_implicite_cote` : 1/cote normalisée sur les cotes présentes (retire l'overround).
- `value` : proba_modele - proba_implicite -> repère les chevaux sous-cotés par le marché.
- `forme_course` : favori écrasant vs course ouverte (écart #1↔#2, dispersion).
"""

import math

_KEEP = (
    "numero_corde", "nom_cheval", "score_total", "rang", "cote",
    "confiance", "nb_courses_historique", "jockey_nom", "entraineur_nom",
    "details_facteurs",
)


def softmax(scores: list[float], temperature: float = 0.15) -> list[float]:
    if not scores:
        return []
    m = max(scores)
    exps = [math.exp((x - m) / temperature) for x in scores]
    total = sum(exps)
    if total <= 0:
        return [1 / len(scores)] * len(scores)
    return [e / total for e in exps]


def proba_implicite(cotes: list[float | None]) -> list[float | None]:
    inv = [(1.0 / c if c and c > 0 else None) for c in cotes]
    total = sum(x for x in inv if x is not None)
    if total <= 0:
        return [None] * len(cotes)
    return [(x / total if x is not None else None) for x in inv]


def course_shape(scores: list[float]) -> dict:
    if len(scores) < 2:
        return {"favori_ecrasant": False, "ecart_favori": 0.0, "dispersion": 0.0}
    ordered = sorted(scores, reverse=True)
    ecart = ordered[0] - ordered[1]
    mean = sum(scores) / len(scores)
    dispersion = math.sqrt(sum((x - mean) ** 2 for x in scores) / len(scores))
    return {
        "favori_ecrasant": ecart >= 0.12,
        "ecart_favori": round(ecart, 4),
        "dispersion": round(dispersion, 4),
    }


def build_signals(classement: list[dict]) -> dict:
    scores = [c["score_total"] for c in classement]
    cotes = [c.get("cote") for c in classement]
    probas = softmax(scores)
    implicites = proba_implicite(cotes)
    chevaux = []
    for c, pm, pi in zip(classement, probas, implicites):
        value = (pm - pi) if pi is not None else None
        row = {k: c.get(k) for k in _KEEP}
        row["proba_modele"] = round(pm, 4)
        row["proba_implicite_cote"] = round(pi, 4) if pi is not None else None
        row["value"] = round(value, 4) if value is not None else None
        chevaux.append(row)
    return {"chevaux": chevaux, "forme_course": course_shape(scores)}
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_signals.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/analyse/__init__.py backend/app/analyse/signals.py backend/tests/test_analyse_signals.py
git commit -m "feat(analyse): signaux value (softmax/proba implicite/value/forme)"
```

---

### Task 3: `app/analyse/fallback.py` (analyse déterministe par règles)

**Files:**
- Create: `backend/app/analyse/fallback.py`
- Test: `backend/tests/test_analyse_fallback.py`

**Interfaces:**
- Consumes : `build_signals(...)` (Task 2), `app.bet_types` (`ANALYSABLE`, `libelle`).
- Produces : `analyse_deterministe(signals, paris) -> dict` avec clés `modele`, `lecture_globale`, `recommandations` (liste `{type_pari, selection, base, tournant, confiance, niveau, avis}`), `coup_de_coeur_value` (`{numero_corde, raison}`|None), `confiance_globale`, `source="regles"`. Ne produit de recommandation **que** pour les paris ∈ `ANALYSABLE`.

- [ ] **Step 1: Écrire le test rouge**

Create `backend/tests/test_analyse_fallback.py` :

```python
from app.analyse.fallback import analyse_deterministe

SIGNALS = {
    "forme_course": {"favori_ecrasant": True, "ecart_favori": 0.3, "dispersion": 0.2},
    "chevaux": [
        {"numero_corde": 4, "nom_cheval": "A", "rang": 1, "value": 0.12},
        {"numero_corde": 1, "nom_cheval": "B", "rang": 2, "value": -0.05},
        {"numero_corde": 7, "nom_cheval": "C", "rang": 3, "value": 0.02},
        {"numero_corde": 2, "nom_cheval": "D", "rang": 4, "value": None},
        {"numero_corde": 9, "nom_cheval": "E", "rang": 5, "value": -0.01},
    ],
}


def test_recommande_seulement_paris_analysables():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT", "MULTI", "TRIO"])
    codes = [r["type_pari"] for r in out["recommandations"]]
    assert "SIMPLE_GAGNANT" in codes and "TRIO" in codes
    assert "MULTI" not in codes  # hors ANALYSABLE


def test_selection_taille_par_pari():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT", "TIERCE", "QUINTE_PLUS"])
    by = {r["type_pari"]: r for r in out["recommandations"]}
    assert by["SIMPLE_GAGNANT"]["selection"] == [4]
    assert by["TIERCE"]["selection"] == [4, 1, 7]
    assert by["QUINTE_PLUS"]["selection"] == [4, 1, 7, 2, 9]
    # base/tournant remplis pour les combinés
    assert by["TIERCE"]["base"] == [4]
    assert by["TIERCE"]["tournant"] == [1, 7]


def test_coup_de_coeur_meilleur_value_positif():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT"])
    assert out["coup_de_coeur_value"]["numero_corde"] == 4  # value +0.12 le plus haut


def test_source_et_niveau():
    out = analyse_deterministe(SIGNALS, ["SIMPLE_GAGNANT"])
    assert out["source"] == "regles"
    assert out["recommandations"][0]["niveau"] in {"faible", "moyen", "eleve"}


def test_pas_de_value_positive_donne_coup_none():
    signals = {"forme_course": {"favori_ecrasant": False, "ecart_favori": 0.0, "dispersion": 0.0},
               "chevaux": [{"numero_corde": 1, "nom_cheval": "X", "rang": 1, "value": None}]}
    out = analyse_deterministe(signals, ["SIMPLE_GAGNANT"])
    assert out["coup_de_coeur_value"] is None
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_fallback.py -q`
Expected: FAIL (module absent).

- [ ] **Step 3: Créer `app/analyse/fallback.py`**

```python
"""Repli déterministe : analyse par règles quand le LLM est indisponible.

Produit la même forme de sortie que le chemin LLM, marquée `source="regles"` :
sélections dérivées du classement, confiance heuristique, avis gabarit.
"""

from app import bet_types

# Taille de sélection par type de pari (nombre de chevaux à retenir).
_TAILLE = {
    "SIMPLE_GAGNANT": 1, "SIMPLE_PLACE": 1,
    "COUPLE_GAGNANT": 2, "COUPLE_PLACE": 2,
    "DEUX_SUR_QUATRE": 4, "TRIO": 3, "TIERCE": 3,
    "QUARTE_PLUS": 4, "QUINTE_PLUS": 5,
}


def _niveau(confiance: int) -> str:
    if confiance >= 66:
        return "eleve"
    if confiance >= 40:
        return "moyen"
    return "faible"


def analyse_deterministe(signals: dict, paris: list[str]) -> dict:
    ordered = sorted(signals["chevaux"], key=lambda c: c["rang"])
    nums = [c["numero_corde"] for c in ordered]
    forme = signals["forme_course"]
    base_conf = 70 if forme.get("favori_ecrasant") else 45

    recommandations = []
    for code in [p for p in paris if p in bet_types.ANALYSABLE]:
        taille = _TAILLE.get(code, 1)
        selection = nums[:taille]
        confiance = max(10, base_conf - 5 * (taille - 1))
        combine = taille > 1
        recommandations.append({
            "type_pari": code,
            "selection": selection,
            "base": selection[:1] if combine else [],
            "tournant": selection[1:] if combine else [],
            "confiance": confiance,
            "niveau": _niveau(confiance),
            "avis": (
                f"Sélection dérivée du classement pour {bet_types.libelle(code)} : "
                + ", ".join(f"n°{n}" for n in selection) + "."
            ),
        })

    values = [c for c in signals["chevaux"] if c.get("value") is not None and c["value"] > 0]
    coup = None
    if values:
        best = max(values, key=lambda c: c["value"])
        coup = {
            "numero_corde": best["numero_corde"],
            "raison": f"Sous-coté par le marché (value +{best['value']:.2f}).",
        }

    tete = ordered[0]["nom_cheval"] if ordered else "—"
    lecture = (
        ("Favori qui se détache" if forme.get("favori_ecrasant") else "Course ouverte")
        + f" ; en tête du modèle : {tete}."
    )
    return {
        "modele": "regles-v1",
        "lecture_globale": lecture,
        "recommandations": recommandations,
        "coup_de_coeur_value": coup,
        "confiance_globale": base_conf,
        "source": "regles",
    }
```

- [ ] **Step 4: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_fallback.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/analyse/fallback.py backend/tests/test_analyse_fallback.py
git commit -m "feat(analyse): repli deterministe par regles"
```

---

### Task 4: `app/analyse/llm.py` (client Opus 4.8 + sortie structurée + repli)

**Files:**
- Create: `backend/app/analyse/llm.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_analyse_llm.py`

**Interfaces:**
- Consumes : `analyse_deterministe` (Task 3), `app.bet_types.ANALYSABLE`, SDK `anthropic`.
- Produces : `analyser(signals, paris) -> dict` — même forme que le repli. Bascule sur le repli si `ANTHROPIC_API_KEY` absente **ou** si l'appel LLM lève. Schémas Pydantic `Recommandation`, `CoupDeCoeur`, `AnalyseLLM` ; `build_prompt(signals, paris_analysables) -> str` ; constante `MODELE = "claude-opus-4-8"`.

- [ ] **Step 1: Ajouter la dépendance**

Modify `backend/requirements.txt` : ajouter une ligne `anthropic` (à la suite des dépendances existantes).

Puis installer dans le venv :

Run: `cd backend && .venv/bin/pip install anthropic`
Expected: installation réussie (ou déjà présent).

- [ ] **Step 2: Écrire le test rouge**

Create `backend/tests/test_analyse_llm.py` :

```python
import app.analyse.llm as llm

SIGNALS = {
    "forme_course": {"favori_ecrasant": True, "ecart_favori": 0.3, "dispersion": 0.2},
    "chevaux": [
        {"numero_corde": 4, "nom_cheval": "A", "rang": 1, "value": 0.12,
         "score_total": 0.8, "cote": 5.0, "proba_modele": 0.6, "proba_implicite_cote": 0.48},
        {"numero_corde": 1, "nom_cheval": "B", "rang": 2, "value": -0.05,
         "score_total": 0.4, "cote": 2.0, "proba_modele": 0.4, "proba_implicite_cote": 0.52},
    ],
}


def test_analyser_sans_cle_bascule_sur_repli(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = llm.analyser(SIGNALS, ["SIMPLE_GAGNANT", "TRIO"])
    assert out["source"] == "regles"
    assert out["modele"] == "regles-v1"
    assert [r["type_pari"] for r in out["recommandations"]] == ["SIMPLE_GAGNANT", "TRIO"]


def test_analyser_erreur_llm_bascule_sur_repli(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("pas de reseau en test")

    # anthropic.Anthropic() lève -> repli déterministe
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", Boom)
    out = llm.analyser(SIGNALS, ["SIMPLE_GAGNANT"])
    assert out["source"] == "regles"


def test_analyser_chemin_llm_mappe_la_sortie(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    reco = llm.Recommandation(
        type_pari="SIMPLE_GAGNANT", selection=[4], base=[], tournant=[],
        confiance=72, niveau="eleve", avis="Le 4 domine.",
    )
    parsed = llm.AnalyseLLM(
        lecture_globale="Favori net.",
        recommandations=[reco],
        coup_de_coeur_value=llm.CoupDeCoeur(numero_corde=4, raison="value positive"),
    )

    class FakeResp:
        parsed_output = parsed

    class FakeMessages:
        def parse(self, **kwargs):
            # Le modèle demandé doit être Opus 4.8.
            assert kwargs["model"] == "claude-opus-4-8"
            assert kwargs["output_format"] is llm.AnalyseLLM
            return FakeResp()

    class FakeClient:
        def __init__(self, *a, **k):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)

    out = llm.analyser(SIGNALS, ["SIMPLE_GAGNANT", "MULTI"])
    assert out["source"] == "llm"
    assert out["modele"] == "claude-opus-4-8"
    assert out["lecture_globale"] == "Favori net."
    assert out["recommandations"][0]["type_pari"] == "SIMPLE_GAGNANT"
    assert out["coup_de_coeur_value"] == {"numero_corde": 4, "raison": "value positive"}
    assert out["confiance_globale"] == 72
```

- [ ] **Step 3: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_llm.py -q`
Expected: FAIL (module absent).

- [ ] **Step 4: Créer `app/analyse/llm.py`**

```python
"""Analyse IA ancrée (Claude Opus 4.8), avec repli déterministe.

Le LLM reçoit nos signaux déterministes (scores, cotes, proba modèle, value, forme)
et produit des recommandations de paris ANCRÉES dessus, en sortie structurée.
Sans clé API ou en cas d'erreur, on bascule sur `analyse_deterministe`.
"""

import json
import os
from typing import Literal

from pydantic import BaseModel

from app import bet_types
from app.analyse.fallback import analyse_deterministe

MODELE = "claude-opus-4-8"

SYSTEM = (
    "Tu es un stratège de paris hippiques ANCRÉ, pas un oracle prédictif. "
    "Tu reçois le classement d'un modèle déterministe (scores, cotes, probabilité "
    "modèle, probabilité implicite de la cote, value) et la forme de la course. "
    "Règles : n'invente aucune donnée ; chaque sélection s'appuie sur les signaux "
    "fournis ; privilégie les value bets (value>0) pour la dimension surprise ; sois "
    "honnête sur les courses ouvertes et la faible confiance. La confiance est un "
    "indice relatif 0–100 (force de conviction), PAS une probabilité de gain. "
    "Ne propose de recommandation QUE pour les types de paris listés."
)


class Recommandation(BaseModel):
    type_pari: str
    selection: list[int]
    base: list[int] = []
    tournant: list[int] = []
    confiance: int
    niveau: Literal["faible", "moyen", "eleve"]
    avis: str


class CoupDeCoeur(BaseModel):
    numero_corde: int
    raison: str


class AnalyseLLM(BaseModel):
    lecture_globale: str
    recommandations: list[Recommandation]
    coup_de_coeur_value: CoupDeCoeur | None = None


def build_prompt(signals: dict, paris_analysables: list[str]) -> str:
    return (
        "Analyse cette course hippique et propose des paris ancrés sur les signaux.\n\n"
        f"Types de paris à analyser (uniquement ceux-ci) : {paris_analysables}\n\n"
        f"Forme de course : {json.dumps(signals['forme_course'], ensure_ascii=False)}\n\n"
        "Chevaux classés par le modèle déterministe (rang 1 = meilleur) :\n"
        + json.dumps(signals["chevaux"], ensure_ascii=False, indent=2)
    )


def _confiance_globale(recommandations: list[dict]) -> int | None:
    confs = [r["confiance"] for r in recommandations]
    return round(sum(confs) / len(confs)) if confs else None


def analyser(signals: dict, paris: list[str]) -> dict:
    paris_analysables = [p for p in paris if p in bet_types.ANALYSABLE]
    if not os.getenv("ANTHROPIC_API_KEY"):
        return analyse_deterministe(signals, paris)
    try:
        import anthropic

        client = anthropic.Anthropic()
        # effort 'high' par défaut : on l'omet (évite tout conflit avec parse()).
        resp = client.messages.parse(
            model=MODELE,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM,
            output_format=AnalyseLLM,
            messages=[{"role": "user", "content": build_prompt(signals, paris_analysables)}],
        )
        out = resp.parsed_output
        recommandations = [r.model_dump() for r in out.recommandations]
        return {
            "modele": MODELE,
            "lecture_globale": out.lecture_globale,
            "recommandations": recommandations,
            "coup_de_coeur_value": (
                out.coup_de_coeur_value.model_dump() if out.coup_de_coeur_value else None
            ),
            "confiance_globale": _confiance_globale(recommandations),
            "source": "llm",
        }
    except Exception:
        # Repli gracieux : pas de clé valide, réseau, quota, schéma… -> règles.
        return analyse_deterministe(signals, paris)
```

- [ ] **Step 5: Lancer (vert)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_llm.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/analyse/llm.py backend/requirements.txt backend/tests/test_analyse_llm.py
git commit -m "feat(analyse): client Opus 4.8 (sortie structuree) + repli"
```

---

### Task 5: Extraire `score_and_persist` (réutilisable) + enrichir jockey/entraîneur

**Files:**
- Modify: `backend/app/scoring/routes.py`

**Interfaces:**
- Produces : `score_and_persist(client, course_id) -> list[dict]` — corps actuel de `compute_score`, renvoyant le classement enrichi **avec `jockey_nom`/`entraineur_nom` ajoutés à chaque ligne**. `compute_score` l'appelle et se contente d'emballer la réponse.
- Consumers : `compute_score` (inchangé côté HTTP), `app/analyse/routes.py` (Task 6).

- [ ] **Step 1: Écrire le test rouge (enrichissement jockey/entraîneur)**

Ajouter à `backend/tests/test_scoring_routes.py` (le fichier bascule sur `_fake_supabase` en Task 6 ; ici, ajouter juste ce test à la fin, il utilise le `FakeStore`/`FakeClient`/`_override` déjà présents dans le fichier) :

```python
def test_score_classement_expose_jockey_entraineur():
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        body = client.post("/courses/course-1/score").json()
        top = next(r for r in body["classement"] if r["numero_corde"] == 1)
        assert top["jockey_nom"] == "S.PASQUIER"
        assert top["entraineur_nom"] == "N.CAULLERY"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_scoring_routes.py::test_score_classement_expose_jockey_entraineur -q`
Expected: FAIL (`KeyError`/absence de `jockey_nom`).

- [ ] **Step 3: Refactor — extraire `score_and_persist` et enrichir**

Dans `backend/app/scoring/routes.py`, remplacer la fonction `compute_score` (endpoint actuel `@router.post("/courses/{course_id}/score")`) par un helper pur + un endpoint mince. **Remplacer** le bloc de `compute_score` par :

```python
def score_and_persist(client, course_id: str) -> list[dict]:
    """Score la course, remplace scores_pronostic, renvoie le classement enrichi
    (nom_cheval, partant_id, jockey_nom, entraineur_nom). Lève 404 si course absente."""
    course = _get_course_or_404(client, course_id)
    partants = _get_partants_for_course(client, course_id)
    partant_id_by_corde = {p["numero_corde"]: p["id"] for p in partants}
    perfs_par_cheval = _performances_par_cheval(client, [p["cheval_id"] for p in partants])
    partant_dicts = [
        _partant_dict_for_scoring(client, p, perfs_par_cheval.get(p["cheval_id"], []))
        for p in partants
    ]
    context = _course_context(client, course)

    ponderation = load_active_ponderation(client, course["discipline"])
    classement = score_course(partant_dicts, course["discipline"], ponderation["poids"], context)

    client.table("scores_pronostic").delete().eq("course_id", course_id).execute()

    if classement:
        rows = [
            {
                "course_id": course_id,
                "partant_id": partant_id_by_corde[row["numero_corde"]],
                "ponderation_config_id": ponderation["id"],
                "score_total": row["score_total"],
                "rang_pronostique": row["rang"],
                "details_facteurs": row["details_facteurs"],
                "confiance": row["confiance"],
                "nb_courses_historique": row["nb_courses_historique"],
            }
            for row in classement
        ]
        client.table("scores_pronostic").insert(rows).execute()

    cheval_map = _cheval_nom_par_partant(client, list(partant_id_by_corde.values()))
    jke_by_corde = {p["numero_corde"]: _jockey_entraineur_noms(client, p) for p in partants}
    enriched = []
    for row in classement:
        corde = row["numero_corde"]
        jockey_nom, entraineur_nom = jke_by_corde.get(corde, (None, None))
        enriched.append({
            **row,
            "partant_id": partant_id_by_corde[corde],
            "nom_cheval": cheval_map.get(partant_id_by_corde[corde], (None, None, None))[1],
            "jockey_nom": jockey_nom,
            "entraineur_nom": entraineur_nom,
        })
    return enriched


@router.post("/courses/{course_id}/score")
def compute_score(course_id: str, client=Depends(get_supabase_client)) -> dict:
    return {"course_id": course_id, "classement": score_and_persist(client, course_id)}
```

- [ ] **Step 4: Lancer (vert) + non-régression**

Run: `cd backend && .venv/bin/pytest tests/test_scoring_routes.py -q`
Expected: PASS (tous, y compris le nouveau test et les existants — l'ajout de `jockey_nom`/`entraineur_nom` est additif).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/routes.py backend/tests/test_scoring_routes.py
git commit -m "refactor(scoring): score_and_persist reutilisable + jockey/entraineur au classement"
```

---

### Task 6: Endpoints d'analyse + persistance/archivage + fakes partagés

**Files:**
- Create: `backend/app/analyse/routes.py`, `backend/tests/_fake_supabase.py`, `backend/tests/test_analyse_routes.py`
- Modify: `backend/app/main.py`, `backend/tests/test_scoring_routes.py`

**Interfaces:**
- Consumes : `score_and_persist` (Task 5), `signals.build_signals` (Task 2), `llm.analyser` (Task 4), `_get_course_or_404` (scoring/routes).
- Produces :
  - `GET /courses/{id}/analyse` → ligne `analyses_llm` stockée, ou **404** si aucune.
  - `POST /courses/{id}/analyse` (corps `{"paris": [...]}`, query `?force=bool`) → si analyse existe et `force` faux : la renvoie **sans appel LLM** ; sinon : score → signaux → `analyser` → persiste (archive l'ancienne si `force`) → renvoie.

- [ ] **Step 1: Extraire les fakes partagés**

Create `backend/tests/_fake_supabase.py` avec le **contenu exact** des classes `FakeResult`, `FakeQuery`, `FakeStore`, `FakeClient` **actuellement dans `test_scoring_routes.py`** (copier tel quel), en ajoutant à `FakeStore.__init__` deux tables vides :

```python
            "analyses_llm": [],
            "analyses_llm_historique": [],
```

(à insérer dans le dict `self.tables`, après `"scores_pronostic": [],`). Ne rien changer d'autre à la logique des fakes.

- [ ] **Step 2: Faire pointer `test_scoring_routes.py` sur les fakes partagés**

Dans `backend/tests/test_scoring_routes.py`, **supprimer** les définitions locales de `FakeResult`, `FakeQuery`, `FakeStore`, `FakeClient` et les remplacer par un import en tête de fichier :

```python
from tests._fake_supabase import FakeClient, FakeStore
```

(Garder `_override` et tous les tests inchangés.)

- [ ] **Step 3: Vérifier la non-régression scoring**

Run: `cd backend && .venv/bin/pytest tests/test_scoring_routes.py -q`
Expected: PASS (identique à avant l'extraction).

- [ ] **Step 4: Écrire le test rouge des routes d'analyse**

Create `backend/tests/test_analyse_routes.py` :

```python
from fastapi.testclient import TestClient

from app.main import app
from app.supabase_client import get_supabase_client
from tests._fake_supabase import FakeClient, FakeStore


def _override(store):
    app.dependency_overrides[get_supabase_client] = lambda: FakeClient(store)


def test_get_analyse_404_quand_absente():
    store = FakeStore()
    _override(store)
    try:
        assert TestClient(app).get("/courses/course-1/analyse").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_cree_via_repli_sans_cle(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post(
            "/courses/course-1/analyse",
            json={"paris": ["SIMPLE_GAGNANT", "TRIO", "MULTI"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "regles"
        assert body["course_id"] == "course-1"
        codes = [r["type_pari"] for r in body["recommandations"]]
        assert "SIMPLE_GAGNANT" in codes and "TRIO" in codes and "MULTI" not in codes
        assert body["input_snapshot"]["paris"] == ["SIMPLE_GAGNANT", "TRIO", "MULTI"]
        assert len(store.tables["analyses_llm"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_existante_sans_force_ne_rappelle_pas_le_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    store.tables["analyses_llm"].append({
        "id": "a-existante", "course_id": "course-1", "modele": "regles-v1",
        "source": "regles", "recommandations": [], "lecture_globale": "déjà là",
        "coup_de_coeur_value": None, "input_snapshot": {}, "confiance_globale": 50,
        "created_at": "2026-07-14T00:00:00Z",
    })
    _override(store)

    import app.analyse.routes as routes

    def boom(*a, **k):
        raise AssertionError("analyser ne doit PAS être appelé quand une analyse existe")

    monkeypatch.setattr(routes, "analyser", boom)
    try:
        client = TestClient(app)
        resp = client.post("/courses/course-1/analyse", json={"paris": ["SIMPLE_GAGNANT"]})
        assert resp.status_code == 200
        assert resp.json()["id"] == "a-existante"
        # GET renvoie la même
        assert client.get("/courses/course-1/analyse").json()["id"] == "a-existante"
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_force_archive_et_remplace(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = FakeStore()
    store.tables["analyses_llm"].append({
        "id": "a-vieille", "course_id": "course-1", "modele": "regles-v1",
        "source": "regles", "recommandations": [], "lecture_globale": "ancienne",
        "coup_de_coeur_value": None, "input_snapshot": {}, "confiance_globale": 50,
        "created_at": "2026-07-14T00:00:00Z",
    })
    _override(store)
    try:
        client = TestClient(app)
        resp = client.post(
            "/courses/course-1/analyse?force=true",
            json={"paris": ["SIMPLE_GAGNANT"]},
        )
        assert resp.status_code == 200
        assert len(store.tables["analyses_llm_historique"]) == 1  # ancienne archivée
        assert len(store.tables["analyses_llm"]) == 1              # une seule courante
        assert store.tables["analyses_llm"][0]["id"] != "a-vieille"
    finally:
        app.dependency_overrides.clear()


def test_post_analyse_404_course_absente():
    store = FakeStore()
    _override(store)
    try:
        resp = TestClient(app).post("/courses/inexistante/analyse", json={"paris": []})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 5: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_routes.py -q`
Expected: FAIL (routes absentes / 404 sur POST).

- [ ] **Step 6: Créer `app/analyse/routes.py`**

```python
"""Endpoints d'analyse IA d'une course (get/post/force) + persistance.

- GET  /courses/{id}/analyse        -> analyse stockée (404 si aucune).
- POST /courses/{id}/analyse        -> renvoie l'existante (zéro appel LLM) sinon
                                       score -> signaux -> analyser -> persiste.
- POST /courses/{id}/analyse?force=true -> ré-analyse (archive l'ancienne).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.analyse import signals as signals_mod
from app.analyse.llm import analyser
from app.scoring.routes import _get_course_or_404, score_and_persist
from app.supabase_client import get_supabase_client

router = APIRouter()

_ARCHIVE_COLS = (
    "course_id", "modele", "source", "recommandations", "lecture_globale",
    "coup_de_coeur_value", "input_snapshot", "confiance_globale", "created_at",
)


class AnalyseRequest(BaseModel):
    paris: list[str] = []


def _existing_analyse(client, course_id: str) -> dict | None:
    rows = (
        client.table("analyses_llm").select("*").eq("course_id", course_id).limit(1).execute().data
    )
    return rows[0] if rows else None


@router.get("/courses/{course_id}/analyse")
def get_analyse(course_id: str, client=Depends(get_supabase_client)) -> dict:
    _get_course_or_404(client, course_id)
    analyse = _existing_analyse(client, course_id)
    if not analyse:
        raise HTTPException(status_code=404, detail="Aucune analyse pour cette course")
    return analyse


@router.post("/courses/{course_id}/analyse")
def post_analyse(
    course_id: str,
    body: AnalyseRequest,
    force: bool = False,
    client=Depends(get_supabase_client),
) -> dict:
    _get_course_or_404(client, course_id)
    existing = _existing_analyse(client, course_id)
    if existing and not force:
        return existing

    classement = score_and_persist(client, course_id)
    sig = signals_mod.build_signals(classement)
    result = analyser(sig, body.paris)

    if existing:
        client.table("analyses_llm_historique").insert(
            {k: existing.get(k) for k in _ARCHIVE_COLS}
        ).execute()
        client.table("analyses_llm").delete().eq("course_id", course_id).execute()

    row = {
        "course_id": course_id,
        "modele": result["modele"],
        "source": result["source"],
        "recommandations": result["recommandations"],
        "lecture_globale": result["lecture_globale"],
        "coup_de_coeur_value": result["coup_de_coeur_value"],
        "input_snapshot": {"signaux": sig, "paris": body.paris},
        "confiance_globale": result["confiance_globale"],
    }
    return client.table("analyses_llm").insert(row).execute().data[0]
```

- [ ] **Step 7: Monter le routeur dans `main.py`**

Dans `backend/app/main.py`, après `from app.scoring.routes import router as scoring_router`, ajouter :

```python
from app.analyse.routes import router as analyse_router
```

et après `app.include_router(scoring_router)`, ajouter :

```python
app.include_router(analyse_router)
```

- [ ] **Step 8: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_analyse_routes.py -q`
Expected: PASS (5 tests).

Run: `cd backend && .venv/bin/pytest -q`
Expected: toute la suite verte.

- [ ] **Step 9: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/analyse/routes.py backend/app/main.py backend/tests/_fake_supabase.py backend/tests/test_scoring_routes.py backend/tests/test_analyse_routes.py
git commit -m "feat(analyse): endpoints get/post/force + persistance + fakes partages"
```

---

### Task 7: Frontend — types `AnalyseIA` + client API

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api.ts`

**Interfaces:**
- Produces : types `Recommandation`, `CoupDeCoeur`, `AnalyseIA` ; `api.getAnalyse(id)`, `api.analyseCourse(id, paris, force)`.

- [ ] **Step 1: Types — `frontend/lib/types.ts`**

Ajouter à la fin du fichier :

```typescript
export type Recommandation = {
  type_pari: string;
  selection: number[];
  base: number[];
  tournant: number[];
  confiance: number;
  niveau: string;
  avis: string;
};

export type CoupDeCoeur = { numero_corde: number; raison: string };

export type AnalyseIA = {
  id: string;
  course_id: string;
  modele: string;
  source: string;
  lecture_globale: string | null;
  recommandations: Recommandation[];
  coup_de_coeur_value: CoupDeCoeur | null;
  confiance_globale: number | null;
  created_at?: string;
};
```

- [ ] **Step 2: Client — `frontend/lib/api.ts`**

Étendre l'import de types en tête : `import type { AnalyseIA, Course, Partant, Programme, ScoreRow } from "./types";`

Puis, dans l'objet `api`, ajouter (après `getProgramme`) :

```typescript
  getAnalyse: (id: string) => req<AnalyseIA>(`/courses/${id}/analyse`),
  analyseCourse: (id: string, paris: string[], force = false) =>
    req<AnalyseIA>(`/courses/${id}/analyse?force=${force}`, {
      method: "POST",
      body: JSON.stringify({ paris }),
    }),
```

- [ ] **Step 3: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (seul l'avertissement pré-existant multiple-lockfiles est toléré).

- [ ] **Step 4: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(plateforme): types AnalyseIA + client getAnalyse/analyseCourse"
```

---

### Task 8: Frontend — composant `AnalyseIA`

**Files:**
- Create: `frontend/components/AnalyseIA.tsx`

**Interfaces:**
- Consumes : types `AnalyseIA`/`Recommandation` (Task 7), `libellePari` (Plan A, `lib/paris`).
- Produces : `AnalyseIA({ analyse, loading, onAnalyser, onReanalyser, disabled })` — état vide + CTA « Analyser », cartes par pari, coup de cœur value, badge source.

- [ ] **Step 1: Créer `frontend/components/AnalyseIA.tsx`**

```tsx
"use client";

import type { AnalyseIA as Analyse, Recommandation } from "@/lib/types";
import { libellePari } from "@/lib/paris";

type Props = {
  analyse: Analyse | null;
  loading: boolean;
  onAnalyser: () => void;
  onReanalyser: () => void;
  disabled: boolean;
};

function niveauClasse(niveau: string): string {
  if (niveau === "eleve") return "bg-green-500";
  if (niveau === "moyen") return "bg-amber-400";
  return "bg-red-400";
}

function Puce({ n, base }: { n: number; base: boolean }) {
  return (
    <span
      className={`inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-xs font-bold tabular-nums ${
        base
          ? "bg-green-600 text-white"
          : "border border-dashed border-green-500 text-green-700"
      }`}
    >
      {n}
    </span>
  );
}

function Carte({ reco }: { reco: Recommandation }) {
  const combine = reco.base.length > 0 || reco.tournant.length > 0;
  const puces = combine
    ? [...reco.base.map((n) => ({ n, base: true })), ...reco.tournant.map((n) => ({ n, base: false }))]
    : reco.selection.map((n) => ({ n, base: true }));
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-extrabold text-slate-900">{libellePari(reco.type_pari)}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-500">
          {reco.niveau}
        </span>
      </div>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {puces.map((p, i) => (
          <Puce key={i} n={p.n} base={p.base} />
        ))}
      </div>
      <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-green-100">
        <div className={`h-full ${niveauClasse(reco.niveau)}`} style={{ width: `${reco.confiance}%` }} />
      </div>
      <p className="text-xs leading-relaxed text-slate-600">{reco.avis}</p>
    </div>
  );
}

export function AnalyseIA({ analyse, loading, onAnalyser, onReanalyser, disabled }: Props) {
  if (loading) {
    return <p className="text-sm text-slate-400">Analyse en cours…</p>;
  }

  if (!analyse) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-4">
        <p className="mb-3 text-sm text-slate-400">Pas encore d'analyse pour cette course.</p>
        <button
          type="button"
          onClick={onAnalyser}
          disabled={disabled}
          className="rounded-full bg-green-600 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
        >
          Analyser cette course
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
            analyse.source === "llm" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {analyse.source === "llm" ? "analyse enregistrée" : "analyse par règles"}
        </span>
        <button
          type="button"
          onClick={onReanalyser}
          disabled={disabled}
          className="text-[11px] font-bold text-slate-500 transition-colors hover:text-green-700 disabled:opacity-50"
        >
          Ré-analyser
        </button>
      </div>

      {analyse.lecture_globale && (
        <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
          {analyse.lecture_globale}
        </p>
      )}

      {analyse.coup_de_coeur_value && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-xs text-green-800">
          <span className="font-extrabold">Value · n°{analyse.coup_de_coeur_value.numero_corde}</span>{" "}
          {analyse.coup_de_coeur_value.raison}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {analyse.recommandations.map((reco) => (
          <Carte key={reco.type_pari} reco={reco} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi (le composant n'est pas encore monté ; le build valide TS/JSX).

- [ ] **Step 3: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/components/AnalyseIA.tsx
git commit -m "feat(plateforme): composant AnalyseIA (cartes paris + value + source)"
```

---

### Task 9: Frontend — câbler `AnalyseIA` dans le dashboard (`page.tsx`)

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes : `api.getAnalyse`/`api.analyseCourse` (Task 7), `AnalyseIA` (Task 8), état `selectedParis`/`courseId` existant.
- Produces : colonne droite = `AnalyseIA` réelle ; récupération persistée à l'ouverture d'une course ; boutons Analyser/Ré-analyser.

- [ ] **Step 1: Importer le composant et les types**

Dans `frontend/app/page.tsx`, ajouter l'import du composant (à côté des autres imports de composants) :

```tsx
import { AnalyseIA } from "@/components/AnalyseIA";
```

et étendre l'import de types pour inclure `AnalyseIA as AnalyseIAType` :

```tsx
import type {
  AnalyseIA as AnalyseIAType,
  Course,
  Partant,
  Programme,
  ProgrammeCourse,
  ProgrammeReunion,
  ScoreRow,
} from "@/lib/types";
```

- [ ] **Step 2: Ajouter l'état + les handlers d'analyse**

Après la déclaration `const [scoring, setScoring] = useState(false);`, ajouter :

```tsx
  const [analyse, setAnalyse] = useState<AnalyseIAType | null>(null);
  const [analyseLoading, setAnalyseLoading] = useState(false);
```

Dans `selectCourse`, après `setClassement(null);` (le reset au début du `try` ou juste avant), réinitialiser l'analyse — ajouter `setAnalyse(null);` dans le bloc de reset (avec les autres `setCourse(null); setPartants([]); setClassement(null);`).

Dans `loadCourse` (le `useCallback`), après avoir chargé le pronostic, tenter de récupérer l'analyse persistée. Remplacer le corps de `loadCourse` par :

```tsx
  const loadCourse = useCallback(async (id: string) => {
    const data = await api.getCourse(id);
    setCourse(data.course);
    setPartants(data.partants);
    setClassement(null);
    setAnalyse(null);
    try {
      const p = await api.getPronostic(id);
      setClassement(p.classement);
    } catch {
      /* pas encore de pronostic — normal */
    }
    try {
      const a = await api.getAnalyse(id);
      setAnalyse(a);
    } catch {
      /* pas encore d'analyse — normal (404) */
    }
  }, []);
```

Ajouter les deux handlers d'analyse (à côté de `handleScore`) :

```tsx
  async function runAnalyse(force: boolean) {
    if (!courseId) return;
    setAnalyseLoading(true);
    setError(null);
    try {
      const a = await api.analyseCourse(courseId, selectedParis, force);
      setAnalyse(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de l'analyse IA.");
    } finally {
      setAnalyseLoading(false);
    }
  }
```

- [ ] **Step 3: Remplacer le placeholder de la colonne droite**

Remplacer tout le bloc `<aside ...>` de la colonne « Analyse IA » (celui contenant `L'analyse IA (paris, confiance, avis) arrive au prochain incrément.`) par :

```tsx
        {/* Colonne droite : analyse IA */}
        <aside className="border-t border-slate-200 bg-slate-50/40 p-4 lg:border-t-0 lg:border-l">
          <div className="mb-2 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Analyse IA
          </div>
          {course ? (
            <AnalyseIA
              analyse={analyse}
              loading={analyseLoading}
              onAnalyser={() => runAnalyse(false)}
              onReanalyser={() => runAnalyse(true)}
              disabled={analyseLoading}
            />
          ) : (
            <p className="text-sm text-slate-400">—</p>
          )}
        </aside>
```

(`libellePari` reste importé pour d'autres usages éventuels ; s'il devient inutilisé et que le lint casse le build, retirer son import.)

- [ ] **Step 4: Vérifier le build**

Run: `cd /Users/alantouati/pronoturf/frontend && npm run build`
Expected: build réussi. Si l'import `libellePari` devient inutilisé et fait échouer le lint, retirer cet import et relancer.

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add frontend/app/page.tsx
git commit -m "feat(plateforme): colonne Analyse IA branchee (persistee + analyser/re-analyser)"
```

---

### Task 10: Vérification bout-en-bout (contrôleur, chemin repli)

**Files:** aucun (vérification).

Prérequis : migration `0004` appliquée (Task 1). Pas de clé Anthropic → l'analyse emprunte le **repli déterministe** (`source="regles"`).

- [ ] **Step 1: Lancer les deux serveurs**

Avant de démarrer, vérifier qu'aucun process ne squatte le port 8000 (`lsof -tiTCP:8000 -sTCP:LISTEN` ; tuer si besoin).

```bash
cd /Users/alantouati/pronoturf/backend && .venv/bin/uvicorn app.main:app --port 8000   # A (arrière-plan)
cd /Users/alantouati/pronoturf/frontend && npm run dev                                  # B (arrière-plan)
```

- [ ] **Step 2: Vérifier le contrat HTTP réel (ce que le front appelle)**

Sur une course listée par `GET /programme/14072026` (ex. R1C3, Quinté+) :
1. `POST /courses/import` (date+R+C) → `course_id`.
2. `GET /courses/{id}/analyse` (avec `Origin: http://localhost:3000`) → **404** (aucune analyse encore).
3. `POST /courses/{id}/analyse` corps `{"paris": ["QUINTE_PLUS","SIMPLE_GAGNANT","TRIO"]}` → 200 ; vérifier `source == "regles"`, `recommandations` non vide (uniquement les paris ∈ ANALYSABLE), `input_snapshot.paris` conservé, `coup_de_coeur_value` présent ou `null` cohérent.
4. `GET /courses/{id}/analyse` → 200, **même** analyse (retrouvée sans re-payer).
5. `POST /courses/{id}/analyse?force=true` même corps → 200 ; nouvelle ligne courante (id différent) ; l'ancienne est archivée dans `analyses_llm_historique` (vérif Supabase ou via une 2e ré-analyse).

- [ ] **Step 3: Vérifier le rendu** (contrôle visuel utilisateur — pas d'outil navigateur dans l'env)

Ouvrir http://localhost:3000 : sélectionner une course → colonne droite « Analyse IA » avec le bouton **Analyser cette course** ; cliquer → cartes par pari (Quinté+ en tête si présent), puces base (plein vert)/tournant (pointillé), barre de confiance + niveau, avis, éventuel encart Value ; badge **analyse par règles** ; bouton **Ré-analyser**. Recharger la page / re-sélectionner la course → l'analyse revient sans nouvel appel (persistée).

- [ ] **Step 4: Corriger tout écart** (câblage, CORS, forme des données) et re-vérifier. Arrêter les serveurs.

---

## Ce que ce plan produit

La colonne « Analyse IA » est fonctionnelle : à l'ouverture d'une course, l'analyse persistée est affichée sans coût ; un bouton la génère (repli déterministe tant que la clé Anthropic n'est pas fournie, chemin Opus 4.8 prêt sinon), avec sélections ancrées sur nos signaux value, confiance 0–100 + niveau, avis et coup de cœur value. Les analyses sont stockées (entrée + sortie) et retrouvées sans re-payer ; la ré-analyse archive l'historique — jeu de données prêt pour le futur Plan C (calibration/backtest).

## Hors périmètre (Plan B)

- Vrai appel Opus 4.8 vérifié E2E (nécessite la clé — testé plus tard ; le chemin est codé et couvert par un test unitaire mocké).
- Calibration statistique de la confiance / vraies probabilités → **Plan C** (backtest).
- Analyse des paris hors sous-ensemble `ANALYSABLE` (Multi, Pick5, Super Quatre…).
- Recherche cheval/jockey, prise de pari réelle, auth/déploiement.
