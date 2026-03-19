import difflib
import json
import logging
import mimetypes
import os
import re

import atlas
import atlas.config as config


def handleFileSearchPrompt(prompt):
    logging.info("Entering handleFileSearchPrompt() function...")
    matches = searchFiles(prompt)
    outcome = buildFileSearchResponse(matches)

    config.session.last_file_search_results.clear()
    if outcome["status"] == "multiple":
        config.session.last_file_search_results.extend(outcome["matches"])
    elif outcome["status"] == "single":
        config.session.current_file_path = outcome["selected_path"]

    logging.info(f"File search outcome: {outcome}")
    return outcome


def searchFiles(prompt):
    info = extractFileInfo(prompt)
    filename, extension = info["filename"], info["extension"]

    all_results = []
    seen_paths = set()

    _extend_unique(all_results, seen_paths, exactSearch(filename, extension))

    if not all_results:
        _extend_unique(all_results, seen_paths, fuzzySearch(filename))

    if 2 <= len(all_results) < 5:
        semantic_keywords = extractSemanticKeywords(prompt)
        _extend_unique(all_results, seen_paths, semanticSearch(semantic_keywords))

    matches = all_results[:5]
    logging.info(f"File search matches: {matches}")
    return matches


def buildFileSearchResponse(matches):
    if not matches:
        return {
            "status": "not_found",
            "matches": [],
            "selected_path": None,
            "message": "I'm sorry, I couldn't find any files matching your request.",
        }

    if len(matches) == 1:
        path = matches[0]
        return {
            "status": "single",
            "matches": matches,
            "selected_path": path,
            "message": f"I found the requested file: {path}",
        }

    lines = ["I've found multiple files possibly matching your request:"]
    for idx, file_path in enumerate(matches, start=1):
        lines.append(f"{idx}. {os.path.basename(file_path)}")
    lines.append("Please specify which one you want by voice.")

    return {
        "status": "multiple",
        "matches": matches,
        "selected_path": None,
        "message": "\n".join(lines),
    }


def handleFileChoice(user_choice, file_list):
    logging.info("Entering handleFileChoice() function...")

    chosen_path = resolveFileChoice(user_choice, file_list)
    if chosen_path:
        logging.info(f"Resolved file choice locally: {chosen_path}")
        return chosen_path

    prompt_llm = (
        "You are a model that extracts exactly ONE filename from a user's choice.\n"
        "You receive a numbered list of filenames and the user's spoken choice.\n"
        "You MUST return ONLY the exact filename from the provided list matching the user's choice.\n"
        "If no choice can be resolved, return ONLY NONE."
    )

    file_names = [os.path.basename(path) for path in file_list]
    user_prompt = f"List:\n{json.dumps(file_names)}\nUser choice: {user_choice}"
    response = config.get_groq_client().chat.completions.create(
        messages=[
            {"role": "system", "content": prompt_llm},
            {"role": "user", "content": user_prompt},
        ],
        model=config.app.groq_model,
    )

    chosen_filename = response.choices[0].message.content.strip()
    logging.info(f"Extracted file choice via LLM: {chosen_filename}")

    if chosen_filename == "NONE":
        return None

    for path in file_list:
        if os.path.basename(path) == chosen_filename:
            return path

    return None


def resolveFileChoice(user_choice, file_list):
    normalized_choice = user_choice.strip().lower()
    file_names = [os.path.basename(path) for path in file_list]

    number_match = re.search(r"\b([1-9]\d*)\b", normalized_choice)
    if number_match:
        index = int(number_match.group(1)) - 1
        if 0 <= index < len(file_list):
            return file_list[index]

    for path, file_name in zip(file_list, file_names):
        base_name = os.path.splitext(file_name)[0].lower()
        lowered_name = file_name.lower()
        if lowered_name in normalized_choice or base_name in normalized_choice:
            return path

    return None


def summarizeFile(file_path):
    file_content = readFileContent(file_path)
    file_content = file_content[:2000] if file_content else "No readable content."
    summary_prompt = f"Summarize the following file content in 2-3 sentences: {file_content}"
    return atlas.groqPrompt(summary_prompt, None, None, None)


