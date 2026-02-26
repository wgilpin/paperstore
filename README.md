# PaperStore

A personal research paper library. Submit papers by URL (arXiv or direct PDF link), store them in PostgreSQL with full-text search, back the PDFs up to your Google Drive, and annotate them with tags and notes. Metadata extraction via Gemini is built in.

---

## Features

- Submit papers from arXiv URLs or direct PDF links
- Automatic metadata ingestion from the arXiv API
- LLM-assisted metadata extraction (title, authors, date, abstract) from PDF text via Gemini
- PDF storage in your own Google Drive
- Full-text search (PostgreSQL tsvector / GIN index) across title, abstract, and authors
- Tags, user notes, sort, and pagination
- Single-user — protected by Google OAuth 2.0

---

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL 16 |
| Auth | Google OAuth 2.0 (Desktop app credentials) |
| Storage | Google Drive API |
| LLM | Google Gemini API |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Packaging | `uv` |
| Container | Docker + Docker Compose |

---

## Prerequisites

- Docker and Docker Compose
- A Google Cloud project with the following enabled:
  - **Google Drive API**
  - **Google Generative Language API** (Gemini)
  - An **OAuth 2.0 Desktop application** credential
- A Gemini API key

---

## Configuration

Copy `.env.example` to `.env` and fill in all values.

```bash
cp .env.example .env
```

```dotenv
# PostgreSQL — the docker-compose.yml overrides this for the api container
DATABASE_URL=postgresql://paperstore:paperstore@localhost:5432/paperstore

# Absolute path to your Google OAuth 2.0 Desktop credentials JSON file
# Download from Google Cloud Console → APIs & Services → Credentials
GOOGLE_CREDENTIALS_PATH=/absolute/path/to/credentials.json

# Where the OAuth token will be written after first authorisation
# The file is created automatically; just provide the desired path
GOOGLE_TOKEN_PATH=/absolute/path/to/token.json

# Must match exactly what is registered in Google Cloud Console
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
GOOGLE_JS_ORIGIN=http://localhost:8000

# Optional: Drive folder ID to upload papers into (blank = Drive root)
DRIVE_FOLDER_ID=

# Session cookie signing key
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET=replace-me

# Gemini API key and model name
GEMINI_API_KEY=AIza...
GEMINI_PDF_MODEL=gemini-2.0-flash
```

> **Important:** `GOOGLE_CREDENTIALS_PATH` and `GOOGLE_TOKEN_PATH` must be **absolute paths** — `~` is not expanded. The credentials file is mounted read-only into the container. The token directory is persisted via a named Docker volume.

---

## Local Development

```bash
# 1. Clone and configure
git clone <repo>
cd paperStore
cp .env.example .env
# edit .env — fill in all values

# 2. Start the stack
docker compose up

# 3. Open the app
open http://localhost:8000
```

On first load you are redirected to Google OAuth. After authorising, you are returned to the paper library.

### Hot reload

`docker-compose.yml` mounts `./backend/src` and `./frontend` directly into the container. Uvicorn runs with `--reload`, so backend changes apply immediately. Frontend changes are served as static files — refresh the browser.

### Running tests

```bash
cd backend
uv run pytest
```

Tests cover backend services only (no API endpoint tests, no frontend tests, no live network calls).

### Linting and type-checking

```bash
cd backend
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

---

## Project Structure

```text
paperStore/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml          # Dependencies + ruff / mypy config
│   ├── uv.lock
│   └── src/
│       ├── main.py             # FastAPI app, middleware, startup
│       ├── db.py               # SQLAlchemy engine, schema, FTS trigger
│       ├── api/                # Route handlers (auth, papers, tags)
│       ├── models/             # ORM models
│       ├── schemas/            # Pydantic request / response schemas
│       └── services/
│           ├── ingestion.py    # Paper submission workflow
│           ├── search.py       # Full-text search
│           ├── drive.py        # Google Drive upload / download
│           ├── gemini.py       # LLM metadata extraction
│           ├── arxiv_client.py # arXiv API client
│           ├── pdf_parser.py   # PDF text extraction
│           └── types.py        # Shared TypedDicts
├── frontend/
│   ├── index.html              # Paper list page
│   ├── paper.html              # Paper detail page
│   └── static/
│       ├── index.js
│       ├── paper.js
│       └── utils.js
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable the **Google Drive API** and the **Generative Language API**.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**
   - Download the JSON — this is your `credentials.json`.
