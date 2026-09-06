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

Milestone 3.5 accepts UTF-8 `.txt` scripts, parses dialogue into a validated scene, and lets an actor choose their character and practise with an AI-generated reader voice. No microphone, recording, or persistence is used.

## Scene playback

Select your character and press **Start Scene**. The current line appears above the controls and is outlined in the dialogue list. Your lines remain silent; perform them and press **Continue**. The next two reader lines are generated ahead of time and played when reached; a line that is still loading waits for that same request. After playback, use **Continue** or **Replay Reader Line**. Space also continues while the player is running and focus is on the page body or within the player, outside interactive controls. It prevents page scrolling even during loading/playback; held-key repeats do not advance. Inputs, selects, buttons, links, and other page content retain their normal keyboard behavior. Progression is manual after every line, including consecutive reader lines.

If autoplay is blocked, press **Play Reader Line**. A transient generation failure gets one automatic recovery attempt when the line is needed. If that fails, **Retry Reader Line** remains available without skipping dialogue. **Restart Scene** stops audio and returns to the ready state; press Start Scene for another run. Changing character or analyzing another script also clears playback. Audio is held only for the current reader line and up to two upcoming reader lines. Advancing discards older audio; restart, completion, and unmount clear the buffer. Restarting generates reader audio again. Canceling a browser request cannot guarantee cancellation of work already received by OpenAI.

## Speech configuration and architecture

The backend reads `OPENAI_API_KEY`, `OPENAI_MODEL` (parsing, default `gpt-5-mini`), `OPENAI_TTS_MODEL` (default `gpt-4o-mini-tts`), `OPENAI_TTS_VOICE` (default `marin`), and `OPENAI_TTS_VOICES` (ordered palette, default `marin,cedar,coral,ash`). Existing `.env` files need no additional values unless overriding defaults. Never put the API key in a frontend/Vite variable.

React compares the current line's character with the selected actor. Only reader text and a deterministic character index are posted as `{"text":"Hello.","voice_index":1}` to `/api/speech`. The endpoint validates a nonempty string of up to 4096 characters, delegates to a small speech service, and returns WAV bytes with `audio/wav` and `Cache-Control: no-store`. Provider limits can also reject text; the UI reports a controlled failure. The synchronous route runs in FastAPI's thread pool. Individual speech calls have a 30-second timeout and SDK retries disabled. The frontend owns a single bounded recovery attempt, so retry layers cannot multiply requests.

The playback hook holds an explicit phase and line index. Phases are idle, actor, loading, playing, reader-ready, audio-blocked, speech-error, and complete. It uses synchronous guards against duplicate actions, an AbortController for pending requests, and a generation counter to ignore stale asynchronous results. Audio generation starts from user actions, avoiding duplicate requests from React StrictMode effect replay. Object URLs are revoked when no longer needed. The buffer stores both in-flight promises and prepared audio elements by line index, so foreground playback and prefetch share work. Failed prefetches do not retry in the background. When the line is needed, a transient failure gets one fresh on-demand request after a cancelable 500 ms backoff. Concurrent consumers share the recovery promise; a second failure reaches the controlled UI error. The same one-recovery limit applies to a cold on-demand request. Permanent errors (including invalid requests, authentication, configuration, and exhausted quota) do not automatically retry. The server communicates transient provider failures through `X-Speech-Retryable` and logs only error type, status/code, and request ID, never dialogue or credentials. No requests happen before Start; the first reader may still need to load. Prefetch may generate up to two lines that are never played if the user stops early.

## Reader voices and delivery

The index in the validated scene's `characters` array maps to a server-side voice palette using modulo. The default voice is first, followed by the configured palette with duplicates removed. Character identity stays stable across repeated lines, restart, and changes to the selected actor within the same parsed scene. Voices repeat after the palette is exhausted; actor slots are left in the ordering to keep identities stable. No gender inference or additional AI call is involved. To use only the default voice, set `OPENAI_TTS_VOICES` to that voice or an empty value. Invalid voice names produce a controlled configuration error.

