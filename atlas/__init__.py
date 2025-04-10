# Core functionalities
from .core import groqPrompt, functionCall

# Voice and TTS
from .tts import speak

# Screenshot and visual context
from .screenshot import takeScreenshot, visionPrompt

# File handling
from .fileHandler import handleFileSearchPrompt, handleFileChoice, openFile

# Weather handling
from .weather import handleWeatherPrompt

# Wakeword and listening loop
from .wakeword import startListening

# Audio processing
from .audioProcessing import waveToText, extractPrompt

# Meal plan logic
from .buildMealPlan import buildMealPlan, askForMeal, changeMealSuggestion, setUserMealPlanPref

# Import config as a module to preserve shared global state
import atlas.config as config