"""LoL Helper : quel champion conseiller à ce rang et à ce poste ?

Lancer : uv run streamlit run app.py --server.address 127.0.0.1
"""

import os

import httpx
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import carte
import data
import modele

# ---------- Couleurs (thème sombre, fond #0A1428) ----------
# Okabe-Ito, une couleur par poste, ajusté au fond sombre (bleu, orange et rose
# un peu assombris : même teinte, éclat maîtrisé). Vérifié : contraste >= 4,7:1
# sur le fond, daltonisme : écart OKLab >= 11 entre voisins. Les barres portent
# toujours le nom du champion et une légende : la couleur n'est jamais seule.
COULEURS = {
    "TOP": "#D55E00",
    "JUNGLE": "#009E73",
    "MIDDLE": "#3A9AD4",
    "ADC": "#C28500",
    "SUPPORT": "#C06A9A",
}
FOND = "#0A1428"  # fond de page (bleu nuit)
TEXTE = "#F0E6D2"  # texte crème (14,8:1 sur le fond)
TEXTE_DOUX = "#A09B8C"  # texte secondaire (6,6:1)
LIGNE = "#B8B2A6"  # lignes de référence (8,7:1)
OR = "#C8AA6E"  # accent (8,3:1)
PANNEAU = "#111C2E"  # fond des encadrés
BANDE = "rgba(240, 230, 210, 0.12)"  # zone du hasard
# Texte dans les barres : bleu nuit sur les couleurs pleines (>= 4,7:1), crème
# sur les barres atténuées
TEXTE_BARRE, TEXTE_ATTENUE = FOND, TEXTE
BLEU, ARDOISE, VERMILLON, GRIS = "#3A9AD4", "#7A8599", "#D55E00", TEXTE_DOUX
CHOISI, AUTRE = "Rang choisi", "Autres rangs"
NOMS_POSTES = {
    "TOP": "au top",
    "JUNGLE": "en jungle",
    "MIDDLE": "au mid",
    "ADC": "en ADC",
    "SUPPORT": "en support",
}
MIN_DETAIL = 20  # minimum de parties pour une barre du zoom sur un champion
CONFIG = {"displayModeBar": False}


def pct(x: float) -> str:
    """0.5866 -> '58,7 %' (format français, espace insécable)."""
    return f"{x * 100:.1f} %".replace(".", ",")


def nombre(n: int) -> str:
    """4588 -> '4 588'."""
    return f"{n:,}".replace(",", " ")


def liste_fr(valeurs: list[str]) -> str:
    """['Gold', 'Silver'] -> 'Gold et Silver'."""
    if len(valeurs) > 3:
        return f"{len(valeurs)} rangs"
    if len(valeurs) == 1:
        return valeurs[0]
    return ", ".join(valeurs[:-1]) + " et " + valeurs[-1]


def styliser(fig, marge_haut: int = 50):
    """Polices lisibles (jamais sous 12 px) et légende au-dessus du graphique."""
    fig.update_layout(
        font={"size": 14},
        legend_font_size=13,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"t": marge_haut},
        # Jamais de texte sous 12 px dans les barres, même si Plotly voudrait
        # le rapetisser pour le faire tenir
        uniformtext={"minsize": 12, "mode": "show"},
    )
    # Le thème Streamlit réduit les polices des axes : on les fixe
    fig.update_xaxes(tickfont_size=13, title_font_size=14)
    fig.update_yaxes(tickfont_size=13, title_font_size=14)
    return fig


def afficher(fig, constat: str, key: str):
    """Le constat en titre (il se replie sur téléphone), puis le graphique."""
    st.markdown(f"#### {constat}")
    st.plotly_chart(fig, alt=constat, key=key, config=CONFIG)


def barres_rangs(fig):
    """Rangs choisis en bleu, autres en ardoise, liseré du fond entre les barres."""
    for trace in fig.data:
        trace.marker.line = {"color": FOND, "width": 2}
        trace.textfont = {"color": TEXTE_BARRE, "size": 13}
        trace.error_y.color = TEXTE
    return fig


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
def top_par_poste(vue, n_min):
    return data.meilleurs_par_poste(vue, n_min, top=5)


@st.cache_data
def fiabilite(vue):
    return data.fiabilite(vue, n_plancher=10)


@st.cache_data
def composition(vue_postes, n_min):
    return data.composition_ideale(vue_postes, n_min)


@st.cache_data
def bans(vue_postes, n_min, exclure):
    return data.bans_conseilles(vue_postes, n_min, exclure=list(exclure))


@st.cache_resource
def charger_modele():
    return modele.charger_modele()


@st.cache_data
def charger_metriques():
    return modele.charger_metriques()


