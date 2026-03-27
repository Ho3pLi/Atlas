import logging
from datetime import datetime

import atlas


def handle_audio(audio=None, debug_mode=None):
    if debug_mode is None:
        debug_mode = atlas.config.app.debug_mode

    if debug_mode:
        run_debug_loop()
        return

    try:
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
    except Exception as exc:
        logging.exception(f"Audio handling failed: {exc}")
        _speak_if_enabled("C'e stato un problema durante l'elaborazione dell'audio.")


def run_debug_loop():
    while True:
        clean_prompt = input("USER: ")
        process_user_prompt(clean_prompt)


def process_user_prompt(clean_prompt):
    try:
        handled, response = _handle_file_selection(clean_prompt)
        if handled:
            _speak_if_enabled(response)
            return response

        intent = atlas.functionCall(clean_prompt)
        action = intent["action"]
        logging.info(
            "Intent routing result: action=%s confidence=%.2f needs_clarification=%s source=%s reason=%s",
            intent["action"],
            intent["confidence"],
            intent["needs_clarification"],
            intent["source"],
            intent["reason"],
        )
        visual_context = None
        weather_data = None
        meal_suggestion = None
        response = None

        if intent["needs_clarification"]:
            response = "Non ho capito con sufficiente certezza cosa vuoi fare. Riformula la richiesta in modo piu specifico."
            _speak_if_enabled(response)
            return response
        if action == "none" and intent.get("reason") == "capabilities_query":
            response = _build_capabilities_message()
            _speak_if_enabled(response)
            return response

        if action == "take_screenshot":
            screenshot_result = atlas.takeScreenshot()
            if screenshot_result["status"] == "ok":
                visual_context = atlas.visionPrompt(clean_prompt, screenshot_result["path"])
            else:
                response = screenshot_result["message"]
        elif action == "get_date":
            response = _build_today_message()
        elif action == "get_time":
            response = _build_time_message()
        elif action == "search_file":
            search_outcome = atlas.handleFileSearchPrompt(clean_prompt)
            response = search_outcome["message"]
        elif action == "get_weather":
            weather_data = atlas.handleWeatherPrompt(clean_prompt)
            if weather_data["report"]["status"] != "ok":
                response = weather_data["message"]
        elif action == "open_app":
            app_launch_result = atlas.handleAppLaunchPrompt(clean_prompt)
            response = app_launch_result["message"]
        elif action == "close_app":
            app_close_result = atlas.handleCloseAppPrompt(clean_prompt)
            response = app_close_result["message"]
        elif action == "build_meal_plan":
            if atlas.config.session.last_day_planned:
                meal_suggestion = atlas.buildMealPlan(atlas.config.session.last_day_planned)
            else:
                meal_suggestion = atlas.buildMealPlan()

        if response is None:
            response = atlas.groqPrompt(clean_prompt, visual_context, None, weather_data, meal_suggestion)

        _speak_if_enabled(response)
        return response
    except Exception as exc:
        logging.exception(f"Prompt processing failed: {exc}")
        response = "Si e verificato un errore durante l'elaborazione della richiesta."
        _speak_if_enabled(response)
        return response


def run():
    if atlas.config.app.debug_mode:
        logging.info("Initializing Atlas in debug mode...")
        run_debug_loop()
        return

    try:
        atlas.startListening(handle_audio)
    except Exception as exc:
        logging.exception(f"Listening loop failed: {exc}")
        _speak_if_enabled("Non riesco ad avviare l'ascolto in questo momento.")


def _handle_file_selection(clean_prompt):
    if not atlas.config.session.last_file_search_results:
        return False, None

    chosen_file = atlas.handleFileChoice(clean_prompt, atlas.config.session.last_file_search_results)

    if not chosen_file:
        return True, "Non sono riuscito a capire quale file intendi. Di' il numero oppure il nome esatto del file."

    atlas.config.session.last_file_search_results.clear()
    atlas.config.session.current_file_path = chosen_file
    summary = atlas.summarizeFile(chosen_file)
    return True, summary


def _speak_if_enabled(response):
    if atlas.config.app.enable_tts and response:
        atlas.speak(response)


def _build_today_message():
    today = datetime.now()
    weekdays = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
    weekday = weekdays[today.weekday()]
    return f"Oggi e {weekday}, {today.strftime('%Y-%m-%d')}."


def _build_time_message():
    now = datetime.now()
    return f"Sono le {now.strftime('%H:%M')} del {now.strftime('%Y-%m-%d')}."


def _build_capabilities_message():
    available_apps = atlas.listConfiguredApps()
    listed_apps = ", ".join(available_apps[:8]) if available_apps else "nessuna app configurata"
    return (
        "Posso aiutarti con conversazione generale, meteo, ricerca file, screenshot, data/ora, meal plan, "
        "e anche aprire o chiudere applicazioni configurate. "
        f"Al momento ho questi alias app: {listed_apps}."
    )
