from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import data

APP = str(Path(__file__).parent.parent / "app.py")
MODES = ["Par patch", "Tous patchs confondus"]


def lancer() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def valeurs_metriques(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


# ---------- Tests de l'appli ----------


def test_changer_de_rang_change_les_indicateurs():
    at = lancer()
    assert not at.exception
    gold = valeurs_metriques(at)

    at.multiselect(key="f_rang").set_value(["Master"]).run()
    assert not at.exception
    master = valeurs_metriques(at)

    assert list(gold) == [
        "Parties",
        "Champions distincts",
        "Champion le plus joué",
        "Meilleur champion",
    ]
    # Au mid : Gold -> Akali la plus jouée, Master -> Syndra
    assert gold["Parties"] != master["Parties"]
    assert gold["Champions distincts"] != master["Champions distincts"]
    assert gold["Champion le plus joué"] != master["Champion le plus joué"]
    assert gold["Meilleur champion"] != master["Meilleur champion"]


def test_vue_vide_affiche_un_avertissement():
    at = lancer()
    at.multiselect(key="f_rang").set_value([]).run()
    assert at.warning
    assert not at.metric


@pytest.mark.parametrize("rang", ["Grandmaster", "Challenger", "Iron"])
@pytest.mark.parametrize("mode", MODES)
def test_petits_rangs_sans_erreur(rang, mode):
    """Un rang où aucun champion n'atteint le minimum ne doit pas planter."""
    at = lancer()
    at.multiselect(key="f_rang").set_value([rang]).run()
    at.radio(key="f_mode").set_value(mode).run()
    assert not at.exception


def test_changer_de_champion_dans_le_zoom():
    at = lancer()
    choix = at.selectbox(key="f_champion")
    autre = choix.options[-1]
    choix.set_value(autre).run()
    assert not at.exception
    assert at.selectbox(key="f_champion").value == autre


def test_le_champion_suit_les_filtres():
    """Si le champion choisi sort de la vue, le zoom revient à un champion valide."""
    at = lancer()
    at.multiselect(key="f_poste").set_value(["SUPPORT"]).run()
    assert not at.exception
    choix = at.selectbox(key="f_champion")
    assert choix.value in choix.options


def test_section_composition_gold_et_challenger():
    """La section composition et bans s'affiche en Gold et ne plante pas en
    Challenger (où aucun champion n'atteint 50 parties à un poste)."""
    at = lancer()
    assert not at.exception
    titres = [m.value for m in at.markdown]
    assert any("la composition la plus sûre" in t for t in titres)
    assert any("Ban 1" in t for t in titres)

    at.multiselect(key="f_rang").set_value(["Challenger"]).run()
    assert not at.exception
    assert any("Composition" in s.value for s in at.subheader)


# ---------- Tests de data.py ----------


@pytest.fixture(scope="module")
def df():
    return data.charger()


def test_filtrer_ne_garde_que_les_valeurs_choisies(df):
    vue = data.filtrer(df, rangs=["Gold"], postes=["MIDDLE"])
    assert len(vue) > 0
    assert set(vue["rang"].astype(str)) == {"Gold"}
    assert set(vue["poste"].astype(str)) == {"MIDDLE"}


def test_stats_champions_respecte_le_minimum(df):
    stats = data.stats_champions(data.filtrer(df, rangs=["Gold"]), n_min=50)
    assert (stats["parties"] >= 50).all()
    assert stats["taux_victoire"].is_monotonic_decreasing


def test_indicateurs_coherents(df):
    vue = data.filtrer(df, rangs=["Gold"], postes=["MIDDLE"])
    ind = data.indicateurs(vue, n_min=50)
    compte = vue["champion"].value_counts()
    assert ind["champions"] == int((compte > 0).sum())
    assert 0 < ind["champions_assez_joues"] <= ind["champions"]
    assert ind["plus_joue"] == compte.index[0]
    assert ind["plus_joue_parties"] == compte.iloc[0]
    assert ind["meilleur_parties"] >= 50


def test_intervalle_encadre_le_taux_et_se_resserre():
    bas, haut = data.intervalle([15, 150], [30, 300])
    assert (bas < 0.5).all() and (haut > 0.5).all()
    assert (haut[1] - bas[1]) < (haut[0] - bas[0])


def test_meilleurs_par_patch_poste_peut_etre_vide(df):
    vue = data.filtrer(df, rangs=["Challenger"])
    assert data.meilleurs_par_patch_poste(vue, n_min=200).empty


def test_par_duree_compte_toutes_les_parties(df):
    vue = data.filtrer(df, rangs=["Gold"], postes=["MIDDLE"])
    champion = data.champions_joues(vue)[0]
    stats = data.par_duree(vue, champion)
    assert stats["parties"].sum() == (vue["champion"] == champion).sum()


def test_effectifs_rangs_somme_a_100(df):
    eff = data.effectifs_rangs(df)
    assert eff["part"].sum() == pytest.approx(1)
    assert eff["rang"].tolist() == [r for r in data.RANGS if r in set(eff["rang"])]


def test_formulaire_et_si_affiche_une_probabilite():
    at = lancer()
    at.button(key="FormSubmitter:form_et_si-Estimer").click().run()
    assert not at.exception
    chances = [m for m in at.metric if m.label == "Chances de victoire"]
    assert len(chances) == 1
    valeur = float(chances[0].value.replace("\u00a0%", "").replace(",", "."))
    assert 0 < valeur < 100


def test_modele_renvoie_une_probabilite():
    import modele

    p = modele.predire(modele.charger_modele(), "Ahri", "Zed", "MIDDLE", "Gold")
    assert 0 < p < 1
    assert modele.charger_metriques()["auc"] > 0.5


def test_assistant_sans_api_affiche_un_message(monkeypatch):
    """Si l'API ne répond pas, la page reste utilisable et le dit."""
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")
    at = lancer()
    at.chat_input(key="chat_question").set_value("Quel main en Gold mid ?").run()
    assert not at.exception
    textes = [m.value for m in at.sidebar.markdown] + [m.value for m in at.markdown]
    assert any("ne répond pas" in v for v in textes)


def test_api_routes_donnees():
    from fastapi.testclient import TestClient

    import api

    client = TestClient(api.app)
    assert client.get("/sante").json()["statut"] == "ok"
    meilleurs = client.get("/meilleurs", params={"rang": "Master", "poste": "MIDDLE"})
    assert meilleurs.status_code == 200
    assert all(c["parties"] >= 50 for c in meilleurs.json()["meilleurs"])
    prediction = client.post(
        "/predire",
        json={
            "champion": "Ahri",
            "adversaire": "Zed",
            "poste": "MIDDLE",
            "rang": "Gold",
        },
    )
    assert 0 < prediction.json()["probabilite_victoire"] < 1
    assert client.get("/champion/ChampionInexistant").status_code == 404


def test_composition_un_champion_par_poste(df):
    vue = data.filtrer(df, rangs=["Master"])
    compo = data.composition_ideale(vue, n_min=50)
    retenus = compo[compo["place"] == 1]
    assert retenus["poste"].tolist() == data.POSTES
    assert (compo["parties"] >= 50).all()
    # Dans chaque poste, la place 1 a la meilleure borne basse
    for _, groupe in compo.groupby("poste"):
        assert groupe["ic_bas"].is_monotonic_decreasing


def test_bans_excluent_notre_composition(df):
    vue = data.filtrer(df, rangs=["Master"])
    compo = data.composition_ideale(vue, n_min=50)
    nos_champions = compo.loc[compo["place"] == 1, "champion"].tolist()
    bans = data.bans_conseilles(vue, n_min=50, exclure=nos_champions)
    assert len(bans) == 5
    assert not set(bans["champion"]) & set(nos_champions)
    assert bans["ic_bas"].is_monotonic_decreasing
