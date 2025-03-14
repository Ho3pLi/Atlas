import os
from dotenv import load_dotenv

load_dotenv()

groqApiKey = os.getenv('groqApiKey')
googleApiKey = os.getenv('googleApiKey')
openaiApiKey = os.getenv('openaiApiKey')
weatherApiKey = os.getenv('openWeatherApiKey')
porcupineApiKey = os.getenv('porcupineApiKey')
narakeetApiKey = os.getenv('narakeetApiKey')

wakeWordModel = 'models/atlas.ppn'
porcupineModelPath = 'models/porcupine_params_it.pv'

enableTTS = False
allowedDirs = [os.path.expanduser('~/Documents/AtlasDir')]
