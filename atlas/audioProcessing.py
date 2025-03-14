import logging

from atlas.config import whisperModel

def waveToText(audioPath):
    logging.info(f"Transcribing audio: {audioPath}")
    segments, _ = whisperModel.transcribe(audioPath, language='it')
    text = ' '.join([segment.text for segment in segments])

    logging.info(f"Transcribed text: {text}")
    return text

def extractPrompt(transcribedText):
    logging.info(f"Extracted prompt: {transcribedText}")
    return transcribedText.strip() if transcribedText else None