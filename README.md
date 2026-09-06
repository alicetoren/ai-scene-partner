# AI Scene Partner

An in-progress web application for actors to practise scenes, with React, FastAPI, structured AI script parsing, and reader speech playback.

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

Open the URL Vite prints (usually `http://localhost:5173`). Vite proxies `/api` requests to FastAPI.

## Current scope

Milestone 3 accepts UTF-8 `.txt` scripts, parses dialogue into a validated scene, and lets an actor choose their character and practise with an AI-generated reader voice. No microphone, recording, or persistence is used.

## Scene playback

Select your character and press **Start Scene**. The current line appears above the controls and is outlined in the dialogue list. Your lines remain silent; perform them and press **Continue**. Reader lines are synthesized and played automatically when reached. After playback, use **Continue** or **Replay Reader Line**. Space also continues when focus is outside interactive controls. Progression is manual after every line, including consecutive reader lines.

If autoplay is blocked, press **Play Reader Line**. Failed generation offers **Retry Reader Line** without skipping dialogue. **Restart Scene** stops audio and returns to the ready state; press Start Scene for another run. Changing character or analyzing another script also clears playback. Audio is held only for the current reader line and released on advancement, restart, or unmount. Restarting generates reader audio again. Canceling a browser request cannot guarantee cancellation of work already received by OpenAI.

## Speech configuration and architecture

The backend reads `OPENAI_API_KEY`, `OPENAI_MODEL` (parsing, default `gpt-5-mini`), `OPENAI_TTS_MODEL` (default `gpt-4o-mini-tts`), and `OPENAI_TTS_VOICE` (default `marin`). Existing `.env` files need no additional values unless overriding defaults. Never put the API key in a frontend/Vite variable.

React compares the current line's character with the selected actor. Only reader text is posted as `{"text":"Hello."}` to `/api/speech`. The endpoint validates a nonempty string of up to 4096 characters, delegates to a small speech service, and returns MP3 bytes with `audio/mpeg` and `Cache-Control: no-store`. Provider limits can also reject text; the UI reports a controlled failure. The synchronous route runs in FastAPI's thread pool. Speech calls have a 30-second timeout and no automatic retries.

The playback hook holds an explicit phase and line index. Phases are idle, actor, loading, playing, reader-ready, audio-blocked, speech-error, and complete. It uses synchronous guards against duplicate actions, an AbortController for pending requests, and a generation counter to ignore stale asynchronous results. Audio generation starts from user actions, avoiding duplicate requests from React StrictMode effect replay. Object URLs are revoked when no longer needed.

## Verification

```bash
cd backend
.venv/bin/python -m pytest -q
cd ../frontend
npm run build
```

Backend tests mock external AI boundaries; no real API requests are made. There is no frontend test framework in this milestone.

Manual smoke test with a configured API key:

1. Upload a short script with alternating characters and consecutive actor/reader lines, then select your character.
2. Start, check the current-line indicator, listen to reader audio, and verify actor turns remain silent. Use Continue and Space to reach completion.
3. Replay a reader line and check the browser Network panel: replay should make no additional `/api/speech` request. Actor lines should never cause a speech request.
4. Try rapid clicks, restart during loading/playback, and change character during playback. Old audio should stop and stale responses should not play.
5. Check autoplay recovery in your browser and use offline mode to check speech failure/retry. Confirm Space does not interfere with inputs, selects, or buttons.
