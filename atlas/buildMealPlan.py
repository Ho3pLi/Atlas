import logging
from atlas.config import debugMode, groqClient, groqModel, mealPreferences
from atlas.tts import speak
from atlas.audioProcessing import waveToText

mealPlan = {}

def buildMealPlan():
    logging.info('Entering buildMealPlan() function...')
    preferences = setUserMealPlanPref()
    # weekDays = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    return
    for day in weekDays:
        mealPlan[day] = {}
        askForMeal(preferences, day)

def getVoiceInput():
    logging.info('Entering getVoiceInput() function...')
    if not debugMode:
        speak("Sono pronto, dimmi!")
        text = waveToText("temp/prompt.wav")
        return text.strip()
    else:
        return input(f'USER: ')

def setUserMealPlanPref():
    logging.info("Entering setUserMealPlanPref() function...")

    mealPreferences = {}
    questions = {
        "restrictions": "Hai delle restrizioni alimentari? Ad esempio, sei vegetariano o intollerante a qualcosa?",
        "preferences": "Hai delle preferenze particolari? Ad esempio, vuoi più proteine o pasti leggeri la sera?",
        "foodToAvoid": "Ci sono cibi che non vuoi nel tuo piano alimentare? Ad esempio, pesce, latticini o peperoni?",
        "favoriteFood": "Quali sono i tuoi cibi preferiti? Ad esempio, pollo, riso, frutta?",
        "dailyMealNum": "Quanti pasti al giorno vuoi inserire? Due, per pranzo e cena, o tre, con anche la colazione?",
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

def askForMeal(preferences, day):
    logging.info('Entering askForMeal() function...')
    prompt = (
    'You are a meal plan specialized assistant.'
    'You speak italian.'
    'The user has expressed these preferences:',
    f'- Restrictions: {preferences["restrictions"]}',
    f'- Preferences: {preferences["preferences"]}',
    f'- Food to avoid: {preferences["foodToAvoid"]}',
    f'- Favorite food: {preferences["favoriteFood"]}',
    f'- Daily meal count: {preferences["dailyMealNum"]}',
    f'- Wants variety: {preferences["variety"]}',
    f'Generate a meal plan for {day} with {preferences["dailyMealNum"]} meals. Do not include descriptions, only the names of the dishes, separated by commas.',
    'Talk with the user till you understand he is satisfied with the daily meal plan and return the choices in this format: "day": {"breakfast": "x", "lunch": "y", "dinner": "q"}'
    )

    response = groqClient.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=groqModel)
    # return response.choices[0].message.content.split(", ")
    print(f'res: {response.choices[0].message.content}')
    return response.choices[0].message.content
