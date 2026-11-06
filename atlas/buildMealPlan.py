"""Meal planning with explicit preferences and atomic plan updates."""

import json
import logging
from pathlib import Path

import atlas.config as config
from atlas.tts import speak
from atlas.audioProcessing import waveToText

QUESTIONS = {
    "restrictions": "Hai restrizioni alimentari o intolleranze?",
    "preferences": "Hai preferenze particolari per i pasti?",
    "foodToAvoid": "Quali cibi vuoi evitare?",
    "favoriteFood": "Quali sono i tuoi cibi preferiti?",
    "dailyMealNum": "Quanti pasti al giorno vuoi, da 1 a 5? Due comprende pranzo e cena; tre anche la colazione.",
    "variety": "Vuoi pasti diversi ogni giorno?",
}
MEALS_BY_COUNT = {
    1: ("pranzo",),
    2: ("pranzo", "cena"),
    3: ("colazione", "pranzo", "cena"),
    4: ("colazione", "spuntino1", "pranzo", "cena"),
    5: ("colazione", "spuntino1", "pranzo", "spuntino2", "cena"),
}


def validatePreference(key, answer):
    answer = answer.strip()
    if not answer:
        raise ValueError("La risposta non puo essere vuota.")
    if key == "dailyMealNum":
        numbers = {"uno": "1", "due": "2", "tre": "3", "quattro": "4", "cinque": "5"}
        answer = numbers.get(answer.casefold(), answer)
        if answer not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Indica un numero di pasti da 1 a 5.")
    return answer


def buildMealPlan(day=None):
    day = day or config.app.week_days[0]
    if config.session.meal_preferences is None:
        setUserMealPlanPref()
    return askForMeal(day)


def getVoiceInput():
    if config.app.debug_mode:
        return input("USER: ").strip()
    recognizer = config.get_recognizer()
    microphone = config.get_microphone()
    if microphone is None:
        raise RuntimeError("Microfono non disponibile")
    if config.app.enable_tts:
        speak("Sono pronto, dimmi!")
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(
            source,
            timeout=config.app.listen_timeout,
            phrase_time_limit=config.app.phrase_time_limit,
        )
    path = Path(config.app.prompt_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(audio.get_wav_data())
        return waveToText(str(path)).strip()
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not remove temporary preference audio.")


def setUserMealPlanPref():
    preferences = {}
    for key, question in QUESTIONS.items():
        while True:
            if config.app.enable_tts:
                speak(question)
            else:
                print(question)
            try:
                preferences[key] = validatePreference(key, getVoiceInput())
                break
            except ValueError as exc:
                print(str(exc))
    config.session.meal_preferences = preferences
    return preferences


def _generate_plan(day, previous=None, additional_request=None):
    preferences = config.session.meal_preferences
    if not isinstance(preferences, dict) or any(
        key not in preferences for key in QUESTIONS
    ):
        raise ValueError("Completa prima le preferenze alimentari.")
    count = int(validatePreference("dailyMealNum", str(preferences["dailyMealNum"])))
    keys = MEALS_BY_COUNT[count]
    prompt = (
        "Generate a meal plan in Italian. Respect all restrictions and preferences below. "
        "Return ONLY a JSON object with these exact keys and nonempty dish descriptions: "
        + json.dumps(keys)
        + "\nDay: "
        + str(day)
        + "\nPreferences: "
        + json.dumps(preferences, ensure_ascii=False)
    )
    if previous is not None:
        prompt += "\nReplace this plan with different dishes: " + json.dumps(
            previous, ensure_ascii=False
        )
    if additional_request:
        prompt += "\nRequested change: " + additional_request
    response = config.get_groq_client().chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=config.app.groq_model,
        response_format={"type": "json_object"},
    )
    meals = json.loads(response.choices[0].message.content)
    if (
        not isinstance(meals, dict)
        or set(meals) != set(keys)
        or any(
            not isinstance(meals[key], str) or not meals[key].strip() for key in keys
        )
    ):
        raise ValueError("Il servizio non ha restituito un piano completo.")
    plan = {key: meals[key].strip() for key in keys}
    # Save only after the entire response has passed validation.
    if config.session.meal_plan is None:
        config.session.meal_plan = {}
    config.session.meal_plan[day] = plan
    config.session.last_day_planned = day
    return plan


def askForMeal(day):
    return _generate_plan(day)


def changeMealSuggestion(day, previousSuggestion, additionalRequest=None):
    return _generate_plan(day, previousSuggestion, additionalRequest)
