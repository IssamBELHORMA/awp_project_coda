"""LoL Helper : quel champion conseiller à ce rang et à ce poste ?

Lancer : uv run streamlit run app.py --server.address 127.0.0.1
"""

import plotly.express as px
import streamlit as st

import data

# Okabe-Ito (sans le jaune, trop peu contrasté sur fond blanc), une couleur par poste
COULEURS = {
    "TOP": "#D55E00",
    "JUNGLE": "#009E73",
    "MIDDLE": "#0072B2",
    "ADC": "#E69F00",
    "SUPPORT": "#CC79A7",
}
# Texte lisible sur chaque couleur (contraste >= 4,5:1)
TEXTE_SUR = {"MIDDLE": "#FFFFFF"}
NOMS_POSTES = {
    "TOP": "au top",
    "JUNGLE": "en jungle",
    "MIDDLE": "au mid",
    "ADC": "en ADC",
    "SUPPORT": "en support",
}
POLICE = {"size": 14}


def pct(x: float) -> str:
    """0.5866 -> '58,7 %' (format français)."""
    return f"{x * 100:.1f} %".replace(".", ",")


def liste_fr(valeurs: list[str]) -> str:
    """['Gold', 'Silver'] -> 'Gold et Silver'."""
    if len(valeurs) > 3:
        return f"{len(valeurs)} rangs"
    if len(valeurs) == 1:
        return valeurs[0]
    return ", ".join(valeurs[:-1]) + " et " + valeurs[-1]


@st.cache_data
def charger():
    return data.charger()


@st.cache_data
def filtrer(df, rangs, postes, regions, patchs):
    return data.filtrer(df, rangs, postes, regions, patchs)


@st.cache_data
def top_par_patch_poste(vue, n_min):
    return data.meilleurs_par_patch_poste(vue, n_min, top=5)


@st.cache_data
def top_tous_patchs(vue, n_min):
    stats = data.stats_champions(vue, n_min, par=["poste"])
    stats["place"] = stats.groupby("poste", observed=True).cumcount() + 1
    stats = stats[stats["place"] <= 5].copy()
    stats["poste"] = stats["poste"].astype(str)
    stats["champion"] = stats["champion"].astype(str)
    return stats


st.set_page_config(page_title="LoL Helper", page_icon="🎯", layout="wide")

df = charger()
tous_patchs = data.liste_patchs(df)

# ---------- Barre latérale : les filtres ----------
with st.sidebar:
    st.header("Filtres")
    rangs = st.multiselect("Rang", data.RANGS, default=["Gold"], key="f_rang")
    postes = st.multiselect("Poste", data.POSTES, default=["MIDDLE"], key="f_poste")
    regions = st.multiselect(
        "Région", data.REGIONS, default=data.REGIONS, key="f_region"
    )
    patchs = st.multiselect("Patch", tous_patchs, default=tous_patchs, key="f_patch")
    n_min = st.slider(
        "Minimum de parties par champion",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        key="f_n_min",
        help="Les champions joués moins souvent sont masqués : leur taux de "
        "victoire n'est pas fiable.",
    )

# ---------- Titre : la question du coach ----------
st.title("Quel champion conseiller à ce rang et à ce poste ?")
st.caption(
    "Pour un coach de joueurs classés : parties classées réelles, patchs "
    f"{tous_patchs[0]} à {tous_patchs[-1]}, EUW / NA / KR."
)

# Vue sans le filtre de poste (graphique principal) et vue complète (le reste)
vue_postes = filtrer(df, rangs, None, regions, patchs)
vue = filtrer(vue_postes, None, postes, None, None)

if vue.empty:
    st.warning(
        "Aucune partie pour ces filtres : choisissez au moins un rang, un poste, "
        "une région et un patch."
    )
    st.stop()

# ---------- Les 3 indicateurs ----------
ind = data.indicateurs(vue, n_min)
c1, c2, c3 = st.columns(3)
c1.metric("Parties", f"{ind['parties']:,}".replace(",", " "), border=True)
c2.metric("Taux de victoire moyen", pct(ind["taux_victoire"]), border=True)
if ind["meilleur_champion"]:
    c3.metric(
        "Meilleur champion",
        ind["meilleur_champion"],
        delta=f"{pct(ind['meilleur_taux'])} sur {ind['meilleur_parties']} parties",
        delta_color="off",
        delta_arrow="off",
        border=True,
    )
