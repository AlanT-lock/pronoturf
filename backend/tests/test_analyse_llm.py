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