def extractFileInfo(prompt):
    logging.info("Entering extractFileInfo() function...")
    sys_msg = (
        "You are a model that precisely extracts information from user requests. "
        "You will receive a sentence in which the user asks to search for a file on the PC. "
        "You must identify and return ONLY the exact filename and its extension (only if explicitly stated). "
        "ATTENTION: Do NOT invent or infer extensions not explicitly stated by the user. "
        'If the user does NOT clearly mention an extension, return "NONE". '
        "Examples:\n"
        '- "Find the pdf of the thesis" -> {"filename":"thesis","extension":".pdf"}\n'
        '- "Look for the file pippo.docx" -> {"filename":"pippo","extension":".docx"}\n'
        '- "Find pippo" -> {"filename":"pippo","extension":"NONE"}\n'
        '- "Search for the file balance" -> {"filename":"balance","extension":"NONE"}\n'
        'ALWAYS respond in this exact JSON format: {"filename":"filename", "extension":".ext"} or {"filename":"filename", "extension":"NONE"}'
    )

    chat_completion = config.get_groq_client().chat.completions.create(
        messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        model=config.app.groq_model,
    )
    response = chat_completion.choices[0].message.content
    logging.info(f"Response in extractFileInfo(): {response}")
    return json.loads(response)


def exactSearch(filename, extension, allowed_dirs=None):
    logging.info("Entering exactSearch() function...")
    allowed_dirs = allowed_dirs or config.app.allowed_dirs
    results = []
    for base_dir in allowed_dirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]

            for file_name in files:
                name, ext = os.path.splitext(file_name)
                if extension != "NONE":
                    if name.lower() == filename.lower() and ext.lower() == extension.lower():
                        results.append(os.path.join(root, file_name))
                elif name.lower() == filename.lower():
                    results.append(os.path.join(root, file_name))
    logging.info(f"exactSearch res: {results}")
    return results


def fuzzySearch(filename, allowed_dirs=None, cutoff=0.8):
    logging.info("Entering fuzzySearch() function...")
    allowed_dirs = allowed_dirs or config.app.allowed_dirs
    results = []
    for base_dir in allowed_dirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]

            file_names = [os.path.splitext(file_name)[0] for file_name in files]
            close_matches = difflib.get_close_matches(filename.lower(), file_names, n=10, cutoff=cutoff)

            for match in close_matches:
                for file_name in files:
                    if match == os.path.splitext(file_name)[0].lower():
                        results.append(os.path.join(root, file_name))

    logging.info(f"fuzzySearch res: {results}")
    return results


def extractSemanticKeywords(prompt):
    logging.info("Entering extractSemanticKeywords() function...")
    sys_msg = (
        "You are a semantic keyword extractor. "
        "Given a user prompt, generate a short list (5-10) of related keywords that might match filenames "
        "on a user's computer. Return only a JSON array of keywords."
    )

    chat_completion = config.get_groq_client().chat.completions.create(
        messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        model=config.app.groq_model,
    )

    response = chat_completion.choices[0].message.content
    logging.info(f"Response in extractSemanticKeywords(): {response}")
    return json.loads(response)


def semanticSearch(keywords, allowed_dirs=None):
    allowed_dirs = allowed_dirs or config.app.allowed_dirs
    matches = []
    for base_dir in allowed_dirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]

            for file_name in files:
                if any(keyword.lower() in file_name.lower() for keyword in keywords):
                    matches.append(os.path.join(root, file_name))

    logging.info(f"semanticSearch: {matches}")
    return matches


def openFile(file_path):
    logging.info("Entering openFile() function...")

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return "Error: File not found."

    try:
        os.startfile(file_path)
        return "Opening file..."
    except Exception as exc:
        logging.error(f"Error opening file: {exc}")
        return "Error: Unable to open the file."


def readFileContent(file_path):
    logging.info("Entering readFileContent() function...")

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return "Error: File not found."

    mime_type, _ = mimetypes.guess_type(file_path)
    logging.info(f"Mime type: {mime_type}")

    if mime_type and mime_type.startswith("text"):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as exc:
            logging.error(f"Error reading file: {exc}")
            return "Error: Unable to read the file."

    if file_path.endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
            return text if text else "No readable text found in the PDF."
        except Exception as exc:
            logging.error(f"Error reading PDF: {exc}")
            return "Error: Unable to read the PDF."

    if file_path.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text if text else "No readable text found in the document."
        except Exception as exc:
            logging.error(f"Error reading DOCX: {exc}")
            return "Error: Unable to read the document."

    return "No readable content."


def _extend_unique(destination, seen_paths, new_paths):
    for path in new_paths:
        if path not in seen_paths:
            seen_paths.add(path)
            destination.append(path)
