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
uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`. Visit `http://127.0.0.1:8000/api/health` to check it directly.

## Run the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). The page requests `/api/health`; Vite proxies that request to FastAPI.

## Current scope

Only the frontend-to-backend connection is implemented. AI, file upload, TTS, user accounts, persistence, and scene processing are intentionally not included yet.
