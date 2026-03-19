import logging
import struct

import atlas.config as config

def startListening(on_audio):
    logging.info('Initializing startListening() function...')
    if not callable(on_audio):
        raise ValueError("startListening requires a callable on_audio callback.")

    import pvporcupine
    import pyaudio

    porcupine = pvporcupine.create(
        access_key=config.app.porcupine_api_key,
        keyword_paths=[config.app.wake_word_model],
        model_path=config.app.porcupine_model_path
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
        frames_per_buffer=porcupine.frame_length
    )

    logging.info("Atlas is listening for the wake word...")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
            keyword_index = porcupine.process(pcm_unpacked)

            if keyword_index >= 0:
                logging.info("Wake word detected! Listening for prompt...")
                with microphone as m:
                    recognizer.adjust_for_ambient_noise(m, duration=0.5)
                    logging.info("Capturing prompt...")
                    audio = recognizer.listen(m)
                    on_audio(audio)

    except KeyboardInterrupt:
        logging.info("Interrupted by user.")

    finally:
        if porcupine is not None:
            porcupine.delete()

        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()
