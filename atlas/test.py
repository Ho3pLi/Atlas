# import atlas.atlas as atlas

# atlas.enableTTS = True

# while True:
#     prompt = input('USER: ')
#     if atlas.lastFileSearchResults:
#         chosen_file = atlas.handleFileChoice(prompt, atlas.lastFileSearchResults)
#         if chosen_file:
#             response = f"You selected the file:\n{chosen_file}"
#             atlas.lastFileSearchResults = []
#         else:
#             response = "I'm sorry, I didn't understand your choice. Please repeat."
#     else:
#         call = atlas.functionCall(prompt)
#         visualContext = None
#         filePath = None
#         weatherData = None

#         if 'take screenshot' in call:
#             atlas.takeScreenshot()
#             visualContext = atlas.visionPrompt(prompt, 'screenshot.png')
#         elif 'search file' in call:
#             filePath = atlas.handleFileSearchPrompt(prompt)
#         elif 'get weather' in call:
#             weatherData = atlas.handleWeatherPrompt(prompt)

#         response = atlas.groqPrompt(prompt, visualContext, filePath, weatherData)

#     if atlas.enableTTS:
#         atlas.speak(response)
import os
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq
import google.generativeai as genai
import speech_recognition as sr
from faster_whisper import WhisperModel

load_dotenv()

print(os.getenv('groqApiKey'))

groqApiKey = os.getenv('groqApiKey')
googleApiKey = os.getenv('googleApiKey')
openaiApiKey = os.getenv('openaiApiKey')
weatherApiKey = os.getenv('openWeatherApiKey')
porcupineApiKey = os.getenv('porcupineApiKey')
narakeetApiKey = os.getenv('narakeetApiKey')

wakeWordModel = 'models/atlas.ppn'
porcupineModelPath = 'models/porcupine_params_it.pv'

groqClient = Groq(api_key=groqApiKey)
genai.configure(api_key=googleApiKey)
openai = OpenAI(api_key=openaiApiKey)
