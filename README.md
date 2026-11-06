# Atlas - Multimodal Personal Assistant

**Italiano**

Atlas e un assistente personale vocale basato su intelligenza artificiale, scritto in Python. Il progetto integra riconoscimento vocale, orchestrazione LLM, contesto visivo da screenshot, ricerca file, meteo e funzionalita sperimentali per la pianificazione dei pasti.

Attualmente il progetto e ancora un prototipo: il codice e molto piu strutturato rispetto alla versione iniziale, ma diverse integrazioni restano opzionali e dipendono dalla configurazione locale.

Funzionalita principali:

- Riconoscimento vocale
- Sintesi vocale (TTS)
- Routing degli intenti con LLM
- Ricerca file e sintesi del contenuto
- Screenshot e analisi del contesto visivo
- Richieste meteo
- Pianificazione pasti (sperimentale)

**English**

Atlas is a Python voice assistant prototype with speech recognition, LLM orchestration, screenshot-based visual context, file search, weather lookup, and experimental meal-plan features.

The project is still a prototype: the codebase is much more structured than the original version, but several integrations are still optional and depend on local setup.

Main features:

- Speech recognition
- Text-to-speech (TTS)
- LLM-based intent routing
- File search and content summarization
- Screenshot capture and visual context analysis
- Weather requests
- Meal planning (experimental)

---

## Project Structure

- `main.py`: startup entrypoint
- `atlas/config.py`: configuration loading and validation
- `atlas/orchestrator.py`: request orchestration
- `atlas/core.py`: LLM prompting and intent routing
- `atlas/audioProcessing.py`: speech-to-text
- `atlas/tts.py`: text-to-speech
- `atlas/fileHandler.py`: file search and summarization
- `atlas/weather.py`: weather extraction and forecast retrieval
- `atlas/screenshot.py`: screenshot capture and visual context
- `atlas/wakeword.py`: wake word listening loop

---

## Requirements

**Italiano**

- Python 3.11+ (installazione e test verificati con Python 3.12 su Windows)
- `pip install -r requirements.txt`
- una `GROQ_API_KEY` valida per il flusso principale dell'assistente

Alcune integrazioni richiedono anche dipendenze native locali:

- `PyAudio` per microfono e wake word
- `ffmpeg` se usi `pydub` per la riproduzione audio
- supporto di piattaforma per la cattura screenshot

**English**

- Python 3.11+ (installation and tests verified with Python 3.12 on Windows)
- `pip install -r requirements.txt`
- a valid `GROQ_API_KEY` for the main assistant flow

Some integrations also require native local dependencies:

- `PyAudio` for microphone and wake word flows
- `ffmpeg` when using `pydub` playback
- platform support for screenshot capture

---

## Running the Project

```bash
git clone https://github.com/Ho3pLi/atlas.git
cd atlas
pip install -r requirements.txt
copy .envExample .env
python main.py
```

**Italiano**

Per default il progetto gira in debug mode se `DEBUG_MODE=true`, quindi puoi interagire dal terminale senza avviare il loop wake word.

**English**

By default the project runs in debug mode if `DEBUG_MODE=true`, so you can interact through the terminal without starting the wake word loop.

PyQt GUI mode:

```bash
python main.py --gui
```

---

## Environment Variables

**Italiano**

Copia `.envExample` in `.env` e compila solo le variabili che ti servono.

Obbligatoria:

- `GROQ_API_KEY`
  Usata per risposte principali, routing degli intenti, helper LLM per file e meal plan.

Opzionali:

- `GOOGLE_API_KEY`
  Abilita l'analisi visiva degli screenshot.
- `OPENAI_API_KEY`
  Riservata a integrazioni future o alternative.
- `OPENWEATHER_API_KEY`
  Abilita le richieste meteo.
- `PORCUPINE_API_KEY`
  Abilita la modalita wake word.
- `NARAKEET_API_KEY`
  Abilita il TTS se `ENABLE_TTS=true`.

Flag runtime:

- `DEBUG_MODE`
  `true` avvia l'assistente in terminal/debug mode.
- `ENABLE_TTS`
  `true` abilita l'output vocale se `NARAKEET_API_KEY` e presente.
- `WHISPER_SIZE`
  Controlla la dimensione del modello Faster Whisper.
- `ATLAS_CREATOR_NAME`
  Nome del creatore da usare quando Atlas risponde a domande su chi l'ha creato.

Path opzionali:

