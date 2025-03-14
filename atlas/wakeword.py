import logging
import pvporcupine
import pyaudio
import struct

from atlas.config import porcupineApiKey, wakeWordModel, porcupineModelPath, r, mic

def startListening():
    porcupine = pvporcupine.create(
        access_key=porcupineApiKey,
        keyword_paths=[wakeWordModel],
        model_path=porcupineModelPath
    )

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
                with mic as m:
                    r.adjust_for_ambient_noise(m, duration=0.5)
                    logging.info("Capturing prompt...")
                    audio = r.listen(m)
                    callback(audio)

    except KeyboardInterrupt:
        logging.info("Interrupted by user.")

    finally:
        if porcupine is not None:
            porcupine.delete()

        audio_stream.stop_stream()
        audio_stream.close()
        pa.terminate()