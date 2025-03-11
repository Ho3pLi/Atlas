import json
from dotenv import load_dotenv
import os
from groq import Groq
import speech_recognition as sr
import time
from PIL import ImageGrab, Image
from openai import OpenAI
import google.generativeai as genai
from datetime import datetime, timedelta
import pyaudio
from faster_whisper import WhisperModel
import re
import logging
import difflib
import requests

# Configurazione logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("atlas.log"),
        logging.StreamHandler()
    ]
)

logging.info("Starting Atlas Assistant...")

load_dotenv()

groqApiKey = os.getenv('groqApiKey')
googleApiKey = os.getenv('googleApiKey')
openaiApiKey = os.getenv('openaiApiKey')
openWeatherApiKey = os.getenv('openWeatherApiKey')

wakeWord = 'atlas'

groqClient = Groq(api_key=groqApiKey)
genai.configure(api_key=googleApiKey)
openai = OpenAI(api_key=openaiApiKey)

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

enableTTS = False

allowedDirs = [os.path.expanduser('~/Documents'), os.path.expanduser('~/Desktop')]
lastFoundFilePath = None

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

def groqPrompt(prompt, imgContext, filePath, weatherData):
    if imgContext and prompt:
        prompt = f'USER PROMPT: {prompt}\n\n    IMAGE CONTEXT: {imgContext}'
    elif filePath and prompt:
        prompt = f'USER PROMPT: {prompt}\n\n    PATH CONTEXT: {filePath}'
    elif weatherData and prompt:
        prompt = f'USER PROMPT: {prompt}\n\n    WEATHER CONTEXT: {weatherData}'

    model = 'llama-3.1-8b-instant' if len(prompt) < 50 else 'llama-3.3-70b-versatile'
    logging.info(f"[Groq] Sending request - Model: {model} | Prompt: {prompt}")

    convo.append({'role':'user', 'content':prompt})
    chatCompletion = groqClient.chat.completions.create(messages=convo, model=model)
    response = chatCompletion.choices[0].message
    convo.append(response)

    # logging.info(f"[Groq] Response received: {response.content[:100]}...")  # Mostriamo solo i primi 100 caratteri
    logging.info(f"[Groq] Response received: {response.content}")

    return response.content

def functionCall(prompt):
    logging.info(f"Does the prompt need special functions?: {prompt}")

    sysMsg = (
        'You are an AI function calling model. You will determine whether search for weather, '
        'taking a screenshot, search for a file or calling no functions is best for a voice assistant to respond '
        'to the users prompt. The webcam can be assumed to be a normal laptop webcam facing the user. You will '
        'respond with only one selection from this list: ["get weather", "take screenshot", "search file", "None"]'
    )

    functionConvo = [{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}]
    chatCompletion = groqClient.chat.completions.create(messages=functionConvo, model='llama-3.3-70b-versatile')
    response = chatCompletion.choices[0].message

    logging.info(f"Chosen function: {response.content}")

    return response.content

def takeScreenshot():
    path = f'screenshot.png'
    logging.info(f"Taking a screenshot in {path}...")
    screenshot = ImageGrab.grab()
    rgbScreenshot = screenshot.convert('RGB')
    rgbScreenshot.save(path, quality=15)
    logging.info("Screenshot successfully saved.")

def extractFileInfo(prompt):
    sysMsg = (
        'You are a model that precisely extracts information from user requests. '
        'You will receive a sentence in which the user asks to search for a file on the PC. '
        'You must identify and return ONLY the exact filename and its extension (only if explicitly stated). '
        'ATTENTION: Do NOT invent or infer extensions not explicitly stated by the user. '
        'If the user does NOT clearly mention an extension, return "NONE". '
        'Examples:\n'
        '- "Find the pdf of the thesis" -> {"filename":"thesis","extension":".pdf"}\n'
        '- "Look for the file pippo.docx" -> {"filename":"pippo","extension":".docx"}\n'
        '- "Find pippo" -> {"filename":"pippo","extension":"NONE"}\n'
        '- "Search for the file balance" -> {"filename":"balance","extension":"NONE"}\n'
        'ALWAYS respond in this exact JSON format: {"filename":"filename", "extension":".ext"} or {"filename":"filename", "extension":"NONE"}'
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model='llama-3.1-8b-instant'  
    )
    response = chatCompletion.choices[0].message.content
    return json.loads(response)

def extractSemanticKeywords(prompt):
    sysMsg = (
        "You are a semantic keyword extractor. "
        "Given a user prompt, generate a short list (5-10) of related keywords that might match filenames "
        "on a user's computer. Return only a JSON array of keywords."
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model='llama-3.1-8b-instant'
    )

    response = chatCompletion.choices[0].message.content
    return json.loads(response)

