from dataclasses import dataclass
import difflib
import json
import logging
import mimetypes
import os
import re

import atlas
import atlas.config as config


@dataclass(frozen=True)
class _FileReadResult:
    content: str | None = None
    message: str = "Nessun contenuto leggibile."


def handleFileSearchPrompt(prompt):
    logging.info("Entering handleFileSearchPrompt() function...")
    try:
        matches = searchFiles(prompt)
        outcome = buildFileSearchResponse(matches)
    except Exception as exc:
        logging.error("File search failed (%s)", type(exc).__name__)
        outcome = {
            "status": "error",
            "matches": [],
            "selected_path": None,
            "message": "Si e verificato un problema durante la ricerca del file.",
        }

    config.session.last_file_search_results.clear()
    if outcome["status"] == "multiple":
        config.session.last_file_search_results.extend(outcome["matches"])
    elif outcome["status"] == "single":
        config.session.current_file_path = outcome["selected_path"]

    return outcome


def searchFiles(prompt):
    info = extractFileInfo(prompt)
    filename, extension = info["filename"], info["extension"]

    all_results = []
    seen_paths = set()

    _extend_unique(all_results, seen_paths, exactSearch(filename, extension))

    if not all_results:
        _extend_unique(
            all_results, seen_paths, fuzzySearch(filename, extension=extension)
        )

    if 2 <= len(all_results) < 5:
        semantic_keywords = extractSemanticKeywords(prompt)
        _extend_unique(
            all_results,
            seen_paths,
            semanticSearch(semantic_keywords, extension=extension),
        )

    matches = all_results[:5]
    return matches


def buildFileSearchResponse(matches):
    if not matches:
        return {
            "status": "not_found",
            "matches": [],
            "selected_path": None,
            "message": "Non ho trovato file che corrispondano alla tua richiesta.",
        }

    if len(matches) == 1:
        path = matches[0]
        return {
            "status": "single",
            "matches": matches,
            "selected_path": path,
            "message": f"Ho trovato il file richiesto: {path}",
        }

    lines = ["Ho trovato piu file che potrebbero corrispondere alla tua richiesta:"]
    for idx, file_path in enumerate(matches, start=1):
        lines.append(f"{idx}. {os.path.basename(file_path)}")
    lines.append("Dimmi quale vuoi aprire specificando il numero o il nome.")

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
        return chosen_path

    # Ambiguous local selections must never be guessed by a language model.
    return None


def resolveFileChoice(user_choice, file_list):
    choice = user_choice.strip().casefold()
    number = re.fullmatch(
        r"(?:(?:apri\s+|scegli\s+)?(?:il\s+)?(?:file\s+)?(?:numero\s+)?)([1-9]\d*)[.!]?",
        choice,
    )
    if number:
        index = int(number.group(1)) - 1
        return file_list[index] if 0 <= index < len(file_list) else None
    for names in (
        [(path, path.casefold()) for path in file_list],
        [(path, os.path.basename(path).casefold()) for path in file_list],
        [
            (path, os.path.splitext(os.path.basename(path))[0].casefold())
            for path in file_list
        ],
    ):
        exact = [path for path, name in names if name == choice]
        if exact:
            return exact[0] if len(exact) == 1 else None
    candidates = [(path, os.path.basename(path).casefold()) for path in file_list]
    matches = [
        (path, name)
        for path, name in candidates
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", choice)
    ]
    if not matches:
        matches = [
            (path, name)
            for path, name in candidates
            if re.search(
                r"(?<!\w)" + re.escape(os.path.splitext(name)[0]) + r"(?!\w)", choice
            )
        ]
    # Longest matching name wins only when unique (report finale vs report).
    if matches:
        longest = max(len(name) for _, name in matches)
        winners = [path for path, name in matches if len(name) == longest]
        return winners[0] if len(winners) == 1 else None
    return None


def summarizeFile(file_path):
    result = _read_file_content(file_path)
    if result.content is None or not result.content.strip():
        return result.message

    file_content = result.content[:2000]
    summary_prompt = f"Riassumi il seguente contenuto del file in 2-3 frasi in italiano: {file_content}"
    try:
        return atlas.groqPrompt(summary_prompt, None, None, None)
    except Exception as exc:
        logging.error("File summarization failed (%s)", type(exc).__name__)
        return "Ho trovato il file, ma non sono riuscito a riassumerne il contenuto."


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
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ],
        model=config.app.groq_model,
    )
    response = chat_completion.choices[0].message.content
    try:
        return json.loads(response)
    except json.JSONDecodeError as exc:
        logging.error("File info parsing failed (%s)", type(exc).__name__)
        return {"filename": prompt.strip(), "extension": "NONE"}


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
                    if (
                        name.lower() == filename.lower()
                        and ext.lower() == extension.lower()
                    ):
                        results.append(os.path.join(root, file_name))
                elif name.lower() == filename.lower():
                    results.append(os.path.join(root, file_name))
    return results


