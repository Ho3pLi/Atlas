import logging
import atlas

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("atlas.log"),
        logging.StreamHandler()
    ]
)

def callback(audio):
    logging.info("Audio received, thinking...")
    
    promptAudioPath = 'prompt.wav'
    with open(promptAudioPath, 'wb') as f:
        f.write(audio.get_wav_data())

    promptText = atlas.waveToText(promptAudioPath)
    cleanPrompt = atlas.extractPrompt(promptText)

    if not cleanPrompt:
        logging.warning("No prompt detected, try again.")
        return

    logging.info(f"Prompt detected: {cleanPrompt}")

    if atlas.lastFileSearchResults:
        chosen_file = atlas.handleFileChoice(cleanPrompt, atlas.lastFileSearchResults)
        if chosen_file:
            response = f"You selected the file:\n{chosen_file}"
            atlas.lastFileSearchResults = []
        else:
            response = "I'm sorry, I didn't understand your choice. Please repeat."
    else:
        call = atlas.functionCall(cleanPrompt)
        visualContext = None
        filePath = None
        weatherData = None
    
        if 'take screenshot' in call:
            atlas.takeScreenshot()
            visualContext = atlas.visionPrompt(cleanPrompt, 'screenshot.png')
        elif 'search file' in call:
            filePath = atlas.handleFileSearchPrompt(cleanPrompt)
        elif 'get weather' in call:
            weatherData = atlas.handleWeatherPrompt(cleanPrompt)
    
        response = atlas.groqPrompt(cleanPrompt, visualContext, filePath, weatherData)
        logging.info(f"Assistant response: {response}")

    if atlas.enableTTS:
        atlas.speak(response)

if __name__ == "__main__":
    atlas.startListening()