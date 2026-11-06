import logging
from io import BytesIO
import requests

import atlas.config as config


def speak(text):
    if not config.app.narakeet_api_key:
        logging.warning("TTS skipped: missing Narakeet API key.")
        return False

    url = "https://api.narakeet.com/text-to-speech/m4a?voice=vincenzo"
    headers = {
        "Accept": "application/octet-stream",
        "Content-Type": "text/plain",
        "x-api-key": config.app.narakeet_api_key,
    }

    try:
        import pydub
        from pydub.playback import play

        response = requests.post(
            url, headers=headers, data=text.encode("utf-8"), timeout=30
        )
        response.raise_for_status()

        sound = pydub.AudioSegment.from_file(BytesIO(response.content), format="m4a")
        play(sound)
        logging.info("Audio successfully played.")
        return True
    except requests.RequestException as exc:
        logging.error("TTS request failed (%s)", type(exc).__name__)
    except Exception as exc:
        logging.error("TTS playback failed (%s)", type(exc).__name__)
    return False