`TTS_READER_INSTRUCTIONS` in backend configuration centralizes grounded, understated, conversational delivery with varied intonation and no unnecessary dramatic pauses. The default `gpt-4o-mini-tts` supports these instructions; alternate model overrides must support speech instructions and the configured voices. [Official speech documentation](https://developers.openai.com/api/docs/guides/text-to-speech) describes delivery instructions and recommends WAV/PCM for low latency.

## Post-line silence

The original frontend transitioned directly from the audio `ended` event to reader-ready, without a timer. It waited through the entire generated file, including trailing silence. Three manually generated samples using the original MP3 settings had approximately 0.22, 0.41, and 0.07 seconds of trailing samples below -60 dBFS. These confirm an audio-tail contribution but do not reproduce the entire reported 0.5–1.5-second delay. Browser/output-device latency and other generated lines remain manual verification items.

Speech now uses WAV, which can be inspected with Python's standard library without introducing a codec dependency. The backend trims only a contiguous near-silent tail of at least 300 ms, keeping 150 ms after the last sample above approximately -60 dBFS in any channel. It preserves internal pauses, quiet endings above that conservative threshold, short tails, and all-silent audio. Provider WAVs may use unknown-length headers. Output headers are rebuilt using the actual downloaded frame count, even when no silence is trimmed. Unrecognized formats pass through unchanged; optional post-processing errors return the original audio and log an error type. Completion still follows the actual audio end; there is no timer that guesses when dialogue has finished. WAV is larger than MP3, a tradeoff mitigated by the small prefetch window. Check soft endings and interrupted lines by ear; waveform thresholds cannot prove perceptual silence for every possible recording.

## Verification

```bash
cd backend
.venv/bin/python -m pytest -q
cd ../frontend
npm test
npm run build
```

Automated tests mock external AI boundaries; no real API requests are made. Frontend deterministic tests use Node’s built-in test runner without new dependencies. They cover the prefetch buffer, actor exclusion, voice indices, cleanup, retry, and keyboard ownership. Backend tests cover the speech contract, voice mapping, provider failures, and conservative audio trimming. Browser playback itself still needs manual verification.

Manual smoke test with a configured API key:

1. Upload a short script with alternating characters and consecutive actor/reader lines, then select your character.
2. Start, check the current-line indicator, listen to reader audio, and verify actor turns remain silent. Use Continue and Space to reach completion.
3. Replay a reader line and check the browser Network panel: replay should make no additional `/api/speech` request. Actor lines should never cause a speech request.
4. Try rapid clicks, restart during loading/playback, and change character during playback. Old audio should stop and stale responses should not play.
5. Check autoplay recovery in your browser and use offline mode to check speech failure/retry. Confirm Space does not interfere with inputs, selects, or buttons.

Milestone 3.5 manual checks:

- Use the three-character scene again: confirm distinct, consistent reader voices and grounded conversational delivery.
- While an actor is speaking, check that upcoming requests are already underway. Advance after they finish and confirm immediate playback with no second request for that line. Repeat for consecutive reader lines and multiple actor lines between readers.
- Replay should use the existing audio; rapid Continue/Space presses during loading should neither scroll nor create duplicate requests.
- Compare short words, soft final consonants, and interrupted lines for shorter end pauses without audible clipping.
- Restart or change character with prefetch pending; confirm no obsolete audio plays. Finish a scene and check replay, retry, and completion still behave as documented.

## Milestone 3.5 reliability regression

Live reproduction found a WAV header bug, not a confirmed concurrency/rate-limit issue. OpenAI returned finite audio with `0xffffffff` data-size placeholders, parsed as 2,147,483,647 frames. On lines with enough trailing silence, the old trimming writer copied that frame count and overflowed RIFF's 32-bit size field (`struct.error`). Lines without a long tail bypassed the writer, explaining the intermittent failures and apparent success on retry. The same exception occurred with sequential calls. Milestone 3 used MP3 without this processing step.

The writer now uses actual output frames and has a safe original-audio fallback for expected format/packing errors. A synthetic provider-header fixture and a complete mocked endpoint test reproduce the original failure without real API calls. The failed-prefetch behavior was also corrected: foreground playback can recover from transient cached/pending failures automatically, with one shared replacement request and no retry loop. The two-reader lookahead remains because concurrent requests were not the cause of the reproduced failure.

For manual retesting, reload the frontend and ensure the backend has reloaded. Run several passes of the same three-character scene, including short/long lines and consecutive readers. Check that prefetched audio still starts promptly, reader lines no longer fail intermittently, actor lines stay silent, and replay makes no request. Temporarily interrupt the network during prefetch, restore it before advancing, and verify automatic recovery. Restart during loading/recovery to verify stale audio cannot play. If a failure remains, preserve the backend traceback or the new provider error metadata.
