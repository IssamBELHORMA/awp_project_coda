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
