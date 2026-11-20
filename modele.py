"""Chargement du modèle « et si ? » et prédiction (partagé par app.py et l'API)."""

import json
from pathlib import Path

import joblib
import pandas as pd

RACINE = Path(__file__).parent
CHEMIN_MODELE = RACINE / "model.joblib"
CHEMIN_METRIQUES = RACINE / "metriques.json"


def charger_modele():
    return joblib.load(CHEMIN_MODELE)


def charger_metriques() -> dict:
    return json.loads(CHEMIN_METRIQUES.read_text(encoding="utf-8"))


def predire(modele, champion: str, adversaire: str, poste: str, rang: str) -> float:
    """Probabilité de victoire (0 à 1) avant la partie."""
    x = pd.DataFrame(
        [{"champion": champion, "adversaire": adversaire, "poste": poste, "rang": rang}]
    )
    return float(modele.predict_proba(x)[0, 1])
