import atlas.config as config


def waveToText(audioPath):
    segments, _ = config.get_whisper_model().transcribe(audioPath, language="it")
    text = " ".join([segment.text for segment in segments])

    return text


def extractPrompt(transcribedText):
    return transcribedText.strip() if transcribedText else None