- `ALLOWED_DIRS`
  Directory radice per la ricerca file. Usa il separatore di path della piattaforma.
  Su Windows: `C:\Docs;D:\Archive`
  Su sistemi Unix-like: `/home/user/Documents:/home/user/Desktop`
- `WAKE_WORD_MODEL`
- `PORCUPINE_MODEL_PATH`
- `SCREENSHOT_PATH`
- `PROMPT_PATH`
- `LOG_PATH`

Override opzionali dei modelli:

- `GROQ_MODEL`
- `GROQ_MODEL2`

Tuning memoria conversazionale:

- `MAX_RECENT_CONVERSATION_MESSAGES`
- `CONVERSATION_SUMMARY_TRIGGER`

**English**

Copy `.envExample` to `.env` and fill only the variables you need.

Required:

- `GROQ_API_KEY`
  Used for main assistant responses, intent routing, file-related LLM helpers, and meal plan generation.

Optional:

- `GOOGLE_API_KEY`
  Enables screenshot vision analysis.
- `OPENAI_API_KEY`
  Reserved for future or alternative integrations.
- `OPENWEATHER_API_KEY`
  Enables weather requests.
- `PORCUPINE_API_KEY`
  Enables wake word mode.
- `NARAKEET_API_KEY`
  Enables TTS when `ENABLE_TTS=true`.

Runtime flags:

- `DEBUG_MODE`
  `true` runs the assistant in terminal/debug mode.
- `ENABLE_TTS`
  `true` enables speech output if `NARAKEET_API_KEY` is also set.
- `WHISPER_SIZE`
  Controls the Faster Whisper model size.
- `ATLAS_CREATOR_NAME`
  Creator name Atlas should mention when asked who created it.

Optional paths:

- `ALLOWED_DIRS`
  Search roots for file search. Use the platform path separator.
  On Windows: `C:\Docs;D:\Archive`
  On Unix-like systems: `/home/user/Documents:/home/user/Desktop`
- `WAKE_WORD_MODEL`
- `PORCUPINE_MODEL_PATH`
- `SCREENSHOT_PATH`
- `PROMPT_PATH`
- `LOG_PATH`

Optional model overrides:

- `GROQ_MODEL`
- `GROQ_MODEL2`

Conversation memory tuning:

- `MAX_RECENT_CONVERSATION_MESSAGES`
- `CONVERSATION_SUMMARY_TRIGGER`

---

## Configuration Validation

**Italiano**

Atlas valida la configurazione all'avvio e segnala subito setup mancanti o incompleti.

Casi tipici:

- manca `GROQ_API_KEY`: il flusso principale non puo funzionare
- manca `OPENWEATHER_API_KEY`: il meteo fallisce in modo controllato
- manca `GOOGLE_API_KEY`: lo screenshot puo funzionare, ma non l'analisi visiva
- `ENABLE_TTS=true` senza `NARAKEET_API_KEY`: il TTS resta disabilitato
- manca `PORCUPINE_API_KEY`: la wake word puo fallire fuori dal debug mode

**English**

Atlas validates configuration on startup and immediately reports missing or incomplete setup.

Typical cases:

- missing `GROQ_API_KEY`: the main flow cannot work
- missing `OPENWEATHER_API_KEY`: weather requests fail gracefully
- missing `GOOGLE_API_KEY`: screenshot capture may work, but vision analysis will not
- `ENABLE_TTS=true` without `NARAKEET_API_KEY`: TTS stays disabled
- missing `PORCUPINE_API_KEY`: wake word mode may fail outside debug mode

---

## Wake Word Assets

**Italiano**

La modalita wake word dipende anche da file modello locali:

- `atlas/models/atlas.ppn`
- `atlas/models/porcupine_params_it.pv`

Questi file non sono attualmente inclusi nel repository. Se mancano, la validazione iniziale segnala un warning e le feature legate alla wake word possono fallire.

**English**

Wake word mode also depends on local model files:

- `atlas/models/atlas.ppn`
- `atlas/models/porcupine_params_it.pv`

These files are not currently included in the repository. If they are missing, startup validation logs a warning and wake word-related features may fail.

---

## Running Modes

**Italiano**

Debug mode:

```env
DEBUG_MODE=true
```

Questa modalita evita il bootstrap del microfono/wake word e usa l'input da terminale.

Wake word mode:

```env
DEBUG_MODE=false
PORCUPINE_API_KEY=...
```

Servono anche:

- accesso al microfono
- asset wake word presenti
- `PyAudio` installato correttamente

