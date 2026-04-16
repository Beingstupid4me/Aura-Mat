from __future__ import annotations

import hashlib
import importlib
import logging
import threading
from pathlib import Path

from gtts import gTTS
from playsound import playsound


def _load_audio_segment():
    try:
        module = importlib.import_module("pydub")
        audio_segment = getattr(module, "AudioSegment", None)
        effects = importlib.import_module("pydub.effects")
        normalize = getattr(effects, "normalize", None)
        return audio_segment, normalize
    except Exception:
        return None, None


class GTTSSpeaker:
    def __init__(
        self,
        enabled: bool,
        cache_dir: str,
        lang: str,
        gain_db: float = 9.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._enabled = enabled
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lang = lang
        self._gain_db = gain_db
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()

    def set_gain_db(self, gain_db: float) -> None:
        with self._lock:
            self._gain_db = gain_db

    def get_gain_db(self) -> float:
        with self._lock:
            return self._gain_db

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split()).strip()

    def synthesize(self, text: str) -> Path | None:
        if not self._enabled:
            return None

        clean_text = self._normalize_text(text)
        if not clean_text:
            return None

        gain_db = self.get_gain_db()

        digest = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:20]
        audio_path = self._cache_dir / f"{digest}.mp3"
        play_path = audio_path

        if not audio_path.exists():
            tts = gTTS(text=clean_text, lang=self._lang, slow=False)
            tts.save(str(audio_path))

        if gain_db != 0:
            boosted_path = self._cache_dir / f"{digest}_norm_plus_{int(gain_db * 10)}.mp3"
            play_path = self._build_boosted_audio(audio_path=audio_path, boosted_path=boosted_path, gain_db=gain_db)

        return play_path

    def play(self, audio_path: Path | None) -> None:
        if not self._enabled or audio_path is None:
            return
        playsound(str(audio_path))

    def speak(self, text: str) -> None:
        audio_path = self.synthesize(text)
        self.play(audio_path)

    def _build_boosted_audio(self, audio_path: Path, boosted_path: Path, gain_db: float) -> Path:
        if boosted_path.exists():
            return boosted_path

        audio_segment, normalize = _load_audio_segment()
        if audio_segment is None or normalize is None:
            self._logger.warning("pydub is unavailable. Playing TTS without gain boost.")
            return audio_path

        try:
            original = audio_segment.from_file(str(audio_path), format="mp3")
            normalized_audio = normalize(original)
            final_audio = normalized_audio + gain_db
            final_audio.export(str(boosted_path), format="mp3")
            return boosted_path
        except Exception as err:
            self._logger.warning("Failed to apply TTS gain boost (%s). Playing original audio.", err)
            return audio_path
