"""L'assistant LoL Helper : un LLM gratuit (Groq) branché sur deux serveurs MCP.

- « nos données » : mcp_donnees.py (FastMCP, dans le même processus)
- OP.GG : serveur MCP officiel distant (https://mcp-api.op.gg/mcp)

Le comportement et le vocabulaire viennent de assistant_lol.md (prompt système).
Clé requise : GROQ_API_KEY (gratuite sur https://console.groq.com).
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

import mcp_donnees

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

RACINE = Path(__file__).parent
URL_OPGG = "https://mcp-api.op.gg/mcp"
MODELE_PAR_DEFAUT = "openai/gpt-oss-120b"
# Seuls les outils OP.GG utiles au coach : chaque schéma d'outil coûte des tokens
# à chaque appel, et l'offre gratuite de Groq limite les tokens par minute.
# (lol_get_lane_matchup_guide est écarté : sa réponse fait ~46 000 caractères.)
OUTILS_OPGG = {
    "lol_get_summoner_profile",
    "lol_list_summoner_matches",
    "lol_list_lane_meta_champions",
}
LIMITE_REPONSE_OUTIL = 6000  # caractères gardés par réponse d'outil OP.GG
APPLI = "LoL Helper/1.0"
TOURS_HISTORIQUE = 6  # derniers messages de la conversation renvoyés au modèle


async def appel_opgg(_ctx, appeler, nom: str, arguments: dict):
    """Ajoute `client_app` (demandé par OP.GG) et tronque les réponses trop longues."""
    resultat = await appeler(nom, {**arguments, "client_app": APPLI})
    texte = (
        resultat
        if isinstance(resultat, str)
        else json.dumps(resultat, ensure_ascii=False, default=str)
    )
    if len(texte) > LIMITE_REPONSE_OUTIL:
        return texte[:LIMITE_REPONSE_OUTIL] + " … [réponse tronquée]"
    return resultat


def nom_modele() -> str:
    return os.environ.get("GROQ_MODEL", MODELE_PAR_DEFAUT)


def instructions() -> str:
    return (RACINE / "assistant_lol.md").read_text(encoding="utf-8")


def creer_agent() -> Agent:
    nos_donnees = MCPToolset(mcp_donnees.serveur, id="nos_donnees")
    opgg = MCPToolset(
        URL_OPGG,
        id="opgg",
        tool_error_behavior="failed",
        process_tool_call=appel_opgg,
    ).filtered(lambda _ctx, outil: outil.name in OUTILS_OPGG)
    return Agent(
        f"groq:{nom_modele()}",
        instructions=instructions(),
        toolsets=[nos_donnees, opgg],
        retries=2,
    )


# Lien de profil OP.GG : op.gg/(lol/)summoners/<région>/<Nom>-<TAG>
LIEN_OPGG = re.compile(
    r"op\.gg/(?:[a-z]{2}/)?(?:lol/)?summoners/([a-z]+)/([^\s?#/]+)", re.IGNORECASE
)
TAG_PAR_DEFAUT = {"euw": "EUW", "eune": "EUNE", "na": "NA1", "kr": "KR1"}


def lire_lien_opgg(texte: str) -> str | None:
    """Tire la région et le Riot ID d'un lien OP.GG (sans lire la page)."""
    trouve = LIEN_OPGG.search(texte)
    if not trouve:
        return None
    region, joueur = trouve.group(1).lower(), unquote(trouve.group(2))
    nom, _, tag = joueur.rpartition("-")
    if not nom:
        nom, tag = joueur, TAG_PAR_DEFAUT.get(region, region.upper())
    return f"Riot ID : {nom}#{tag}, région : {region} (tiré du lien OP.GG)"


def formuler(question: str, historique: list[dict] | None) -> str:
    """Ajoute les derniers échanges à la question (contexte de conversation)."""
    lien = lire_lien_opgg(question)
    if lien:
        question = f"{question}\n[{lien}]"
    if not historique:
        return question
    lignes = [
        f"{'Utilisateur' if m['role'] == 'user' else 'Assistant'} : {m['contenu']}"
        for m in historique[-TOURS_HISTORIQUE:]
    ]
    return (
        "Conversation précédente :\n" + "\n".join(lignes) + f"\n\nQuestion : {question}"
    )


async def repondre(question: str, historique: list[dict] | None = None) -> dict:
    """Pose la question à l'agent. Renvoie la réponse et les outils appelés."""
    resultat = await creer_agent().run(formuler(question, historique))
    outils = [
        partie.tool_name
        for message in resultat.all_messages()
        for partie in message.parts
        if partie.part_kind == "tool-call"
    ]
    return {"reponse": resultat.output, "outils": outils, "modele": nom_modele()}