def exactSearch(filename, extension, allowedDirs=allowedDirs):
    results = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                name, ext = os.path.splitext(file)
                if extension != "NONE":
                    if name.lower() == filename.lower() and ext.lower() == extension.lower():
                        results.append(os.path.join(root, file))
                else:
                    if name.lower() == filename.lower():
                        results.append(os.path.join(root, file))
    logging.info(f'exactSearch res: {results}')
    return results

def fuzzySearch(filename, allowedDirs=allowedDirs, cutoff=0.8):
    results = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            file_names = [os.path.splitext(f)[0] for f in files]
            close_matches = difflib.get_close_matches(filename.lower(), file_names, n=10, cutoff=cutoff)

            for match in close_matches:
                for file in files:
                    if match == os.path.splitext(file)[0].lower():
                        results.append(os.path.join(root, file))

    logging.info(f'fuzzySearch res: {results}')
    return results

def semanticSearch(keywords, allowedDirs=allowedDirs):
    matches = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                if any(kw.lower() in file.lower() for kw in keywords):
                    matches.append(os.path.join(root, file))

    logging.info(f'semanticSearch: {matches}')
    return matches

def handleFileSearchPrompt(prompt):
    info = extractFileInfo(prompt)
    filename, extension = info["filename"], info["extension"]

    all_results = set()

    exact_results = exactSearch(filename, extension, allowedDirs)
    all_results.update(exact_results)

    if len(all_results) < 5:
        fuzzy_results = fuzzySearch(filename, allowedDirs)
        all_results.update(fuzzy_results)

    if len(all_results) < 5:
        semantic_keywords = extractSemanticKeywords(prompt)
        semantic_results = semanticSearch(semantic_keywords, allowedDirs)
        all_results.update(semantic_results)

    if not all_results:
        response = "I'm sorry, I couldn't find any files matching your request."
    elif len(all_results) == 1:
        path = list(all_results)[0]
        response = f"I've found the requested file:\n {path}"
    else:
        response = "I've found multiple files possibly matching your request:\n"
        for idx, file in enumerate(all_results, start=1):
            response += f"{idx}. {file}\n"
        response += "Please specify which one you want."

    print(f"Assistant Response: {response}")
    return response

def getWeather(city, lang="it", units="metric", date='today'):
    baseUrl = "http://api.openweathermap.org/data/2.5/"
    # url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={openWeatherApiKey}&lang={lang}&units={units}"
    # response = requests.get(url)
    
    # if response.status_code == 200:
    #     weather_data = response.json()
        
    #     description = weather_data["weather"][0]["description"]
    #     temp = weather_data["main"]["temp"]
    #     feels_like = weather_data["main"]["feels_like"]
    #     humidity = weather_data["main"]["humidity"]

    #     result = (f"Current weather in {city}:\n"
    #               f"- Weather: {description}\n"
    #               f"- Temperature: {temp}°C (Feel like: {feels_like}°C)\n"
    #               f"- Umidity: {humidity}%")
    #     return result
    # else:
    #     return f"Can't find data for {city}."
    
    if date == 'today':
        url = f"{baseUrl}weather?q={city}&appid={openWeatherApiKey}&units={units}&lang={lang}"
        response = requests.get(url).json()
        
        if response.get('cod') != 200:
            return "I'm sorry, I couldn't retrieve today's weather."
        
        weather_desc = response['weather'][0]['description']
        temp = response['main']['temp']
        return f"Today's weather in {city}: {weather_desc}, temperature {temp}°C."
    else:
        url = f"{baseUrl}forecast?q={city}&appid={openWeatherApiKey}&units={units}&lang={lang}"
        response = requests.get(url).json()

        if response.get('cod') != "200":
            return "I'm sorry, I couldn't retrieve the forecast."

        if date == 'tomorrow':
            target_date = (datetime.now() + timedelta(days=1)).date()
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d').date() #FIXME - weekday to fix

        forecasts = response['list']
        target_forecasts = [f for f in forecasts if datetime.fromtimestamp(f['dt']).date() == target_date]

        if not target_forecasts:
            return f"I'm sorry, I couldn't find weather information for {date}."

        # Media delle temperature della giornata
        avg_temp = sum([f['main']['temp'] for f in target_forecasts]) / len(target_forecasts)
        weather_desc = target_forecasts[0]['weather'][0]['description']

        formatted_date = target_date.strftime("%Y-%m-%d")
        return f"Weather in {city} on {formatted_date}: {weather_desc}, average temperature {avg_temp:.1f}°C."
    
def extractWeatherInfo(prompt):
    sysMsg = (
        "You are a model that extracts ONLY the city name and the requested date from a user's weather-related request.\n"
        "If the user mentions 'tomorrow', return 'tomorrow'. If a specific date is given, return it in YYYY-MM-DD format.\n"
        "If a weekday is given, return the date of the closest weekday matching the request in YYYY-MM-DD format.\n"
        "If no date is mentioned, return 'today'.\n"
        "Examples:\n"
        "- 'What's the weather like in Rome tomorrow?' -> {\"city\":\"Rome\",\"date\":\"tomorrow\"}\n"
        "- 'Weather in Paris on 2024-03-12' -> {\"city\":\"Paris\",\"date\":\"2024-03-12\"}\n"
        "- 'Weather in Milan' -> {\"city\":\"Milan\",\"date\":\"today\"}\n"
        "Always respond with JSON format: {\"city\":\"city_name\",\"date\":\"YYYY-MM-DD/tomorrow/today\"}"
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model='llama-3.1-8b-instant'
    )

    response = chatCompletion.choices[0].message.content
    logging.info(f'{response}')
    return json.loads(response)

