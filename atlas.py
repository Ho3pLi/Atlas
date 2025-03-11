import json
from dotenv import load_dotenv
import os
from groq import Groq
import speech_recognition as sr
import time
from PIL import ImageGrab, Image
from openai import OpenAI
import google.generativeai as genai
from datetime import date
import pyaudio
from faster_whisper import WhisperModel
import re
import logging

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

enableTTS = True

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

def groqPrompt(prompt, imgContext):
    if imgContext and prompt:
        prompt = f'USER PROMPT: {prompt}\n\n    IMAGE CONTEXT: {imgContext}'

    model = 'llama-3.1-8b-instant' if len(prompt) < 50 else 'llama-3.3-70b-versatile'
    logging.info(f"[Groq] Sending request - Model: {model} | Prompt: {prompt}")

    convo.append({'role':'user', 'content':prompt})
    chatCompletion = groqClient.chat.completions.create(messages=convo, model=model)
    response = chatCompletion.choices[0].message
    convo.append(response)

    logging.info(f"[Groq] Response received: {response.content[:100]}...")  # Mostriamo solo i primi 100 caratteri

    return response.content

def functionCall(prompt):
    logging.info(f"Does the prompt need special functions?: {prompt}")

    sysMsg = (
        'You are an AI function calling model. You will determine whether extracting the users clipboard content, '
        'taking a screenshot, capturing the webcam or calling no functions is best for a voice assistant to respond '
        'to the users prompt. The webcam can be assumed to be a normal laptop webcam facing the user. You will '
        'respond with only one selection from this list: ["extract clipboard", "take screenshot", "capture webcam", "None"]'
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

def searchFile(filename, extension=None, allowedDirs=allowedDirs):
    found_files = []

    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                file_name, file_ext = os.path.splitext(file)

                if extension:
                    if file_name.lower() == filename.lower() and file_ext.lower() == extension.lower():
                        return os.path.join(root, file)
                else:
                    if file_name.lower() == filename.lower():
                        found_files.append(os.path.join(root, file))

    if not found_files:
        return None
    elif len(found_files) == 1:
        return found_files[0]
    else:
        return found_files

def handleFileSearchPrompt(prompt):
    info = extractFileInfo(prompt)

    extension = None if info["extension"] == "NONE" else info["extension"]

    logging.info(f"Extracted file info: filename = {info['filename']}, extension = {extension}")

    paths = searchFile(info["filename"], extension=extension)

    if not paths:
        response = "I'm sorry, I couldn't find the requested file."
    elif isinstance(paths, list):
        response = "I've found multiple files:\n"
        for idx, file in enumerate(paths, start=1):
            response += f"{idx}. {file}\n"
        response += "Please specify which one you want."
    else:
        response = f"I've found the requested file: {paths}"

    return response

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

def callback(recognizer, audio):
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

    if 'take screenshot' in call:
        takeScreenshot()
        visualContext = visionPrompt(cleanPrompt, 'screenshot.png')

    response = groqPrompt(cleanPrompt, visualContext)
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

print(handleFileSearchPrompt("Atlas, trova il file dell'universita"))

# startListening()

# waveToText('prompt.wav')

# while True:
#     prompt = input('USER: ')
#     call = functionCall(prompt)

#     if 'take screenshot' in call:
#         takeScreenshot()
#         visualContext = visionPrompt(prompt, f'screenshot.png')
#     else:
#         visualContext = None

#     response = groqPrompt(prompt, visualContext)
#     print(f'Atlas: {response}')
#     speak(response) # ENABLE ONLY FOR PRODUCTION TO REDUCE COSTS