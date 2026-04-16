# Aura Mat Backend KT Document

## 1. Project Status (Current)

Status: In progress, backend MVP is functional and isolated from the legacy script.

Completed:

- Fresh Flask + Socket.IO backend architecture.
- Non-blocking serial listener thread with reconnection loop.
- Dedicated serial reader + dispatcher threads with queue buffering for burst-safe ingestion.
- Real-time dashboard updates for scan state and story pipeline.
- Gemini story generation service.
- Four-phase interactive story pipeline with timed laptop-mic listening between phases.
- Strict turn-based orchestration: 4 phases with exactly 3 child input turns (after phases 1, 2, and 3).
- Seed-driven prompt strategy loaded from prompt_v2/story_seeds.json.
- Dummy mode for full 4-phase pipeline testing without Gemini API calls.
- TTS service with audio cache.
- Manual reset and tag simulation API endpoints.
- Legacy mapping import from Story_Reader.py using AST parsing (no runtime import side effects).
- Gemini model fallback chain for unsupported model names (404 recovery).

Pending:

- Hardware-in-loop end-to-end validation with live ESP32 stream and Bluetooth audio playback confirmation.
- Optional hardening (structured logs, unit tests, CI checks).

## 2. Architecture Snapshot

Backend modules:

- app.py: API, socket events, orchestration and story pipeline trigger.
- config.py: Environment-driven runtime settings.
- state_store.py: Thread-safe shared state for round progress and transcript.
- services/serial_listener.py: Serial TAG_ID ingestion and debouncing.
- GET /api/serial-stats: Stream counters and queue depth visibility.
- services/story_service.py: Gemini call wrapper.
- services/story_service.py: Seed-driven phase prompts + Gemini fallback + dummy cache mode.
- services/tts_service.py: gTTS generation + playsound playback with cache.
- services/mic_listener.py: Timed microphone listener with auto-continue on timeout.
- mapping_loader.py: Unified mapping load from JSON + Story_Reader.py.

## 3. ESP32 Alignment Notes

The firmware in iot_mix_test.cpp emits lines in this format:

- TAG_ID:<HEX_UID>

Backend alignment implemented:

- Incoming TAG_ID normalization to uppercase, whitespace-free form.
- Mapping aliases include trimmed-leading-zero variants to handle UID formatting differences between historical captures and current firmware output.
- Debounce + unique round logic ensures a held card does not trigger repeated story generation.
- Reader thread is isolated from business logic latency via queue-based dispatch.

## 4. Legacy Mapping Source Integration

Requirement implemented: mapping list imported from previous Story_Reader.py.

How it works:

- mapping_loader.py parses card_mappings and word_categories from Story_Reader.py via AST.
- No direct import of Story_Reader.py, so Gemini/TTS/Vosk side effects are avoided.
- Categories are inferred from word_categories when available.
- JSON mapping file remains as fallback and can still provide defaults.

Related env keys:

- AURA_TAG_MAPPING_FILE=data/tag_mappings.json
- AURA_LEGACY_MAPPING_ENABLED=true
- AURA_LEGACY_MAPPING_PY=../Story_Reader.py

## 5. Local Run Instructions

1. Open terminal in this folder.
2. Create/activate Python environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy .env.example to .env and set GEMINI_API_KEY.
	- For louder voice output, set AURA_TTS_GAIN_DB (for example 4.0 to 9.0).
	- For microphone phase timeout, set AURA_MIC_TIMEOUT_SEC (default 30 seconds).
	- For team seed strategy, keep AURA_STORY_SEED_FILE=../prompt_v2/story_seeds.json.
	- For dummy mode, set AURA_DUMMY_MODE=true (Gemini is skipped).
5. Run backend:

```bash
python app.py
```

6. Open dashboard:

http://127.0.0.1:5000

## 6. Basic Dry Run Procedure

Without hardware:

- Set AURA_SERIAL_ENABLED=false.
- Use dashboard Simulate Scan or POST /api/simulate-tag.
- Confirm state transitions: idle -> collecting -> generating -> narrating -> complete -> idle.

With hardware:

- Keep AURA_SERIAL_ENABLED=true and AURA_SERIAL_PORT=COM11 (or your active port).
- Tap mapped cards and verify tag_scanned events and story trigger after configured card count.
- Query /api/serial-stats to confirm lines_read, tags_enqueued, tags_dispatched, and queue_depth.
- During story generation, backend now waits for laptop mic response up to AURA_MIC_TIMEOUT_SEC after each phase, then continues automatically.
- During listening turns, the backend records from laptop mic for the configured window, then transcribes and continues to next phase.

Reproducible dry run script:

```bash
python tools/dry_run_mapping.py
```

Last dry run evidence:

```text
Loaded 12 tag mappings from JSON: ...\aura_backend\data\tag_mappings.json
Imported 12 legacy mappings from ...\Story_Reader.py
--- DRY RUN: ESP32 TAG LINE TO MAPPING ---
TAG_ID:0B3B0F16 -> Princess (character)
TAG_ID:B3B0F16 -> Princess (character)
TAG_ID:0061DD07 -> Castle (place)
TAG_ID:85D950FC -> Dragon (character)
TAG_ID:FFFFFFFF -> UNMAPPED
```

## 7. Handover Notes

- Legacy script remains untouched.
- New backend lives fully under this folder and can be versioned independently.
- Next recommended milestone: add a small automated test set for mapping parsing and tag normalization.

## 8. Troubleshooting

Serial access denied (PermissionError 13):

- Cause: COM port is open in another app (for example PlatformIO serial monitor).
- Fix: close the monitor, then rerun backend. Auto-reconnect will attach when the port is released.

Burst misses (high scan rate):

- Likely cause: blocking line-based reads can lose burst lines while processing callbacks.
- Likely cause: fragmented half-lines arriving across multiple serial chunks.
- Likely cause: monitor contention where another serial consumer steals bytes.
- Current backend fix: non-blocking accumulator reader with `in_waiting` + `read(...)`, dedicated queue, and separate dispatcher thread.
- Recommended tuning: `AURA_SERIAL_TIMEOUT_SEC=0.05`, `AURA_SERIAL_POLL_SLEEP_SEC=0.01`, and increase `AURA_SERIAL_QUEUE_MAX_SIZE` if `queue_drop_replace` appears in live feed.
- Verification: use dashboard Live Serial Feed and `/api/serial-stats` to compare `tags_detected` vs `tags_dispatched`.

Gemini model 404 NOT_FOUND:

- Cause: model name is not available for generateContent in the current API version/account.
- Fix: set AURA_GEMINI_MODEL to a supported model, such as gemini-2.5-flash.
- Backend behavior: story service now automatically tries fallback models in sequence.

TTS not louder even after setting AURA_TTS_GAIN_DB:

- The gain boost path uses pydub and requires ffmpeg to be available in PATH on Windows.
- If ffmpeg is missing, backend falls back to original audio and logs a warning.

Microphone capture not working:

- Ensure laptop microphone permission is enabled for Python/Terminal apps in Windows privacy settings.
- Install required dependencies from requirements.txt, including SpeechRecognition and microphone backend dependencies.
- If no speech is captured, backend waits until timeout and auto-continues to the next story phase.

Dummy mode behavior:

- Uses AURA_DUMMY_CACHE_FILE to load prewritten phase outputs.
- Runs the same 4-phase pipeline flow, TTS, and mic wait states without calling Gemini.