st.set_page_config(
    page_title="LoL Helper",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Titres de section en or (8,3:1 sur le fond). Les constats (h4) sont encadrés
# d'un liseré or pour se lire d'un coup d'œil. La barre de filtres reste collée
# en haut quand on fait défiler la page.
st.markdown(
    f"""<style>
h1, h2, h3 {{ color: {OR} !important; }}
h2, h3 {{ border-bottom: 1px solid {OR}55; padding-bottom: 0.2rem; }}
h4 {{ border-left: 4px solid {OR}; background: {PANNEAU}; padding: 0.5rem 0.8rem
     !important; border-radius: 0 6px 6px 0; line-height: 1.4 !important; }}
[data-testid="stCaptionContainer"] {{ color: #D9D0BE !important;
     font-size: 0.95rem !important; }}
/* Étiquettes des filtres : bleu nuit sur or (8,3:1) au lieu de blanc (2,2:1) */
[data-tag], [data-tag] span, [data-tag] button {{ color: {FOND} !important; }}
.st-key-barre_filtres {{ position: sticky; top: 3.2rem; z-index: 990;
     background: {FOND}; border-bottom: 1px solid {OR}88; padding: 0.4rem 0; }}
.st-key-barre_filtres a {{ color: {OR} !important; text-decoration: none;
     margin-right: 0.9rem; white-space: nowrap; font-size: 0.95rem; }}
</style>""",
    unsafe_allow_html=True,
)

df = charger()
tous_patchs = data.liste_patchs(df)

# ---------- Titre : la question du coach ----------
st.title("Quel champion conseiller à ce rang et à ce poste\u00a0?")
st.caption(
    "Pour un coach de joueurs classés : parties classées réelles, patchs "
    f"{tous_patchs[0]} à {tous_patchs[-1]}, EUW / NA / KR. L'assistant IA est "
    "dans la barre latérale."
)

# ---------- Barre de filtres, collée en haut pendant le défilement ----------
etat = st.session_state
resume = (
    f"⚙️ Filtres : {', '.join(etat.get('f_rang', ['Gold'])) or 'aucun rang'} · "
    f"{', '.join(etat.get('f_poste', ['MIDDLE'])) or 'aucun poste'} · "
    f"min {etat.get('f_n_min', 50)} parties"
)
with st.container(key="barre_filtres"):
    col_filtres, col_liens = st.columns([2, 3], vertical_alignment="center")
    with col_filtres.popover(resume, use_container_width=True):
        rangs = st.multiselect("Rang", data.RANGS, default=["Gold"], key="f_rang")
        postes = st.multiselect("Poste", data.POSTES, default=["MIDDLE"], key="f_poste")
        regions = st.multiselect(
            "Région", data.REGIONS, default=data.REGIONS, key="f_region"
        )
        patchs = st.multiselect(
            "Patch", tous_patchs, default=tous_patchs, key="f_patch"
        )
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
    col_liens.markdown(
        "[Meilleurs](#meilleurs) [Composition](#composition) "
        "[Tableau tactique](#tableau) [Fiabilité](#fiabilite) "
        "[Zoom](#zoom) [Et si ?](#et-si) [Méthode](#methode)"
    )

# Trois vues : sans filtre de poste (graphique principal), sans filtre de rang
# (graphiques par rang), et la vue complète (tout le reste)
vue_postes = filtrer(df, rangs, None, regions, patchs)
vue_rangs = filtrer(df, None, postes, regions, patchs)
vue = filtrer(vue_postes, None, postes, None, None)

if vue.empty:
    st.warning(
        "Aucune partie pour ces filtres : choisissez au moins un rang, un poste, "
        "une région et un patch."
    )
    st.stop()

postes_choisis = [p for p in data.POSTES if p in postes]
poste_vedette = postes_choisis[0]
rangs_choisis = [r for r in data.RANGS if r in rangs]
rangs_txt = liste_fr(rangs_choisis)
postes_txt = (
    NOMS_POSTES[poste_vedette] if len(postes_choisis) == 1 else "sur ces postes"
)
conseil_vide = "baissez le minimum de parties ou ajoutez des rangs (Master par exemple)"

# ---------- Les 4 indicateurs ----------
# (le taux de victoire moyen n'est pas affiché : il vaut toujours ~50 %, car
# chaque partie a un gagnant et un perdant)
ind = data.indicateurs(vue, n_min)
NEUTRE = {"delta_color": "off", "delta_arrow": "off", "border": True}
c1, c2, c3, c4 = st.columns(4)
c1.metric("Parties", nombre(ind["parties"]), border=True)
c2.metric(
    "Champions distincts",
    nombre(ind["champions"]),
    delta=f"{ind['champions_assez_joues']} avec ≥ {n_min} parties",
    help="Champions joués au moins une fois dans la vue. Seuls ceux qui atteignent "
    "le minimum de parties sont classés.",
    **NEUTRE,
)
c3.metric(
    "Champion le plus joué",
    ind["plus_joue"],
    delta=f"{ind['plus_joue_parties']} parties ({pct(ind['plus_joue_part'])})",
    help="Le choix le plus populaire à ce rang et à ce poste.",
    **NEUTRE,
)
if ind["meilleur_champion"]:
    c4.metric(
        "Meilleur champion",
        ind["meilleur_champion"],
        delta=f"{pct(ind['meilleur_taux'])} sur {ind['meilleur_parties']} parties",
        help=f"Meilleur taux de victoire parmi les champions qui ont au moins "
        f"{n_min} parties.",
        **NEUTRE,
    )
else:
    c4.metric(
        "Meilleur champion",
        "—",
        delta=f"aucun n'a {n_min} parties",
        **NEUTRE,
    )

# ---------- Q1. Le graphique principal ----------
st.subheader("Le meilleur champion de chaque poste", anchor="meilleurs")
mode = st.radio(
    "Affichage",
    ["Par patch", "Tous patchs confondus"],
    horizontal=True,
    key="f_mode",
    label_visibility="collapsed",
)


def mettre_en_valeur(fig):
    """Couleur pleine pour les postes choisis, atténuée pour les autres."""
    for trace in fig.data:
        choisi = trace.name in postes_choisis
        trace.marker.opacity = 1.0 if choisi else 0.4
        trace.marker.line = {"color": FOND, "width": 2}
        couleur = TEXTE_BARRE if choisi else TEXTE_ATTENUE
        trace.textfont = {"color": couleur, "size": 13}
    fig.update_layout(legend_title_text="Poste")
    return styliser(fig)


if mode == "Par patch":
    top = top_par_patch_poste(vue_postes, n_min)
    if top.empty:
        st.info(
            f"En {rangs_txt}, aucun champion n'atteint {n_min} parties sur un "
            f"patch : {conseil_vide}, ou passez en « Tous patchs confondus »."
        )
    else:
        # Le survol : le top 5 du poste à ce patch
        top = top.assign(
            ligne=[
                f"{p}. {c} : {pct(t)} ({n} parties)"
                for p, c, t, n in zip(
                    top["place"], top["champion"], top["taux_victoire"], top["parties"]
                )
            ]
        )
        survol = (
            top.groupby(["patch", "poste"])["ligne"].agg("<br>".join).rename("top5")
        )
        meilleurs = top[top["place"] == 1].join(survol, on=["patch", "poste"])
        meilleurs["taux_pct"] = meilleurs["taux_victoire"] * 100

        # Le constat, pour le poste mis en valeur
        du_poste = meilleurs[meilleurs["poste"] == poste_vedette]
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
                f"En {rangs_txt}, {champ} est le meilleur "
                f"{NOMS_POSTES[poste_vedette]} sur {k} patch{'s' if k > 1 else ''} "
                f"sur {len(patchs)} ({pct(ligne['taux_victoire'])} sur "
                f"{int(ligne['parties'])} parties tous patchs confondus)"
            )

        ordre_patchs = [p for p in tous_patchs if p in patchs]
        fig = px.bar(
            meilleurs,
            x="patch",
            y="taux_pct",
            color="poste",
            text="champion",
            barmode="group",
            category_orders={"patch": ordre_patchs, "poste": data.POSTES},
            color_discrete_map=COULEURS,
            custom_data=["poste", "top5"],
            labels={"patch": "Patch", "taux_pct": "Taux de victoire (%)"},
        )
        fig.update_traces(
            textposition="inside",
            textangle=-90,
            insidetextanchor="start",
            hovertemplate="<b>%{customdata[0]}, patch %{x}</b><br>"
            "%{customdata[1]}<extra></extra>",
        )
        fig.add_hline(y=50, line_dash="dash", line_color=LIGNE)
        fig.update_yaxes(range=[0, max(70, meilleurs["taux_pct"].max() + 5)])
        # Garder tous les patchs choisis sur l'axe, même ceux sans barre
        fig.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=ordre_patchs,
            range=[-0.5, len(ordre_patchs) - 0.5],
        )
        afficher(mettre_en_valeur(fig), constat, "graph_principal")

        vides = len(patchs) * len(data.POSTES) - len(meilleurs)
        if vides:
            st.caption(
                f"{vides} case{'s' if vides > 1 else ''} sans champion assez joué : "
                "baissez le minimum de parties, ajoutez des rangs ou passez en "
                "« Tous patchs confondus »."
            )
        st.caption(
            "Ligne pointillée : 50 % de victoires. Survolez une barre pour voir "
            "le top 5."
        )

