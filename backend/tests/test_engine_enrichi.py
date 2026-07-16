from app.scoring.engine import score_course
from app.scoring.ponderations import DEFAULT_PONDERATIONS

CTX = {"distance_m": 1400, "allocation": 20000, "hippodrome": "DIEPPE"}


def _partant(corde, nb_perfs, jockey_taux=None, entraineur_taux=None):
    perfs = [{"place": 1, "distance_m": 1400, "discipline": "plat", "allocation": 20000, "hippodrome": "DIEPPE"}] * nb_perfs
    return {"numero_corde": corde, "statut": "partant", "cote_valeur": 4.0, "poids_kg": 56.0,
            "musique": "1p1p1p", "nombre_courses": 10, "nombre_victoires": 5, "nombre_places": 3,
            "place_corde": corde, "performances": perfs,
            "jockey_taux": jockey_taux, "entraineur_taux": entraineur_taux}


def test_score_course_adds_confidence_and_history_count():
    rows = score_course([_partant(1, nb_perfs=12, jockey_taux=0.4, entraineur_taux=0.5),
                          _partant(2, nb_perfs=0)], "plat", DEFAULT_PONDERATIONS["plat"], CTX)
    by_corde = {r["numero_corde"]: r for r in rows}
    assert by_corde[1]["nb_courses_historique"] == 12
    assert by_corde[1]["confiance"] == 1.0                 # >=10 perfs, jockey+entraineur connus
    assert by_corde[2]["nb_courses_historique"] == 0
    assert by_corde[2]["confiance"] == 0.0


def test_score_course_weights_still_sum_to_one():
    rows = score_course([_partant(1, nb_perfs=5), _partant(2, nb_perfs=5)],
                        "plat", DEFAULT_PONDERATIONS["plat"], CTX)
    for r in rows:
        assert abs(sum(d["poids_effectif"] for d in r["details_facteurs"].values()) - 1.0) < 1e-9


def test_no_history_horse_weights_sum_to_one_over_base_factors_only():
    # Un cheval sans historique de perfs n'a que les 5 facteurs de base + taux_discipline
    # (celui-ci vient désormais de la musique "1p1p1p", 3 courses plat toutes top-3), et
    # les poids doivent être redistribués pour sommer à 1 -> pas de dilution.
    rows = score_course([_partant(1, nb_perfs=0)], "plat", DEFAULT_PONDERATIONS["plat"], CTX)
    details = rows[0]["details_facteurs"]
    assert set(details.keys()) == {"forme", "taux_reussite", "ferrage_poids", "cote", "corde",
                                    "taux_discipline"}
    assert abs(sum(d["poids_effectif"] for d in details.values()) - 1.0) < 1e-9
