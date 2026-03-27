import logging
import os
import json
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_env(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _get_bool_env(*names, default=False):
    value = _get_env(*names)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(*names, default):
    value = _get_env(*names)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning(f"Invalid integer for env var {names[0]}: {value}. Using default {default}.")
        return default


def _get_list_env(*names, default=None):
    value = _get_env(*names)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(os.pathsep) if item.strip()]


def _get_json_dict_env(*names, default=None):
    value = _get_env(*names)
    if value is None:
        return default or {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logging.warning("Invalid JSON for env var %s. Using default value.", names[0])
        return default or {}

    if not isinstance(parsed, dict):
        logging.warning("Env var %s must be a JSON object. Using default value.", names[0])
        return default or {}

    normalized = {}
    for key, app_target in parsed.items():
        if isinstance(key, str) and isinstance(app_target, str) and key.strip() and app_target.strip():
            normalized[key.strip()] = app_target.strip()

    return normalized


def _default_app_aliases():
    return {
        "blocco note": "notepad.exe",
        "notepad": "notepad.exe",
        "discord": "discord.exe",
        "steam": "steam.exe",
        "valorant": "RiotClientServices.exe --launch-product=valorant --launch-patchline=live",
        "riot client": "RiotClientServices.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "vscode": "code",
        "visual studio code": "code",
    }


def _build_system_message(creator_name):
    return (
        "You are a multimodal AI voice assistant. Your name is Atlas. You speak italian. "
        f"You were created by {creator_name}. If the user asks who created you, answer with that name clearly. "
        "Your user may or may not have attached a photo for context "
        "(either a screenshot or a webcam capture). Any photo has already been processed into a highly detailed "
        "text prompt that will be attached to their transcribed voice prompt. Generate the most useful and "
        "factual response possible, carefully considering all previous generated text in your response before "
        "adding new tokens to the response. Do not expect or request images, just use the context if added. "
        "Use all of the context of this conversation so your response is relevant to the conversation. Make "
        "your responses clear and concise, avoiding any verbosity."
    )


@dataclass
class AppConfig:
    groq_api_key: str | None = _get_env("GROQ_API_KEY", "groqApiKey")
    google_api_key: str | None = _get_env("GOOGLE_API_KEY", "googleApiKey")
    openai_api_key: str | None = _get_env("OPENAI_API_KEY", "openaiApiKey")
    weather_api_key: str | None = _get_env("OPENWEATHER_API_KEY", "openWeatherApiKey")
    porcupine_api_key: str | None = _get_env("PORCUPINE_API_KEY", "porcupineApiKey")
    narakeet_api_key: str | None = _get_env("NARAKEET_API_KEY", "narakeetApiKey")
    wake_word_model: str = _get_env("WAKE_WORD_MODEL", default="atlas/models/atlas.ppn")
    porcupine_model_path: str = _get_env("PORCUPINE_MODEL_PATH", default="atlas/models/porcupine_params_it.pv")
    screenshot_path: str = _get_env("SCREENSHOT_PATH", default="temp/screenshot.png")
    prompt_path: str = _get_env("PROMPT_PATH", default="temp/prompt.wav")
    log_path: str = _get_env("LOG_PATH", default="logs/atlas.log")
    atlas_creator_name: str = _get_env("ATLAS_CREATOR_NAME", "atlasCreatorName", default="Daniele")
    groq_model: str = _get_env("GROQ_MODEL", default="llama-3.1-8b-instant")
    groq_model2: str = _get_env("GROQ_MODEL2", default="llama-3.3-70b-versatile")
    whisper_size: str = _get_env("WHISPER_SIZE", default="medium")
    enable_tts: bool = _get_bool_env("ENABLE_TTS", default=False)
    debug_mode: bool = _get_bool_env("DEBUG_MODE", default=True)
    allowed_dirs: list[str] = field(
        default_factory=lambda: _get_list_env("ALLOWED_DIRS", default=[os.path.expanduser("~/Documents/AtlasDir")])
    )
    app_aliases: dict[str, str] = field(
        default_factory=lambda: _get_json_dict_env("APP_ALIASES_JSON", default=_default_app_aliases())
    )
    week_days: list[str] = field(
        default_factory=lambda: ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
    )
    system_message: str = _build_system_message(_get_env("ATLAS_CREATOR_NAME", "atlasCreatorName", default="Daniele"))
    generation_config: dict = field(
        default_factory=lambda: {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    )
    max_recent_conversation_messages: int = _get_int_env("MAX_RECENT_CONVERSATION_MESSAGES", default=8)
    conversation_summary_trigger: int = _get_int_env("CONVERSATION_SUMMARY_TRIGGER", default=12)
    safety_settings: list[dict] = field(
        default_factory=lambda: [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )


@dataclass
class SessionState:
    conversation: list[dict] = field(default_factory=list)
    conversation_summary: str | None = None
    last_file_search_results: list[str] = field(default_factory=list)
    current_file_path: str | None = None
    meal_preferences: dict | None = None
    last_day_planned: str | None = None
    meal_plan: dict | None = None


app = AppConfig()
session = SessionState()

_groq_client = None
_gemini_model = None
_whisper_model = None
_recognizer = None
_microphone = None


def ensure_directories():
    for path in [
        app.wake_word_model,
        app.porcupine_model_path,
        app.screenshot_path,
        app.prompt_path,
        app.log_path,
    ]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def reset_conversation():
    session.conversation = [{"role": "system", "content": app.system_message}]
    session.conversation_summary = None


def validate_config():
    issues = {"errors": [], "warnings": [], "feature_flags": {}}

    if not app.groq_api_key:
        issues["errors"].append("Missing GROQ_API_KEY. The main assistant chat flow will not work.")

    issues["feature_flags"]["weather_enabled"] = bool(app.weather_api_key)
    if not app.weather_api_key:
        issues["warnings"].append("OPENWEATHER_API_KEY not set. Weather requests will fail.")

    issues["feature_flags"]["vision_enabled"] = bool(app.google_api_key)
    if not app.google_api_key:
        issues["warnings"].append("GOOGLE_API_KEY not set. Screenshot vision analysis will fail.")

    issues["feature_flags"]["tts_enabled"] = bool(app.enable_tts and app.narakeet_api_key)
    if app.enable_tts and not app.narakeet_api_key:
        issues["warnings"].append("ENABLE_TTS is true but NARAKEET_API_KEY is missing. TTS will stay disabled.")

    issues["feature_flags"]["wakeword_enabled"] = bool(app.porcupine_api_key)
    if not app.debug_mode and not app.porcupine_api_key:
        issues["warnings"].append("PORCUPINE_API_KEY not set. Wake word mode may fail outside debug mode.")

    issues["feature_flags"]["app_launcher_enabled"] = bool(app.app_aliases)
    if not app.app_aliases:
        issues["warnings"].append("APP_ALIASES_JSON is empty. App launching requests will fail.")

    for asset_path, label in [
        (app.wake_word_model, "Wake word model"),
        (app.porcupine_model_path, "Porcupine model"),
    ]:
        if not Path(asset_path).exists():
            issues["warnings"].append(f"{label} not found at {asset_path}. Related wake word features may fail.")

    if app.conversation_summary_trigger <= app.max_recent_conversation_messages:
        issues["warnings"].append(
            "CONVERSATION_SUMMARY_TRIGGER should be greater than MAX_RECENT_CONVERSATION_MESSAGES for useful trimming."
        )

    for warning in issues["warnings"]:
        logging.warning(warning)
    for error in issues["errors"]:
        logging.error(error)

    return issues


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=app.groq_api_key)
    return _groq_client


def get_gemini_model():
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai

        genai.configure(api_key=app.google_api_key)
        _gemini_model = genai.GenerativeModel(
            "gemini-2.0-flash",
            safety_settings=app.safety_settings,
            generation_config=app.generation_config,
        )
    return _gemini_model


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        cores_count = max(1, os.cpu_count() or 1)
        worker_count = max(1, cores_count // 2)
        _whisper_model = WhisperModel(
            app.whisper_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=worker_count,
            num_workers=worker_count,
        )
    return _whisper_model


def get_recognizer():
    global _recognizer
    if _recognizer is None:
        import speech_recognition as sr

        _recognizer = sr.Recognizer()
    return _recognizer


def get_microphone():
    global _microphone
    if _microphone is None:
        import speech_recognition as sr

        try:
            _microphone = sr.Microphone()
        except OSError:
            logging.info("No microphone available.")
            _microphone = None
    return _microphone


ensure_directories()
reset_conversation()
