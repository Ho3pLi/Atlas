import logging

import atlas.config as config

def groqPrompt(prompt, imgContext=None, filePath=None, weatherData=None, mealSuggestion=None):
    if imgContext:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nIMAGE CONTEXT: {imgContext}\n'
    elif filePath:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nPATH CONTEXT: {filePath}\n'
    elif weatherData:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nWEATHER CONTEXT: {weatherData}\n'
    elif mealSuggestion:
        prompt = f'\n\nUSER PROMPT: {prompt}\n\nMEALS YOU HAVE TO SUGGEST AS YOU HAD THOUGHT OF THEM: {mealSuggestion}\n\nIN THE END ASK THE USER IF THEY WANT TO CHANGE THEM\n'

    model =  config.groqModel if len(prompt) < 50 else config.groqModel2
    logging.info(f"[Groq] Sending request - Model: {model} | Prompt: {prompt}")

    config.convo.append({'role':'user', 'content':prompt})
    chatCompletion = config.groqClient.chat.completions.create(messages=config.convo, model=model)
    response = chatCompletion.choices[0].message
    config.convo.append(response)

    logging.info(f"[Groq] Response received: {response.content}")
    return response.content

def functionCall(prompt):
    logging.info('Entering functionCall() function...')
    sysMsg = (
        'You are an AI function calling model. You will determine whether search for weather, '
        'taking a screenshot, search for a file, build a meal plan, change a meal suggestion or calling no functions is best for a voice assistant to respond '
        'to the users prompt. The webcam can be assumed to be a normal laptop webcam facing the user. You will '
        'respond with only one selection from this list: ["get weather", "take screenshot", "search file", "build meal plan", "change meal suggestion "None"]'
    )

    functionConvo = [{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}]
    chatCompletion = config.groqClient.chat.completions.create(messages=functionConvo, model=config.groqModel2)
    response = chatCompletion.choices[0].message

    logging.info(f"Chosen function: {response.content}")

    return response.content