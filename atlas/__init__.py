from importlib import import_module

import atlas.config as config


def _load_attr(module_name, attr_name):
    module = import_module(module_name, package=__name__)
    return getattr(module, attr_name)


def groqPrompt(*args, **kwargs):
    return _load_attr(".core", "groqPrompt")(*args, **kwargs)


def functionCall(*args, **kwargs):
    return _load_attr(".core", "functionCall")(*args, **kwargs)


def speak(*args, **kwargs):
    return _load_attr(".tts", "speak")(*args, **kwargs)


def takeScreenshot(*args, **kwargs):
    return _load_attr(".screenshot", "takeScreenshot")(*args, **kwargs)


def visionPrompt(*args, **kwargs):
    return _load_attr(".screenshot", "visionPrompt")(*args, **kwargs)


def handleFileSearchPrompt(*args, **kwargs):
    return _load_attr(".fileHandler", "handleFileSearchPrompt")(*args, **kwargs)


def handleFileChoice(*args, **kwargs):
    return _load_attr(".fileHandler", "handleFileChoice")(*args, **kwargs)


def openFile(*args, **kwargs):
    return _load_attr(".fileHandler", "openFile")(*args, **kwargs)


def readFileContent(*args, **kwargs):
    return _load_attr(".fileHandler", "readFileContent")(*args, **kwargs)


def summarizeFile(*args, **kwargs):
    return _load_attr(".fileHandler", "summarizeFile")(*args, **kwargs)


def handleWeatherPrompt(*args, **kwargs):
    return _load_attr(".weather", "handleWeatherPrompt")(*args, **kwargs)


def handleAppLaunchPrompt(*args, **kwargs):
    return _load_attr(".appLauncher", "handleAppLaunchPrompt")(*args, **kwargs)


def startListening(*args, **kwargs):
    return _load_attr(".wakeword", "startListening")(*args, **kwargs)


def waveToText(*args, **kwargs):
    return _load_attr(".audioProcessing", "waveToText")(*args, **kwargs)


def extractPrompt(*args, **kwargs):
    return _load_attr(".audioProcessing", "extractPrompt")(*args, **kwargs)


def buildMealPlan(*args, **kwargs):
    return _load_attr(".buildMealPlan", "buildMealPlan")(*args, **kwargs)


def askForMeal(*args, **kwargs):
    return _load_attr(".buildMealPlan", "askForMeal")(*args, **kwargs)


def changeMealSuggestion(*args, **kwargs):
    return _load_attr(".buildMealPlan", "changeMealSuggestion")(*args, **kwargs)


def setUserMealPlanPref(*args, **kwargs):
    return _load_attr(".buildMealPlan", "setUserMealPlanPref")(*args, **kwargs)


def handle_audio(*args, **kwargs):
    return _load_attr(".orchestrator", "handle_audio")(*args, **kwargs)


def process_user_prompt(*args, **kwargs):
    return _load_attr(".orchestrator", "process_user_prompt")(*args, **kwargs)


def run(*args, **kwargs):
    return _load_attr(".orchestrator", "run")(*args, **kwargs)


def run_gui(*args, **kwargs):
    return _load_attr(".gui", "run")(*args, **kwargs)
