import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import unicodedata
from pathlib import Path

import atlas.config as config


APP_LAUNCH_PATTERNS = [
    r"\b(?:apri|avvia|lancia|esegui)\b\s+(?:il|lo|la|l'|un|una)?\s*(?:programma|applicazione|app)?\s*(.+)$",
]


def handleAppLaunchPrompt(prompt):
    logging.info("Entering handleAppLaunchPrompt() function...")
    app_name = extractAppName(prompt)
    if not app_name:
        return {
            "status": "error",
            "app_name": None,
            "target": None,
            "message": "Non ho capito quale programma vuoi aprire.",
        }

    target = resolveAppAlias(app_name)
    if not target:
        available_apps = ", ".join(sorted(config.app.app_aliases.keys()))
        return {
            "status": "not_found",
            "app_name": app_name,
            "target": None,
            "message": (
                f"Non ho un alias configurato per '{app_name}'. "
                f"App disponibili: {available_apps}."
            ),
        }

    return launchApplication(app_name, target)


def extractAppName(prompt):
    prompt_text = (prompt or "").strip()
    if not prompt_text:
        return None

    lowered = prompt_text.lower()

    for pattern in APP_LAUNCH_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            candidate = _clean_app_name(match.group(1))
            return candidate or None

    return None


def resolveAppAlias(app_name):
    if not app_name:
        return None

    normalized_requested = _normalize_text(app_name)
    for alias, app_target in config.app.app_aliases.items():
        if _normalize_text(alias) == normalized_requested:
            return app_target
    return None


def launchApplication(app_name, target):
    try:
        command = shlex.split(target, posix=False)
        if not command:
            raise ValueError("empty app launch command")
        resolved_executable = _resolve_executable(command[0])
        if not resolved_executable:
            raise FileNotFoundError(command[0])

        launch_command = _build_launch_command(app_name, resolved_executable, command[1:])
        subprocess.Popen(
            launch_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return {
            "status": "ok",
            "app_name": app_name,
            "target": target,
            "message": f"Apro {app_name}.",
        }
    except FileNotFoundError:
        logging.error("App target not found: %s", target)
        return {
            "status": "error",
            "app_name": app_name,
            "target": target,
            "message": f"Non trovo l'eseguibile configurato per {app_name}: {target}.",
        }
    except Exception as exc:
        logging.error("App launch failed for %s (%s): %s", app_name, target, exc)
        return {
            "status": "error",
            "app_name": app_name,
            "target": target,
            "message": f"Non sono riuscito ad aprire {app_name}.",
        }


def _clean_app_name(value):
    candidate = re.sub(r"[.!?]+$", "", value).strip()
    candidate = re.sub(r"\b(per favore|grazie)\b", "", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().lower()


def _build_launch_command(app_name, resolved_executable, args):
    normalized_app = _normalize_text(app_name)
    command = [resolved_executable, *args]

    # Discord may require Update.exe with process args on some installations.
    if normalized_app == "discord" and Path(resolved_executable).name.lower() == "update.exe" and not args:
        command = [resolved_executable, "--processStart", "Discord.exe"]

    return command


def _resolve_executable(executable):
    if not executable:
        return None

    expanded_input = os.path.expandvars(executable.strip().strip('"'))
    if os.path.exists(expanded_input):
        return expanded_input

    from_path = shutil.which(executable)
    if from_path:
        return from_path

    lowered = executable.lower()
    for candidate in _candidate_paths(lowered):
        if _is_existing_path(candidate):
            return candidate

    return None


def _is_existing_path(path):
    expanded = os.path.expandvars(path.strip().strip('"'))
    return os.path.exists(expanded)


def _candidate_paths(executable_lower):
    local_app_data = os.getenv("LOCALAPPDATA", "")
    program_files = os.getenv("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")

    candidates = []

    if executable_lower == "chrome.exe":
        candidates.extend(
            [
                rf"{program_files}\Google\Chrome\Application\chrome.exe",
                rf"{program_files_x86}\Google\Chrome\Application\chrome.exe",
                rf"{local_app_data}\Google\Chrome\Application\chrome.exe",
            ]
        )
    elif executable_lower == "msedge.exe":
        candidates.extend(
            [
                rf"{program_files}\Microsoft\Edge\Application\msedge.exe",
                rf"{program_files_x86}\Microsoft\Edge\Application\msedge.exe",
            ]
        )
    elif executable_lower == "steam.exe":
        candidates.extend(
            [
                rf"{program_files_x86}\Steam\steam.exe",
                rf"{program_files}\Steam\steam.exe",
            ]
        )
    elif executable_lower == "riotclientservices.exe":
        candidates.extend(_riot_client_candidates(program_files, program_files_x86, local_app_data))
    elif executable_lower == "discord.exe":
        discord_root = Path(local_app_data) / "Discord"
        if discord_root.exists():
            app_dirs = sorted(discord_root.glob("app-*"), reverse=True)
            candidates.extend(str(path / "Discord.exe") for path in app_dirs)
        candidates.append(rf"{local_app_data}\Discord\Update.exe")

    return [os.path.expandvars(candidate) for candidate in candidates]


def _riot_client_candidates(program_files, program_files_x86, local_app_data):
    candidates = [
        r"C:\Riot Games\Riot Client\RiotClientServices.exe",
        rf"{program_files}\Riot Games\Riot Client\RiotClientServices.exe",
        rf"{program_files_x86}\Riot Games\Riot Client\RiotClientServices.exe",
        rf"{local_app_data}\Riot Games\Riot Client\RiotClientServices.exe",
    ]

    program_data = os.getenv("PROGRAMDATA", r"C:\ProgramData")
    installs_json = Path(program_data) / "Riot Games" / "RiotClientInstalls.json"
    if installs_json.exists():
        try:
            payload = json.loads(installs_json.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                for value in payload.values():
                    if isinstance(value, str) and value.lower().endswith("riotclientservices.exe"):
                        candidates.append(value)
        except Exception as exc:
            logging.warning("Cannot parse RiotClientInstalls.json: %s", exc)

    riot_root = Path(r"C:\Riot Games")
    if riot_root.exists():
        for candidate in riot_root.glob("**/RiotClientServices.exe"):
            candidates.append(str(candidate))

    return candidates
