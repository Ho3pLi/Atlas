import logging
from atlas.config import debugMode, groqClient, groqModel, mealPreferences, weekDays, lastDayPlanned, mealPlan
from atlas.tts import speak
from atlas.audioProcessing import waveToText

def buildMealPlan(day=weekDays[0]):
    logging.info('Entering buildMealPlan() function...')
    setUserMealPlanPref()
    return askForMeal(day)

def getVoiceInput():
    logging.info('Entering getVoiceInput() function...')
    if not debugMode:
        speak("Sono pronto, dimmi!")
        text = waveToText("temp/prompt.wav")
        return text.strip()
    else:
        return input(f'USER: ')

def setUserMealPlanPref():
    global mealPreferences
    logging.info("Entering setUserMealPlanPref() function...")

    mealPreferences = {}
    questions = {
        "restrictions": "Hai delle restrizioni alimentari? Ad esempio, sei vegetariano o intollerante a qualcosa?",
        "preferences": "Hai delle preferenze particolari? Ad esempio, vuoi più proteine o pasti leggeri la sera?",
        "foodToAvoid": "Ci sono cibi che non vuoi nel tuo piano alimentare? Ad esempio, pesce, latticini o peperoni?",
        "favoriteFood": "Quali sono i tuoi cibi preferiti? Ad esempio, pollo, riso, frutta?",
        "dailyMealNum": "Quanti pasti al giorno vuoi inserire? Due, per pranzo e cena, o tre, con anche la colazione? Puoi anche selezionare 4 o 5 pasti includendo gli spuntini.",
        "variety": "Vuoi pasti diversi ogni giorno? Rispondi sì o no."
    }

    for key, question in questions.items():
        if not debugMode:
            speak(question)
        else:
            logging.info(question)
        mealPreferences[key] = getVoiceInput()

    logging.info(f'Meal preferences: {mealPreferences}')
    logging.info("Food preferences successfully saved.")
    if not debugMode:
        speak('Ho salvato con successo le preferenze!')
    return mealPreferences

# def askForMeal(day):
#     logging.info('Entering askForMeal() function...')
#     global lastDayPlanned, mealPlan
#     logging.info(f'Asking for meal suggestion for {day}...')
#     logging.info(f'Last day planned: {lastDayPlanned}')
#     logging.info(f'Meal plan: {mealPlan}')
#     prompt = (
#         "You are a meal plan specialized assistant.\n"
#         "You must reply ONLY in Italian, using exactly these keys:\n"
#         "colazione, spuntino1, pranzo, spuntino2, cena.\n"
#         "Each key must be followed by a colon and the corresponding suggested dish.\n"
#         "No introductions, no extra formatting, just the plan.\n"
#         "User preferences are:\n"
#         f"- Restrictions: {mealPreferences['restrictions']}\n"
#         f"- Preferences: {mealPreferences['preferences']}\n"
#         f"- Food to avoid: {mealPreferences['foodToAvoid']}\n"
#         f"- Favorite food: {mealPreferences['favoriteFood']}\n"
#         f"- Daily meal count: {mealPreferences['dailyMealNum']}\n"
#         f"- Wants variety: {mealPreferences['variety']}\n"
#         f"Generate a meal plan for {day} using the keys and structure described above."
#     )
#     lastDayPlanned = day
#     response = groqClient.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=groqModel)
#     # return response.choices[0].message.content.split(", ")
#     suggestion = response.choices[0].message.content.strip()
#     logging.info(f'Suggestion for {day}: {suggestion}')
#     meals = [x.strip() for x in suggestion.split(",") if x.strip()]
#     logging.info(f'Meals: {meals}')
#     mealKeys = ["colazione", "spuntino1", "pranzo", "spuntino2", "cena"]

#     try:
#         desiredCount = int(mealPreferences['dailyMealNum'])
#     except ValueError:
#         desiredCount = 3

#     if mealPlan is None:
#         mealPlan = {}
#     mealPlan[day] = {
#         mealKeys[i]: meals[i] if i < len(meals) else ""
#         for i in range(desiredCount)
#     }
#     return suggestion

def askForMeal(day):
    import re

    logging.info('Entering askForMeal() function...')
    global lastDayPlanned, mealPlan

    mealKeys = ["colazione", "spuntino1", "pranzo", "spuntino2", "cena"]

    # Assicurati che mealPlan esista
    if mealPlan is None:
        mealPlan = {}

    try:
        desiredCount = int(mealPreferences['dailyMealNum'])
    except (ValueError, TypeError):
        logging.warning("Invalid or missing 'dailyMealNum'. Falling back to 3.")
        desiredCount = 3

    # Prompt
    prompt = (
        "You are a meal plan specialized assistant.\n"
        "You must reply ONLY in Italian, using exactly these keys:\n"
        "colazione, spuntino1, pranzo, spuntino2, cena.\n"
        "Each key must be followed by a colon and the corresponding suggested dish.\n"
        "No introductions, no explanations, just the plan.\n"
        "User preferences are:\n"
        f"- Restrictions: {mealPreferences['restrictions']}\n"
        f"- Preferences: {mealPreferences['preferences']}\n"
        f"- Food to avoid: {mealPreferences['foodToAvoid']}\n"
        f"- Favorite food: {mealPreferences['favoriteFood']}\n"
        f"- Daily meal count: {mealPreferences['dailyMealNum']}\n"
        f"- Wants variety: {mealPreferences['variety']}\n"
        f"Generate a meal plan for {day} using the keys and structure described above."
    )

    # Richiesta al modello
    lastDayPlanned = day
    response = groqClient.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=groqModel
    )
    suggestion = response.choices[0].message.content.strip()
    logging.info(f'Suggestion for {day}:\n{suggestion}')

    # Parsing del testo in dizionario
    meals = {}
    for line in suggestion.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in mealKeys:
                meals[key] = value

    logging.info(f'Parsed meals: {meals}')

    # Riempimento mealPlan[day]
    mealPlan[day] = {
        key: meals.get(key, "")
        for key in mealKeys[:desiredCount]
    }

    logging.info(f'Final meal plan for {day}: {mealPlan[day]}')
    return mealPlan[day]

def changeMealSuggestion(day):
    logging.info('Entering changeMealSuggestion() function...')
    prompt = (
        "You are a meal plan specialized assistant.\n"
        "You speak italian.\n"
        "The user has expressed these preferences:\n"
        f"- Restrictions: {mealPreferences['restrictions']}\n"
        f"- Preferences: {mealPreferences['preferences']}\n"
        f"- Food to avoid: {mealPreferences['foodToAvoid']}\n"
        f"- Favorite food: {mealPreferences['favoriteFood']}\n"
        f"- Daily meal count: {mealPreferences['dailyMealNum']}\n"
        f"- Wants variety: {mealPreferences['variety']}\n\n"
        f"The following meal plan for {day} was rejected by the user:\n"
        f"{previousSuggestion}\n\n"
        "Generate a new meal plan with different dishes.\n"
        "Avoid repeating any of the previous suggestions.\n"
    )

    if additionalRequest:
        prompt += f"The user has also requested: {additionalRequest}\n"

    prompt += "Return only the names of the dishes, separated by commas."