import logging
import requests
import pydub
from pydub.playback import play

from atlas.config import narakeetApiKey

def speak(text):    
    if not narakeetApiKey:
        raise ValueError("API key not found.")

    url = "https://api.narakeet.com/text-to-speech/m4a?voice=vincenzo"
    headers = {
        "Accept": "application/octet-stream",
        "Content-Type": "text/plain",
        "x-api-key": narakeetApiKey,
    }

    response = requests.post(url, headers=headers, data=text.encode("utf-8"))
    
    if response.status_code == 200:
        with open("temp/debug_output.m4a", "wb") as f:
            f.write(response.content)
        sound = pydub.AudioSegment.from_file("temp/debug_output.m4a", format="m4a")
        play(sound)
        logging.info("Audio successfully played.")
    else:
        logging.error(f"Error {response.status_code}: {response.text}")
