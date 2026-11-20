from pathlib import Path

from streamlit.testing.v1 import AppTest

import data

APP = str(Path(__file__).parent.parent / "app.py")


def valeurs_metriques(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


def test_changer_de_rang_change_les_indicateurs():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    gold = valeurs_metriques(at)

    at.multiselect(key="f_rang").set_value(["Master"]).run()
    assert not at.exception
    master = valeurs_metriques(at)

    assert gold["Parties"] != master["Parties"]
    assert gold["Taux de victoire moyen"] != master["Taux de victoire moyen"]


def test_vue_vide_affiche_un_avertissement():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.multiselect(key="f_rang").set_value([]).run()
    assert at.warning
    assert not at.metric


def test_filtrer_ne_garde_que_les_valeurs_choisies():
    df = data.charger()
    vue = data.filtrer(df, rangs=["Gold"], postes=["MIDDLE"])
    assert len(vue) > 0
    assert set(vue["rang"].astype(str)) == {"Gold"}
    assert set(vue["poste"].astype(str)) == {"MIDDLE"}


def test_stats_champions_respecte_le_minimum():
    df = data.filtrer(data.charger(), rangs=["Gold"])
    stats = data.stats_champions(df, n_min=50)
    assert (stats["parties"] >= 50).all()
    assert stats["taux_victoire"].is_monotonic_decreasing