else:
    top = top_par_poste(vue_postes, n_min)
    if top.empty:
        st.info(
            f"En {rangs_txt}, aucun champion n'atteint {n_min} parties : {conseil_vide}."
        )
    else:
        top["taux_pct"] = top["taux_victoire"] * 100
        top["etiquette"] = top["poste"] + " · " + top["champion"]
        top["texte"] = [
            f"{pct(t)} · {n} p." for t, n in zip(top["taux_victoire"], top["parties"])
        ]

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
                f"meilleur {NOMS_POSTES[poste_vedette]} "
                f"({pct(ligne['taux_victoire'])} sur {int(ligne['parties'])} parties)"
            )

        fig = px.bar(
            top,
            x="taux_pct",
            y="etiquette",
            color="poste",
            orientation="h",
            text="texte",
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
        fig.add_vline(x=50, line_dash="dash", line_color=LIGNE)
        fig.update_xaxes(range=[0, max(70, top["taux_pct"].max() + 5)])
        afficher(mettre_en_valeur(fig), constat, "graph_principal")
        st.caption(
            "Ligne pointillée : 50 % de victoires. Chaque barre indique le nombre "
            "de parties (p.)."
        )

# ---------- Composition et bans conseillés (avec la carte) ----------
st.subheader("Composition et bans conseillés", anchor="composition")
compo = composition(vue_postes, n_min)
if compo.empty:
    st.info(
        f"En {rangs_txt}, aucun champion n'atteint {n_min} parties à un poste : "
        f"{conseil_vide}."
    )
else:
    retenus = compo[compo["place"] == 1]
    a_bannir = bans(vue_postes, n_min, tuple(retenus["champion"]))
    noms = ", ".join(retenus["champion"])
    constat = f"En {rangs_txt}, la composition la plus sûre : {noms}"
    if not a_bannir.empty:
        b = a_bannir.iloc[0]
        constat += (
            f" ; à bannir en priorité : {b['champion']} "
            f"({pct(b['taux_victoire'])} sur {int(b['parties'])} parties)"
        )
    st.markdown(f"#### {constat}")
    col_carte, col_bans = st.columns([3, 2], gap="large")
    with col_carte:
        fig = carte.figure(compo, COULEURS, pct, data.POSTES)
        st.plotly_chart(fig, alt=constat, key="graph_carte", config=CONFIG)
        manquants = [p for p in data.POSTES if p not in set(retenus["poste"])]
        if manquants:
            st.caption(
                f"Sans champion ({', '.join(manquants)}) : aucun n'atteint {n_min} "
                f"parties à ce poste ; {conseil_vide}."
            )
        st.caption("Survolez un repère pour voir les alternatives du poste.")
    with col_bans:
        st.markdown("##### ⛔ Bans conseillés")
        if a_bannir.empty:
            st.info(f"Aucun autre champion n'atteint {n_min} parties.")
        for i, ban in enumerate(a_bannir.itertuples(), start=1):
            with st.container(border=True):
                icone = carte.url_icone(ban.champion)
                if icone:
                    st.image(icone, width=56)
                st.markdown(
                    f"⛔ **Ban {i} · {ban.champion}**  \n"
                    f"{pct(ban.taux_victoire)} sur {int(ban.parties)} parties "
                    f"(IC 95 % : {pct(ban.ic_bas)} à {pct(ban.ic_haut)})"
                )
    with st.expander("Voir la composition en tableau"):
        tableau = compo.assign(
            taux=compo["taux_victoire"].map(pct),
            intervalle=[
                f"{pct(a)} à {pct(b)}"
                for a, b in zip(compo["ic_bas"], compo["ic_haut"])
            ],
            choix=np.where(compo["place"] == 1, "Retenu", "Alternative"),
        )[["poste", "place", "choix", "champion", "taux", "parties", "intervalle"]]
        st.dataframe(
            tableau,
            hide_index=True,
            column_config={
                "poste": "Poste",
                "place": "Place",
                "choix": "Rôle",
                "champion": "Champion",
                "taux": "Taux de victoire",
                "parties": "Parties",
                "intervalle": "Intervalle 95 %",
            },
        )
    st.caption(
        "Méthode : à chaque poste, les champions sont classés par la borne basse "
        "de leur intervalle de confiance à 95 % : un taux élevé sur peu de parties "
        "ne passe pas devant un taux un peu moins élevé mais solide. Bans : les "
        "champions les plus fiablement forts à ce rang, hors de notre composition. "
        "Les données ne mesurent pas les synergies entre alliés (environ 1 joueur "
        "suivi par partie) : c'est le champion le plus sûr de chaque poste, pas "
        "une équipe testée ensemble."
    )

# ---------- Tableau tactique : une carte sur laquelle le coach dessine ----------
st.subheader("Tableau tactique", anchor="tableau")
st.markdown(
    "#### Dessinez vos plans de jeu sur la carte : chemins de jungle, rotations, "
    "objectifs"
)
st.caption(
    "Outils en haut à droite de la carte : tracé libre, ligne, cercle, rectangle, "
    "gomme (cliquez un dessin puis la gomme), et l'appareil photo pour télécharger "
    "la carte annotée en PNG. Les icônes sont la composition conseillée ci-dessus. "
    "Les dessins ne sont pas enregistrés."
)
st.plotly_chart(
    carte.figure_tableau(None if compo.empty else compo),
    config=carte.CONFIG_DESSIN,
    key="tableau_tactique",
)

# ---------- Q2. Ces taux de victoire sont-ils fiables ? ----------
st.subheader("Ces taux de victoire sont-ils fiables ?", anchor="fiabilite")
fiab, moyenne = fiabilite(vue)
if fiab.empty:
    st.info(f"Aucun champion n'a 10 parties en {rangs_txt} {postes_txt}.")
else:
    fiab = fiab.assign(
        taux_pct=fiab["taux_victoire"] * 100,
        statut=np.select(
            [fiab["au_dessus"], fiab["en_dessous"]],
            ["Nettement au-dessus", "Nettement en dessous"],
            "Dans la zone du hasard",
        ),
    )
    surs = fiab[fiab["au_dessus"]].sort_values("ic_bas", ascending=False)
    if surs.empty:
        constat = (
            f"En {rangs_txt} {postes_txt}, aucun champion ne gagne nettement plus "
            f"que la moyenne ({pct(moyenne)}) : les écarts restent dans la zone "
            "du hasard"
        )
    else:
        meilleur = surs.iloc[0]
        n_surs = len(surs)
        constat = (
            f"En {rangs_txt} {postes_txt}, {n_surs} champion{'s' if n_surs > 1 else ''} "
            f"gagne{'nt' if n_surs > 1 else ''} nettement plus que la moyenne "
            f"({pct(moyenne)}) ; le plus sûr : {meilleur['champion']}, "
            f"{pct(meilleur['taux_victoire'])} sur {meilleur['parties']} parties"
        )

    bande = data.bande_hasard(moyenne, int(fiab["parties"].max()))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=np.concatenate([bande["parties"], bande["parties"][::-1]]),
            y=np.concatenate([bande["haut"], bande["bas"][::-1]]) * 100,
            fill="toself",
            fillcolor=BANDE,
            line={"width": 0},
            hoverinfo="skip",
            name="Zone du hasard (95 %)",
        )
    )
    # Un symbole ET une couleur par statut : la couleur ne porte pas seule le sens
    styles = {
        "Nettement au-dessus": (BLEU, "circle"),
        "Dans la zone du hasard": (GRIS, "circle-open"),
        "Nettement en dessous": (VERMILLON, "diamond"),
    }
    # On nomme les champions hors de la zone (au plus 12, les plus joués)
    a_nommer = set(
        fiab[fiab["au_dessus"] | fiab["en_dessous"]].nlargest(12, "parties")["champion"]
    )
    for statut, (couleur, symbole) in styles.items():
        part = fiab[fiab["statut"] == statut]
        if part.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=part["parties"],
                y=part["taux_pct"],
                mode="markers+text",
                name=statut,
                marker={
                    "color": couleur,
                    "symbol": symbole,
                    "size": 10,
                    "line": {"color": couleur, "width": 2},
                },
                text=[c if c in a_nommer else "" for c in part["champion"]],
                textposition="top center",
                textfont={"size": 13, "color": TEXTE},
                customdata=np.stack(
                    [part["champion"], part["ic_bas"] * 100, part["ic_haut"] * 100],
                    axis=-1,
                ),
                hovertemplate="<b>%{customdata[0]}</b><br>%{y:.1f} % sur %{x} "
                "parties<br>Intervalle 95 % : %{customdata[1]:.0f} à "
                "%{customdata[2]:.0f} %<extra></extra>",
            )
        )
    fig.add_hline(y=moyenne * 100, line_dash="dash", line_color=LIGNE)
    fig.add_vline(x=n_min, line_dash="dot", line_color=GRIS)
    # Sur un axe logarithmique, les annotations et la plage sont en log10
    fig.add_annotation(
        x=np.log10(n_min),
        y=1,
        yref="paper",
        text=f"minimum : {n_min}",
        showarrow=False,
        xanchor="left",
        font={"size": 13, "color": TEXTE_DOUX},
    )
    fig.update_xaxes(
        type="log",
        title="Nombre de parties (échelle logarithmique)",
        range=[np.log10(8), np.log10(max(fiab["parties"].max(), n_min) * 1.3)],
    )
    fig.update_yaxes(title="Taux de victoire (%)")
    fig.update_layout(height=480)
    afficher(styliser(fig, marge_haut=70), constat, "graph_fiabilite")
    st.caption(
        "Chaque point est un champion (au moins 10 parties). Ligne pointillée : "
        "taux de victoire moyen de la vue. La zone claire montre où tombe un "
        "champion moyen par simple hasard : elle se resserre quand le nombre de "
        "parties augmente. Un champion au-dessus de la zone gagne vraiment plus."
    )