4. On the **OAuth consent screen**, add your Google account as a test user (required while the app is in Testing mode).
5. Get a **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey) and set it as `GEMINI_API_KEY`.

---

## Deploying to Coolify

Coolify can build and run the Docker Compose stack directly from your Git repository.

### 1. Push the repository

Make the repo accessible to Coolify (GitHub, GitLab, Gitea, or a self-hosted source).

### 2. Create a new service

- **New Resource → Docker Compose**
- Point it at your repository and branch.
- Coolify will detect `docker-compose.yml` automatically.

### 3. Set environment variables

In Coolify's **Environment Variables** panel, set all variables from `.env.example`. Key differences from local:

| Variable | Production value |
| --- | --- |
| `GOOGLE_REDIRECT_URI` | `https://your-domain.com/auth/callback` |
| `GOOGLE_JS_ORIGIN` | `https://your-domain.com` |
| `SESSION_SECRET` | A securely generated random hex string |
| `DATABASE_URL` | Leave unset — `docker-compose.yml` sets it to the internal `db` host |
| `GOOGLE_CREDENTIALS_PATH` | `/root/.config/paperstore/credentials.json` (see below) |
| `GOOGLE_TOKEN_PATH` | `/root/.config/paperstore/token.json` |

Do **not** set `OAUTHLIB_INSECURE_TRANSPORT` in production — it is only needed for local HTTP.

### 4. Mount the Google credentials file

The `credentials.json` OAuth file must be present inside the container. Use Coolify's **Persistent Storage** tab to bind-mount it:

- **Source** (on the Coolify server): `/opt/paperstore/credentials.json`
  - Copy the file to this path on the server via SSH before deploying.
- **Destination** (inside container): `/root/.config/paperstore/credentials.json`
- **Mode**: read-only

```bash
# SSH to the server and place the file
ssh user@coolify-server
mkdir -p /opt/paperstore
scp credentials.json user@coolify-server:/opt/paperstore/credentials.json
```

### 5. OAuth token persistence

The token (`token.json`) is created automatically on first login. It is stored in the `google_token` named Docker volume, so it survives container restarts and redeployments.

After deploying, visit `https://your-domain.com/auth/login` in your browser to complete the OAuth flow. The token is then cached in the volume for all future requests.

### 6. Update Google Cloud Console

Before OAuth will work with your production domain, register it in Google Cloud Console:

- **Authorised redirect URIs**: `https://your-domain.com/auth/callback`
- **Authorised JavaScript origins**: `https://your-domain.com`

### 7. Deploy

Click **Deploy** in Coolify. The `db` service starts first, then `api`. Database tables and the full-text search trigger are created automatically at startup.

---

## API Reference

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/auth/login` | Start Google OAuth flow |
| `GET` | `/auth/callback` | OAuth callback |
| `POST` | `/papers` | Submit a paper by URL |
| `GET` | `/papers` | List / search papers |
| `GET` | `/papers/{id}` | Get paper detail |
| `PATCH` | `/papers/{id}` | Update metadata |
| `DELETE` | `/papers/{id}` | Delete paper |
| `PATCH` | `/papers/{id}/note` | Update user note |
| `POST` | `/papers/{id}/extract-metadata` | LLM metadata extraction |
| `GET` | `/papers/{id}/pdf` | Redirect to Drive preview |
| `GET` | `/tags` | List tags with usage counts |

Interactive API docs are available at `/docs` (Swagger UI) and `/redoc` when running locally.
