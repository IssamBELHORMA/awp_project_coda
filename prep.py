# prep.py — lancé une seule fois depuis la racine : uv run python prep.py
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).parent
BRUT = RACINE / "Data" / "raw"
SORTIE = RACINE / "Data" / "processed" / "joueurs.parquet"
SORTIE.parent.mkdir(parents=True, exist_ok=True)

OBJETS_SUPPORT = [3860, 3862, 3863, 3864, 3865, 3866, 3867, 3869, 3870, 3871, 3876, 3877]
REGIONS = ["EUW1", "NA1", "KR"]
MIN_PARTIES_PATCH = 1000
COLS_OBJETS = [f"item{i}" for i in range(1, 7)]


def lire(nom: str, **kw) -> pd.DataFrame:
    return pd.read_csv(BRUT / f"{nom}.csv", **kw)


# 1. Lecture : seulement les colonnes utiles
stats = lire("MatchStatsTbl", usecols=[
    "SummonerMatchFk", "Lane", "Win", "EnemyChampionFk",
    "kills", "deaths", "assists", "MinionsKilled", "TotalGold",
    "DmgDealt", "visionScore", *COLS_OBJETS,
])
liens = lire("SummonerMatchTbl", usecols=["SummonerMatchId", "MatchFk", "ChampionFk"])
matchs = lire("MatchTbl")
rangs = lire("RankTbl")
items = lire("ItemTbl")
noms = lire("ChampionTbl").set_index("ChampionId")["ChampionName"]

print("Doublons de SummonerMatchFk :", stats["SummonerMatchFk"].duplicated().sum())
print("Types de partie :\n", matchs["QueueType"].value_counts().to_string())

# 2. Jointures (inner : on écarte les lignes orphelines)
n0 = len(stats)
df = stats.merge(liens, left_on="SummonerMatchFk", right_on="SummonerMatchId")
print(f"\nstats -> liens : {n0} -> {len(df)} lignes")
df = df.merge(matchs, left_on="MatchFk", right_on="MatchId")
print(f"-> matchs : {len(df)} lignes")
df = df.merge(rangs, left_on="RankFk", right_on="RankId", how="left")

# 3. Filtres sur les parties
df = df[(df["QueueType"] == "CLASSIC")     # Faille de l'invocateur uniquement
        & (df["RankFk"] != 0)              # parties classées uniquement (0 = Unranked)
        & (df["ChampionFk"] != 0)          # retire "No Champion"
        & (df["GameDuration"] >= 300)]     # retire les parties de moins de 5 min
print(f"après filtres parties : {len(df)} lignes")

# 4. Colonnes calculées
propre = pd.DataFrame({
    "match_id": df["MatchId"],
    "region": df["MatchId"].str.split("_").str[0],
    "patch": df["Patch"].str.split(".").str[:2].str.join("."),
    "rang_id": df["RankFk"],
    "rang": df["RankName"],
    "duree_min": (df["GameDuration"] / 60).round(1),
    "poste": df["Lane"],
    "champion": df["ChampionFk"].map(noms),
    "adversaire": df["EnemyChampionFk"].map(noms),
    "victoire": df["Win"],
    "kills": df["kills"],
    "deaths": df["deaths"],
    "assists": df["assists"],
    "kda": ((df["kills"] + df["assists"]) / df["deaths"].clip(lower=1)).round(2),
    "cs": df["MinionsKilled"],
    "or_total": df["TotalGold"],
    "degats": df["DmgDealt"],
    "vision": df["visionScore"],
    "objet_support": df[COLS_OBJETS].isin(OBJETS_SUPPORT).any(axis=1),
})

# 5. Postes : retirer NONE, séparer BOTTOM en ADC / SUPPORT par l'objet de support
propre = propre[propre["poste"] != "NONE"].copy()
bas = propre["poste"] == "BOTTOM"
propre.loc[bas & propre["objet_support"], "poste"] = "SUPPORT"
propre.loc[bas & ~propre["objet_support"], "poste"] = "ADC"

# 6. Régions et patchs
propre = propre[propre["region"].isin(REGIONS)]
parties_par_patch = propre.groupby("patch")["match_id"].nunique()
patchs_gardes = parties_par_patch[parties_par_patch >= MIN_PARTIES_PATCH].index
propre = propre[propre["patch"].isin(patchs_gardes)]

# 7. Types légers, puis sauvegarde
for col in ["region", "patch", "rang", "poste", "champion", "adversaire"]:
    propre[col] = propre[col].astype("category")
propre.to_parquet(SORTIE, index=False)

# 8. Vérifications
print("\n========== VÉRIFICATIONS ==========")
print("Objets de support reconnus :")
print(items[items["ItemID"].isin(OBJETS_SUPPORT)].to_string(index=False))

print(f"\nParquet : {SORTIE.stat().st_size / 1e6:.1f} Mo")
print(f"Lignes : {len(propre)} | parties distinctes : {propre['match_id'].nunique()}")

print("\nPostes :\n", propre["poste"].value_counts().to_string())
cs_min = propre["cs"] / propre["duree_min"]
print("\ncs/min médian par poste :\n",
      cs_min.groupby(propre["poste"], observed=True).median().round(1).to_string())
print("\nSUPPORT avec plus de 5 cs/min (suspects) :",
      int(((propre["poste"] == "SUPPORT") & (cs_min > 5)).sum()))
print("ADC avec moins de 3 cs/min (suspects) :",
      int(((propre["poste"] == "ADC") & (cs_min < 3)).sum()))

print("\nRangs :\n", propre["rang"].value_counts().to_string())
print("\nRégions :\n", propre["region"].value_counts().to_string())
print("\nPatchs gardés (parties distinctes) :\n",
      propre.groupby("patch", observed=True)["match_id"].nunique().to_string())

print("\nChampions sans nom :", propre["champion"].isna().sum(),
      "| adversaires sans nom :", propre["adversaire"].isna().sum())
print("Taux de victoire global :", round(propre["victoire"].mean(), 3))
print("Taux de victoire par poste :\n",
      propre.groupby("poste", observed=True)["victoire"].mean().round(3).to_string())