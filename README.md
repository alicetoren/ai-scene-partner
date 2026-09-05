# AI Scene Partner

An in-progress web application for actors to practise scenes. This initial milestone establishes a React frontend communicating with a FastAPI backend.

## Prerequisites

- Node.js 22 or later
- Python 3.13 or later

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit ../.env and replace the placeholder with your API key.
uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`. The OpenAI key is read only from the backend environment; copy the variable name from [`.env.example`](.env.example) if you prefer to use a local ignored `.env` file. Visit `http://127.0.0.1:8000/api/health` to check the backend directly.

## Run the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The page requests `/api/health`; Vite proxies that request to FastAPI.

## Current scope

The current milestone accepts UTF-8 `.txt` scripts, parses dialogue into a structured scene, and lets an actor choose their character. TTS, audio playback, user accounts, persistence, and other features are intentionally not included.
