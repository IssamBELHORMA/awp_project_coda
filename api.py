"""API LoL Helper (FastAPI) : nos données, le modèle « et si ? » et l'assistant.

Lancer : uv run uvicorn api:app --host 127.0.0.1 --port 8000
Doc interactive : http://127.0.0.1:8000/docs
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import data
import mcp_donnees


def charger_env() -> None:
    """Lit un fichier .env local (jamais versionné) s'il existe."""
    fichier = Path(__file__).parent / ".env"
    if fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                cle, valeur = ligne.split("=", 1)
                os.environ.setdefault(cle.strip(), valeur.strip().strip('"'))


charger_env()

import assistant

app = FastAPI(
    title="LoL Helper API",
    version="1.0.0",
    description="Statistiques de parties classées LoL, prédiction avant la partie "
    "et assistant IA (Groq + MCP : nos données et OP.GG).",
)


class DemandePrediction(BaseModel):
    champion: str = Field(examples=["Ahri"])
    adversaire: str = Field(examples=["Zed"])
    poste: str = Field(examples=["MIDDLE"])
    rang: str = Field(examples=["Gold"])


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    contenu: str


class DemandeAssistant(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    historique: list[Message] = []


@app.get("/sante")
def sante() -> dict:
    """Vérifie que l'API répond et si l'assistant est configuré."""
    return {
        "statut": "ok",
        "assistant_configure": bool(os.environ.get("GROQ_API_KEY")),
        "modele_llm": assistant.nom_modele(),
    }


@app.get("/donnees")
def donnees() -> dict:
    """Périmètre et limites de nos données."""
    return mcp_donnees.decrire_donnees()


@app.get("/champions")
def champions() -> list[str]:
    """La liste des champions de la base."""
    return sorted(mcp_donnees._df()["champion"].astype(str).unique())


@app.get("/meilleurs")
def meilleurs(
    rang: str = "Gold", poste: str = "MIDDLE", min_parties: int = 50, top: int = 8
) -> dict:
    """Les meilleurs champions à un rang et un poste."""
    if poste.upper() not in data.POSTES + ["MID", "BOT", "SUP"]:
        raise HTTPException(422, f"poste inconnu : {poste}")
    return mcp_donnees.meilleurs_champions(rang, poste, min_parties, top)


@app.get("/champion/{nom}")
def champion(nom: str, poste: str | None = None, rang: str | None = None) -> dict:
    """Le profil d'un champion (par rang, par durée)."""
    resultat = mcp_donnees.profil_champion(nom, poste, rang)
    if "erreur" in resultat:
        raise HTTPException(404, resultat["erreur"])
    return resultat


@app.post("/predire")
def predire(demande: DemandePrediction) -> dict:
    """Probabilité de victoire avant la partie (modèle « et si ? »)."""
    resultat = mcp_donnees.predire_victoire(**demande.model_dump())
    if "erreur" in resultat:
        raise HTTPException(404, resultat["erreur"])
    return resultat


@app.post("/assistant")
async def poser_question(demande: DemandeAssistant) -> dict:
    """Pose une question à l'assistant (Groq + MCP nos données + MCP OP.GG)."""
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(503, "assistant non configuré : GROQ_API_KEY manquante")
    try:
        return await assistant.repondre(
            demande.question, [m.model_dump() for m in demande.historique]
        )
    except Exception as erreur:  # quota Groq, OP.GG indisponible…
        raise HTTPException(
            502, f"l'assistant n'a pas pu répondre : {erreur}"
        ) from erreur
