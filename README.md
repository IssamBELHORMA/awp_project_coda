# LoL Helper

**URL :** https://<nom>.streamlit.app *(à remplir après le déploiement)*

**Pour :** un coach de joueurs classés, qui doit conseiller quel champion jouer
(le main) selon le rang et le poste, avec des chiffres fiables.

**Données :** League of Legends Relational Database for Match Prediction
(Kaggle, nathansmallcalder), API Riot Games, patchs 15.19 à 16.1, EUW / NA / KR,
licence *<à relever sur Kaggle>*.

**Préparation :** `prep.py` (parties classées CLASSIC ≥ 5 min, ADC / support
séparés par l'objet de support) → `Data/processed/joueurs.parquet`.

**Limites :** rangs non représentatifs du jeu (joueurs suivis : Master
surreprésenté, Challenger presque absent), ~1 joueur suivi par partie,
~1 % d'ADC / supports mal classés, petits effectifs par rang × patch × poste
(d'où l'absence de face-à-face : trop peu de parties par paire de champions).

**Framework :** Streamlit : mise en ligne gratuite et rapide sur Community Cloud,
cache et formulaires intégrés, adapté à un outil d'aide à la décision.

**Couche ML :** *(sprint 3)*

**Assistant de code :** *<lequel, pour quoi faire>*

**Depuis la version intermédiaire :** 4 indicateurs (parties, champions distincts,
champion le plus joué, meilleur champion) à la place du taux de victoire moyen,
qui valait toujours ~50 % ; bug des petits rangs corrigé (Grandmaster
faisait planter l'appli), graphique de fiabilité (taux × parties avec la zone du
hasard), zoom sur un champion (selon le rang, selon la durée, ses parties),
parties par rang dans « Méthode et limites ». Contre-pick retiré : au mid en Gold,
aucune paire champion × adversaire n'atteint 20 parties.

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
| `data.py` | calculs pandas purs (filtres, indicateurs, top par poste, intervalles de confiance, stats par rang et par durée) |
| `app.py` | l'interface Streamlit (filtres, indicateurs, graphique principal, fiabilité, zoom sur un champion, méthode et limites) |
| `tests/test_app.py` | 17 tests : un filtre change vraiment les indicateurs, petits rangs sans erreur, zoom, fonctions de `data.py` |
