"""Entraîne le modèle « et si ? » une seule fois : uv run python train.py

Cible : victoire (0/1). Variables : champion, adversaire, poste, rang, c'est-à-dire
uniquement ce qui est connu AVANT la partie (kills, or, durée… sont interdits :
fuite de données). Sorties : model.joblib et metriques.json.
"""

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

import data

RACINE = Path(__file__).parent
VARIABLES = ["champion", "adversaire", "poste", "rang"]
CIBLE = "victoire"
LISSAGE = 20  # parties « fictives » à 50 % ajoutées à chaque groupe de la référence


def preparer(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = df.dropna(subset=VARIABLES)
    return df[VARIABLES].astype(str), df[CIBLE].astype(int)


def creer_modele() -> Pipeline:
    return Pipeline(
        [
            ("encodage", OneHotEncoder(handle_unknown="ignore")),
            ("modele", LogisticRegression(C=0.1, max_iter=2000)),
        ]
    )


def reference(x_train, y_train, x_test) -> np.ndarray:
    """Référence : le taux de victoire du champion à ce poste et à ce rang.

    Calculé sur les plis d'entraînement seulement, lissé vers la moyenne pour
    les groupes à peu de parties.
    """
    cles = ["champion", "poste", "rang"]
    moyenne = y_train.mean()
    groupes = (
        x_train[cles].assign(v=y_train.values).groupby(cles)["v"].agg(["sum", "count"])
    )
    taux = (groupes["sum"] + LISSAGE * moyenne) / (groupes["count"] + LISSAGE)
    index = pd.MultiIndex.from_frame(x_test[cles])
    return taux.reindex(index).fillna(moyenne).to_numpy()


def main() -> None:
    x, y = preparer(data.charger())
    plis = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = {"auc": [], "exactitude": [], "auc_ref": [], "exactitude_ref": []}

    for i, (train, test) in enumerate(plis.split(x, y), start=1):
        modele = creer_modele().fit(x.iloc[train], y.iloc[train])
        proba = modele.predict_proba(x.iloc[test])[:, 1]
        ref = reference(x.iloc[train], y.iloc[train], x.iloc[test])
        y_test = y.iloc[test]
        scores["auc"].append(roc_auc_score(y_test, proba))
        scores["exactitude"].append(accuracy_score(y_test, proba >= 0.5))
        scores["auc_ref"].append(roc_auc_score(y_test, ref))
        scores["exactitude_ref"].append(accuracy_score(y_test, ref >= 0.5))
        print(
            f"pli {i} : AUC {scores['auc'][-1]:.3f} "
            f"(référence {scores['auc_ref'][-1]:.3f})"
        )

    metriques = {
        "modele": "Régression logistique (one-hot : champion, adversaire, poste, rang)",
        "validation": "validation croisée stratifiée à 5 plis",
        "auc": round(float(np.mean(scores["auc"])), 4),
        "auc_ecart_type": round(float(np.std(scores["auc"])), 4),
        "exactitude": round(float(np.mean(scores["exactitude"])), 4),
        "auc_reference": round(float(np.mean(scores["auc_ref"])), 4),
        "exactitude_reference": round(float(np.mean(scores["exactitude_ref"])), 4),
        "reference": "taux de victoire du champion à ce poste et à ce rang "
        "(plis d'entraînement, lissé)",
        "lignes": len(x),
        "variables": VARIABLES,
        "date": date.today().isoformat(),
    }

    # Modèle final, entraîné sur toutes les lignes
    joblib.dump(creer_modele().fit(x, y), RACINE / "model.joblib", compress=3)
    (RACINE / "metriques.json").write_text(
        json.dumps(metriques, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metriques, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
