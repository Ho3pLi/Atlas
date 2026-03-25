import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    groq_api_key: str | None = os.getenv("groqApiKey")
    google_api_key: str | None = os.getenv("googleApiKey")
    openai_api_key: str | None = os.getenv("openaiApiKey")
    weather_api_key: str | None = os.getenv("openWeatherApiKey")
    porcupine_api_key: str | None = os.getenv("porcupineApiKey")
    narakeet_api_key: str | None = os.getenv("narakeetApiKey")
    wake_word_model: str = "atlas/models/atlas.ppn"
    porcupine_model_path: str = "atlas/models/porcupine_params_it.pv"
    screenshot_path: str = "temp/screenshot.png"
    prompt_path: str = "temp/prompt.wav"
    log_path: str = "logs/atlas.log"
    groq_model: str = "llama-3.1-8b-instant"
    groq_model2: str = "llama-3.3-70b-versatile"
    whisper_size: str = "medium"
    enable_tts: bool = False
    debug_mode: bool = True
    allowed_dirs: list[str] = field(default_factory=lambda: [os.path.expanduser("~/Documents/AtlasDir")])
    week_days: list[str] = field(
        default_factory=lambda: ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
    )
    system_message: str = (
        "You are a multimodal AI voice assistant. Your name is Atlas. You speak italian. "
        "Your user may or may not have attached a photo for context "
        "(either a screenshot or a webcam capture). Any photo has already been processed into a highly detailed "
        "text prompt that will be attached to their transcribed voice prompt. Generate the most useful and "
        "factual response possible, carefully considering all previous generated text in your response before "
        "adding new tokens to the response. Do not expect or request images, just use the context if added. "
        "Use all of the context of this conversation so your response is relevant to the conversation. Make "
        "your responses clear and concise, avoiding any verbosity."
    )
    generation_config: dict = field(
        default_factory=lambda: {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    )
    max_recent_conversation_messages: int = 8
    conversation_summary_trigger: int = 12
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