# ---------- Q3. Zoom sur un champion ----------
st.subheader("Zoom sur un champion", anchor="zoom")
options = data.champions_joues(vue)
defaut = ind["meilleur_champion"] if ind["meilleur_champion"] in options else options[0]
# Si les filtres changent et que le champion n'est plus dans la vue, on revient
# au meilleur champion
if st.session_state.get("f_champion") not in options:
    st.session_state["f_champion"] = defaut
champion = st.selectbox(
    "Champion (du plus joué au moins joué)", options, key="f_champion"
)

onglet_rang, onglet_duree, onglet_parties = st.tabs(
    ["Selon le rang", "Selon la durée", "Ses parties"]
)

with onglet_rang:
    stats_r = data.par_rang(vue_rangs, champion)
    visibles = stats_r[stats_r["parties"] >= MIN_DETAIL].copy()
    if visibles.empty:
        st.info(
            f"{champion} n'a {MIN_DETAIL} parties dans aucun rang {postes_txt} : "
            "ajoutez des patchs ou des régions."
        )
    else:
        sel = stats_r[stats_r["rang"].isin(rangs_choisis)]
        n_sel = int(sel["parties"].sum())
        meilleur = visibles.loc[visibles["taux_victoire"].idxmax()]
        debut = (
            f"{champion} {postes_txt} gagne {pct(sel['victoires'].sum() / n_sel)} "
            f"de ses {n_sel} parties en {rangs_txt}"
            if n_sel
            else f"{champion} n'a aucune partie en {rangs_txt} {postes_txt}"
        )
        constat = (
            f"{debut} ; son meilleur rang est {meilleur['rang']} "
            f"({pct(meilleur['taux_victoire'])} sur {meilleur['parties']} parties)"
        )
        visibles = visibles.assign(
            taux_pct=visibles["taux_victoire"] * 100,
            err_haut=(visibles["ic_haut"] - visibles["taux_victoire"]) * 100,
            err_bas=(visibles["taux_victoire"] - visibles["ic_bas"]) * 100,
            choix=np.where(visibles["rang"].isin(rangs_choisis), CHOISI, AUTRE),
            texte=[f"{n} p." for n in visibles["parties"]],
        )
        fig = px.bar(
            visibles,
            x="rang",
            y="taux_pct",
            color="choix",
            error_y="err_haut",
            error_y_minus="err_bas",
            text="texte",
            category_orders={"rang": data.RANGS, "choix": [CHOISI, AUTRE]},
            color_discrete_map={CHOISI: BLEU, AUTRE: ARDOISE},
            custom_data=["parties", "ic_bas", "ic_haut"],
            labels={"rang": "Rang", "taux_pct": "Taux de victoire (%)", "choix": ""},
        )
        fig.update_traces(
            textposition="inside",
            insidetextanchor="start",
            hovertemplate="<b>%{x}</b><br>%{y:.1f} % sur %{customdata[0]} "
            "parties<extra></extra>",
        )
        fig.add_hline(y=50, line_dash="dash", line_color=LIGNE)
        fig.update_yaxes(range=[0, max(75, visibles["ic_haut"].max() * 100 + 5)])
        afficher(styliser(barres_rangs(fig)), constat, "graph_rang")
        caches = stats_r[stats_r["parties"] < MIN_DETAIL]["rang"].tolist()
        st.caption(
            "Trait vertical : intervalle de confiance à 95 %. Ce graphique montre "
            "tous les rangs ; le filtre de rang met en valeur les rangs choisis."
            + (
                f" Masqués (moins de {MIN_DETAIL} parties) : {', '.join(caches)}."
                if caches
                else ""
            )
        )

