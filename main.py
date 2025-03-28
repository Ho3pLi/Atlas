import logging
from atlas.config import logPath, debugMode
import atlas

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(logPath),
        logging.StreamHandler()
    ]
)

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
        chosenFile = atlas.handleFileChoice(cleanPrompt, atlas.lastFileSearchResults)
        
        if chosenFile:
            atlas.lastFileSearchResults.clear()
            atlas.currentFilePath = chosenFile

            fileContent = atlas.openFile(chosenFile)
            fileContent = fileContent[:2000] if fileContent else "No readable content."

            summaryPrompt = f"Summarize the following file content in 2-3 sentences: {fileContent}"
            summary = atlas.groqPrompt(summaryPrompt, None, None, None)

            if atlas.enableTTS:
                atlas.speak(summary)
        return  

    call = atlas.functionCall(cleanPrompt)
    visualContext = None
    filePath = None
    weatherData = None

    if 'take screenshot' in call:
        screenRes = atlas.takeScreenshot()
        if screenRes:
            visualContext = atlas.visionPrompt(cleanPrompt, atlas.screenshotPath)
    elif 'search file' in call:
        filePath = atlas.handleFileSearchPrompt(cleanPrompt)
    elif 'get weather' in call:
        weatherData = atlas.handleWeatherPrompt(cleanPrompt)
    elif 'build meal plan' in call:
        atlas.buildMealPlan()
        return
        # print('ao')

    response = atlas.groqPrompt(cleanPrompt, visualContext, filePath, weatherData)

    if atlas.enableTTS:
        atlas.speak(response)

if __name__ == "__main__":
    if not debugMode:
        atlas.startListening()
    else:
        logging.info('Initializing Atlas in debug mode...')
        callback()