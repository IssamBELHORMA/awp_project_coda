"""Fonctions de calcul de LoL Helper : pandas pur, aucune ligne Streamlit."""

from pathlib import Path

import numpy as np
import pandas as pd

CHEMIN = Path(__file__).parent / "Data" / "processed" / "joueurs.parquet"

POSTES = ["TOP", "JUNGLE", "MIDDLE", "ADC", "SUPPORT"]
RANGS = [
    "Iron",
    "Bronze",
    "Silver",
    "Gold",
    "Platinum",
    "Emerald",
    "Diamond",
    "Master",
    "Grandmaster",
    "Challenger",
]
REGIONS = ["EUW1", "NA1", "KR"]

# Tranches de durée (quartiles des parties : 27 et 35 min environ)
BORNES_DUREE = [0, 27, 35, np.inf]
TRANCHES_DUREE = ["Moins de 27 min", "27 à 35 min", "Plus de 35 min"]

Z = 1.96  # intervalle de confiance à 95 %


def cle_patch(patch: str) -> tuple[int, ...]:
    """'15.19' -> (15, 19), pour trier les patchs dans l'ordre du jeu."""
    return tuple(int(x) for x in str(patch).split("."))


def charger() -> pd.DataFrame:
    """Lit le Parquet préparé par prep.py."""
    return pd.read_parquet(CHEMIN)


def liste_patchs(df: pd.DataFrame) -> list[str]:
    """Les patchs présents, dans l'ordre chronologique."""
    return sorted(df["patch"].astype(str).unique(), key=cle_patch)


def filtrer(
    df: pd.DataFrame,
    rangs: list[str] | None = None,
    postes: list[str] | None = None,
    regions: list[str] | None = None,
    patchs: list[str] | None = None,
) -> pd.DataFrame:
    """Applique les filtres. Un filtre à None n'est pas appliqué."""
    masque = pd.Series(True, index=df.index)
    for col, valeurs in [
        ("rang", rangs),
        ("poste", postes),
        ("region", regions),
        ("patch", patchs),
    ]:
        if valeurs is not None:
            masque &= df[col].isin(valeurs)
    return df[masque]


def intervalle(victoires, parties, z: float = Z) -> tuple[np.ndarray, np.ndarray]:
    """Intervalle de Wilson du taux de victoire (bornes entre 0 et 1).

    Plus il y a de parties, plus l'intervalle est étroit : c'est ce qui dit
    si un taux de victoire est fiable.
    """
    n = np.asarray(parties, dtype=float)
    p = np.asarray(victoires, dtype=float) / n
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    demi = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return centre - demi, centre + demi


def agreger(vue: pd.DataFrame, cles: list[str]) -> pd.DataFrame:
    """Parties, victoires, taux de victoire et intervalle par groupe."""
    stats = (
        vue.groupby(cles, observed=True)["victoire"]
        .agg(parties="size", victoires="sum")
        .reset_index()
    )
    stats["taux_victoire"] = stats["victoires"] / stats["parties"]
    stats["ic_bas"], stats["ic_haut"] = intervalle(stats["victoires"], stats["parties"])
    for col in cles:
        stats[col] = stats[col].astype(str)
    return stats


def stats_champions(
    vue: pd.DataFrame, n_min: int = 0, par: list[str] | None = None
) -> pd.DataFrame:
    """Parties et taux de victoire par champion (et par poste, patch… si `par`).

    Ne garde que les groupes d'au moins `n_min` parties, triés du meilleur
    taux de victoire au moins bon.
    """
    par = par or []
    stats = agreger(vue, [*par, "champion"])
    stats = stats[stats["parties"] >= n_min]
    return stats.sort_values(
        [*par, "taux_victoire", "parties"],
        ascending=[*([True] * len(par)), False, False],
    ).reset_index(drop=True)


