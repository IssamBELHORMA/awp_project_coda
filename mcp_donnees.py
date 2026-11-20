"""Serveur MCP « LoL Helper — nos données » (FastMCP).

Expose nos statistiques de parties classées (patchs 15.19 à 16.1, EUW / NA / KR)
et le modèle « et si ? » sous forme d'outils MCP, en lecture seule.

- Utilisé en interne par l'assistant (api.py), dans le même processus.
- Lançable seul pour un autre client MCP (Claude Desktop, Cursor…) :
      uv run python mcp_donnees.py            (stdio)
"""

from functools import cache

from fastmcp import FastMCP

import data
import modele

serveur = FastMCP(
    "lol-helper-donnees",
    instructions=(
        "Statistiques de parties classées League of Legends (base Kaggle, API Riot, "
        "patchs 15.19 à 16.1, EUW / NA / KR). Toujours citer le nombre de parties : "
        "un taux de victoire sur moins de 50 parties est peu fiable. Rangs en anglais "
        "(Iron … Challenger), postes : TOP, JUNGLE, MIDDLE, ADC, SUPPORT."
    ),
)


@cache
def _df():
    return data.charger()


@cache
def _modele():
    return modele.charger_modele()


def _rangs(rang: str | None) -> list[str] | None:
    return None if not rang else [r.strip().capitalize() for r in rang.split(",")]


def _postes(poste: str | None) -> list[str] | None:
    if not poste:
        return None
    alias = {
        "MID": "MIDDLE",
        "JGL": "JUNGLE",
        "JUNGLER": "JUNGLE",
        "BOT": "ADC",
        "SUP": "SUPPORT",
        "SUPP": "SUPPORT",
        "BOTTOM": "ADC",
    }
    return [alias.get(p.strip().upper(), p.strip().upper()) for p in poste.split(",")]


def _nom(champion: str) -> str | None:
    """Retrouve le nom exact d'un champion (insensible à la casse et aux espaces)."""
    cible = champion.replace(" ", "").replace("'", "").replace(".", "").lower()
    for nom in _df()["champion"].cat.categories:
        if nom.replace(" ", "").replace("'", "").replace(".", "").lower() == cible:
            return nom
    return None


def _ligne(s) -> dict:
    return {
        "champion": s["champion"],
        "parties": int(s["parties"]),
        "taux_victoire": round(float(s["taux_victoire"]), 3),
        "intervalle_95": [round(float(s["ic_bas"]), 3), round(float(s["ic_haut"]), 3)],
    }


@serveur.tool
def decrire_donnees() -> dict:
    """Décrit la base : périmètre, nombre de parties, rangs disponibles et limites."""
    df = _df()
    return {
        "source": "League of Legends Relational Database (Kaggle, nathansmallcalder), "
        "API Riot Games",
        "lignes": len(df),
        "parties": int(df["match_id"].nunique()),
        "patchs": data.liste_patchs(df),
        "regions": data.REGIONS,
        "parties_par_rang": data.effectifs_rangs(df)
        .set_index("rang")["parties"]
        .to_dict(),
        "limites": [
            "rangs non représentatifs du jeu (Master surreprésenté, Challenger rare)",
            "environ 1 joueur suivi par partie : face-à-face trop rares pour être fiables",
            "ADC / support déduits de l'objet de support (~1 % d'erreurs)",
        ],
    }


@serveur.tool
def meilleurs_champions(
    rang: str, poste: str, min_parties: int = 50, top: int = 8
) -> dict:
    """Les champions qui gagnent le plus à un rang et un poste (nos données).

    rang : ex. "Gold" ou "Gold,Platinum". poste : TOP, JUNGLE, MIDDLE, ADC, SUPPORT.
    Renvoie aussi le taux moyen et, pour chaque champion, s'il est nettement
    au-dessus de la moyenne (intervalle de confiance à 95 % au-dessus).
    """
    vue = data.filtrer(_df(), rangs=_rangs(rang), postes=_postes(poste))
    if vue.empty:
        return {"erreur": "aucune partie pour ce rang et ce poste"}
    stats, moyenne = data.fiabilite(vue, n_plancher=min_parties)
    ind = data.indicateurs(vue, min_parties)
    return {
        "rang": rang,
        "poste": poste,
        "parties": ind["parties"],
        "taux_victoire_moyen": round(moyenne, 3),
        "champions_distincts": ind["champions"],
        "plus_joue": {
            "champion": ind["plus_joue"],
            "parties": ind["plus_joue_parties"],
        },
        "meilleurs": [
            {**_ligne(s), "nettement_au_dessus": bool(s["au_dessus"])}
            for _, s in stats.head(top).iterrows()
        ],
    }


@serveur.tool
def profil_champion(
    champion: str, poste: str | None = None, rang: str | None = None
) -> dict:
    """Profil d'un champion dans nos données : taux de victoire au rang choisi,
    selon chaque rang, et selon la durée de la partie (moins de 27, 27-35, plus de 35 min).
    """
    nom = _nom(champion)
    if nom is None:
        return {"erreur": f"champion inconnu : {champion}"}
    vue_postes = data.filtrer(_df(), postes=_postes(poste))
    vue = data.filtrer(vue_postes, rangs=_rangs(rang))
    sous = vue[vue["champion"] == nom]
    if sous.empty:
        return {"erreur": f"aucune partie de {nom} avec ces filtres"}
    moyenne = float(vue["victoire"].mean())
    global_ = data.agreger(sous, ["champion"]).iloc[0]
    return {
        "champion": nom,
        "poste": poste,
        "rang": rang,
        **_ligne(global_),
        "taux_moyen_de_la_vue": round(moyenne, 3),
        "par_rang": [
            {
                "rang": r["rang"],
                "parties": int(r["parties"]),
                "taux_victoire": round(float(r["taux_victoire"]), 3),
            }
            for _, r in data.par_rang(vue_postes, nom).iterrows()
        ],
        "par_duree": [
            {
                "duree": r["duree"],
                "parties": int(r["parties"]),
                "taux_victoire": round(float(r["taux_victoire"]), 3),
            }
            for _, r in data.par_duree(vue, nom).iterrows()
        ],
        "kda_moyen": round(float(sous["kda"].mean()), 2),
        "duree_moyenne_min": round(float(sous["duree_min"].mean()), 1),
    }


@serveur.tool
def predire_victoire(champion: str, adversaire: str, poste: str, rang: str) -> dict:
    """Probabilité de victoire AVANT la partie (modèle « et si ? »), avec la
    qualité du modèle. Le modèle ignore le niveau du joueur : AUC proche de 0,52.
    """
    nom, adv = _nom(champion), _nom(adversaire)
    if nom is None or adv is None:
        return {
            "erreur": f"champion inconnu : {champion if nom is None else adversaire}"
        }
    poste_ok = (_postes(poste) or ["MIDDLE"])[0]
    rang_ok = (_rangs(rang) or ["Gold"])[0]
    m = modele.charger_metriques()
    return {
        "champion": nom,
        "adversaire": adv,
        "poste": poste_ok,
        "rang": rang_ok,
        "probabilite_victoire": round(
            modele.predire(_modele(), nom, adv, poste_ok, rang_ok), 3
        ),
        "modele": m["modele"],
        "auc": m["auc"],
        "auc_reference": m["auc_reference"],
    }


if __name__ == "__main__":
    serveur.run()
