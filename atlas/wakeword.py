import logging
import struct

import atlas.config as config


def startListening(on_audio):
    if not callable(on_audio):
        raise ValueError("startListening requires a callable on_audio callback.")
    import pvporcupine
    import pyaudio
    import speech_recognition as sr

    porcupine = pa = audio_stream = None
    try:
        porcupine = pvporcupine.create(
            access_key=config.app.porcupine_api_key,
            keyword_paths=[config.app.wake_word_model],
            model_path=config.app.porcupine_model_path,
        )
        recognizer = config.get_recognizer()
        microphone = config.get_microphone()
        if microphone is None:
            raise RuntimeError("Microphone not available.")
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )
        logging.info("Atlas is listening for the wake word...")
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            if (
                porcupine.process(struct.unpack_from("h" * porcupine.frame_length, pcm))
                >= 0
            ):
                audio_stream.stop_stream()
                try:
                    with microphone as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = recognizer.listen(
                            source,
                            timeout=config.app.listen_timeout,
                            phrase_time_limit=config.app.phrase_time_limit,
                        )
                    # Release the microphone before callbacks perform further captures.
                    on_audio(audio)
                except sr.WaitTimeoutError:
                    logging.info("No prompt received before listening timeout.")
                finally:
                    audio_stream.start_stream()
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
    finally:
        # Each cleanup is independent: a failed close must not leak the others.
        for resource, method in (
            (audio_stream, "stop_stream"),
            (audio_stream, "close"),
            (pa, "terminate"),
            (porcupine, "delete"),
        ):
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    logging.warning("Audio resource cleanup failed: %s", method)
