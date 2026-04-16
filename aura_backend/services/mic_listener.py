from __future__ import annotations

import importlib
import logging
import time


def _load_speech_recognition_module():
    try:
        return importlib.import_module("speech_recognition")
    except Exception:
        return None


class TimedMicrophoneListener:
    def __init__(
        self,
        enabled: bool,
        listen_timeout_sec: float,
        phrase_time_limit_sec: float,
        ambient_adjust_sec: float,
        logger: logging.Logger | None = None,
    ) -> None:
        self._enabled = enabled
        self._listen_timeout_sec = max(1.0, listen_timeout_sec)
        self._phrase_time_limit_sec = max(1.0, phrase_time_limit_sec)
        self._ambient_adjust_sec = max(0.0, ambient_adjust_sec)
        self._logger = logger or logging.getLogger(__name__)

    def _sleep_timeout(self, timeout_sec: float) -> str:
        time.sleep(max(0.0, timeout_sec))
        return ""

    def listen_for_response(self, timeout_override_sec: float | None = None) -> str:
        total_timeout = self._listen_timeout_sec if timeout_override_sec is None else max(1.0, timeout_override_sec)

        if not self._enabled:
            self._logger.info("Microphone disabled. Returning empty after %.1fs.", total_timeout)
            return self._sleep_timeout(total_timeout)

        sr = _load_speech_recognition_module()
        if sr is None:
            self._logger.error("❌ speech_recognition module not available. Install with: pip install SpeechRecognition PyAudio")
            return self._sleep_timeout(total_timeout)

        recognizer = sr.Recognizer()
        self._logger.info("🎤 Starting microphone capture (timeout: %.1fs)...", total_timeout)

        try:
            # Try to open microphone
            self._logger.info("Attempting to open microphone...")
            with sr.Microphone() as source:
                self._logger.info("✅ Microphone opened successfully")
                
                if self._ambient_adjust_sec > 0:
                    self._logger.info("Adjusting for ambient noise (%.1fs)...", self._ambient_adjust_sec)
                    recognizer.adjust_for_ambient_noise(source, duration=self._ambient_adjust_sec)
                    self._logger.info("✅ Ambient noise adjustment complete")

                # Capture the full turn window, then transcribe what was spoken.
                self._logger.info("🔴 Recording audio for %.1fs...", total_timeout)
                audio = recognizer.record(source, duration=total_timeout)
                self._logger.info("✅ Audio recording complete. Sending to Google Speech-to-Text...")

            try:
                text = recognizer.recognize_google(audio).strip()
                if text:
                    self._logger.info("✅ Transcription success: '%s'", text[:100])
                    return text
                else:
                    self._logger.warning("⚠️ Audio captured but no speech detected (silence)")
                    return ""
            except sr.UnknownValueError:
                self._logger.warning("⚠️ Could not understand audio. Try speaking louder or clearer.")
                return ""
            except sr.RequestError as err:
                self._logger.error("❌ Google Speech-to-Text API error: %s", err)
                self._logger.error("   Make sure internet is working and Google API is accessible")
                return ""
        except OSError as err:
            self._logger.error("❌ Microphone/PyAudio error: %s", err)
            self._logger.error("   Try: 1) Restart the app, 2) Check microphone is plugged in, 3) Run: pip install --upgrade pyaudio")
            return self._sleep_timeout(total_timeout)
        except Exception as err:
            self._logger.error("❌ Unexpected error during mic capture: %s", err)
            return self._sleep_timeout(total_timeout)
