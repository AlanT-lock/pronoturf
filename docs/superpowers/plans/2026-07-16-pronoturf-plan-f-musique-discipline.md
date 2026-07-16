# Plan F — `taux_discipline` depuis la musique — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alimenter le facteur contextuel `taux_discipline` depuis la **musique** (~10-15 courses passées, place+discipline) au lieu de `chevaux_performances` (~1 course), pour qu'il discrimine enfin au lieu d'être omis/redistribué.

**Architecture:** Étendre `app/scoring/musique.py` (capturer la lettre de discipline, `parse_musique_disciplines` + `taux_discipline_musique` avec les seuils existants de `context_stats`) ; re-brancher `factors.py` (`tdi = taux_discipline_musique(p.get("musique"), discipline)`). `parse_musique`/`forme_score` inchangés. Pur backend, aucune migration.

**Tech Stack :** FastAPI + pytest (TDD).

**Réf. spec :** `docs/superpowers/specs/2026-07-15-pronoturf-plan-f-musique-discipline-design.md`.

## Global Constraints

- Mapping lettres (minuscule) → enum : `a`→`trot_attele`, `m`→`trot_monte`, `p`→`plat`, `h`/`s`/`c`/`o`→`obstacle`, autre → `None` (course exclue du calcul par discipline).
- Seuils **réutilisés** depuis `context_stats` (imports, pas de copie) : succès = place ≤ `SUCCESS_MAX_PLACE` (3) ; `None` si < `MIN_SAMPLE` (3) courses dans la discipline. DNF (place `None`) compte au dénominateur, pas au numérateur. Taux simple (pas de pondération récence).
- **Piège à éviter** : `discipline=None` ne doit PAS matcher les courses à discipline inconnue (`d == discipline` avec les deux à `None`) → garde explicite `if discipline is None: return None`.
- `parse_musique` et `forme_score` **inchangés** (comportement identique — `_PERF_RE` gagne un 2e groupe de capture mais `group(1)` ne bouge pas).
- Les 3 autres facteurs contextuels (distance/niveau/hippodrome) restent sur `chevaux_performances`. `context_stats.taux_discipline` reste en place (plus appelé par le scoring).
- Gate : `cd backend && .venv/bin/pytest` — **toute la suite** verte (150 tests avant plan).
- TDD strict.

## Structure des fichiers

- `backend/app/scoring/musique.py` — **modifier** : regex 2 groupes, `_DISCIPLINE_LETTRE`, `parse_musique_disciplines`, `taux_discipline_musique`.
- `backend/app/scoring/factors.py` — **modifier** : import + re-branchement `tdi`.
- `backend/tests/test_musique.py` — **modifier** : nouveaux tests (les tests existants restent inchangés et verts).
- `backend/tests/test_factors_enrichi.py` — **modifier** : adapter le test « no data » (impacté par le changement de source, voulu) + nouveau test « taux_discipline vient de la musique ».

---

### Task 1: Étendre `musique.py` (parse disciplines + taux)

**Files:**
- Modify: `backend/app/scoring/musique.py`
- Test: `backend/tests/test_musique.py`

**Interfaces:**
- Produces : `parse_musique_disciplines(musique) -> list[tuple[Optional[int], Optional[str]]]` ; `taux_discipline_musique(musique, discipline) -> float | None` ; constante `_DISCIPLINE_LETTRE`. Consommés par Task 2.

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à la fin de `backend/tests/test_musique.py` (imports en tête si absents : `from app.scoring.musique import parse_musique_disciplines, taux_discipline_musique`) :

```python
def test_parse_disciplines_musique_reelle():
    # JAINA D'ESSARTS : 9 courses attelé, places 3,1,1,3,7 puis 3 disqualifications puis 2e.
    out = parse_musique_disciplines("3a1a1a3a7a(25)DaDaDa2a")
    assert len(out) == 9
    assert all(d == "trot_attele" for _, d in out)
    assert [p for p, _ in out] == [3, 1, 1, 3, 7, None, None, None, 2]


def test_parse_disciplines_mapping_complet():
    out = parse_musique_disciplines("1a2m3p4h5s6c7o")
    assert [d for _, d in out] == [
        "trot_attele", "trot_monte", "plat",
        "obstacle", "obstacle", "obstacle", "obstacle",
    ]


def test_parse_disciplines_lettre_inconnue_et_vide():
    assert parse_musique_disciplines("1x2a") == [(1, None), (2, "trot_attele")]
    assert parse_musique_disciplines(None) == []
    assert parse_musique_disciplines("") == []


def test_taux_discipline_musique_calcule():
    # 9 courses attelé : top-3 = 3,1,1,3,2 -> 5 succès ; Da (None) au dénominateur.
    assert abs(taux_discipline_musique("3a1a1a3a7a(25)DaDaDa2a", "trot_attele") - 5 / 9) < 1e-9


def test_taux_discipline_musique_dnf_au_denominateur():
    assert abs(taux_discipline_musique("1aDaDa", "trot_attele") - 1 / 3) < 1e-9


def test_taux_discipline_musique_gates():
    # Mauvaise discipline (0 course de plat) -> None.
    assert taux_discipline_musique("3a1a1a3a7a", "plat") is None
    # Sous MIN_SAMPLE (2 courses attelé) -> None.
    assert taux_discipline_musique("1a2a", "trot_attele") is None
    # discipline None ne matche PAS les lettres inconnues.
    assert taux_discipline_musique("1x2x3x", None) is None
    assert taux_discipline_musique(None, "plat") is None
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_musique.py -q`
Expected: FAIL (`ImportError: cannot import name 'parse_musique_disciplines'`).