def indicateurs(vue: pd.DataFrame, n_min: int) -> dict:
    """Les 4 indicateurs du haut de page, calculés sur la vue filtrée.

    Parties, champions distincts (dont ceux qui ont au moins `n_min` parties),
    champion le plus joué et meilleur champion (parmi ceux qui ont `n_min`
    parties).
    """
    tous = stats_champions(vue)
    stats = tous[tous["parties"] >= n_min]
    meilleur = stats.iloc[0] if len(stats) else None
    joue = tous.sort_values("parties", ascending=False, kind="stable")
    plus_joue = joue.iloc[0] if len(joue) else None
    return {
        "parties": int(vue["match_id"].nunique()),
        "taux_victoire": float(vue["victoire"].mean()) if len(vue) else float("nan"),
        "champions": len(tous),
        "champions_assez_joues": len(stats),
        "plus_joue": None if plus_joue is None else str(plus_joue["champion"]),
        "plus_joue_parties": 0 if plus_joue is None else int(plus_joue["parties"]),
        "plus_joue_part": (
            0.0 if plus_joue is None else float(plus_joue["parties"] / len(vue))
        ),
        "meilleur_champion": None if meilleur is None else str(meilleur["champion"]),
        "meilleur_taux": None if meilleur is None else float(meilleur["taux_victoire"]),
        "meilleur_parties": None if meilleur is None else int(meilleur["parties"]),
    }


def meilleurs_par_patch_poste(
    vue: pd.DataFrame, n_min: int, top: int = 5
) -> pd.DataFrame:
    """Le top `top` des champions par patch et par poste (graphique principal).

    Colonne `place` : 1 pour le meilleur champion du couple (patch, poste).
    Peut être vide si aucun champion n'atteint `n_min` parties.
    """
    stats = stats_champions(vue, n_min, par=["patch", "poste"])
    stats["place"] = stats.groupby(["patch", "poste"]).cumcount() + 1
    return stats[stats["place"] <= top].reset_index(drop=True)


def meilleurs_par_poste(vue: pd.DataFrame, n_min: int, top: int = 5) -> pd.DataFrame:
    """Le top `top` des champions par poste, tous patchs confondus."""
    stats = stats_champions(vue, n_min, par=["poste"])
    stats["place"] = stats.groupby("poste").cumcount() + 1
    return stats[stats["place"] <= top].reset_index(drop=True)


def fiabilite(vue: pd.DataFrame, n_plancher: int = 10) -> tuple[pd.DataFrame, float]:
    """Chaque champion avec son intervalle, comparé au taux moyen de la vue.

    `au_dessus` : tout l'intervalle est au-dessus de la moyenne, l'écart
    n'est donc pas dû au hasard (au seuil de 95 %).
    """
    moyenne = float(vue["victoire"].mean())
    stats = stats_champions(vue, n_plancher)
    stats["au_dessus"] = stats["ic_bas"] > moyenne
    stats["en_dessous"] = stats["ic_haut"] < moyenne
    return stats, moyenne


def bande_hasard(moyenne: float, n_max: int, n_debut: int = 10) -> pd.DataFrame:
    """La zone où tombe un champion « moyen » par simple hasard, selon ses parties."""
    n = np.unique(np.geomspace(n_debut, max(n_max, n_debut + 1), 80).round())
    demi = Z * np.sqrt(moyenne * (1 - moyenne) / n)
    return pd.DataFrame({"parties": n, "bas": moyenne - demi, "haut": moyenne + demi})


def champions_joues(vue: pd.DataFrame) -> list[str]:
    """Les champions de la vue, du plus joué au moins joué."""
    compte = vue["champion"].value_counts()
    return [str(c) for c in compte[compte > 0].index]


def par_rang(vue_tous_rangs: pd.DataFrame, champion: str) -> pd.DataFrame:
    """Taux de victoire d'un champion à chaque rang (Iron -> Challenger)."""
    stats = agreger(vue_tous_rangs[vue_tous_rangs["champion"] == champion], ["rang"])
    stats["ordre"] = stats["rang"].map(RANGS.index)
    return stats.sort_values("ordre").drop(columns="ordre").reset_index(drop=True)


