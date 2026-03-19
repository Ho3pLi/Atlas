import logging
import atlas

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(atlas.config.app.log_path),
        logging.StreamHandler()
    ]
)

def callback(audio=None, debugMode=None):
    if debugMode is None:
        debugMode = atlas.config.app.debug_mode

    if not debugMode:
        logging.info("Audio received, thinking...")

        promptAudioPath = atlas.config.app.prompt_path
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
    if atlas.config.session.last_file_search_results:
        chosenFile = atlas.handleFileChoice(cleanPrompt, atlas.config.session.last_file_search_results)
        
        if chosenFile:
            atlas.config.session.last_file_search_results.clear()
            atlas.config.session.current_file_path = chosenFile

            fileContent = atlas.openFile(chosenFile)
            fileContent = fileContent[:2000] if fileContent else "No readable content."

            summaryPrompt = f"Summarize the following file content in 2-3 sentences: {fileContent}"
            summary = atlas.groqPrompt(summaryPrompt, None, None, None)

            if atlas.config.app.enable_tts:
                atlas.speak(summary)
        return
    
    

    call = atlas.functionCall(cleanPrompt)
    visualContext = None
    filePath = None
    weatherData = None
    mealSuggestion = None

    if 'take screenshot' in call:
        screenRes = atlas.takeScreenshot()
        if screenRes:
            visualContext = atlas.visionPrompt(cleanPrompt, atlas.config.app.screenshot_path)
    elif 'search file' in call:
        filePath = atlas.handleFileSearchPrompt(cleanPrompt)
    elif 'get weather' in call:
        weatherData = atlas.handleWeatherPrompt(cleanPrompt)
    elif 'build meal plan' in call:
        if atlas.config.session.last_day_planned:
            mealSuggestion = atlas.buildMealPlan(atlas.config.session.last_day_planned)
        else:
            mealSuggestion = atlas.buildMealPlan()
    # elif 'change meal suggestion' in call:


    response = atlas.groqPrompt(cleanPrompt, visualContext, filePath, weatherData, mealSuggestion)

    if atlas.config.app.enable_tts:
        atlas.speak(response)

if __name__ == "__main__":
    if not atlas.config.app.debug_mode:
        atlas.startListening(callback)
    else:
        logging.info('Initializing Atlas in debug mode...')
        callback()
