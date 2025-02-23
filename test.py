import openai

openai.api_key = ''

try:
    response = openai.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input="Ciao, questo è un test del Text-to-Speech di OpenAI.",
    )

    with open("output_audio.mp3", "wb") as audio_file:
        audio_file.write(response.content)

    print("✅ Audio generato con successo e salvato come 'output_audio.mp3'.")
except Exception as e:
    print(f"Errore durante la generazione dell'audio: {e}")