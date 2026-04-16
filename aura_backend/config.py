import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _to_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    debug: bool

    serial_enabled: bool
    serial_port: str
    serial_baud_rate: int
    serial_timeout_sec: float
    serial_reconnect_sec: float
    scan_cooldown_sec: float
    serial_queue_max_size: int
    serial_poll_sleep_sec: float

    cards_needed: int

    gemini_api_key: str
    gemini_model: str
    gemini_temperature: float
    story_seed_file: str
    dummy_mode: bool
    dummy_cache_file: str

    tts_enabled: bool
    tts_cache_dir: str
    tts_lang: str
    tts_gain_db: float

    mic_enabled: bool
    mic_timeout_sec: float
    mic_phrase_time_limit_sec: float
    mic_ambient_adjust_sec: float

    tag_mapping_file: str
    legacy_mapping_enabled: bool
    legacy_mapping_python_file: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        return cls(
            host=os.getenv("AURA_HOST", "127.0.0.1"),
            port=int(os.getenv("AURA_PORT", "5000")),
            debug=_to_bool(os.getenv("AURA_DEBUG"), default=False),
            serial_enabled=_to_bool(os.getenv("AURA_SERIAL_ENABLED"), default=True),
            serial_port=os.getenv("AURA_SERIAL_PORT", "COM11"),
            serial_baud_rate=int(os.getenv("AURA_BAUD_RATE", "115200")),
            serial_timeout_sec=float(os.getenv("AURA_SERIAL_TIMEOUT_SEC", "1.0")),
            serial_reconnect_sec=float(os.getenv("AURA_SERIAL_RECONNECT_SEC", "2.0")),
            scan_cooldown_sec=float(os.getenv("AURA_SCAN_COOLDOWN_SEC", "1.5")),
            serial_queue_max_size=int(os.getenv("AURA_SERIAL_QUEUE_MAX_SIZE", "256")),
            serial_poll_sleep_sec=float(os.getenv("AURA_SERIAL_POLL_SLEEP_SEC", "0.01")),
            cards_needed=int(os.getenv("AURA_CARDS_NEEDED", "3")),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("AURA_GEMINI_MODEL", "gemini-1.5-flash"),
            gemini_temperature=float(os.getenv("AURA_GEMINI_TEMPERATURE", "0.7")),
            story_seed_file=os.getenv("AURA_STORY_SEED_FILE", "../prompt_v2/story_seeds.json"),
            dummy_mode=_to_bool(os.getenv("AURA_DUMMY_MODE"), default=False),
            dummy_cache_file=os.getenv("AURA_DUMMY_CACHE_FILE", "data/dummy_phase_cache.json"),
            tts_enabled=_to_bool(os.getenv("AURA_TTS_ENABLED"), default=True),
            tts_cache_dir=os.getenv("AURA_TTS_CACHE_DIR", "tts_cache"),
            tts_lang=os.getenv("AURA_TTS_LANG", "en"),
            tts_gain_db=float(os.getenv("AURA_TTS_GAIN_DB", "15.0")),
            mic_enabled=_to_bool(os.getenv("AURA_MIC_ENABLED"), default=True),
            mic_timeout_sec=float(os.getenv("AURA_MIC_TIMEOUT_SEC", "30.0")),
            mic_phrase_time_limit_sec=float(os.getenv("AURA_MIC_PHRASE_LIMIT_SEC", "8.0")),
            mic_ambient_adjust_sec=float(os.getenv("AURA_MIC_AMBIENT_ADJUST_SEC", "0.35")),
            tag_mapping_file=os.getenv("AURA_TAG_MAPPING_FILE", "data/tag_mappings.json"),
            legacy_mapping_enabled=_to_bool(os.getenv("AURA_LEGACY_MAPPING_ENABLED"), default=True),
            legacy_mapping_python_file=os.getenv("AURA_LEGACY_MAPPING_PY", "../Story_Reader.py"),
        )