with onglet_duree:
    stats_d = data.par_duree(vue, champion)
    visibles = stats_d[stats_d["parties"] >= MIN_DETAIL].copy()
    if visibles.empty:
        st.info(
            f"{champion} n'a {MIN_DETAIL} parties dans aucune tranche de durée en "
            f"{rangs_txt} : ajoutez des rangs ou baissez les filtres."
        )
    else:
        meilleur = visibles.loc[visibles["taux_victoire"].idxmax()]
        tranche = meilleur["duree"][0].lower() + meilleur["duree"][1:]
        constat = (
            f"En {rangs_txt}, {champion} gagne le plus dans les parties de "
            f"{tranche} ({pct(meilleur['taux_victoire'])} sur "
            f"{meilleur['parties']} parties)"
        )
        visibles = visibles.assign(
            taux_pct=visibles["taux_victoire"] * 100,
            err_haut=(visibles["ic_haut"] - visibles["taux_victoire"]) * 100,
            err_bas=(visibles["taux_victoire"] - visibles["ic_bas"]) * 100,
            texte=[
                f"{pct(t)} · {n} p."
                for t, n in zip(visibles["taux_victoire"], visibles["parties"])
            ],
        )
        fig = px.bar(
            visibles,
            x="duree",
            y="taux_pct",
            error_y="err_haut",
            error_y_minus="err_bas",
            text="texte",
            category_orders={"duree": data.TRANCHES_DUREE},
            color_discrete_sequence=[BLEU],
            custom_data=["parties"],
            labels={"duree": "Durée de la partie", "taux_pct": "Taux de victoire (%)"},
        )
        fig.update_traces(
            textposition="inside",
            insidetextanchor="start",
            textfont={"color": TEXTE_BARRE, "size": 13},
            marker_line={"color": FOND, "width": 2},
            error_y_color=TEXTE,
            hovertemplate="<b>%{x}</b><br>%{y:.1f} % sur %{customdata[0]} "
            "parties<extra></extra>",
        )
        fig.add_hline(y=50, line_dash="dash", line_color=LIGNE)
        fig.update_yaxes(range=[0, max(75, visibles["ic_haut"].max() * 100 + 5)])
        afficher(styliser(fig), constat, "graph_duree")
        st.caption(
            "Trait vertical : intervalle de confiance à 95 %. La durée n'est connue "
            "qu'après la partie : ce graphique décrit le profil du champion (début "
            "ou fin de partie) et n'est jamais utilisé par le modèle."
        )

