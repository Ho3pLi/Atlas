import logging

import atlas.config as config
from atlas.tts import speak
from atlas.audioProcessing import waveToText

def buildMealPlan(day=None):
    logging.info('Entering buildMealPlan() function...')
    if day is None:
        day = config.app.week_days[0]

    if not config.app.debug_mode:
        setUserMealPlanPref()
    else:
        config.session.meal_preferences = {
            'restrictions': 'no',
            'preferences': 'pochi grassi',
            'foodToAvoid': 'pesce',
            'favoriteFood': 'frutta',
            'dailyMealNum': '5',
            'variety': 'si'
        }
    return askForMeal(day)

def getVoiceInput():
    logging.info('Entering getVoiceInput() function...')
    if not config.app.debug_mode:
        speak("Sono pronto, dimmi!")
        text = waveToText("temp/prompt.wav")
        return text.strip()
    else:
        return input('USER: ')

def setUserMealPlanPref():
    logging.info("Entering setUserMealPlanPref() function...")
    config.session.meal_preferences = {}

    questions = {
        "restrictions": "Hai delle restrizioni alimentari? Ad esempio, sei vegetariano o intollerante a qualcosa?",
        "preferences": "Hai delle preferenze particolari? Ad esempio, vuoi più proteine o pasti leggeri la sera?",
        "foodToAvoid": "Ci sono cibi che non vuoi nel tuo piano alimentare? Ad esempio, pesce, latticini o peperoni?",
        "favoriteFood": "Quali sono i tuoi cibi preferiti? Ad esempio, pollo, riso, frutta?",
        "dailyMealNum": "Quanti pasti al giorno vuoi inserire? Due, per pranzo e cena, o tre, con anche la colazione? Puoi anche selezionare 4 o 5 pasti includendo gli spuntini.",
        "variety": "Vuoi pasti diversi ogni giorno? Rispondi sì o no."
    }

    for key, question in questions.items():
        if not config.app.debug_mode:
            speak(question)
        else:
            logging.info(question)
        config.session.meal_preferences[key] = getVoiceInput()

    logging.info(f"Meal preferences: {config.session.meal_preferences}")
    logging.info("Food preferences successfully saved.")
    if not config.app.debug_mode:
        speak('Ho salvato con successo le preferenze!')
    return config.session.meal_preferences

def askForMeal(day):
    logging.info('Entering askForMeal() function...')

    mealKeys = ["colazione", "spuntino1", "pranzo", "spuntino2", "cena"]

    if config.session.meal_plan is None:
        config.session.meal_plan = {}

    try:
        desiredCount = int(config.session.meal_preferences['dailyMealNum'])
    except (ValueError, TypeError):
        logging.warning("Invalid or missing 'dailyMealNum'. Falling back to 3.")
        desiredCount = 3

    prompt = (
        "You are a meal plan specialized assistant.\n"
        "You must reply ONLY in Italian, using exactly these keys:\n"
        "colazione, spuntino1, pranzo, spuntino2, cena.\n"
        "Each key must be followed by a colon and the corresponding suggested dish.\n"
        "No introductions, no explanations, just the plan.\n"
        "User preferences are:\n"
        f"- Restrictions: {config.session.meal_preferences['restrictions']}\n"
        f"- Preferences: {config.session.meal_preferences['preferences']}\n"
        f"- Food to avoid: {config.session.meal_preferences['foodToAvoid']}\n"
        f"- Favorite food: {config.session.meal_preferences['favoriteFood']}\n"
        f"- Daily meal count: {config.session.meal_preferences['dailyMealNum']}\n"
        f"- Wants variety: {config.session.meal_preferences['variety']}\n"
        f"Generate a meal plan for {day} using the keys and structure described above."
    )

    config.session.last_day_planned = day
    response = config.get_groq_client().chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=config.app.groq_model
    )

    suggestion = response.choices[0].message.content.strip()
    logging.info(f'Suggestion for {day}:\n{suggestion}')

    meals = {}
    for line in suggestion.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in mealKeys:
                meals[key] = value

    logging.info(f'Parsed meals: {meals}')

    config.session.meal_plan[day] = {
        key: meals.get(key, "")
        for key in mealKeys[:desiredCount]
    }

    logging.info(f"Final meal plan for {day}: {config.session.meal_plan[day]}")
    return config.session.meal_plan[day]

def changeMealSuggestion(day, previousSuggestion, additionalRequest=None):
    logging.info('Entering changeMealSuggestion() function...')

    prompt = (
        "You are a meal plan specialized assistant.\n"
        "You speak italian.\n"
        "The user has expressed these preferences:\n"
        f"- Restrictions: {config.session.meal_preferences['restrictions']}\n"
        f"- Preferences: {config.session.meal_preferences['preferences']}\n"
        f"- Food to avoid: {config.session.meal_preferences['foodToAvoid']}\n"
        f"- Favorite food: {config.session.meal_preferences['favoriteFood']}\n"
        f"- Daily meal count: {config.session.meal_preferences['dailyMealNum']}\n"
        f"- Wants variety: {config.session.meal_preferences['variety']}\n\n"
        f"The following meal plan for {day} was rejected by the user:\n"
        f"{previousSuggestion}\n\n"
        "Generate a new meal plan with different dishes.\n"
        "Avoid repeating any of the previous suggestions.\n"
    )

    if additionalRequest:
        prompt += f"The user has also requested: {additionalRequest}\n"

    prompt += "Return only the names of the dishes, separated by commas."

    response = config.get_groq_client().chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=config.app.groq_model
    )

    newSuggestion = response.choices[0].message.content.strip()
    logging.info(f'New suggestion for {day}:\n{newSuggestion}')
    return newSuggestion
