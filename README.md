# SP2I_Build

SP2I_Build est une application métier orientée construction, DQE et pilotage CAPEX.  
Le projet combine un pipeline data Python, une API FastAPI, des dashboards Streamlit et une base analytique exploitable pour des usages type Power BI.

## Objectifs

- Centraliser les données DQE, métrés, lots, familles, bâtiments et niveaux
- Produire des dashboards métier fiables :
  - `Direction`
  - `Audit Chantier`
  - `Audit Import`
- Outiller l’import intelligent de DQE Excel / PDF
- Préparer une base robuste pour une future extension ERP / SaaS

## Architecture actuelle

### Stack technique

- `Python` pour ETL, services métier et tests
- `FastAPI` pour l’API backend
- `Streamlit` pour le frontend et les dashboards
- `SQLite` pour le local
- `SQLAlchemy` pour le modèle analytique et la couche SaaS
- `Plotly` pour les visualisations

### Vision cible

- `Python ETL + BI` pour la donnée et l’analyse
- `Dashboard Streamlit` pour le pilotage rapide
- `Future Java` pour une couche ERP / métier plus large si nécessaire

## Structure du projet

```text
sp2i_build/
├── backend/                 # API FastAPI, modèles, services, contrats
│   ├── api/                 # Routes HTTP
│   ├── contracts/           # Schémas de contrats métier
│   ├── core/                # Sécurité, config SaaS
│   ├── db/                  # Session SQLAlchemy, scripts d'init / seed
│   ├── models/              # Modèles SQLAlchemy
│   ├── saas_services/       # Services orientés SaaS
│   └── services/            # Services dashboards, DQE, ERP
├── frontend/                # Application Streamlit
│   ├── pages/               # Pages dashboards et écrans métier
│   ├── api_client.py        # Client HTTP vers FastAPI
│   └── ui.py                # Composants visuels partagés
├── data/                    # Scripts d'import et fichiers source locaux
├── scripts/                 # Scripts d'audit, comparaison et migration
├── sql/                     # Scripts SQL de structure et migration
├── tests/                   # Tests automatiques
├── artifacts/               # Rapports générés localement
├── run_app.bat              # Lancement rapide Windows
├── run_app.ps1              # Lancement PowerShell
└── requirements.txt         # Dépendances Python
```

## Organisation recommandée à moyen terme

Sans casser l’existant, l’organisation suivante est recommandée pour professionnaliser encore le dépôt :

```text
sp2i_build/
├── apps/
│   ├── api/                 # FastAPI
│   └── dashboard/           # Streamlit
├── domain/                  # Logique métier pure
├── infrastructure/          # Base, fichiers, connecteurs externes
├── etl/                     # Pipelines d'import et transformation
├── docs/                    # Documentation fonctionnelle et technique
├── scripts/                 # Outils ponctuels
├── tests/                   # Tests unitaires / intégration
└── sql/                     # DDL / migrations SQL
```

Cette cible est une proposition. Le dépôt actuel est déjà exploitable tel quel.

## Installation locale

### 1. Créer un environnement virtuel

```powershell
python -m venv venv
venv\Scripts\activate
```

### 2. Installer les dépendances

```powershell
python -m pip install -r requirements.txt
```

### 3. Lancer l’API FastAPI

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Lancer le frontend Streamlit

```powershell
python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

### Alternative Windows

```powershell
.\run_app.ps1
```

ou

```cmd
run_app.bat
```

## Deploiement Streamlit Cloud

### Point d'entree recommande

Le fichier racine a utiliser sur Streamlit Cloud est :

```text
streamlit_app.py
```

### Configuration requise

L'application Streamlit ne demarre pas de backend FastAPI elle-meme.  
Pour un deploiement cloud stable, il faut fournir une URL backend publique via :

- variable d'environnement `SP2I_API_URL`
- ou secret Streamlit `SP2I_API_URL`

Exemple :

```toml
SP2I_API_URL = "https://mon-backend-fastapi.example.com"
```

Si ce parametre n'est pas fourni, l'application essaiera `http://127.0.0.1:8000`, ce qui ne fonctionne que localement.

### Ce qui est cloud-safe

- `streamlit_app.py` comme point d'entree simple
- `frontend/app.py` sans ETL ni initialisation lourde
- gestion propre si le backend n'est pas joignable
- dependances Python epinglees dans `requirements.txt`
- version Python fixee dans `runtime.txt`

## Deploiement FastAPI

Le depot contient maintenant deux fichiers utiles pour deployer l'API :

- [Procfile](./Procfile)
- [render.yaml](./render.yaml)

### Commande backend

Le backend FastAPI est lance avec :

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Variables backend recommandees

- `SP2I_JWT_SECRET`
- `SP2I_DATABASE_URL`

Exemple PostgreSQL :

```bash
SP2I_DATABASE_URL=postgresql+psycopg://user:password@host:5432/sp2i_build
```

### Note importante

Le code supporte SQLite en local, mais pour un hebergement cloud stable il est recommande d'utiliser PostgreSQL plutot qu'une base SQLite embarquee.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Bases locales

Le projet peut utiliser plusieurs bases locales selon le module :

- `sp2i_build.db` : base analytique / historique principale
- `sp2i_saas.db` : socle SaaS local
- `sp2i_erp.db` : base ERP / DQE locale structurée

Ces fichiers sont utiles en local, mais ne devraient pas être versionnés sur GitHub.

## Variables d’environnement utiles

Voir [.env.example](./.env.example)

Variables principales :

- `SP2I_DATABASE_URL`
- `SP2I_JWT_SECRET`
- `SP2I_ACCESS_TOKEN_EXPIRE_MINUTES`

## Workflow Git recommandé

### Branches

- `main` : branche stable
- `develop` : intégration continue de fonctionnalités
- `feature/...` : nouvelle fonctionnalité
- `fix/...` : correction ciblée
- `refactor/...` : amélioration interne sans changement fonctionnel

### Convention de commit

- `feat: ajout du dashboard audit import`
- `fix: correction du calcul capex optimise`
- `refactor: simplification du service de ventilation`
- `docs: mise à jour du readme`
- `test: ajout des smoke tests api`

Le détail est documenté dans [CONTRIBUTING.md](./CONTRIBUTING.md).

## Fichiers sensibles ou volumineux

À ne pas pousser sur GitHub :

- fichiers `.env`
- bases `.db`
- exports `artifacts/*.csv`, `artifacts/*.pdf`
- sources métier lourdes `*.pdf`, `*.xlsx`
- logs runtime

## Points d’attention sur le dépôt actuel

Le dépôt contient déjà des fichiers qui devraient idéalement sortir du suivi Git :

- bases SQLite locales
- fichiers Excel / PDF métier
- logs
- `__pycache__`

Le `.gitignore` ajouté empêche les nouveaux ajouts, mais les fichiers déjà suivis doivent être retirés de l’index Git via une opération de nettoyage dédiée.

## Roadmap technique

- consolider une source de vérité unique par dashboard
- renforcer les migrations de données DQE
- améliorer la séparation `métier / API / UI`
- préparer une cible PostgreSQL / MySQL ou Java ERP selon les besoins