else:
    c3.metric(
        "Meilleur champion",
        "—",
        delta=f"aucun n'a {n_min} parties",
        delta_color="off",
        delta_arrow="off",
        border=True,
    )

# ---------- Le graphique principal ----------
st.subheader("Le meilleur champion de chaque poste")
mode = st.radio(
    "Affichage",
    ["Par patch", "Tous patchs confondus"],
    horizontal=True,
    key="f_mode",
    label_visibility="collapsed",
)

# Le poste mis en valeur : le premier poste choisi (ou TOP par défaut)
postes_choisis = [p for p in data.POSTES if p in postes]
poste_vedette = postes_choisis[0] if postes_choisis else "TOP"
rangs_txt = liste_fr([r for r in data.RANGS if r in rangs])


def mettre_en_valeur(fig):
    """Couleur pleine pour les postes choisis, atténuée pour les autres."""
    for trace in fig.data:
        choisi = trace.name in postes_choisis
        trace.marker.opacity = 1.0 if choisi else 0.3
        trace.marker.line = {"color": "#333333", "width": 1}
        couleur = TEXTE_SUR.get(trace.name, "#000000") if choisi else "#000000"
        trace.textfont = {"color": couleur, "size": 13}
    fig.update_layout(
        font=POLICE,
        legend_title_text="Poste",
        legend_font_size=13,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": 50},
    )
    # Pas de texte sous 12 px : le thème Streamlit réduit les polices par défaut
    fig.update_xaxes(tickfont_size=13, title_font_size=14)
    fig.update_yaxes(tickfont_size=13, title_font_size=14)
    return fig


if mode == "Par patch":
    top = top_par_patch_poste(vue_postes, n_min)
    meilleurs = top[top["place"] == 1].copy()

    # Le survol : le top 5 du poste à ce patch
    survol = (
        top.assign(
            ligne=lambda t: (
                t["place"].astype(str)
                + ". "
                + t["champion"]
                + " : "
                + t["taux_victoire"].map(pct)
                + " ("
                + t["parties"].astype(str)
                + " parties)"
            )
        )
        .groupby(["patch", "poste"])["ligne"]
        .agg("<br>".join)
        .rename("top5")
    )
    meilleurs = meilleurs.join(survol, on=["patch", "poste"])
    meilleurs["taux_pct"] = meilleurs["taux_victoire"] * 100

    # Le constat, pour le poste mis en valeur
    du_poste = meilleurs[meilleurs["poste"] == poste_vedette]
    n_patchs = len(patchs)
    if du_poste.empty:
        constat = (
            f"En {rangs_txt}, aucun champion n'atteint {n_min} parties "
            f"{NOMS_POSTES[poste_vedette]} sur un patch"
        )
    else:
        # Le champion premier sur le plus de patchs ; à égalité, le meilleur
        # taux de victoire sur l'ensemble des patchs choisis
        global_champ = data.stats_champions(
            data.filtrer(vue_postes, postes=[poste_vedette])
        ).set_index("champion")
        classement = (
            du_poste["champion"]
            .value_counts()
            .rename("patchs_gagnes")
            .to_frame()
            .join(global_champ)
            .sort_values(["patchs_gagnes", "taux_victoire"], ascending=False)
        )
        champ, ligne = classement.index[0], classement.iloc[0]
        k = int(ligne["patchs_gagnes"])
        constat = (
            f"En {rangs_txt}, {champ} est le meilleur {NOMS_POSTES[poste_vedette]} "
            f"sur {k} patch{'s' if k > 1 else ''} sur {n_patchs} "
            f"({pct(ligne['taux_victoire'])} sur {int(ligne['parties'])} parties "
            "tous patchs confondus)"
        )

    fig = px.bar(
        meilleurs,
        x="patch",
        y="taux_pct",
        color="poste",
        text="champion",
        barmode="group",
        category_orders={
            "patch": [p for p in tous_patchs if p in patchs],
            "poste": data.POSTES,
        },
        color_discrete_map=COULEURS,
        custom_data=["poste", "top5"],
        labels={"patch": "Patch", "taux_pct": "Taux de victoire (%)"},
    )
    fig.update_traces(
        textposition="inside",
        textangle=-90,
        insidetextanchor="start",
        hovertemplate="<b>%{customdata[0]}, patch %{x}</b><br>%{customdata[1]}"
        "<extra></extra>",
    )
    fig.add_hline(y=50, line_dash="dash", line_color="#333333")
    fig.update_yaxes(range=[0, max(70, meilleurs["taux_pct"].max() + 5)])
    # Garder tous les patchs choisis sur l'axe, même ceux sans barre
    ordre_patchs = [p for p in tous_patchs if p in patchs]
    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=ordre_patchs,
        range=[-0.5, len(ordre_patchs) - 0.5],
    )
    st.markdown(f"#### {constat}")
    st.plotly_chart(mettre_en_valeur(fig), alt=constat, key="graph_principal")

    vides = len(patchs) * len(data.POSTES) - len(meilleurs)
    if vides:
        st.caption(
            f"{vides} case{'s' if vides > 1 else ''} sans champion assez joué : "
            "baissez le minimum de parties, ajoutez des rangs ou passez en "
            "« Tous patchs confondus »."
        )

