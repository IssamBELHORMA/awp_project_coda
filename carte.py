"""La vraie carte de la Faille de l'invocateur (minicarte Riot Data Dragon) avec
l'icône de chaque champion de la composition conseillée, plus un tableau tactique
sur lequel un coach peut dessiner.

Images : CDN public Data Dragon de Riot (autorisé pour les projets de fans non
commerciaux). Aucun appel réseau à l'import : seulement quand on demande une icône.
Repère : carré 0-1, base bleue en bas à gauche, base rouge en haut à droite.
"""

import functools
import re
from collections.abc import Callable

import httpx
import pandas as pd
import plotly.graph_objects as go

DDRAGON = "https://ddragon.leagueoflegends.com"
VERSION_DE_SECOURS = "16.23.1"
URL_CARTE = f"{DDRAGON}/cdn/6.8.1/img/map/map11.png"  # minicarte 512 x 512

TEXTE = "#F0E6D2"
TEXTE_DOUX = "#A09B8C"
FOND = "#0A1428"
OR = "#C8AA6E"
FOND_ETIQUETTE = "rgba(10, 20, 40, 0.88)"
ERREURS_RESEAU = (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError)

TAILLE_ICONE = 0.11
# Centre de l'icône de chaque poste côté bleu (calé sur la minicarte), et ancrage
# horizontal de l'étiquette pour qu'elle ne sorte pas de la carte
POSITIONS = {
    "TOP": (0.10, 0.78, "left"),
    "JUNGLE": (0.27, 0.40, "center"),
    "MIDDLE": (0.50, 0.53, "center"),
    "ADC": (0.66, 0.17, "center"),
    "SUPPORT": (0.88, 0.27, "right"),
}

# Noms usuels qui ne correspondent pas à l'identifiant Data Dragon
CAS_PARTICULIERS = {
    "wukong": "MonkeyKing",
    "nunuwillump": "Nunu",
    "nunu": "Nunu",
    "renataglasc": "Renata",
    "renata": "Renata",
}

CONFIG_DESSIN = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,
    "modeBarButtonsToAdd": [
        "drawopenpath",
        "drawline",
        "drawcircle",
        "drawrect",
        "eraseshape",
    ],
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
    ],
}


def _normaliser(nom: str) -> str:
    return re.sub(r"[\s'.&]", "", str(nom)).lower()


@functools.cache
def version_ddragon() -> str:
    """Dernière version de Data Dragon (version de secours si hors ligne)."""
    try:
        reponse = httpx.get(f"{DDRAGON}/api/versions.json", timeout=5)
        reponse.raise_for_status()
        return str(reponse.json()[0])
    except ERREURS_RESEAU:
        return VERSION_DE_SECOURS


@functools.cache
def _index_champions() -> dict[str, str]:
    """Nom ou identifiant normalisé -> identifiant Data Dragon ({} si hors ligne)."""
    url = f"{DDRAGON}/cdn/{version_ddragon()}/data/fr_FR/champion.json"
    try:
        reponse = httpx.get(url, timeout=5)
        reponse.raise_for_status()
        champions = reponse.json()["data"].values()
    except ERREURS_RESEAU:
        return {}
    index = {}
    for c in champions:
        index[_normaliser(c["name"])] = c["id"]
        index[_normaliser(c["id"])] = c["id"]
    return index


def url_icone(champion: str) -> str | None:
    """URL de l'icône carrée du champion, ou None s'il est inconnu (ou hors ligne)."""
    index = _index_champions()
    cle = _normaliser(champion)
    ident = index.get(cle)
    if ident is None and cle in CAS_PARTICULIERS:
        ident = index.get(_normaliser(CAS_PARTICULIERS[cle]))
    if ident is None:
        return None
    return f"{DDRAGON}/cdn/{version_ddragon()}/img/champion/{ident}.png"


def _fond_carte(fig: go.Figure, hauteur: int, dessin: bool = False) -> None:
    """Minicarte en fond (assombrie par l'opacité sur le fond marine), axes 0-1
    cachés et figés, repère carré."""
    fig.add_layout_image(
        source=URL_CARTE,
        xref="x",
        yref="y",
        x=0,
        y=1,
        sizex=1,
        sizey=1,
        sizing="stretch",
        xanchor="left",
        yanchor="top",
        opacity=0.72,
        layer="below",
    )
    fig.update_xaxes(range=[0, 1], visible=False, fixedrange=True, constrain="domain")
    fig.update_yaxes(
        range=[0, 1],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        constrain="domain",
    )
    fig.update_layout(
        height=hauteur,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        plot_bgcolor=FOND,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"size": 13, "color": TEXTE},
        hoverlabel={"bgcolor": FOND, "font_color": TEXTE, "bordercolor": TEXTE_DOUX},
        dragmode="drawopenpath" if dessin else False,
        showlegend=False,
    )


