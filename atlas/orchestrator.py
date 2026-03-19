import logging

import atlas


def handle_audio(audio=None, debug_mode=None):
    if debug_mode is None:
        debug_mode = atlas.config.app.debug_mode

    if debug_mode:
        run_debug_loop()
        return

    logging.info("Audio received, thinking...")

    prompt_audio_path = atlas.config.app.prompt_path
    with open(prompt_audio_path, "wb") as audio_file:
        audio_file.write(audio.get_wav_data())

    prompt_text = atlas.waveToText(prompt_audio_path)
    clean_prompt = atlas.extractPrompt(prompt_text)

    if not clean_prompt:
        logging.warning("No prompt detected, try again.")
        return

    logging.info(f"Prompt detected: {clean_prompt}")
    process_user_prompt(clean_prompt)


def run_debug_loop():
    while True:
        clean_prompt = input("USER: ")
        process_user_prompt(clean_prompt)


def process_user_prompt(clean_prompt):
    handled, response = _handle_file_selection(clean_prompt)
    if handled:
        _speak_if_enabled(response)
        return

    call = atlas.functionCall(clean_prompt)
    visual_context = None
    weather_data = None
    meal_suggestion = None
    response = None

    if "take screenshot" in call:
        screenshot_result = atlas.takeScreenshot()
        if screenshot_result:
            visual_context = atlas.visionPrompt(clean_prompt, atlas.config.app.screenshot_path)
    elif "search file" in call:
        search_outcome = atlas.handleFileSearchPrompt(clean_prompt)
        response = search_outcome["message"]
    elif "get weather" in call:
        weather_data = atlas.handleWeatherPrompt(clean_prompt)
    elif "build meal plan" in call:
        if atlas.config.session.last_day_planned:
            meal_suggestion = atlas.buildMealPlan(atlas.config.session.last_day_planned)
        else:
            meal_suggestion = atlas.buildMealPlan()

    if response is None:
        response = atlas.groqPrompt(clean_prompt, visual_context, None, weather_data, meal_suggestion)

    _speak_if_enabled(response)


def run():
    if atlas.config.app.debug_mode:
        logging.info("Initializing Atlas in debug mode...")
        run_debug_loop()
        return

    atlas.startListening(handle_audio)


def _handle_file_selection(clean_prompt):
    if not atlas.config.session.last_file_search_results:
        return False, None

    chosen_file = atlas.handleFileChoice(clean_prompt, atlas.config.session.last_file_search_results)

    if not chosen_file:
        return True, "I couldn't determine which file you meant. Please say the number or the exact file name."

    atlas.config.session.last_file_search_results.clear()
    atlas.config.session.current_file_path = chosen_file
    summary = atlas.summarizeFile(chosen_file)
    return True, summary


def _speak_if_enabled(response):
    if atlas.config.app.enable_tts and response:
        atlas.speak(response)