with onglet_parties:
    detail = data.parties(vue, champion)
    n_vic = int((detail["Résultat"] == "Victoire").sum())
    st.markdown(
        f"#### {champion} : {n_vic} victoires sur {len(detail)} parties en "
        f"{rangs_txt} {postes_txt}"
    )
    st.dataframe(
        detail,
        hide_index=True,
        column_config={
            "KDA": st.column_config.NumberColumn(format="%.2f"),
            "Durée (min)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

# ---------- Couche ML : « Et si ? » ----------
st.subheader("Et si ? Les chances de victoire avant la partie", anchor="et-si")
tous_champions = sorted(df["champion"].astype(str).unique())
with st.form("form_et_si"):
    f1, f2 = st.columns(2)
    mon_champion = f1.selectbox(
        "Mon champion",
        tous_champions,
        index=tous_champions.index(champion),
        key="ml_champion",
    )
    # Par défaut : l'adversaire le plus fréquent dans la vue
    adversaire_frequent = str(vue["adversaire"].value_counts().index[0])
    adversaire = f2.selectbox(
        "L'adversaire en face",
        tous_champions,
        index=tous_champions.index(adversaire_frequent),
        key="ml_adversaire",
    )
    f3, f4 = st.columns(2)
    poste_ml = f3.selectbox(
        "Poste",
        data.POSTES,
        index=data.POSTES.index(poste_vedette),
        key="ml_poste",
    )
    rang_ml = f4.selectbox(
        "Rang",
        data.RANGS,
        index=data.RANGS.index(rangs_choisis[0]),
        key="ml_rang",
    )
    estimer = st.form_submit_button("Estimer")

metriques = charger_metriques()
if estimer:
    proba = modele.predire(
        charger_modele(), mon_champion, adversaire, poste_ml, rang_ml
    )
    st.metric(
        "Chances de victoire",
        pct(proba),
        delta=f"{mon_champion} contre {adversaire}, {poste_ml}, {rang_ml}",
        delta_color="off",
        delta_arrow="off",
        border=True,
    )
st.caption(
    f"Régression logistique, validation croisée à 5 plis : AUC "
    f"{str(metriques['auc']).replace('.', ',')} (référence "
    f"{str(metriques['auc_reference']).replace('.', ',')}), exactitude "
    f"{pct(metriques['exactitude'])} (référence "
    f"{pct(metriques['exactitude_reference'])}), sur {nombre(metriques['lignes'])} "
    "lignes. Référence : le taux de victoire du champion à ce poste et à ce rang. "
    "Le modèle n'utilise que ce qui est connu avant la partie (champion, "
    "adversaire, poste, rang) : il ne tient pas compte du niveau du joueur, d'où "
    "une AUC proche de 0,5."
)

# ---------- Assistant IA dans la barre latérale (API FastAPI séparée) ----------


def url_api() -> str:
    """Adresse de l'API : secret Streamlit, variable d'environnement ou local."""
    try:
        return st.secrets["API_URL"].rstrip("/")
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")


def demander(question: str, historique: list[dict]) -> dict:
    """Envoie la question à l'API ; renvoie le message à afficher."""
    try:
        reponse = httpx.post(
            f"{url_api()}/assistant",
            json={
                "question": question,
                "historique": [
                    {"role": m["role"], "contenu": m["contenu"]} for m in historique
                ],
            },
            timeout=240,
        )
    except httpx.HTTPError:
        return {
            "role": "assistant",
            "contenu": "⚠️ L'API de l'assistant ne répond pas. Elle est peut-être en "
            "veille (hébergement gratuit) : réessayez dans une minute. Le reste de "
            "la page fonctionne sans elle.",
        }
    if reponse.status_code == 200:
        corps = reponse.json()
        return {
            "role": "assistant",
            "contenu": corps["reponse"],
            "outils": sorted(set(corps["outils"])),
        }
    detail = reponse.json().get("detail", reponse.text)
    return {"role": "assistant", "contenu": f"⚠️ L'assistant a échoué : {detail}"}


if "conversation" not in st.session_state:
    st.session_state["conversation"] = []

with st.sidebar:
    st.header("🤖 Assistant")
    st.caption(
        "Croise vos parties OP.GG avec nos données. Exemples : « Je suis Gold mid, "
        "quel main choisir ? », « Analyse le joueur Nom#TAG en EUW ». Modèle "
        "gpt-oss-120b (Groq) + MCP. Texte généré par une IA : vérifiez les "
        "chiffres dans les graphiques. Réponse en 30 s à 2 min."
    )
    for message in st.session_state["conversation"]:
        with st.chat_message(message["role"]):
            st.markdown(message["contenu"])
            if message.get("outils"):
                st.caption("Outils utilisés : " + ", ".join(message["outils"]))
    question = st.chat_input("Votre question", key="chat_question")
    if question:
        historique = list(st.session_state["conversation"])
        st.session_state["conversation"].append({"role": "user", "contenu": question})
        with st.spinner("L'assistant consulte nos données et OP.GG…"):
            st.session_state["conversation"].append(demander(question, historique))
        st.rerun()
    if st.session_state["conversation"] and st.button(
        "Effacer la conversation", key="chat_effacer"
    ):
        st.session_state["conversation"] = []
        st.rerun()

st.subheader("Méthode, limites et mentions", anchor="methode")
st.caption(
    "LoL Helper n'est pas approuvé par Riot Games et ne reflète pas les opinions de "
    "Riot Games ni de quiconque officiellement impliqué dans la production ou la "
    "gestion des propriétés de Riot Games. Riot Games et toutes les propriétés "
    "associées sont des marques commerciales ou des marques déposées de Riot "
    "Games, Inc. Images : Data Dragon (Riot Games)."
)
with st.expander("Méthode et limites"):
    effectifs = data.effectifs_rangs(vue_rangs)
    if not effectifs.empty:
        plus = effectifs.loc[effectifs["part"].idxmax()]
        moins = effectifs.loc[effectifs["part"].idxmin()]
        constat = (
            f"{plus['rang']} représente {pct(plus['part'])} des parties de "
            f"l'échantillon, {moins['rang']} seulement {pct(moins['part'])}"
        )
        effectifs = effectifs.assign(
            choix=np.where(effectifs["rang"].isin(rangs_choisis), CHOISI, AUTRE),
            texte=[nombre(n) for n in effectifs["parties"]],
        )
        fig = px.bar(
            effectifs,
            x="rang",
            y="parties",
            color="choix",
            text="texte",
            category_orders={"rang": data.RANGS, "choix": [CHOISI, AUTRE]},
            color_discrete_map={CHOISI: BLEU, AUTRE: ARDOISE},
            labels={"rang": "Rang", "parties": "Parties", "choix": ""},
        )
        fig.update_traces(
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y} parties<extra></extra>",
        )
        for trace in fig.data:
            trace.marker.line = {"color": FOND, "width": 2}
            trace.textfont = {"color": TEXTE, "size": 13}
        fig.update_yaxes(range=[0, effectifs["parties"].max() * 1.15])
        afficher(styliser(fig), constat, "graph_effectifs")
        st.caption(
            "Parties par rang pour les postes, régions et patchs choisis. Cette "
            "répartition vient des joueurs suivis par le collecteur, pas du jeu."
        )

    st.markdown(
        """
**Données** : « League of Legends Relational Database for Match Prediction »
(Kaggle, nathansmallcalder), collectée avec l'API officielle de Riot Games.
Parties classées CLASSIC de plus de 5 minutes, patchs 15.19 à 16.1, EUW / NA / KR.

**Fiabilité** : chaque taux de victoire est donné avec son nombre de parties.
L'intervalle de confiance à 95 % (méthode de Wilson) indique la marge d'erreur :
avec 30 parties, elle est d'environ ± 18 points ; avec 300, d'environ ± 6 points.

**Limites**
1. La répartition des rangs vient des joueurs suivis par le collecteur, pas du
   jeu : Master est surreprésenté, Challenger presque absent (graphique
   ci-dessus). Les statistiques sont donc toujours lues **par rang**.
2. Environ 1 joueur suivi par partie : on n'a pas les 10 joueurs de chaque partie.
   Les face-à-face entre deux champions ont donc trop peu de parties pour être
   affichés (souvent moins de 10 par paire à un rang donné).
3. La séparation ADC / support est déduite de l'objet de support : environ 1 %
   de lignes mal classées.
4. Les stats de fin de partie (kills, or, dégâts, durée…) servent à l'affichage,
   jamais au modèle.
5. Les petits rangs (Challenger, Grandmaster), découpés par patch et par poste,
   donnent peu de parties : le minimum de parties masque les résultats peu fiables.
"""
    )