def _repere(
    fig: go.Figure,
    poste: str,
    champion: str | None,
    couleur: str,
    survol: str,
    etiquette: str | None,
) -> None:
    """Icône du champion (ou son nom en texte), cadre à la couleur du poste,
    zone de survol et étiquette sous l'icône."""
    x, y, ancre = POSITIONS[poste]
    demi = TAILLE_ICONE / 2
    icone = url_icone(champion) if champion else None
    if icone:
        fig.add_layout_image(
            source=icone,
            xref="x",
            yref="y",
            x=x,
            y=y,
            sizex=TAILLE_ICONE,
            sizey=TAILLE_ICONE,
            sizing="stretch",
            xanchor="center",
            yanchor="middle",
            layer="above",
        )
    elif champion:
        fig.add_annotation(
            x=x,
            y=y,
            text=f"<b>{champion}</b>",
            showarrow=False,
            font={"size": 13, "color": TEXTE},
            bgcolor=FOND_ETIQUETTE,
        )
    if champion:
        # Cadre tracé en coordonnées de la carte : il suit la taille de l'icône
        fig.add_shape(
            type="rect",
            x0=x - demi,
            y0=y - demi,
            x1=x + demi,
            y1=y + demi,
            line={"color": couleur, "width": 4},
            layer="above",
        )
    fig.add_trace(
        go.Scatter(
            x=[x],
            y=[y],
            mode="markers",
            marker={
                "size": 52,
                "symbol": "square" if champion else "circle-open",
                "color": "rgba(0,0,0,0)" if champion else couleur,
                "line": {"width": 0 if champion else 3, "color": couleur},
            },
            hovertemplate=survol + "<extra></extra>",
            hoverlabel={"font_size": 13},
            name=poste,
        )
    )
    if etiquette:
        decalage = {"left": -demi, "center": 0, "right": demi}[ancre]
        fig.add_annotation(
            x=x + decalage,
            y=y - demi if champion else y,
            yanchor="top",
            xanchor=ancre,
            yshift=-4 if champion else -16,
            text=etiquette,
            showarrow=False,
            align=ancre,
            font={"size": 13, "color": TEXTE},
            bgcolor=FOND_ETIQUETTE,
            bordercolor=couleur,
            borderwidth=1,
            borderpad=3,
        )


def figure(
    compo: pd.DataFrame,
    couleurs: dict[str, str],
    pct: Callable[[float], str],
    postes: list[str],
    hauteur: int = 520,
) -> go.Figure:
    """La carte avec, pour chaque poste, l'icône du champion retenu (place 1) ; le
    survol donne son nom, son taux, son intervalle et les alternatives."""
    fig = go.Figure()
    _fond_carte(fig, hauteur)
    for poste in postes:
        if poste not in POSITIONS:
            continue
        lignes = compo[compo["poste"] == poste]
        choisi = lignes[lignes["place"] == 1]
        couleur = couleurs.get(poste, OR)
        if choisi.empty:
            _repere(
                fig,
                poste,
                None,
                couleur,
                f"<b>{poste}</b><br>Aucun champion n'atteint le minimum",
                f"<b>{poste}</b> · —",
            )
            continue
        c = choisi.iloc[0]
        alternatives = [
            f"{int(a['place'])}. {a['champion']} : {pct(a['taux_victoire'])} "
            f"sur {int(a['parties'])} parties (IC 95 % : "
            f"{pct(a['ic_bas'])} à {pct(a['ic_haut'])})"
            for _, a in lignes[lignes["place"] > 1].iterrows()
        ]
        survol = (
            f"<b>{poste} : {c['champion']}</b><br>"
            f"{pct(c['taux_victoire'])} sur {int(c['parties'])} parties "
            f"(IC 95 % : {pct(c['ic_bas'])} à {pct(c['ic_haut'])})<br>"
            + (
                "<br>Alternatives :<br>" + "<br>".join(alternatives)
                if alternatives
                else "<br>Pas d'autre champion assez joué"
            )
        )
        etiquette = (
            f"<b>{poste}</b><br>{pct(c['taux_victoire'])} · {int(c['parties'])} p."
        )
        _repere(fig, poste, str(c["champion"]), couleur, survol, etiquette)
    return fig


def figure_tableau(compo: pd.DataFrame | None = None, hauteur: int = 600) -> go.Figure:
    """Tableau tactique : la carte en mode dessin (à afficher avec CONFIG_DESSIN).
    Si `compo` est donné, nos champions retenus sont placés à leur poste."""
    fig = go.Figure()
    _fond_carte(fig, hauteur, dessin=True)
    fig.update_layout(
        newshape={"line": {"color": OR, "width": 4}, "opacity": 0.9},
        # Garde les dessins quand Streamlit redessine la figure sans changement
        uirevision="tableau",
    )
    if compo is not None:
        for c in compo[compo["place"] == 1].itertuples():
            if c.poste in POSITIONS:
                _repere(
                    fig,
                    c.poste,
                    str(c.champion),
                    OR,
                    f"<b>{c.poste} : {c.champion}</b>",
                    None,
                )
    return fig