def fuzzySearch(filename, allowed_dirs=None, cutoff=0.8, extension="NONE"):
    logging.info("Entering fuzzySearch() function...")
    allowed_dirs = allowed_dirs or config.app.allowed_dirs
    results = []
    for base_dir in allowed_dirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]

            files_by_stem = {}
            for file_name in files:
                if (
                    extension != "NONE"
                    and os.path.splitext(file_name)[1].lower() != extension.lower()
                ):
                    continue
                stem = os.path.splitext(file_name)[0].lower()
                files_by_stem.setdefault(stem, []).append(file_name)

            close_matches = difflib.get_close_matches(
                filename.lower(), files_by_stem, n=10, cutoff=cutoff
            )

            for match in close_matches:
                for file_name in files_by_stem[match]:
                    results.append(os.path.join(root, file_name))

    return results


def extractSemanticKeywords(prompt):
    logging.info("Entering extractSemanticKeywords() function...")
    sys_msg = (
        "You are a semantic keyword extractor. "
        "Given a user prompt, generate a short list (5-10) of related keywords that might match filenames "
        "on a user's computer. Return only a JSON array of keywords."
    )

    chat_completion = config.get_groq_client().chat.completions.create(
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ],
        model=config.app.groq_model,
    )

    response = chat_completion.choices[0].message.content
    try:
        return json.loads(response)
    except json.JSONDecodeError as exc:
        logging.error("Semantic keyword parsing failed (%s)", type(exc).__name__)
        return []


def semanticSearch(keywords, allowed_dirs=None, extension="NONE"):
    allowed_dirs = allowed_dirs or config.app.allowed_dirs
    matches = []
    for base_dir in allowed_dirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]

            for file_name in files:
                if (
                    extension != "NONE"
                    and os.path.splitext(file_name)[1].lower() != extension.lower()
                ):
                    continue
                if any(keyword.lower() in file_name.lower() for keyword in keywords):
                    matches.append(os.path.join(root, file_name))

    return matches


def openFile(file_path):
    logging.info("Entering openFile() function...")

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return "Errore: file non trovato."

    try:
        os.startfile(file_path)
        return "Apertura del file in corso..."
    except Exception as exc:
        logging.error("Error opening file (%s)", type(exc).__name__)
        return "Errore: impossibile aprire il file."


def readFileContent(file_path):
    """Return file text or the existing user-facing status message."""
    result = _read_file_content(file_path)
    return result.content if result.content is not None else result.message


def _read_file_content(file_path):
    """Keep readable content separate from errors and empty/unsupported results."""
    logging.info("Entering readFileContent() function...")

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return _FileReadResult(message="Errore: file non trovato.")

    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type and mime_type.startswith("text"):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return _FileReadResult(content=file.read())
        except Exception as exc:
            logging.error("Error reading file (%s)", type(exc).__name__)
            return _FileReadResult(message="Errore: impossibile leggere il file.")

    if str(file_path).lower().endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(
                    text for page in pdf.pages if (text := page.extract_text())
                )
            if text.strip():
                return _FileReadResult(content=text)
            return _FileReadResult(message="Nessun testo leggibile trovato nel PDF.")
        except Exception as exc:
            logging.error("Error reading PDF (%s)", type(exc).__name__)
            return _FileReadResult(message="Errore: impossibile leggere il PDF.")

    if str(file_path).lower().endswith(".docx"):
        try:
            from docx import Document

            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            if text.strip():
                return _FileReadResult(content=text)
            return _FileReadResult(
                message="Nessun testo leggibile trovato nel documento."
            )
        except Exception as exc:
            logging.error("Error reading DOCX (%s)", type(exc).__name__)
            return _FileReadResult(message="Errore: impossibile leggere il documento.")

    return _FileReadResult()


def _extend_unique(destination, seen_paths, new_paths):
    for path in new_paths:
        if path not in seen_paths:
            seen_paths.add(path)
            destination.append(path)
