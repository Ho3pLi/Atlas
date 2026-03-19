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

HEURISTIC_RULES = [
    ("get_weather", ("meteo", "tempo", "piove", "piovera", "temperature", "temperatura", "weather")),
    ("take_screenshot", ("screenshot", "schermata", "schermo", "screen")),
    ("search_file", ("file", "documento", "pdf", "docx", "cartella", "trova", "cerca")),
    ("build_meal_plan", ("pasto", "pasti", "meal plan", "menu", "colazione", "pranzo", "cena", "spuntino")),
    ("change_meal_suggestion", ("cambia pasto", "cambia menu", "altra cena", "altro pranzo", "modifica pasto")),
]

LOW_CONFIDENCE_THRESHOLD = 0.55


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

    heuristic_intent = _route_with_heuristics(prompt)
    if heuristic_intent is not None:
        logging.info(f"Chosen action via heuristics: {heuristic_intent}")
        return heuristic_intent

    llm_intent = _route_with_llm(prompt)
    validated_intent = _validate_intent(llm_intent)
    logging.info(f"Chosen action via LLM: {validated_intent}")
    return validated_intent


def _route_with_heuristics(prompt):
    lowered_prompt = prompt.lower()
    scores = {}

    for action, keywords in HEURISTIC_RULES:
        score = sum(1 for keyword in keywords if keyword in lowered_prompt)
        if score:
            scores[action] = score

    if not scores:
        return None

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_action, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score == second_score:
        return {
            "action": "none",
            "confidence": 0.4,
            "needs_clarification": True,
            "reason": "ambiguous_heuristic_match",
            "source": "heuristic",
        }

    confidence = min(0.95, 0.6 + 0.1 * best_score)
    return {
        "action": best_action,
        "confidence": round(confidence, 2),
        "needs_clarification": False,
        "reason": "heuristic_match",
        "source": "heuristic",
    }


def _route_with_llm(prompt):
    sys_msg = (
        "You are an intent router for a voice assistant. "
        "Choose exactly one action for the user's request.\n"
        "Valid actions: none, get_weather, take_screenshot, search_file, build_meal_plan, change_meal_suggestion.\n"
        "Return ONLY valid JSON in this format: "
        '{"action":"one_of_the_valid_actions","confidence":0.0,"needs_clarification":false,"reason":"short_reason"}\n'
        "confidence must be a number between 0 and 1."
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
        return {
            "action": "none",
            "confidence": 0.0,
            "needs_clarification": True,
            "reason": "invalid_json",
            "source": "llm",
        }

    parsed["source"] = "llm"
    return parsed


def _validate_intent(intent):
    action = intent.get("action", "none")
    if action not in VALID_ACTIONS:
        logging.warning(f"Router returned invalid action '{action}'. Falling back to none.")
        action = "none"

    confidence = _normalize_confidence(intent.get("confidence", 0.0))
    needs_clarification = bool(intent.get("needs_clarification", False))
    reason = str(intent.get("reason", ""))
    source = intent.get("source", "unknown")

    if confidence < LOW_CONFIDENCE_THRESHOLD and action != "none":
        needs_clarification = True

    if needs_clarification and action != "none" and confidence < LOW_CONFIDENCE_THRESHOLD:
        action = "none"

    return {
        "action": action,
        "confidence": confidence,
        "needs_clarification": needs_clarification,
        "reason": reason,
        "source": source,
    }


def _normalize_confidence(value):
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, round(confidence, 2)))
