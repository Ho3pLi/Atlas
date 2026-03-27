import json
import logging
import re
import unicodedata

import atlas.config as config

VALID_ACTIONS = {
    "none",
    "get_date",
    "get_weather",
    "take_screenshot",
    "search_file",
    "open_app",
    "close_app",
    "build_meal_plan",
    "change_meal_suggestion",
}

HEURISTIC_RULES = [
    (
        "none",
        (
            "ciao",
            "salve",
            "buongiorno",
            "buonasera",
            "come va",
            "come stai",
            "hey",
            "hi",
            "hello",
            "chi sei",
            "cosa sai fare",
            "cosa puoi fare",
            "dimmi qualcosa su di te",
            "parlami di te",
        ),
    ),
    ("get_date", ("che giorno", "che data", "data di oggi", "giorno di oggi", "oggi che giorno", "oggi che data")),
    ("get_weather", ("meteo", "tempo", "piove", "piovera", "temperature", "temperatura", "weather")),
    ("take_screenshot", ("screenshot", "schermata", "schermo", "screen")),
    ("search_file", ("file", "documento", "pdf", "docx", "cartella", "trova", "cerca")),
    ("open_app", ("apri programma", "apri app", "avvia", "lancia", "esegui")),
    ("close_app", ("chiudi", "termina", "stoppa")),
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
    _trim_conversation_if_needed()
    chat_completion = config.get_groq_client().chat.completions.create(
        messages=_build_conversation_messages(),
        model=model,
    )
    response = chat_completion.choices[0].message
    config.session.conversation.append({"role": response.role, "content": response.content})
    _trim_conversation_if_needed()

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
    date_intent = _detect_date_intent(prompt)
    if date_intent is not None:
        return date_intent

    open_app_intent = _detect_open_app_intent(prompt)
    if open_app_intent is not None:
        return open_app_intent

    close_app_intent = _detect_close_app_intent(prompt)
    if close_app_intent is not None:
        return close_app_intent

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

    if best_action == "none":
        return {
            "action": "none",
            "confidence": 0.75,
            "needs_clarification": False,
            "reason": "small_talk",
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


def _detect_open_app_intent(prompt):
    lowered_prompt = (prompt or "").strip().lower()
    if not lowered_prompt:
        return None

    match = re.search(
        r"\b(?:apri|avvia|lancia|esegui)\b\s+(?:il|lo|la|l'|un|una)?\s*(?:programma|applicazione|app)?\s*(.+)$",
        lowered_prompt,
    )
    if not match:
        return None

    requested_app = _normalize_text(_clean_app_name(match.group(1)))
    if not requested_app:
        return None

    for alias in config.app.app_aliases.keys():
        if _normalize_text(alias) == requested_app:
            return {
                "action": "open_app",
                "confidence": 0.92,
                "needs_clarification": False,
                "reason": "app_alias_match",
                "source": "heuristic",
            }

    return None


def _detect_close_app_intent(prompt):
    lowered_prompt = (prompt or "").strip().lower()
    if not lowered_prompt:
        return None

    match = re.search(
        r"\b(?:chiudi|termina|stoppa)\b\s+(?:il|lo|la|l'|un|una)?\s*(?:programma|applicazione|app)?\s*(.+)$",
        lowered_prompt,
    )
    if not match:
        return None

    requested_app = _normalize_text(_clean_app_name(match.group(1)))
    if not requested_app:
        return None

    for alias in config.app.app_aliases.keys():
        if _normalize_text(alias) == requested_app:
            return {
                "action": "close_app",
                "confidence": 0.92,
                "needs_clarification": False,
                "reason": "app_alias_match",
                "source": "heuristic",
            }

    return None


def _detect_date_intent(prompt):
    lowered_prompt = _normalize_text(prompt or "")
    if not lowered_prompt:
        return None

    date_patterns = (
        r"\bche giorno (?:e|e') oggi\b",
        r"\boggi che giorno (?:e|e')\b",
        r"\bche data (?:e|e') oggi\b",
        r"\boggi che data (?:e|e')\b",
        r"\bmi dici la data\b",
    )
    if any(re.search(pattern, lowered_prompt) for pattern in date_patterns):
        return {
            "action": "get_date",
            "confidence": 0.95,
            "needs_clarification": False,
            "reason": "date_request",
            "source": "heuristic",
        }

    return None


def _route_with_llm(prompt):
    sys_msg = (
        "You are an intent router for a voice assistant. "
        "Choose exactly one action for the user's request.\n"
        "Valid actions: none, get_date, get_weather, take_screenshot, search_file, open_app, close_app, build_meal_plan, change_meal_suggestion.\n"
        "Use action=none with needs_clarification=false for small talk/greetings (example reason: small_talk).\n"
        "Use action=none with needs_clarification=true for unknown/unclear requests (example reason: unknown_intent) "
        "and keep confidence <= 0.4 in that case.\n"
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
    normalized_reason = reason.strip().lower().replace(" ", "_")
    source = intent.get("source", "unknown")

    if confidence < LOW_CONFIDENCE_THRESHOLD and action != "none":
        needs_clarification = True

    if needs_clarification and action != "none" and confidence < LOW_CONFIDENCE_THRESHOLD:
        action = "none"

    if action == "none":
        fallback_reasons = {"unknown_intent", "no_specific_request", "unclear_request", "fallback", "invalid_json"}
        if needs_clarification or normalized_reason in fallback_reasons:
            confidence = min(confidence, 0.4)
            needs_clarification = True

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


def _clean_app_name(value):
    candidate = re.sub(r"[.!?]+$", "", value).strip()
    candidate = re.sub(r"\b(per favore|grazie)\b", "", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().lower()


def _build_conversation_messages():
    messages = [config.session.conversation[0]]
    if config.session.conversation_summary:
        messages.append(
            {
                "role": "system",
                "content": f"Conversation summary so far: {config.session.conversation_summary}",
            }
        )
    messages.extend(config.session.conversation[1:])
    return messages


def _trim_conversation_if_needed():
    non_system_messages = config.session.conversation[1:]
    trigger = config.app.conversation_summary_trigger
    keep_count = config.app.max_recent_conversation_messages

    if len(non_system_messages) <= trigger:
        return

    messages_to_summarize = non_system_messages[:-keep_count]
    messages_to_keep = non_system_messages[-keep_count:]

    if not messages_to_summarize:
        return

    summary = _summarize_messages(messages_to_summarize, config.session.conversation_summary)
    config.session.conversation_summary = summary
    config.session.conversation = [config.session.conversation[0], *messages_to_keep]
    logging.info(
        "Conversation trimmed: summarized %s messages, kept %s recent messages.",
        len(messages_to_summarize),
        len(messages_to_keep),
    )


def _summarize_messages(messages, previous_summary=None):
    formatted_messages = "\n".join(
        f"{message['role'].upper()}: {message['content']}"
        for message in messages
    )

    summary_prompt = (
        "Summarize the relevant conversation state for future assistant turns. "
        "Keep user preferences, open tasks, chosen files, meal-planning state, and unresolved follow-ups. "
        "Omit filler and repeated phrasing. Limit to 120 words.\n\n"
    )

    if previous_summary:
        summary_prompt += f"Previous summary:\n{previous_summary}\n\n"

    summary_prompt += f"Messages to compress:\n{formatted_messages}"

    summary_messages = [
        {
            "role": "system",
            "content": "You compress conversation state into a short factual memory for an assistant.",
        },
        {"role": "user", "content": summary_prompt},
    ]
    chat_completion = config.get_groq_client().chat.completions.create(
        messages=summary_messages,
        model=config.app.groq_model,
    )
    summary = chat_completion.choices[0].message.content.strip()
    logging.info(f"Updated conversation summary: {summary}")
    return summary
