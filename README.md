# LoL Helper

**URL :** https://<nom>.streamlit.app *(à remplir après le déploiement)*

**Pour :** un coach de joueurs classés, qui doit conseiller quel champion jouer
(le main) et quel champion choisir contre un adversaire (le contre-pick),
selon le rang et le poste.

**Données :** League of Legends Relational Database for Match Prediction
(Kaggle, nathansmallcalder), API Riot Games, patchs 15.19 à 16.1, EUW / NA / KR,
licence *<à relever sur Kaggle>*.

**Préparation :** `prep.py` (parties classées CLASSIC ≥ 5 min, ADC / support
séparés par l'objet de support) → `Data/processed/joueurs.parquet`.

**Limites :** rangs non représentatifs du jeu (joueurs suivis : Master
surreprésenté, Challenger presque absent), ~1 joueur suivi par partie,
~1 % d'ADC / supports mal classés, petits effectifs par rang × patch × poste.

**Framework :** Streamlit : mise en ligne gratuite et rapide sur Community Cloud,
cache et formulaires intégrés, adapté à un outil d'aide à la décision.

**Couche ML :** *(sprint 3)*

**Assistant de code :** *<lequel, pour quoi faire>*

**Depuis la version intermédiaire :** *(à remplir)*

## Lancer

```bash
uv sync
uv run streamlit run app.py --server.address 127.0.0.1
uv run pytest tests -q
uv run ruff check . && uv run ruff format --check .
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `prep.py` | CSV bruts → Parquet (lancé une seule fois) |
| `data.py` | calculs pandas purs (charger, filtrer, indicateurs, top par patch et poste) |
| `app.py` | l'interface Streamlit (filtres, indicateurs, graphique principal) |
| `tests/test_app.py` | test AppTest : passer de Gold à Master change les indicateurs |