else:
    top = top_tous_patchs(vue_postes, n_min)
    top["taux_pct"] = top["taux_victoire"] * 100
    top["etiquette"] = top["poste"] + " · " + top["champion"]

    du_poste = top[(top["poste"] == poste_vedette) & (top["place"] == 1)]
    if du_poste.empty:
        constat = (
            f"En {rangs_txt}, aucun champion n'atteint {n_min} parties "
            f"{NOMS_POSTES[poste_vedette]}"
        )
    else:
        ligne = du_poste.iloc[0]
        constat = (
            f"En {rangs_txt}, tous patchs confondus, {ligne['champion']} est le "
            f"meilleur {NOMS_POSTES[poste_vedette]} ({pct(ligne['taux_victoire'])} "
            f"sur {int(ligne['parties'])} parties)"
        )

    fig = px.bar(
        top,
        x="taux_pct",
        y="etiquette",
        color="poste",
        orientation="h",
        text=top["taux_victoire"].map(pct) + " · " + top["parties"].astype(str) + " p.",
        category_orders={"poste": data.POSTES},
        color_discrete_map=COULEURS,
        custom_data=["champion", "parties"],
        labels={"taux_pct": "Taux de victoire (%)", "etiquette": ""},
        height=max(400, 32 * len(top) + 150),
    )
    fig.update_traces(
        textposition="inside",
        insidetextanchor="end",
        hovertemplate="<b>%{customdata[0]}</b><br>%{x:.1f} % sur "
        "%{customdata[1]} parties<extra></extra>",
    )
    # De haut en bas : TOP -> SUPPORT, et dans chaque poste du 1er au 5e
    ordre = top.assign(i=top["poste"].map(data.POSTES.index)).sort_values(
        ["i", "place"]
    )
    fig.update_yaxes(
        categoryorder="array", categoryarray=ordre["etiquette"].tolist()[::-1]
    )
    fig.add_vline(x=50, line_dash="dash", line_color="#333333")
    fig.update_xaxes(range=[0, max(70, top["taux_pct"].max() + 5)])
    st.markdown(f"#### {constat}")
    st.plotly_chart(mettre_en_valeur(fig), alt=constat, key="graph_principal")

st.caption(
    "Ligne pointillée : 50 % de victoires. Survolez une barre pour voir le top 5."
    if mode == "Par patch"
    else "Ligne pointillée : 50 % de victoires. Chaque barre indique le nombre "
    "de parties (p.)."
)

# ---------- Méthode et limites ----------
with st.expander("Méthode et limites"):
    st.markdown(
        """
**Données** : « League of Legends Relational Database for Match Prediction »
(Kaggle, nathansmallcalder), collectée avec l'API officielle de Riot Games.
Parties classées CLASSIC de plus de 5 minutes, patchs 15.19 à 16.1, EUW / NA / KR.

**Limites**
1. La répartition des rangs vient des joueurs suivis par le collecteur, pas du
   jeu : Master est surreprésenté, Challenger presque absent. Les statistiques
   sont donc toujours lues **par rang**.
2. Environ 1 joueur suivi par partie : on n'a pas les 10 joueurs de chaque partie.
3. La séparation ADC / support est déduite de l'objet de support : environ 1 %
   de lignes mal classées.
4. Les stats de fin de partie (kills, or, dégâts…) servent à l'affichage,
   jamais au modèle.
5. Les petits rangs (Challenger, Grandmaster), découpés par patch et par poste,
   donnent peu de parties : le minimum de parties masque les résultats peu fiables.
"""
    )
