from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO

from config import Settings
from mapping_loader import load_tag_mappings, normalize_tag_id, tag_lookup_keys
from services.mic_listener import TimedMicrophoneListener
from services.serial_listener import SerialListener
from services.story_service import GeminiStoryService
from services.tts_service import GTTSSpeaker
from state_store import AuraStateStore


class AuraBackend:
    def __init__(
        self,
        settings: Settings,
        socketio: SocketIO,
        state: AuraStateStore,
        app_logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.socketio = socketio
        self.state = state
        self.logger = app_logger

        self._tag_mapping = load_tag_mappings(
            base_dir=Path(__file__).parent,
            json_mapping_path=settings.tag_mapping_file,
            legacy_enabled=settings.legacy_mapping_enabled,
            legacy_mapping_path=settings.legacy_mapping_python_file,
            logger=app_logger,
        )
        self._story_service = GeminiStoryService(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=settings.gemini_temperature,
            seed_file=str(Path(__file__).parent / settings.story_seed_file),
            dummy_mode=settings.dummy_mode,
            dummy_cache_file=str(Path(__file__).parent / settings.dummy_cache_file),
            logger=app_logger,
        )
        self._speaker = GTTSSpeaker(
            enabled=settings.tts_enabled,
            cache_dir=str(Path(__file__).parent / settings.tts_cache_dir),
            lang=settings.tts_lang,
            gain_db=settings.tts_gain_db,
            logger=app_logger,
        )
        self._mic_listener = TimedMicrophoneListener(
            enabled=settings.mic_enabled,
            listen_timeout_sec=settings.mic_timeout_sec,
            phrase_time_limit_sec=settings.mic_phrase_time_limit_sec,
            ambient_adjust_sec=settings.mic_ambient_adjust_sec,
            logger=app_logger,
        )

        self._story_lock = threading.Lock()
        self._is_running = False
        self.serial_listener = None

        if settings.serial_enabled:
            self.serial_listener = SerialListener(
                port=settings.serial_port,
                baud_rate=settings.serial_baud_rate,
                timeout_sec=settings.serial_timeout_sec,
                reconnect_sec=settings.serial_reconnect_sec,
                cooldown_sec=settings.scan_cooldown_sec,
                queue_max_size=settings.serial_queue_max_size,
                poll_sleep_sec=settings.serial_poll_sleep_sec,
                on_tag=self.handle_tag,
                on_stream_event=self.handle_serial_stream_event,
                logger=app_logger,
            )

    @property
    def is_running(self) -> bool:
        with self._story_lock:
            return self._is_running

    def start(self) -> None:
        if self.serial_listener:
            self.serial_listener.start()
            self.logger.info("Serial listener started.")
        else:
            self.logger.info("Serial listener disabled (AURA_SERIAL_ENABLED=false).")

    def stop(self) -> None:
        if self.serial_listener:
            self.serial_listener.stop()

    def reset_round(self) -> None:
        if self.is_running:
            raise RuntimeError("Story pipeline is running. Wait for it to complete before reset.")

        self.state.reset_round(keep_story=False)
        self._emit_state()
        self._emit_pipeline_step("pipeline_reset", "Round reset. Tap cards to start again.")

    def _emit_state(self) -> None:
        self.socketio.emit("state_snapshot", self.state.snapshot())

    def _emit_pipeline_step(
        self,
        step: str,
        message: str,
        phase: int | None = None,
        turn: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "step": step,
            "message": message,
            "ts": time.time(),
        }
        if phase is not None:
            payload["phase"] = phase
        if turn is not None:
            payload["turn"] = turn
        if data:
            payload.update(data)
        self.socketio.emit("pipeline_step", payload)

    def handle_serial_stream_event(self, payload: dict) -> None:
        self.socketio.emit("serial_stream", payload)

    def get_tts_settings(self) -> dict:
        return {
            "enabled": self.settings.tts_enabled,
            "gain_db": self._speaker.get_gain_db(),
            "lang": self.settings.tts_lang,
        }

    def set_tts_gain_db(self, gain_db: float) -> dict:
        clamped = max(-10.0, min(24.0, gain_db))
        self._speaker.set_gain_db(clamped)
        return self.get_tts_settings()

    def handle_tag(self, tag_id: str) -> None:
        normalized_tag = normalize_tag_id(tag_id)

        lookup_tag = ""
        for key in tag_lookup_keys(normalized_tag):
            if key in self._tag_mapping:
                lookup_tag = key
                break

        mapping = self._tag_mapping.get(lookup_tag)
        if not mapping:
            self.socketio.emit("unknown_tag", {"tag_id": normalized_tag, "message": "Unknown tag."})
            return

        accepted = self.state.add_card(
            tag_id=lookup_tag,
            label=mapping["name"],
            category=mapping.get("category", "unknown"),
        )
        if not accepted:
            self.socketio.emit(
                "tag_ignored",
                {"tag_id": normalized_tag, "message": "Duplicate or extra scan ignored."},
            )
            return

        self.socketio.emit(
            "tag_scanned",
            {
                "tag_id": normalized_tag,
                "label": mapping["name"],
                "category": mapping["category"],
                "state": self.state.snapshot(),
            },
        )
        self._emit_state()

        if self.state.is_round_complete():
            self._start_story_pipeline()

    def _start_story_pipeline(self) -> None:
        with self._story_lock:
            if self._is_running:
                return
            self._is_running = True

        worker = threading.Thread(target=self._run_story_pipeline, daemon=True, name="story-pipeline")
        worker.start()

    def _run_story_pipeline(self) -> None:
        total_phases = 4
        child_inputs: list[str] = []
        story_parts: list[str] = []

        try:
            self._emit_pipeline_step(
                "pipeline_started",
                "Story pipeline started.",
                data={"total_phases": total_phases},
            )

            labels = self.state.labels_for_story()
            grouped_words = self.state.grouped_words_for_story()
            chat = self._story_service.create_interactive_chat()

            self.state.set_story("", reset_transcript=True)

            for phase in range(1, total_phases + 1):
                prior_child_input = child_inputs[phase - 2] if phase > 1 else ""

                self.state.set_status(f"generating_phase_{phase}")
                self._emit_state()
                self._emit_pipeline_step(
                    "phase_generate_start",
                    f"Generating phase {phase} story text.",
                    phase=phase,
                )

                phase_text = self._story_service.generate_interactive_phase(
                    chat=chat,
                    labels=labels,
                    grouped_words=grouped_words,
                    phase=phase,
                    child_input=prior_child_input,
                )

                story_parts.append(phase_text)
                cumulative_story = "\n\n".join(story_parts)
                self.state.set_story(cumulative_story, reset_transcript=(phase == 1))
                self.socketio.emit("dialogue_entry", {"speaker": "aura", "text": phase_text, "phase": phase})

                self._emit_pipeline_step(
                    "phase_generate_done",
                    f"Phase {phase} story text ready.",
                    phase=phase,
                )

                self.state.set_status(f"synthesizing_phase_{phase}")
                self._emit_state()
                self._emit_pipeline_step(
                    "tts_build_start",
                    f"Building audio for phase {phase}.",
                    phase=phase,
                )

                audio_path = self._speaker.synthesize(phase_text)

                self._emit_pipeline_step(
                    "tts_build_done",
                    f"Audio is ready for phase {phase}.",
                    phase=phase,
                    data={"audio_file": str(audio_path) if audio_path else ""},
                )

                self.state.set_status(f"narrating_phase_{phase}")
                self._emit_state()
                self._emit_pipeline_step(
                    "tts_play_start",
                    f"Playing phase {phase} audio.",
                    phase=phase,
                )

                self._speaker.play(audio_path)
                self.socketio.emit("tts_complete", {"phase": phase})

                self._emit_pipeline_step(
                    "tts_play_done",
                    f"Audio playback completed for phase {phase}.",
                    phase=phase,
                )

                if phase >= total_phases:
                    continue

                turn_number = phase
                timeout_sec = float(self.settings.mic_timeout_sec)

                self.state.set_status(f"listening_turn_{turn_number}")
                self._emit_state()
                self._emit_pipeline_step(
                    "mic_listen_start",
                    f"Turn {turn_number}: listening for {int(timeout_sec)} seconds.",
                    phase=phase,
                    turn=turn_number,
                    data={"timeout_sec": timeout_sec},
                )

                heard_text = self._mic_listener.listen_for_response(timeout_override_sec=timeout_sec).strip()
                captured = bool(heard_text)
                child_text = heard_text if captured else "[Child was quiet]"
                child_inputs.append(child_text)

                self.socketio.emit(
                    "dialogue_entry",
                    {
                        "speaker": "child",
                        "text": child_text,
                        "turn": turn_number,
                        "captured": captured,
                        "source": "backend-mic" if captured else "timeout",
                    },
                )
                self.socketio.emit(
                    "mic_result",
                    {
                        "turn": turn_number,
                        "phase": phase,
                        "captured": captured,
                        "text": child_text,
                        "source": "backend-mic" if captured else "timeout",
                    },
                )

                self._emit_pipeline_step(
                    "mic_listen_done",
                    f"Turn {turn_number}: transcription completed.",
                    phase=phase,
                    turn=turn_number,
                    data={"captured": captured, "text": child_text},
                )

            self.state.set_status("complete")
            self._emit_state()
            self._emit_pipeline_step("pipeline_complete", "Story pipeline complete. Tap reset for a new round.")

        except Exception as err:
            self.logger.exception("Story pipeline failed")
            self.state.set_status("error", str(err))
            self.socketio.emit("backend_error", {"message": str(err)})
            self._emit_state()
        finally:
            with self._story_lock:
                self._is_running = False


def create_app() -> tuple[Flask, SocketIO, AuraBackend, Settings]:
    settings = Settings.from_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    app_logger = logging.getLogger("aura-backend")

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["SECRET_KEY"] = "aura-dev-key"
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    state = AuraStateStore(cards_needed=settings.cards_needed)
    backend = AuraBackend(settings=settings, socketio=socketio, state=state, app_logger=app_logger)

    @app.route("/")
    def index():
        return send_from_directory("static", "index_voice_call.html")

    @app.route("/api/state", methods=["GET"])
    def get_state():
        return jsonify(state.snapshot())

    @app.route("/api/pipeline-status", methods=["GET"])
    def get_pipeline_status():
        return jsonify({"is_running": backend.is_running, "state": state.snapshot()})

    @app.route("/api/reset", methods=["POST"])
    def reset_round():
        try:
            backend.reset_round()
        except RuntimeError as err:
            return jsonify({"ok": False, "error": str(err)}), 409

        return jsonify({"ok": True, "state": state.snapshot()})

    @app.route("/api/serial-stats", methods=["GET"])
    def serial_stats():
        if not backend.serial_listener:
            return jsonify({"serial_enabled": False, "stats": {}})
        return jsonify({"serial_enabled": True, "stats": backend.serial_listener.stats()})

    @app.route("/api/tts-settings", methods=["GET"])
    def get_tts_settings():
        return jsonify({"ok": True, "tts": backend.get_tts_settings()})

    @app.route("/api/tts-settings", methods=["POST"])
    def set_tts_settings():
        payload = request.get_json(silent=True) or {}
        if "gain_db" not in payload:
            return jsonify({"ok": False, "error": "gain_db is required"}), 400

        try:
            gain_db = float(payload.get("gain_db"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "gain_db must be numeric"}), 400

        tts = backend.set_tts_gain_db(gain_db)
        socketio.emit("tts_settings", tts)
        return jsonify({"ok": True, "tts": tts})

    @app.route("/api/simulate-tag", methods=["POST"])
    def simulate_tag():
        payload = request.get_json(silent=True) or {}
        tag_id = normalize_tag_id(str(payload.get("tag_id", "")))
        if not tag_id:
            return jsonify({"ok": False, "error": "tag_id is required"}), 400

        backend.handle_tag(tag_id)
        return jsonify({"ok": True, "tag_id": tag_id, "state": state.snapshot()})

    @socketio.on("connect")
    def on_connect():
        socketio.emit("state_snapshot", state.snapshot())
        socketio.emit("tts_settings", backend.get_tts_settings())

    return app, socketio, backend, settings


def main() -> None:
    app, socketio, backend, settings = create_app()
    backend.start()

    try:
        socketio.run(app, host=settings.host, port=settings.port, debug=settings.debug)
    finally:
        backend.stop()


if __name__ == "__main__":
    main()