def par_duree(vue: pd.DataFrame, champion: str) -> pd.DataFrame:
    """Taux de victoire d'un champion selon la durée de la partie."""
    sous = vue[vue["champion"] == champion]
    sous = sous.assign(
        duree=pd.cut(
            sous["duree_min"], BORNES_DUREE, labels=TRANCHES_DUREE, right=False
        )
    )
    stats = agreger(sous, ["duree"])
    stats["ordre"] = stats["duree"].map(TRANCHES_DUREE.index)
    return stats.sort_values("ordre").drop(columns="ordre").reset_index(drop=True)


def parties(vue: pd.DataFrame, champion: str) -> pd.DataFrame:
    """Le détail des parties d'un champion, prêt à afficher."""
    sous = vue[vue["champion"] == champion]
    detail = pd.DataFrame(
        {
            "Patch": sous["patch"].astype(str),
            "Région": sous["region"].astype(str),
            "Rang": sous["rang"].astype(str),
            "Poste": sous["poste"].astype(str),
            "Adversaire": sous["adversaire"].astype(str),
            "Résultat": np.where(sous["victoire"] == 1, "Victoire", "Défaite"),
            "K / D / A": (
                sous["kills"].astype(str)
                + " / "
                + sous["deaths"].astype(str)
                + " / "
                + sous["assists"].astype(str)
            ),
            "KDA": sous["kda"],
            "CS": sous["cs"],
            "Or": sous["or_total"],
            "Durée (min)": sous["duree_min"],
        }
    )
    # Du patch le plus récent au plus ancien
    rang_patch = detail["Patch"].map(lambda p: cle_patch(p)[0] * 100 + cle_patch(p)[1])
    return (
        detail.assign(_ordre=rang_patch)
        .sort_values("_ordre", ascending=False, kind="stable")
        .drop(columns="_ordre")
        .reset_index(drop=True)
    )


def effectifs_rangs(vue_tous_rangs: pd.DataFrame) -> pd.DataFrame:
    """Nombre de parties et part de chaque rang dans la vue (décrit l'échantillon)."""
    compte = vue_tous_rangs.groupby("rang", observed=True)["match_id"].nunique()
    stats = compte.rename("parties").reset_index()
    stats["rang"] = stats["rang"].astype(str)
    stats["part"] = stats["parties"] / stats["parties"].sum()
    stats["ordre"] = stats["rang"].map(RANGS.index)
    return stats.sort_values("ordre").drop(columns="ordre").reset_index(drop=True)


def composition_ideale(
    vue_postes: pd.DataFrame, n_min: int, alternatives: int = 3
) -> pd.DataFrame:
    """La composition la plus sûre : pour chaque poste, les champions classés par
    la borne basse de leur intervalle de confiance (un taux élevé sur peu de
    parties ne passe pas devant un taux un peu moins élevé mais solide).

    `vue_postes` : la vue filtrée par rang, région et patch, tous postes confondus.
    Colonne `place` : 1 = le champion retenu, 2 et plus = les alternatives.
    """
    stats = stats_champions(vue_postes, n_min, par=["poste"])
    stats = stats.sort_values(["poste", "ic_bas"], ascending=[True, False])
    stats["place"] = stats.groupby("poste").cumcount() + 1
    stats = stats[stats["place"] <= alternatives]
    stats["ordre"] = stats["poste"].map(POSTES.index)
    return (
        stats.sort_values(["ordre", "place"])
        .drop(columns="ordre")
        .reset_index(drop=True)
    )


def bans_conseilles(
    vue_postes: pd.DataFrame,
    n_min: int,
    top: int = 5,
    exclure: list[str] | None = None,
) -> pd.DataFrame:
    """Les bans les plus utiles : les champions les plus fiablement forts à ce
    rang, tous postes confondus (classés par la borne basse de l'intervalle),
    hors champions de notre propre composition (`exclure`).
    """
    stats = stats_champions(vue_postes, n_min)
    if exclure:
        stats = stats[~stats["champion"].isin(exclure)]
    return stats.sort_values("ic_bas", ascending=False).head(top).reset_index(drop=True)
