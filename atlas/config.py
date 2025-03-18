import os
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq
import google.generativeai as genai
import speech_recognition as sr
from faster_whisper import WhisperModel

load_dotenv()

groqApiKey = os.getenv('groqApiKey')
googleApiKey = os.getenv('googleApiKey')
openaiApiKey = os.getenv('openaiApiKey')
weatherApiKey = os.getenv('openWeatherApiKey')
porcupineApiKey = os.getenv('porcupineApiKey')
narakeetApiKey = os.getenv('narakeetApiKey')

wakeWordModel = 'atlas/models/atlas.ppn'
porcupineModelPath = 'atlas/models/porcupine_params_it.pv'
screenshotPath = 'temp/screenshot.png'
promptPath = 'temp/prompt.wav'
logPath = 'log/atlas.log'

groqClient = Groq(api_key=groqApiKey)
genai.configure(api_key=googleApiKey)
openai = OpenAI(api_key=openaiApiKey)

groqModel = 'llama-3.1-8b-instant'
groqModel2 = 'llama-3.3-70b-versatile'

enableTTS = False
allowedDirs = [os.path.expanduser('~/Documents/AtlasDir')]

sysMsg = (
    'You are a multi—modal AI voice assistant. Your name is Atlas. You speak italian. Your user may or may not have attached a photo for context '
    '(either a screenshot or a webcam capture). Any photo has already been processed into a highly detailed '
    'text prompt that witl be attached to their transcribed voice prompt. Generate the most useful and '
    'factual response possible, carefully considering all previous generated text in your response before '
    'adding new tokens to the response. Do not expect or request images, just use the context if added. '
    'Use all of the context of this conversation so your response is relevant to the conversation. Make '
    'your responses clear and concise, avoiding any verbosity.'
)

convo = [{'role':'system', 'content':sysMsg}]

generationConfig = {
    'temperature':0.7,
    'top_p':1,
    'top_k':1,
    'max_output_tokens':2048}
safetySettings = [
    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
]

model = genai.GenerativeModel('gemini-2.0-flash', safety_settings=safetySettings, generation_config=generationConfig)

lastFileSearchResults = []

coresCount = os.cpu_count()
whisperSize = 'medium'
whisperModel = WhisperModel(
    whisperSize,
    device='cpu',
    compute_type='int8',
    cpu_threads=coresCount//2,
    num_workers=coresCount//2
)

r = sr.Recognizer()
mic = sr.Microphone()