def handleWeatherPrompt(prompt):
    info = extractWeatherInfo(prompt)
    city = info['city']
    date = info['date']
    logging.info(f"Weather requested for: City={city}, Date={date}")

    weatherReport = getWeather(city=city, date=date)
    logging.info(f'Weather report: {weatherReport}')
    return weatherReport

def visionPrompt(prompt, photoPath):
    img = Image.open(photoPath)
    prompt = (
        'You are the vision analysis AI that provides semtantic meaning from images to provide context '
        'to send to another AI that will create a response to the user. Do not respond as the AI assistant '
        'to the user. Instead take the user prompt input and try to extract meaning from the photo '
        'relevant to the user prompt. Then generate as much objective data about the image for the AI '
        f'assistant who will respond to the user. \nUSER PROMPT: {prompt}'
    )
    response = model.generate_content([prompt, img])
    return response.text

def speak(text):
    logging.info("Generating audio with OpenAI TTS...")
    playerStream = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)
    streamStart = False

    with openai.audio.speech.with_streaming_response.create(
        model='tts-1',
        voice='fable',
        response_format='pcm',
        input=text
    ) as response:
        silenceThreshold = 0.01
        for chunk in response.iter_bytes(chunk_size=1024):
            if streamStart:
                playerStream.write(chunk)
            else:
                if max(chunk) > silenceThreshold:
                    playerStream.write(chunk)
                    streamStart = True
    logging.info("Audio successfully used.")

def waveToText(audioPath):
    logging.info(f"Transcribing audio: {audioPath}")
    segments, _ = whisperModel.transcribe(audioPath, language='it')
    text = ' '.join([segment.text for segment in segments])

    logging.info(f"Transcribed text: {text}")
    return text

def callback(audio):
    logging.info("Audio received, thinking...")
    
    promptAudioPath = 'prompt.wav'
    with open(promptAudioPath, 'wb') as f:
        f.write(audio.get_wav_data())

    promptText = waveToText(promptAudioPath)
    cleanPrompt = extractPrompt(promptText, wakeWord)

    if not cleanPrompt:
        logging.warning("No prompt detected, try again.")
        return

    logging.info(f"Prompt detected: {cleanPrompt}")

    call = functionCall(cleanPrompt)
    visualContext = None
    filePath = None
    weatherData = None

    if 'take screenshot' in call:
        takeScreenshot()
        visualContext = visionPrompt(cleanPrompt, 'screenshot.png')
    elif 'search file' in call:
        filePath = handleFileSearchPrompt(cleanPrompt)
    elif 'get weather' in call:
        weatherData = handleWeatherPrompt(cleanPrompt)

    response = groqPrompt(cleanPrompt, visualContext, filePath, weatherData)
    logging.info(f"Assistant response: {response}")

    if enableTTS:
        speak(response)

def startListening():
    with mic as m:
        r.adjust_for_ambient_noise(m, duration=2)
        logging.info(f"Starting up the Assistnat. Say '{wakeWord}' followed by your prompt.")

    stopListening = r.listen_in_background(mic, callback)

    try:
        while True:
            time.sleep(.5)
    except KeyboardInterrupt:
        stopListening(False)
        logging.info("Assistant killed :(")

def extractPrompt(transcribedText, wakeWord):
    logging.info(f"Extracting prompt from phrase: {transcribedText}")

    pattern = rf'\b{re.escape(wakeWord)}[\s,.?!]*([A-Za-z0-9].*)'
    match = re.search(pattern, transcribedText, re.IGNORECASE)

    if match:
        logging.info(f"Prompt extracted: {match.group(1).strip()}")
        return match.group(1).strip()
    else:
        logging.warning("No prompt found in the phrase.")
        return None

# print(handleFileSearchPrompt("Atlas, trova il file tesi"))

# startListening()

# waveToText('prompt.wav')

while True:
    prompt = input('USER: ')
    call = functionCall(prompt)
    visualContext = None
    filePath = None
    weatherData = None

    if 'take screenshot' in call:
        takeScreenshot()
        visualContext = visionPrompt(prompt, 'screenshot.png')
    elif 'search file' in call:
        filePath = handleFileSearchPrompt(prompt)
    elif 'get weather' in call:
        weatherData = handleWeatherPrompt(prompt)

    response = groqPrompt(prompt, visualContext, filePath, weatherData)

    if enableTTS:
        speak(response)