**English**

Debug mode:

```env
DEBUG_MODE=true
```

This mode avoids microphone and wake word bootstrapping and uses terminal input instead.

Wake word mode:

```env
DEBUG_MODE=false
PORCUPINE_API_KEY=...
```

You also need:

- microphone access
- wake word assets available
- `PyAudio` installed correctly

---

## Current Status

- Core orchestration works
- Intent routing is more structured and validated
- File search flow is more explicit
- Conversation memory is trimmed and summarized
- Error handling is more defensive than in the original prototype

**Italiano**

Il progetto non e ancora production-grade. Aspettati differenze di setup locale, dipendenze opzionali e funzionalita ancora incomplete.

**English**

The project is still not production-grade. Expect local setup differences, optional integrations, and incomplete features.

---

## Support

For support or questions: **daniele.barile.lavoro@gmail.com**  
Or open an issue on GitHub.

---

## License

[GPL v3](https://choosealicense.com/licenses/gpl-3.0/)

---

## Author

- [@Ho3pLi](https://www.github.com/Ho3pLi)


## Reviewed runtime behavior (November 2026)

**Italiano**

- I modelli predefiniti sono `openai/gpt-oss-20b` / `openai/gpt-oss-120b`
  su **Groq** e `gemini-3.8-flash` per le immagini, tramite `google-genai`.
  Gli override sono `GROQ_MODEL`, `GROQ_MODEL2`, `GEMINI_MODEL`.
  Se hai gia un `.env`, aggiorna gli eventuali vecchi nomi: gli override hanno
  precedenza sui valori predefiniti. Non serve una chiave OpenAI per i modelli
  serviti da Groq. Disponibilita, quote e costi dipendono dal tuo provider/piano;
  cambiare modello non cambia il piano dell'account.
- CLI: le risposte vengono stampate anche con TTS disabilitato; Ctrl+C/EOF
  termina il ciclo. Per chiudere un'app serve un comando esplicito come
  `chiudi chrome`. La chiusura Windows e normale, senza terminazione forzata.
  Se l'app non si chiude, gestiscila manualmente per preservare il lavoro aperto.
- `APP_ALIASES_JSON` accetta stringhe Windows oppure liste di argomenti, ad esempio
  `{"browser":["C:\\Program Files\\Browser\\browser.exe","--profile","Profile 1"]}`.
- Dopo una ricerca con piu file puoi scegliere il numero, il nome completo o
  il percorso; i nomi ambigui richiedono chiarimento. `annulla ricerca` elimina
  la selezione in sospeso. Puoi fare altre domande e tornare alla selezione.
- Il piano pasti raccoglie sei preferenze tramite i normali turni di chat
  (anche nella GUI), senza valori dimostrativi imposti. `annulla piano`
  interrompe la raccolta. Due pasti sono pranzo/cena, tre includono la colazione.
  `cambia pasto` sostituisce e salva il piano corrente solo se completo.
- `LISTEN_TIMEOUT` (10 secondi) e `PHRASE_TIME_LIMIT` (30 secondi) limitano
  l'ascolto. Le registrazioni temporanee vengono eliminate dopo la trascrizione;
  il TTS usa memoria senza un file audio persistente.
- I log omettono prompt, risposte, trascrizioni e preferenze, oscurano le chiavi
  configurate e ruotano a 2 MB con tre copie. Gli screenshot restano nel percorso
  configurato. Log precedenti a questo aggiornamento non vengono riscritti.

**English**

Defaults now use `openai/gpt-oss-20b` / `openai/gpt-oss-120b` on **Groq** and
`gemini-3.8-flash` through `google-genai`. Existing `.env` overrides take
precedence and must be updated if they name retired models. No OpenAI key is
needed for Groq-hosted models; provider access, quotas and pricing still apply.

The CLI always prints responses. Windows application commands require explicit
syntax and close gracefully without forced termination. File selection supports
exact names, paths, numbers, cancellation and switching to other questions.
Meal preferences are collected through ordinary chat turns in CLI/GUI; generated
and replacement plans are validated before saving. Audio capture is bounded,
temporary recordings are removed, and logs omit conversation bodies, redact
configured credentials and rotate with bounded retention.

Run the offline regression suite with:

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Tests use synthetic documents/images/audio and mocked network/process operations.
They do not certify live provider access, hardware audio, ffmpeg playback or
actual application shutdown on your desktop. See [the review fix checklist](docs/review-fixes-20261106.md).
