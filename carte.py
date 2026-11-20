"""Carte schématique de la Faille de l'invocateur, dessinée avec des formes Plotly
(aucune image) : bases, trois voies, rivière, zones de jungle, et un repère par
poste pour la composition conseillée.

Repère : carré 0-100, base bleue en bas à gauche, base rouge en haut à droite.
"""

from collections.abc import Callable

import pandas as pd
import plotly.graph_objects as go

# Couleurs de la carte, volontairement ternes pour laisser ressortir les repères
SOL = "#111C2E"
JUNGLE = "rgba(122, 133, 153, 0.10)"
VOIE = "#33435E"
RIVIERE = "rgba(58, 154, 212, 0.22)"
BASE_BLEUE = "rgba(58, 154, 212, 0.35)"
BASE_ROUGE = "rgba(213, 94, 0, 0.35)"
TEXTE = "#F0E6D2"
TEXTE_DOUX = "#A09B8C"
FOND = "#0A1428"

# Position de chaque poste côté bleu, et décalage de l'étiquette (en pixels)
POSITIONS = {
    "TOP": (9, 80, 14, 0, "left"),
    "JUNGLE": (22, 40, 14, 0, "left"),
    "MIDDLE": (50, 50, -12, 22, "right"),
    "ADC": (66, 9, -14, 0, "right"),
    "SUPPORT": (91, 24, -14, 0, "right"),
}


def _voie(fig, xs, ys):
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line={"color": VOIE, "width": 14},
            hoverinfo="skip",
            showlegend=False,
        )
    )


def figure(
    compo: pd.DataFrame,
    couleurs: dict[str, str],
    pct: Callable[[float], str],
    postes: list[str],
    hauteur: int = 410,
) -> go.Figure:
    """La carte avec, pour chaque poste, le champion retenu (place 1) ; le survol
    donne les alternatives (places 2 et 3)."""
    fig = go.Figure()

    # Zones de jungle : les quatre triangles entre les voies, le mid et la rivière
    for chemin in [
        "M 15 24 L 15 76 L 41 50 Z",
        "M 24 15 L 76 15 L 50 41 Z",
        "M 85 24 L 85 76 L 59 50 Z",
        "M 24 85 L 76 85 L 50 59 Z",
    ]:
        fig.add_shape(
            type="path", path=chemin, line_width=0, fillcolor=JUNGLE, layer="below"
        )
    # La rivière : l'autre diagonale
    fig.add_shape(
        type="line",
        x0=4,
        y0=96,
        x1=96,
        y1=4,
        line={"color": RIVIERE, "width": 22},
        layer="below",
    )
    # Les trois voies
    _voie(fig, [9, 9, 91], [18, 91, 91])  # top : à gauche puis en haut
    _voie(fig, [16, 84], [16, 84])  # mid : la diagonale
    _voie(fig, [18, 91, 91], [9, 9, 82])  # bot : en bas puis à droite
    # Les bases
    for x, y, couleur in [
        (9, 9, BASE_BLEUE),
        (91, 91, BASE_ROUGE),
    ]:
        fig.add_shape(
            type="circle",
            x0=x - 7,
            y0=y - 7,
            x1=x + 7,
            y1=y + 7,
            fillcolor=couleur,
            line={"color": TEXTE_DOUX, "width": 1},
        )
    fig.add_annotation(
        x=2,
        y=17,
        text="Base bleue (nous)",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font={"size": 13, "color": TEXTE},
    )
    fig.add_annotation(
        x=98,
        y=83,
        text="Base rouge",
        showarrow=False,
        xanchor="right",
        yanchor="top",
        font={"size": 13, "color": TEXTE},
    )
    fig.add_annotation(
        x=64,
        y=36,
        text="rivière",
        showarrow=False,
        textangle=45,
        font={"size": 13, "color": TEXTE},
    )

    # Les repères des postes
    for poste in postes:
        x, y, dx, dy, ancre = POSITIONS[poste]
        lignes = compo[compo["poste"] == poste]
        choisi = lignes[lignes["place"] == 1]
        couleur = couleurs[poste]
        if choisi.empty:
            etiquette = f"<b>{poste}</b> · —<br>aucun assez joué"
            survol = f"<b>{poste}</b><br>Aucun champion n'atteint le minimum"
            symbole, taille = "circle-open", 18
        else:
            c = choisi.iloc[0]
            etiquette = (
                f"<b>{poste} · {c['champion']}</b><br>"
                f"{pct(c['taux_victoire'])} · {int(c['parties'])} p."
            )
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
            symbole, taille = "circle", 20
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                marker={
                    "color": couleur,
                    "size": taille,
                    "symbol": symbole,
                    "line": {
                        "color": FOND if symbole == "circle" else couleur,
                        "width": 2,
                    },
                },
                hovertemplate=survol + "<extra></extra>",
                hoverlabel={"font_size": 13},
                showlegend=False,
                name=poste,
            )
        )
        fig.add_annotation(
            x=x,
            y=y,
            text=etiquette,
            showarrow=False,
            xanchor=ancre,
            xshift=dx,
            yshift=dy,
            align=ancre,
            font={"size": 13, "color": TEXTE},
            bgcolor="rgba(10, 20, 40, 0.88)",
            bordercolor=couleur,
            borderwidth=2,
            borderpad=4,
        )

    fig.update_xaxes(range=[0, 100], visible=False, fixedrange=True)
    fig.update_yaxes(
        range=[0, 100],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        constrain="domain",
    )
    fig.update_layout(
        height=hauteur,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        plot_bgcolor=SOL,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"size": 13, "color": TEXTE},
        hoverlabel={"bgcolor": FOND, "font_color": TEXTE, "bordercolor": TEXTE_DOUX},
        dragmode=False,
    )
    return fig
