# LoL Helper

**URL de l'appli :** https://awpprojectcoda-ffzqbmrzu2kwjusemh9nym.streamlit.app
**URL de l'API :** https://lol-helper-api.onrender.com *(à confirmer après le déploiement Render)* — documentation : `/docs`

**Pour :** un coach de joueurs classés (ou un joueur), qui doit choisir quel champion
jouer (le main) selon le rang et le poste, avec des chiffres fiables, et croiser ses
propres parties (OP.GG) avec nos statistiques.

**Données :** League of Legends Relational Database for Match Prediction
(Kaggle, nathansmallcalder), API Riot Games, patchs 15.19 à 16.1, EUW / NA / KR,
licence *<à relever sur Kaggle>*. Données de joueur : serveur MCP officiel d'OP.GG.

**Préparation :** `prep.py` (parties classées CLASSIC ≥ 5 min, ADC / support
séparés par l'objet de support) → `Data/processed/joueurs.parquet`.

**Limites :** rangs non représentatifs du jeu (joueurs suivis : Master
surreprésenté, Challenger presque absent), ~1 joueur suivi par partie,
~1 % d'ADC / supports mal classés, petits effectifs par rang × patch × poste
(d'où l'absence de face-à-face : trop peu de parties par paire de champions ;
la composition conseillée est le meilleur champion par poste, pas une équipe testée).

**Framework :** Streamlit pour l'interface : mise en ligne gratuite sur Community
Cloud, cache et formulaires intégrés, adapté à un outil d'aide à la décision.
FastAPI pour l'API séparée : typée, documentation automatique, asynchrone (utile
pour l'assistant qui attend le LLM et les serveurs MCP).

**Couche ML :** régression logistique (one-hot : champion, adversaire, poste, rang),
probabilité de victoire **avant** la partie. Validation croisée à 5 plis :
**AUC 0,518** contre **0,512** pour la référence (taux de victoire du champion à ce
poste et à ce rang) ; exactitude 51,2 % contre 50,9 %. Limite : le modèle ne connaît
pas le niveau du joueur, et les stats de fin de partie sont exclues (fuite de
données), d'où une AUC proche de 0,5.

**Couche LLM (assistant) :** `openai/gpt-oss-120b` via Groq (gratuit), orchestré
par PydanticAI, avec deux serveurs MCP :
- **nos données** (`mcp_donnees.py`, FastMCP) : `decrire_donnees`,
  `meilleurs_champions`, `profil_champion`, `predire_victoire` ;
- **OP.GG** (serveur MCP officiel, `https://mcp-api.op.gg/mcp`) : profil d'un
  joueur, ses dernières parties, méta par poste (3 outils retenus sur 30, pour tenir
  dans le quota gratuit de Groq ; réponses tronquées à 6 000 caractères).

Le comportement et le vocabulaire (LoL et data science) sont dans
`assistant_lol.md`, chargé comme prompt système à chaque requête : les modèles
gratuits de Groq ne peuvent pas être fine-tunés. Règles : aucun chiffre inventé,
source et nombre de parties toujours cités, réponse d'abord avec nos données.
Texte généré par une IA, signalé comme tel dans l'appli.

**Sécurité :** clé Groq uniquement dans `.env` (local, ignoré par git) ou dans les
variables d'environnement de Render ; jamais dans le dépôt. Outils MCP en lecture
seule. L'appli fonctionne sans l'API (message clair si elle ne répond pas).

**Assistant de code :** Claude Code, pour écrire et tester le code (data.py, app.py,
API, serveur MCP, tests), relire l'accessibilité par captures d'écran et mettre à
jour la documentation. *(à ajuster par l'équipe)*

**Depuis la version intermédiaire :**
- 4 indicateurs (parties, champions distincts, champion le plus joué, meilleur
  champion) à la place du taux de victoire moyen, qui valait toujours ~50 % ;
- bug des petits rangs corrigé (Grandmaster faisait planter l'appli) ;
- graphique de fiabilité (taux × parties avec la zone du hasard), zoom sur un
  champion (selon le rang, selon la durée, ses parties), parties par rang ;
- contre-pick retiré : au mid en Gold, aucune paire champion × adversaire
  n'atteint 20 parties ;
- couche ML « Et si ? », API FastAPI séparée, assistant IA avec MCP (nos données
  et OP.GG), composition et bans conseillés.

## Lancer en local

```bash
uv sync
cp .env.example .env          # puis y mettre GROQ_API_KEY (gratuite : console.groq.com)
uv run python train.py        # (re)crée model.joblib et metriques.json
uv run uvicorn api:app --host 127.0.0.1 --port 8000      # l'API (terminal 1)
uv run streamlit run app.py --server.address 127.0.0.1    # l'appli (terminal 2)
uv run pytest tests -q
uv run ruff check . && uv run ruff format --check .
```

Serveur MCP « nos données » seul, pour un autre client MCP (Claude Desktop…) :
`uv run python mcp_donnees.py` (stdio, lecture seule).

## Déploiement

- **Appli** : Streamlit Community Cloud, branche `main`, fichier `app.py`. Secret
  `API_URL` = l'URL de l'API. Après un push qui modifie un autre fichier
  qu'`app.py`, faire « Reboot app ».
- **API** : Render (offre gratuite), web service depuis le dépôt public.
  Build : `pip install uv && uv sync --frozen --no-dev` ; démarrage :
  `uv run --no-dev uvicorn api:app --host 0.0.0.0 --port $PORT` ; variables :
  `GROQ_API_KEY`, `PYTHON_VERSION=3.13.0` (voir `render.yaml`). Le service
  gratuit s'endort après 15 min : ouvrir `/sante` avant une démo.

## Fichiers

| Fichier | Rôle |
|---|---|
| `prep.py` | CSV bruts → Parquet (lancé une seule fois) |
| `data.py` | calculs pandas purs (filtres, indicateurs, intervalles de confiance, stats par rang et par durée, composition, bans) |
| `app.py` | l'interface Streamlit (filtres, indicateurs, graphiques, zoom, « Et si ? », assistant, méthode et limites) |
| `train.py` | entraîne le modèle → `model.joblib`, `metriques.json` |
| `modele.py` | chargement du modèle et prédiction (partagé par l'appli et l'API) |
| `api.py` | l'API FastAPI |
| `mcp_donnees.py` | le serveur MCP de nos données |
| `assistant.py` | l'agent : Groq + MCP nos données + MCP OP.GG |
| `assistant_lol.md` | le prompt système : rôle, règles, vocabulaire LoL et data science |
| `render.yaml` | le déploiement de l'API sur Render |
| `tests/test_app.py` | les tests : filtres, petits rangs, zoom, ML, API, assistant sans API, données |
