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
    level=logging.INFO,  # Cambia a DEBUG per più dettagli
    handlers=[
        logging.FileHandler("atlas.log"),  # Salva i log in un file
        logging.StreamHandler()  # Mostra i log in console
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
    print(f'Vision: {response.text}')
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

startListening()

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