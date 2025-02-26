# import openai

# openai.api_key = ''

# try:
#     response = openai.audio.speech.create(
#         model="tts-1",
#         voice="alloy",
#         input="Ciao, questo è un test del Text-to-Speech di OpenAI.",
#     )

#     with open("output_audio.mp3", "wb") as audio_file:
#         audio_file.write(response.content)

#     print("✅ Audio generato con successo e salvato come 'output_audio.mp3'.")
# except Exception as e:
#     print(f"Errore durante la generazione dell'audio: {e}")

# from dotenv import load_dotenv
# import os
# from groq import Groq
from PIL import ImageGrab
from datetime import date

# load_dotenv()

# groqApiKey = os.getenv('groqApiKey')

# groqClient = Groq(api_key=groqApiKey)

# def groqPrompt(prompt):
#     convo = [{'role': 'user', 'content': prompt}]
#     chatCompletion = groqClient.chat.completions.create(messages=convo, model='llama-3.3-70b-versatile')
#     response = chatCompletion.choices[0].message
#     return response.content

# def functionCall(prompt):
#     sysMsg = (
#         'You are an AI function calling model. You will determine whether extracting the users clipboard content, '
#         'taking a screenshot, capturing the webcam or calling no functions is best for a voice assistant to respond '
#         'to the users prompt. The webcam can be assumed to be a normal laptop webcam facing the user. You will '
#         'respond with only one selection from this list: ["extract clipboard", "take screenshot", "capture webcam", "None"] \n'
#         'Do not respond with anything but the most logical selection from that list with no explanations. Format the '
#         'function call name exactly as I listed. '
#     )
#     functionConvo = [{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}]
#     chatCompletion = groqClient.chat.completions.create(messages=functionConvo, model='llama-3.3-70b-versatile')
#     response = chatCompletion.choices[0].message
    # return response.content

def takeScreenshot():
    path = 'screenshot_'+date.today().strftime("%d_%m_%Y")+'.png'
    screenshot = ImageGrab.grab()
    rgbScreenshot = screenshot.convert('RGB')
    rgbScreenshot.save(path, quality=15)

takeScreenshot()
# prompt = input("Inserisci il prompt: ")
# functionCallVar = functionCall(prompt)
# print(functionCallVar)
# response = groqPrompt(prompt)
# print(response)