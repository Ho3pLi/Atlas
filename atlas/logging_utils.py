"""Bounded logs that redact configured credentials, including exception text."""

import logging
import re
from urllib.parse import quote, quote_plus

import atlas.config as config


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        rendered = super().format(record)
        for name in (
            "groq_api_key",
            "google_api_key",
            "openai_api_key",
            "weather_api_key",
            "porcupine_api_key",
            "narakeet_api_key",
        ):
            secret = getattr(config.app, name, None)
            if secret:
                for value in (secret, quote(secret, safe=""), quote_plus(secret)):
                    rendered = rendered.replace(value, "[REDACTED]")
        return re.sub(
            r"(?i)(appid=|api_key=|x-api-key[:=]\s*)[^&\s]+", r"\1[REDACTED]", rendered
        )