- [ ] **Step 3: Implémenter dans `app/scoring/musique.py`**

Changer la regex (le groupe 1 ne bouge pas — `parse_musique` intact) :

```python
_PERF_RE = re.compile(r"([0-9DTARdtar])([a-zA-Z])")
```

Ajouter l'import en tête : `from app.scoring.context_stats import MIN_SAMPLE, SUCCESS_MAX_PLACE`
(pas de cycle : `context_stats` n'importe rien du package scoring).

Ajouter à la fin du fichier :

```python
# Lettre de discipline de la musique -> discipline de scoring. Lettre inconnue -> None.
_DISCIPLINE_LETTRE = {
    "a": "trot_attele", "m": "trot_monte", "p": "plat",
    "h": "obstacle", "s": "obstacle", "c": "obstacle", "o": "obstacle",
}


def parse_musique_disciplines(musique: Optional[str]) -> list[tuple[Optional[int], Optional[str]]]:
    """Comme parse_musique, mais conserve la discipline de chaque course passée."""
    if not musique:
        return []
    cleaned = re.sub(r"\([^)]*\)", "", musique)
    out: list[tuple[Optional[int], Optional[str]]] = []
    for match in _PERF_RE.finditer(cleaned):
        result = match.group(1).upper()
        place = int(result) if result.isdigit() and result != "0" else None
        out.append((place, _DISCIPLINE_LETTRE.get(match.group(2).lower())))
    return out


def taux_discipline_musique(musique: Optional[str], discipline: Optional[str]) -> Optional[float]:
    """Taux de top-3 sur les courses de la musique courues dans `discipline`.

    Mêmes règles que context_stats : None si < MIN_SAMPLE courses dans la discipline ;
    DNF (place None) compte au dénominateur, pas au numérateur.
    """
    if discipline is None:
        return None  # sans cette garde, d == discipline matcherait les lettres inconnues
    places = [p for p, d in parse_musique_disciplines(musique) if d == discipline]
    if len(places) < MIN_SAMPLE:
        return None
    succes = sum(1 for p in places if p is not None and p <= SUCCESS_MAX_PLACE)
    return succes / len(places)
```

- [ ] **Step 4: Lancer (vert) + non-régression musique**

Run: `cd backend && .venv/bin/pytest tests/test_musique.py -q`
Expected: PASS (tous — anciens tests `parse_musique`/`forme_score` inclus).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/musique.py backend/tests/test_musique.py
git commit -m "feat(scoring): parse discipline de la musique + taux_discipline_musique"
```

---

### Task 2: Re-brancher `factors.py` + adapter les tests impactés

**Files:**
- Modify: `backend/app/scoring/factors.py`, `backend/tests/test_factors_enrichi.py`

**Interfaces:**
- Consumes : `taux_discipline_musique` (Task 1).
- Produces : `compute_factors` calcule `taux_discipline` depuis `p["musique"]` (signature inchangée).

**Impact tests connu (voulu, analysé)** : dans `test_factors_enrichi.py`, `_partant` a `musique="1p2p3p"` (3 courses plat, toutes top-3 → taux 1.0). Le test `test_no_data_factors_are_omitted_not_neutral` (perfs=[]) attend `taux_discipline` ABSENT — il sera désormais PRÉSENT (1.0 depuis la musique). C'est le comportement cible : adapter ce test + en ajouter un qui verrouille la nouvelle source.

- [ ] **Step 1: Adapter/ajouter les tests (rouges sur le code actuel)**

Dans `backend/tests/test_factors_enrichi.py` :

1. Donner un paramètre musique à `_partant` — remplacer sa signature et la ligne musique :

```python
def _partant(corde, place_corde=None, perfs=None, jockey_taux=None, entraineur_taux=None,
             musique="1p2p3p"):
    return {"numero_corde": corde, "statut": "partant", "cote_valeur": 5.0, "poids_kg": 56.0,
            "musique": musique, "nombre_courses": 10, "nombre_victoires": 3, "nombre_places": 4,
            "place_corde": place_corde, "performances": perfs or [], "ferrage": None,
            "jockey_taux": jockey_taux, "entraineur_taux": entraineur_taux}
```

2. Dans `test_no_data_factors_are_omitted_not_neutral`, remplacer la 1re ligne par
   `factors = compute_factors([_partant(1, perfs=[], musique="1p2p")], "plat", CTX)`
   (2 courses plat < MIN_SAMPLE → les 6 facteurs restent bien absents ; la sémantique
   « pas assez de données → omis » du test est conservée).

3. Ajouter à la fin du fichier :

```python
def test_taux_discipline_vient_de_la_musique_sans_perfs():
    # perfs vides (cas réel PMU ~1 course) mais musique fournie : 1p2p3p = 3 plat, tous top-3.
    factors = compute_factors([_partant(1, perfs=[])], "plat", CTX)
    assert factors[1]["taux_discipline"] == 1.0
    # mauvaise discipline dans la musique -> facteur omis
    factors = compute_factors([_partant(1, perfs=[], musique="1a2a3a")], "plat", CTX)
    assert "taux_discipline" not in factors[1]
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `cd backend && .venv/bin/pytest tests/test_factors_enrichi.py -q`
Expected: FAIL (`test_taux_discipline_vient_de_la_musique_sans_perfs` — le facteur vient encore des perfs).

- [ ] **Step 3: Re-brancher `factors.py`**

Dans `backend/app/scoring/factors.py` :
- Changer l'import : `from app.scoring.musique import forme_score, taux_discipline_musique`
- Remplacer les lignes

```python
        tdi = cs.taux_discipline(perfs, discipline)
```

par

```python
        tdi = taux_discipline_musique(p.get("musique"), discipline)
```

(le `if tdi is not None: f["taux_discipline"] = tdi` qui suit est inchangé).

- [ ] **Step 4: Lancer (vert) + suite complète**

Run: `cd backend && .venv/bin/pytest tests/test_factors_enrichi.py tests/test_factors.py -q`
Expected: PASS. Note : `test_factors.py` utilise `musique="1a1a1a"` avec discipline `"plat"` (0 course plat → facteur omis, comme avant) et un cas `"trot_attele"` où `taux_discipline=1.0` peut APPARAÎTRE — ses assertions portent sur `ferrage_poids`/valeurs relatives, pas sur l'ensemble exact des clés ; si une assertion d'ensemble échoue, l'adapter en ajoutant la clé attendue (comportement cible, pas un bug).

Run: `cd backend && .venv/bin/pytest -q`
Expected: toute la suite verte (~152).

- [ ] **Step 5: Commit**

```bash
cd /Users/alantouati/pronoturf
git add backend/app/scoring/factors.py backend/tests/test_factors_enrichi.py
git commit -m "feat(scoring): taux_discipline alimente depuis la musique (profonde) au lieu des perfs"
```

---

### Task 3: Vérification bout-en-bout (contrôleur)

**Files:** aucun (vérification).

- [ ] **Step 1: E2E réel** — via TestClient in-process (pas besoin de serveurs) : sur une course trot réelle déjà en base (ex. R1C8 du 15/07, chevaux à musique ~9 courses attelé), `POST /courses/{id}/score` → vérifier que `details_facteurs` contient `taux_discipline` **non-neutre** (≠ omis) pour les chevaux à musique fournie, valeur ∈ [0,1], Σ contributions == score_total, Σ poids effectifs == 1. Comparer un cheval à musique riche vs un cheval sans musique (facteur omis → redistribution).

- [ ] **Step 2: Non-régression prod-parity** — suite complète verte ; `GET /backtest` continue de répondre (le classement change de valeurs, pas de forme).

- [ ] **Step 3: Déploiement** — après merge dans `main` : `cd backend && vercel deploy --prod` (les projets Vercel ne sont pas git-connectés ; cf. mémoire [vercel-deployment]). Vérifier `https://pronoturf-api.vercel.app/health` puis un `POST /score` réel en prod.

---

## Ce que ce plan produit

Le facteur `taux_discipline` discrimine enfin : alimenté par ~10-15 courses de la musique au lieu d'~1 course structurée, il est présent pour la quasi-totalité des partants (au lieu d'être omis/redistribué). 1 des 4 facteurs contextuels débloqué sans source externe, sans migration, sans CGU. Les 3 autres attendent Aspiturf.

## Hors périmètre

- distance/hippodrome/niveau (→ Aspiturf), pondération récence, front (aucun changement de forme d'API).
