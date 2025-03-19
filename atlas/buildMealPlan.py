import logging
from atlas.config import debugMode
from atlas.tts import speak
from atlas.audioProcessing import waveToText

def buildMealPlan():
    logging.info('Entering buildMealPlan() function...')
    setUserMealPlanPref()

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
    return mealPreferences
