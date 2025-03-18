import logging
import atlas

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(atlas.logPath),
        logging.StreamHandler()
    ]
)

debugMode = True

def callback(audio=None, debugMode=debugMode):
    if not debugMode:
        logging.info("Audio received, thinking...")

        promptAudioPath = atlas.promptPath
        with open(promptAudioPath, 'wb') as f:
            f.write(audio.get_wav_data())

        promptText = atlas.waveToText(promptAudioPath)
        cleanPrompt = atlas.extractPrompt(promptText)

        if not cleanPrompt:
            logging.warning("No prompt detected, try again.")
            return

        logging.info(f"Prompt detected: {cleanPrompt}")
        processUserPrompt(cleanPrompt)
    else:
        while(True):
            cleanPrompt = input('USER: ')
            processUserPrompt(cleanPrompt)
            

def processUserPrompt(cleanPrompt):
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
            visualContext = atlas.visionPrompt(cleanPrompt, atlas.screenshotPath)
        elif 'search file' in call:
            filePath = atlas.handleFileSearchPrompt(cleanPrompt)
        elif 'get weather' in call:
            weatherData = atlas.handleWeatherPrompt(cleanPrompt)
        response = atlas.groqPrompt(cleanPrompt, visualContext, filePath, weatherData)

    if atlas.enableTTS:
        atlas.speak(response)

if __name__ == "__main__":
    if not debugMode:
        atlas.startListening()
    else:
        logging.info('Initializing Atlas in debug mode...')
        callback()