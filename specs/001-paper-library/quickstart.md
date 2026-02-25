# Quickstart: Academic Paper Library

**Feature**: 001-paper-library
**Date**: 2026-02-25

## Prerequisites

- Docker Desktop running
- Python 3.11 installed
- `uv` installed (`pip install uv` or via [uv installer](https://docs.astral.sh/uv/getting-started/installation/))
- Google Cloud project with OAuth 2.0 Desktop credentials (`credentials.json`)
- Chrome browser (for extension)

---

## 1. Clone and Install

```bash
git clone <repo-url>
cd paperStore
uv sync
```

---

## 2. Configure Google Drive

1. Copy your `credentials.json` (OAuth 2.0 Desktop app) into `~/.config/paperstore/`.
2. On first run, a browser window will open asking you to authorise Google Drive access.
   Approve it — `token.json` will be saved to `~/.config/paperstore/token.json`.

---

## 3. Start the Development Environment

```bash
docker compose up -d
```

This starts:
- PostgreSQL on `localhost:5432`

Then start the backend:

```bash
uv run uvicorn backend.main:app --reload
```

The API is now available at `http://localhost:8000`.

---

## 4. Run Database Migrations

```bash
uv run alembic upgrade head
```

---

## 5. Add a Paper (Web App)

Open `http://localhost:8000` in your browser (or the frontend URL if running separately).

1. Paste an arXiv URL (e.g., `https://arxiv.org/abs/2301.00001`) into the input field.
2. Click **Add Paper**.
3. The paper appears in your library within ~30 seconds.

---

## 6. Install the Chrome Extension

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked** → select the `extension/` directory in this repo
4. Navigate to any arXiv paper page (e.g., `https://arxiv.org/abs/2301.00001`)
5. Click the PaperStore extension icon → paper is added to your library

---

## 7. Run Backend Tests

```bash
uv run pytest tests/
```

---

## 8. Validate the Full Flow

- [ ] Start Docker Compose (`docker compose up -d`)
- [ ] Run migrations (`uv run alembic upgrade head`)
- [ ] Start backend (`uv run uvicorn backend.main:app --reload`)
- [ ] Add an arXiv paper via the web app — confirm it appears in the library
- [ ] Add a plain PDF URL — confirm it appears with best-effort metadata
- [ ] Search for a known paper by author name — confirm it appears in results
- [ ] Open a paper — confirm metadata and PDF viewer both load
- [ ] Add a note to a paper — restart the backend — confirm the note persists
- [ ] Try submitting the same paper twice — confirm duplicate rejection message
- [ ] Install Chrome extension — navigate to an arXiv page — click the icon — confirm paper added

---

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DATABASE_URL` | `postgresql://paperstore:paperstore@localhost:5432/paperstore` | PostgreSQL connection string |
| `GOOGLE_CREDENTIALS_PATH` | `~/.config/paperstore/credentials.json` | Path to OAuth credentials file |
| `GOOGLE_TOKEN_PATH` | `~/.config/paperstore/token.json` | Path to cached OAuth token |
| `DRIVE_FOLDER_ID` | (none) | Optional: Google Drive folder ID to store papers in |
