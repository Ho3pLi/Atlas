import logging
import os
import json
import difflib

from atlas.config import allowedDirs, groqClient, lastFileSearchResults

def handleFileSearchPrompt(prompt):
    global lastFileSearchResults

    info = extractFileInfo(prompt)
    filename, extension = info["filename"], info["extension"]

    all_results = set()

    exact_results = exactSearch(filename, extension, allowedDirs)
    all_results.update(exact_results)

    if len(all_results) < 5:
        fuzzy_results = fuzzySearch(filename, allowedDirs)
        all_results.update(fuzzy_results)

    if len(all_results) < 5:
        semantic_keywords = extractSemanticKeywords(prompt)
        semantic_results = semanticSearch(semantic_keywords, allowedDirs)
        all_results.update(semantic_results)

    if not all_results:
        response = "I'm sorry, I couldn't find any files matching your request."
        lastFileSearchResults = []
    elif len(all_results) == 1:
        path = list(all_results)[0]
        response = f"I've found the requested file:\n{path}"
        lastFileSearchResults = []
    else:
        response = "I've found multiple files possibly matching your request:\n"
        lastFileSearchResults = list(all_results)
        for idx, file in enumerate(lastFileSearchResults, start=1):
            response += f"{idx}. {os.path.basename(file)}\n"
        response += "Please specify which one you want by voice."

    logging.info(f"Assistant Response: {response}")
    return response

def extractFileInfo(prompt):

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
        model='llama-3.1-8b-instant'  
    )
    response = chatCompletion.choices[0].message.content
    return json.loads(response)

def exactSearch(filename, extension, allowedDirs=allowedDirs):
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

    sysMsg = (
        "You are a semantic keyword extractor. "
        "Given a user prompt, generate a short list (5-10) of related keywords that might match filenames "
        "on a user's computer. Return only a JSON array of keywords."
    )

    chatCompletion = groqClient.chat.completions.create(
        messages=[{'role':'system', 'content':sysMsg}, {'role':'user', 'content':prompt}],
        model='llama-3.1-8b-instant'
    )

    response = chatCompletion.choices[0].message.content
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