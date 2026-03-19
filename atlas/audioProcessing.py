import logging

import atlas.config as config

def waveToText(audioPath):
    logging.info(f"Transcribing audio: {audioPath}")
    segments, _ = config.get_whisper_model().transcribe(audioPath, language="it")
    text = " ".join([segment.text for segment in segments])

    logging.info(f"Transcribed text: {text}")
    return text

def extractPrompt(transcribedText):
    logging.info(f"Extracted prompt: {transcribedText}")
    return transcribedText.strip() if transcribedText else None
