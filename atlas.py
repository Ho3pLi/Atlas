from dotenv import load_dotenv
import os
from groq import Groq
from PIL import ImageGrab, Image
import google.generativeai as genai
from datetime import date

load_dotenv()

groqApiKey = os.getenv('groqApiKey')
googleApiKey = os.getenv('googleApiKey')

groqClient = Groq(api_key=groqApiKey)
genai.configure(api_key=googleApiKey)

sysMsg = (
    'You are a multi—modal AI voice assistant. Your name is Atlas. Your user may or may not have attached a photo for context '
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

def groqPrompt(prompt, imgContext):
    if imgContext:
        prompt = f'USER PROMPT: {prompt}\n\n    IMAGE CONTEXT: {imgContext}'
    convo.append({'role':'user', 'content':prompt})
    chatCompletion = groqClient.chat.completions.create(messages=convo, model='llama-3.3-70b-versatile')
    # if not chatCompletion.choices:
    #     if hasattr(chatCompletion, "prompt_feedback"):
    #         print("Prompt Feedback:", chatCompletion.prompt_feedback)
    response = chatCompletion.choices[0].message
    convo.append(response)
    return response.content

def functionCall(prompt):
    sysMsg = (
        'You are an AI function calling model. You will determine whether extracting the users clipboard content, '
        'taking a screenshot, capturing the webcam or calling no functions is best for a voice assistant to respond '
        'to the users prompt. The webcam can be assumed to be a normal laptop webcam facing the user. You will '
        'respond with only one selection from this list: ["extract clipboard", "take screenshot", "capture webcam", "None"] \n'
        'Do not respond with anything but the most logical selection from that list with no explanations. Format the '
        'function call name exactly as I listed. '
    )
    functionConvo = [{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}]
    chatCompletion = groqClient.chat.completions.create(messages=functionConvo, model='llama-3.3-70b-versatile')
    response = chatCompletion.choices[0].message
    return response.content

def takeScreenshot():
    path = f'screenshot_{date.today().strftime("%d_%m_%Y")}.png'
    screenshot = ImageGrab.grab()
    rgbScreenshot = screenshot.convert('RGB')
    rgbScreenshot.save(path, quality=15)

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

while True:
    prompt = input('USER: ')
    call = functionCall(prompt)

    if 'take screenshot' in call:
        takeScreenshot()
        visualContext = visionPrompt(prompt, f'screenshot_{date.today().strftime("%d_%m_%Y")}.png')
    else:
        visualContext = None

    response = groqPrompt(prompt, visualContext)
    print(f'Atlas: {response}')