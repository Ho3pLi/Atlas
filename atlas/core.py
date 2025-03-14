import logging
from atlas.config import groqApiKey
from atlas.main import convo
from groq import Groq

groqClient = Groq(api_key=groqApiKey)

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