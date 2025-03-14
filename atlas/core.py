import logging
from groq import Groq

from atlas.config import groqClient, convo

def groqPrompt(prompt, imgContext=None, filePath=None, weatherData=None):
    if imgContext:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nIMAGE CONTEXT: {imgContext}\n'
    elif filePath:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nPATH CONTEXT: {filePath}\n'
    elif weatherData:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nWEATHER CONTEXT: {weatherData}\n'

    model = 'llama-3.1-8b-instant' if len(prompt) < 50 else 'llama-3.3-70b-versatile'
    logging.info(f"[Groq] Sending request - Model: {model} | Prompt: {prompt}")

    convo.append({'role':'user', 'content':prompt})
    chatCompletion = groqClient.chat.completions.create(messages=convo, model=model)
    response = chatCompletion.choices[0].message
    convo.append(response)

    logging.info(f"[Groq] Response received: {response.content}")
    return response.content

def functionCall(prompt):
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