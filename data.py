"""Fonctions de calcul de LoL Helper : pandas pur, aucune ligne Streamlit."""

from pathlib import Path

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


def stats_champions(
    vue: pd.DataFrame, n_min: int = 0, par: list[str] | None = None
) -> pd.DataFrame:
    """Parties et taux de victoire par champion (et par poste, patch… si `par`).

    Ne garde que les groupes d'au moins `n_min` parties, triés du meilleur
    taux de victoire au moins bon.
    """
    cles = [*(par or []), "champion"]
    stats = (
        vue.groupby(cles, observed=True)["victoire"]
        .agg(parties="size", taux_victoire="mean")
        .reset_index()
    )
    stats = stats[stats["parties"] >= n_min]
    return stats.sort_values(
        [*(par or []), "taux_victoire", "parties"],
        ascending=[*([True] * len(par or [])), False, False],
    ).reset_index(drop=True)


def indicateurs(vue: pd.DataFrame, n_min: int) -> dict:
    """Les 3 indicateurs du haut de page, calculés sur la vue filtrée."""
    stats = stats_champions(vue, n_min)
    meilleur = stats.iloc[0] if len(stats) else None
    return {
        "parties": int(vue["match_id"].nunique()),
        "taux_victoire": float(vue["victoire"].mean()) if len(vue) else float("nan"),
        "meilleur_champion": None if meilleur is None else str(meilleur["champion"]),
        "meilleur_taux": None if meilleur is None else float(meilleur["taux_victoire"]),
        "meilleur_parties": None if meilleur is None else int(meilleur["parties"]),
    }


def meilleurs_par_patch_poste(
    vue: pd.DataFrame, n_min: int, top: int = 5
) -> pd.DataFrame:
    """Le top `top` des champions par patch et par poste (graphique principal).

    Colonne `place` : 1 pour le meilleur champion du couple (patch, poste).
    """
    stats = stats_champions(vue, n_min, par=["patch", "poste"])
    stats["place"] = stats.groupby(["patch", "poste"], observed=True).cumcount() + 1
    stats = stats[stats["place"] <= top].copy()
    stats["patch"] = stats["patch"].astype(str)
    stats["poste"] = stats["poste"].astype(str)
    stats["champion"] = stats["champion"].astype(str)
    return stats.reset_index(drop=True)
