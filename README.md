# LoL Helper

Aider un coach (ou un joueur) de parties classées à choisir **quel champion jouer selon
le rang et le poste**, avec des chiffres fiables, et à croiser ses propres parties
OP.GG avec nos statistiques.

- **Appli :** https://awpprojectcoda-ffzqbmrzu2kwjusemh9nym.streamlit.app
- **API :** https://lol-helper-api.onrender.com (documentation : `/docs`)

**Auteurs et collaborateurs :** Issam BELHORMA, Zakaria SOUAL, Basma BELARBI

## Fonctionnalités

- **Filtres** (rang, poste, région, patch, minimum de parties) dans une barre collée en
  haut de page, avec des liens vers chaque section.
- **4 indicateurs** : parties, champions distincts, champion le plus joué, meilleur
  champion.
- **Meilleur champion par poste**, par patch ou tous patchs confondus.
- **Composition et bans conseillés** sur la carte de la Faille, avec le portrait des
  champions.
- **Bac à sable du coach** : tous les champions du jeu à placer et déplacer, crayon,
  pinceau magique (s'efface en 3 s), Ctrl+Z, export PNG.
- **Fiabilité** : taux de victoire × nombre de parties, avec la zone du hasard.
- **Zoom sur un champion** : selon le rang, selon la durée, ses parties.
- **« Et si ? »** : probabilité de victoire avant la partie (modèle ML).
- **Assistant IA** (barre latérale) : accepte un Riot ID ou un lien OP.GG.

## Données et méthode

- **Source :** League of Legends Relational Database for Match Prediction (Kaggle,
  nathansmallcalder), API Riot Games, patchs 15.19 à 16.1, EUW / NA / KR, licence
  *<à relever sur Kaggle>*. Joueurs : serveur MCP officiel d'OP.GG.
- **Préparation :** `prep.py` garde les parties classées de plus de 5 min et sépare
  ADC et support → `Data/processed/joueurs.parquet`.
- **Fiabilité :** intervalle de confiance de Wilson à 95 % ; la composition classe les
  champions par la borne basse de cet intervalle.
- **Limites :** Master surreprésenté et Challenger presque absent, environ 1 joueur
  suivi par partie (pas de synergies ni de face-à-face), petits effectifs par rang ×
  patch × poste.

## Couches ML et IA

- **ML :** régression logistique (champion, adversaire, poste, rang). Validation
  croisée à 5 plis : **AUC 0,518** contre 0,512 pour la référence. Gain faible mais
  honnête : le niveau du joueur est inconnu, et les stats de fin de partie sont
  exclues pour éviter les fuites de données.
- **Assistant :** `openai/gpt-oss-120b` via Groq (gratuit), orchestré par PydanticAI,
  avec deux serveurs MCP :
  - **nos données** (`mcp_donnees.py`) ;
  - **OP.GG** (profil, dernières parties, méta).
- **Prompt :** `assistant_lol.md` contient le rôle, les règles (aucun chiffre inventé,
  sources citées) et le vocabulaire LoL / data science. Les modèles Groq gratuits ne se
  fine-tunent pas.
- **Sécurité :** la clé Groq est seulement dans `.env` (ignoré par git) ou dans
  Render. Les outils MCP sont en lecture seule. L'appli fonctionne sans l'API.

## Outils

- **Interface :** Streamlit (hébergement gratuit, cache, formulaires).
- **API :** FastAPI (typée, documentée, asynchrone).
- **Assistant de code :** Claude Code, pour écrire et tester le code et relire
  l'accessibilité.

## Lancer en local

```bash
uv sync
cp .env.example .env        # y mettre GROQ_API_KEY (gratuite : console.groq.com)
uv run python train.py      # crée model.joblib et metriques.json
uv run uvicorn api:app --host 127.0.0.1 --port 8000       # API (terminal 1)
uv run streamlit run app.py --server.address 127.0.0.1     # appli (terminal 2)
uv run pytest tests -q && uv run ruff check .
```

## Déploiement

- **Appli :** Streamlit Community Cloud, fichier `app.py`.
  - Secret : `API_URL = "https://lol-helper-api.onrender.com"`.
  - Après un push, faire « Reboot app ».
- **API :** Render, offre gratuite (voir `render.yaml`).
  - Variable : `GROQ_API_KEY`.
  - L'API s'endort après 15 min : ouvrir `/sante` avant une démo.

## Fichiers

| Fichier | Rôle |
|---|---|
| `prep.py` | CSV bruts → Parquet |
| `data.py` | calculs pandas (filtres, indicateurs, intervalles, composition, bans) |
| `app.py` | interface Streamlit |
| `carte.py` | carte de la Faille et portraits (Data Dragon) |
| `tableau.html` | bac à sable du coach |
| `train.py`, `modele.py` | entraînement et prédiction du modèle |
| `api.py` | API FastAPI |
| `mcp_donnees.py` | serveur MCP de nos données |
| `assistant.py`, `assistant_lol.md` | assistant IA et son prompt |
| `render.yaml` | déploiement de l'API |
| `tests/test_app.py` | tests |
