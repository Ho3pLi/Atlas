import logging
import re
from datetime import datetime
from pathlib import Path

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
        Path(prompt_audio_path).parent.mkdir(parents=True, exist_ok=True)
        with open(prompt_audio_path, "wb") as audio_file:
            audio_file.write(audio.get_wav_data())

        prompt_text = atlas.waveToText(prompt_audio_path)
        clean_prompt = atlas.extractPrompt(prompt_text)

        if not clean_prompt:
            logging.warning("No prompt detected, try again.")
            return

        logging.info("Audio prompt transcribed.")
        response = process_user_prompt(clean_prompt)
        if response:
            print(f"ATLAS: {response}")
    except Exception as exc:
        logging.error("Audio handling failed (%s)", type(exc).__name__)
        _speak_if_enabled("C'e stato un problema durante l'elaborazione dell'audio.")
    finally:
        try:
            Path(atlas.config.app.prompt_path).unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not remove temporary prompt audio.")


def run_debug_loop():
    while True:
        try:
            clean_prompt = input("USER: ")
            response = process_user_prompt(clean_prompt)
            if response:
                print(f"ATLAS: {response}")
        except (EOFError, KeyboardInterrupt):
            return


def process_user_prompt(clean_prompt):
    try:
        handled, response = (
            (False, None)
            if atlas.config.session.pending_meal_preferences
            else _handle_file_selection(clean_prompt)
        )
        if handled:
            _speak_if_enabled(response)
            return response

        handled, response = _handle_meal_preferences(clean_prompt)
        if handled:
            _speak_if_enabled(response)
            return response

        intent = atlas.functionCall(clean_prompt)
        action = intent["action"]
        logging.info(
            "Intent routing result: action=%s confidence=%.2f needs_clarification=%s source=%s",
            intent["action"],
            intent["confidence"],
            intent["needs_clarification"],
            intent["source"],
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
                visual_context = atlas.visionPrompt(
                    clean_prompt, screenshot_result["path"]
                )
                if not visual_context:
                    response = "Ho catturato lo screenshot, ma non sono riuscito ad analizzarlo. Riprova."
            else:
                response = screenshot_result["message"]
        elif action == "get_date":
            response = _build_today_message()
        elif action == "get_time":
            response = _build_time_message()
        elif action == "search_file":
            atlas.config.session.pending_meal_preferences = None
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
        elif action in {"build_meal_plan", "change_meal_suggestion"}:
            from atlas.buildMealPlan import (
                QUESTIONS,
                buildMealPlan,
                changeMealSuggestion,
            )

            state = atlas.config.session
            day = state.last_day_planned or atlas.config.app.week_days[0]
            if state.meal_preferences is None:
                state.last_file_search_results.clear()
                state.pending_meal_preferences = {"answers": {}, "day": day}
                response = next(iter(QUESTIONS.values()))
            elif action == "change_meal_suggestion":
                previous = (state.meal_plan or {}).get(day)
                if previous is None:
                    response = "Non hai ancora un piano da modificare. Chiedimi di creare un piano pasti."
                else:
                    response = _format_meals(
                        changeMealSuggestion(day, previous, clean_prompt)
                    )
            else:
                response = _format_meals(buildMealPlan(day))

        if response is None:
            response = atlas.groqPrompt(
                clean_prompt, visual_context, None, weather_data, meal_suggestion
            )

        _speak_if_enabled(response)
        return response
    except Exception as exc:
        logging.error("Prompt processing failed (%s)", type(exc).__name__)
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
        logging.error("Listening loop failed (%s)", type(exc).__name__)
        _speak_if_enabled("Non riesco ad avviare l'ascolto in questo momento.")


def _handle_file_selection(clean_prompt):
    if not atlas.config.session.last_file_search_results:
        return False, None

    if clean_prompt.strip().casefold() in {
        "annulla",
        "annulla ricerca",
        "annulla selezione",
        "cancel",
    }:
        atlas.config.session.last_file_search_results.clear()
        return True, "Ricerca file annullata."
    from atlas.fileHandler import resolveFileChoice

    chosen_file = resolveFileChoice(
        clean_prompt, atlas.config.session.last_file_search_results
    )

    if not chosen_file:
        choice = clean_prompt.strip().casefold()
        names = {
            Path(path).name.casefold()
            for path in atlas.config.session.last_file_search_results
        }
        stems = [
            Path(path).stem.casefold()
            for path in atlas.config.session.last_file_search_results
        ]
        if choice in names or choice in stems:
            return (
                True,
                "Il nome e ambiguo. Di' il numero oppure il nome esatto con il percorso.",
            )
        from atlas.core import _route_with_heuristics

        intent = _route_with_heuristics(clean_prompt)
        if intent and intent["action"] != "none" and not intent["needs_clarification"]:
            return False, None
        # Keep ambiguous selections local, but let unrelated conversation proceed.
        looks_like_selection = re.fullmatch(
            r"(?:numero\s+)?\d+[.!]?", choice
        ) or re.match(
            r"^(?:quello|quella|il primo|il secondo|il terzo|l'ultimo)\b", choice
        )
        mentions_candidate = any(
            re.search(r"(?<!\w)" + re.escape(stem) + r"(?!\w)", choice)
            for stem in stems
        )
        if looks_like_selection or mentions_candidate:
            return (
                True,
                "Non sono riuscito a capire quale file intendi. Di' il numero oppure il nome esatto del file.",
            )
        return False, None

    atlas.config.session.last_file_search_results.clear()
    atlas.config.session.current_file_path = chosen_file
    summary = atlas.summarizeFile(chosen_file)
    return True, summary


def _speak_if_enabled(response):
    if atlas.config.app.enable_tts and response:
        atlas.speak(response)


def _build_today_message():
    today = datetime.now()
    weekdays = [
        "lunedi",
        "martedi",
        "mercoledi",
        "giovedi",
        "venerdi",
        "sabato",
        "domenica",
    ]
    weekday = weekdays[today.weekday()]
    return f"Oggi e {weekday}, {today.strftime('%Y-%m-%d')}."


def _build_time_message():
    now = datetime.now()
    return f"Sono le {now.strftime('%H:%M')} del {now.strftime('%Y-%m-%d')}."


def _build_capabilities_message():
    available_apps = atlas.listConfiguredApps()
    listed_apps = (
        ", ".join(available_apps[:8]) if available_apps else "nessuna app configurata"
    )
    return (
        "Posso aiutarti con conversazione generale, meteo, ricerca file, screenshot, data/ora, meal plan, "
        "e anche aprire o chiudere applicazioni configurate. "
        f"Al momento ho questi alias app: {listed_apps}."
    )


def _format_meals(meals):
    return "\n".join(f"{key}: {value}" for key, value in meals.items())


def _handle_meal_preferences(prompt):
    state = atlas.config.session
    pending = state.pending_meal_preferences
    if pending is None:
        return False, None
    if prompt.strip().casefold() in {
        "annulla",
        "annulla piano",
        "annulla pasti",
        "cancel",
    }:
        state.pending_meal_preferences = None
        return True, "Preparazione del piano annullata."
    from atlas.buildMealPlan import QUESTIONS, buildMealPlan, validatePreference
    from atlas.core import _route_with_heuristics

    intent = _route_with_heuristics(prompt)
    if (
        intent
        and intent["action"]
        not in {"none", "build_meal_plan", "change_meal_suggestion"}
        and not intent["needs_clarification"]
    ):
        return False, None
    answers = pending["answers"]
    key = list(QUESTIONS)[len(answers)]
    try:
        answers[key] = validatePreference(key, prompt)
    except ValueError as exc:
        return True, str(exc)
    if len(answers) < len(QUESTIONS):
        return True, QUESTIONS[list(QUESTIONS)[len(answers)]]
    state.meal_preferences = dict(answers)
    state.pending_meal_preferences = None
    try:
        return True, _format_meals(buildMealPlan(pending["day"]))
    except Exception:
        logging.warning("Meal generation failed; preferences retained for retry.")
        return (
            True,
            "Preferenze salvate, ma non riesco a generare il piano. Chiedimi di riprovare.",
        )
