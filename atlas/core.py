import json
import logging

import atlas.config as config

VALID_ACTIONS = {
    "none",
    "get_weather",
    "take_screenshot",
    "search_file",
    "build_meal_plan",
    "change_meal_suggestion",
}


def groqPrompt(prompt, imgContext=None, filePath=None, weatherData=None, mealSuggestion=None):
    if imgContext:
        prompt = f"\n\nUSER PROMPT: {prompt}\n\nIMAGE CONTEXT: {imgContext}\n"
    elif filePath:
        prompt = f"\n\nUSER PROMPT: {prompt}\n\nPATH CONTEXT: {filePath}\n"
    elif weatherData:
        weather_context = weatherData.get("context") if isinstance(weatherData, dict) else weatherData
        prompt = f"\n\nUSER PROMPT: {prompt}\n\nWEATHER CONTEXT: {weather_context}\n"
    elif mealSuggestion:
        prompt = (
            f"\n\nUSER PROMPT: {prompt}\n\nMEALS YOU HAVE TO SUGGEST AS YOU HAD THOUGHT OF THEM: "
            f"{mealSuggestion}\n\nIN THE END ASK THE USER IF THEY WANT TO CHANGE THEM\n"
        )

    model = config.app.groq_model if len(prompt) < 50 else config.app.groq_model2
    logging.info(f"[Groq] Sending request - Model: {model} | Prompt: {prompt}")

    config.session.conversation.append({"role": "user", "content": prompt})
    chat_completion = config.get_groq_client().chat.completions.create(
        messages=config.session.conversation,
        model=model,
    )
    response = chat_completion.choices[0].message
    config.session.conversation.append({"role": response.role, "content": response.content})

    logging.info(f"[Groq] Response received: {response.content}")
    return response.content


def functionCall(prompt):
    logging.info("Entering functionCall() function...")
    sys_msg = (
        "You are an intent router for a voice assistant. "
        "Choose exactly one action for the user's request.\n"
        "Valid actions: none, get_weather, take_screenshot, search_file, build_meal_plan, change_meal_suggestion.\n"
        "Return ONLY valid JSON in this format: "
        '{"action":"one_of_the_valid_actions","reason":"short_reason"}'
    )

    function_convo = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
    chat_completion = config.get_groq_client().chat.completions.create(
        messages=function_convo,
        model=config.app.groq_model2,
    )
    response = chat_completion.choices[0].message.content.strip()
    logging.info(f"Raw routed action: {response}")

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        logging.warning("Router returned invalid JSON. Falling back to none.")
        return {"action": "none", "reason": "invalid_json"}

    action = parsed.get("action", "none")
    if action not in VALID_ACTIONS:
        logging.warning(f"Router returned invalid action '{action}'. Falling back to none.")
        action = "none"

    result = {
        "action": action,
        "reason": parsed.get("reason", ""),
    }
    logging.info(f"Chosen action: {result}")
    return result
