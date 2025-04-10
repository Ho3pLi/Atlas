import logging
import os
import json
import difflib
import mimetypes
import pdfplumber
from docx import Document

from atlas.config import allowedDirs, groqClient, lastFileSearchResults, groqModel

def handleFileSearchPrompt(prompt):
    logging.info('Entering handleSearchPrompt() function...')
    global lastFileSearchResults

    info = extractFileInfo(prompt)
    filename, extension = info["filename"], info["extension"]

    all_results = set()

    exact_results = exactSearch(filename, extension, allowedDirs)
    all_results.update(exact_results)

    if len(all_results) == 0:
        fuzzy_results = fuzzySearch(filename, allowedDirs)
        all_results.update(fuzzy_results)

    if len(all_results) < 5 and len(all_results) >= 2:
        semantic_keywords = extractSemanticKeywords(prompt)
        semantic_results = semanticSearch(semantic_keywords, allowedDirs)
        all_results.update(semantic_results[:5])

    all_results = list(all_results)[:5]
    logging.info(f'all_results in handleFileSearchPrompt: {all_results}')

    if not all_results:
        response = "I'm sorry, I couldn't find any files matching your request."
        lastFileSearchResults.clear()
    elif len(all_results) == 1:
        path = list(all_results)[0]
        response = f"I've found the requested file:\n{path}"
        lastFileSearchResults.clear()
    else:
        response = "I've found multiple files possibly matching your request:\n"
        lastFileSearchResults.clear()
        lastFileSearchResults.extend(all_results)
        
        for idx, file in enumerate(lastFileSearchResults, start=1):
            response += f"{idx}. {os.path.basename(file)}\n"
        response += "Please specify which one you want by voice."

    logging.info(f"Assistant Response: {response}")
    return response

def extractFileInfo(prompt):
    logging.info('Entering extractFileInfo() function...')
    sysMsg = (
        'You are a model that precisely extracts information from user requests. '
        'You will receive a sentence in which the user asks to search for a file on the PC. '
        'You must identify and return ONLY the exact filename and its extension (only if explicitly stated). '
        'ATTENTION: Do NOT invent or infer extensions not explicitly stated by the user. '
        'If the user does NOT clearly mention an extension, return "NONE". '
        'Examples:\n'
        '- "Find the pdf of the thesis" -> {"filename":"thesis","extension":".pdf"}\n'
        '- "Look for the file pippo.docx" -> {"filename":"pippo","extension":".docx"}\n'
        '- "Find pippo" -> {"filename":"pippo","extension":"NONE"}\n'
        '- "Search for the file balance" -> {"filename":"balance","extension":"NONE"}\n'
        'ALWAYS respond in this exact JSON format: {"filename":"filename", "extension":".ext"} or {"filename":"filename", "extension":"NONE"}'
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model= groqModel  
    )
    response = chatCompletion.choices[0].message.content
    logging.info(f'Response in extractFileInfo(): {response}')
    return json.loads(response)

def exactSearch(filename, extension, allowedDirs=allowedDirs):
    logging.info('Entering exactSearch() function...')
    results = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                name, ext = os.path.splitext(file)
                if extension != "NONE":
                    if name.lower() == filename.lower() and ext.lower() == extension.lower():
                        results.append(os.path.join(root, file))
                else:
                    if name.lower() == filename.lower():
                        results.append(os.path.join(root, file))
    logging.info(f'exactSearch res: {results}')
    return results

def fuzzySearch(filename, allowedDirs=allowedDirs, cutoff=0.8):
    logging.info('Entering fuzzySearch() function...')
    results = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            file_names = [os.path.splitext(f)[0] for f in files]
            close_matches = difflib.get_close_matches(filename.lower(), file_names, n=10, cutoff=cutoff)

            for match in close_matches:
                for file in files:
                    if match == os.path.splitext(file)[0].lower():
                        results.append(os.path.join(root, file))

    logging.info(f'fuzzySearch res: {results}')
    return results

def extractSemanticKeywords(prompt):
    logging.info('Entering extractSemanticKeywords() function...')
    sysMsg = (
        "You are a semantic keyword extractor. "
        "Given a user prompt, generate a short list (5-10) of related keywords that might match filenames "
        "on a user's computer. Return only a JSON array of keywords."
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model= groqModel
    )

    response = chatCompletion.choices[0].message.content
    logging.info(f'Response in extractSemanticKeywords(): {response}')
    return json.loads(response)

def semanticSearch(keywords, allowedDirs=allowedDirs):
    matches = []
    for base_dir in allowedDirs:
        expanded_dir = os.path.expanduser(base_dir)
        for root, dirs, files in os.walk(expanded_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                if any(kw.lower() in file.lower() for kw in keywords):
                    matches.append(os.path.join(root, file))

    logging.info(f'semanticSearch: {matches}')
    return matches

def handleFileChoice(user_choice, fileList):
    logging.info('Entering handleFileChoice() function...')
    promptLLM = (
        "You are a model that extracts exactly ONE filename from a user's choice.\n"
        "You receive a numbered list of filenames and the user's spoken choice.\n"
        "List:\n\n"
        f"{[os.path.basename(f) for f in fileList]}\n\n"
        f"User choice: '{user_choice}'\n\n"
        "You MUST return ONLY the exact filename from the provided list matching the user's choice.\n"
        "Do NOT add any explanations, punctuation, or extra words.\n"
        "Examples:\n"
        "List:\n"
        "1. thesis.pdf\n"
        "2. notes.docx\n"
        "3. lecture.txt\n"
        "\nUser choice: 'I want thesis pdf'\n"
        "Your response: thesis.pdf\n"
        "\nUser choice: 'the notes'\n"
        "Your response: notes.docx\n"
        "\nUser choice: 'lecture file'\n"
        "Your response: lecture.txt\n"
        "\nRespond ONLY with the exact filename, nothing else."
    )

    response = groqClient.chat.completions.create(
        messages=[
            {'role':'system', 'content': promptLLM}
        ],
        model= groqModel
    )

    chosenFilename = response.choices[0].message.content.strip()

    logging.info(f"Extracted file choice: {chosenFilename}")
    logging.info(f'File list: {fileList}')

    if chosenFilename == 'NONE':
        return None

    for path in fileList:
        if os.path.basename(path) == chosenFilename:
            return path
        
    return None

def openFile(filePath):
    logging.info('Entering openFile() function...')
    
    if not os.path.exists(filePath):
        logging.error(f"File not found: {filePath}")
        return "Error: File not found."

    mimeType, _ = mimetypes.guess_type(filePath)
    logging.info(f'Mime type: {mimeType}')

    if mimeType and mimeType.startswith("text"):
        try:
            with open(filePath, "r", encoding="utf-8") as f:
                content = f.read()
            return content[:2000]
        except Exception as e:
            logging.error(f"Error reading file: {e}")
            return "Error: Unable to read the file."

    elif filePath.endswith(".pdf") and pdfplumber:
        try:
            with pdfplumber.open(filePath) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
            return text[:2000] if text else "No readable text found in the PDF."
        except Exception as e:
            logging.error(f"Error reading PDF: {e}")
            return "Error: Unable to read the PDF."

    elif filePath.endswith(".docx") and Document:
        try:
            doc = Document(filePath)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text[:1000] if text else "No readable text found in the document."
        except Exception as e:
            logging.error(f"Error reading DOCX: {e}")
            return "Error: Unable to read the document."

    else:
        try:
            os.startfile(filePath)
            return "Opening file..."
        except Exception as e:
            logging.error(f"Error opening file: {e}")
            return "Error: Unable to open the file."