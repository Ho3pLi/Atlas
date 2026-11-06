# Repository review fixes — 2026-11-06

Scope: the 16 findings against `dfc5d8267417ce8ebc8b7d3661fae06cf3d7e3eb`,
plus the accompanying logging, diagnostics and audio-resource observations.

| Finding | Result | Regression coverage |
| --- | --- | --- |
| R01 | Shared, anchored app-command parser; informational/negated prompts cannot execute app commands, including LLM fallback. Windows close requests omit `/F`. | Information/negation, app routing, mocked taskkill arguments |
| R02 | CLI prints responses and exits cleanly on EOF/Ctrl+C. | CLI input/output loop and real CLI time-query smoke check |
| R03 | Exact path/name/stem precedes unique partial selection. Duplicate names require a number/path. Digits in filenames are preserved. | Longer filename, duplicate basename, numbered filename |
| R04 | Pending file choices support cancellation and unrelated conversation/commands. Ambiguity stays local. | Time query, ordinary conversation, cancellation, ambiguous basename |
| R05 | Fuzzy and semantic candidates are filtered by the requested extension before limiting results. | Mixed PDF/DOCX files with case-insensitive extensions |
| R06 | OpenWeather uses HTTPS and encoded query parameters; errors do not log raw request URLs. | Current-weather request inspection and credential redaction |
| R07 | Relative `today` survives extraction and selects current weather. | End-to-end extraction/current endpoint test |
| R08 | Forecast timestamps and relative target dates use the provider's city offset, not the machine timezone. | UTC-midnight/New York boundary fixture |
| R09 | Meal-change routing has priority and updates the current saved plan. The displayed plan is the saved object. | Router and orchestration/state replacement tests |
| R10 | Explicit meal sets for 1–5 meals; two includes lunch/dinner, three adds breakfast. Responses are validated before saving. | All meal counts, invalid counts, malformed/missing/empty response data |
| R11 | Preferences are ordinary chat turns in CLI/GUI, reused on later plans. Standalone voice input records fresh audio using `PROMPT_PATH` and bounded listening. | Six distinct recordings, configured path, preference reuse, headless Qt conversation |
| R12 | Windows strings use `CommandLineToArgvW`; structured argument lists are also accepted, without a shell. | Real benign child process checks quoted/escaped arguments |
| R13 | Failed vision analysis produces an explicit error instead of a text-only answer pretending to use the screenshot. Image resources close after use. | Vision failure and real SDK image serialization/cleanup |
| R14 | Router JSON must be an object with a known string action, finite numeric confidence in range, and a real boolean. Invalid data requests clarification. | Arrays, null, strings, unknown/unhashable actions, NaN, wrong field types |
| R15 | Configurable Gemini model with the maintained `google-genai` SDK; default `gemini-3.8-flash`. Legacy SDK-only dependencies removed. | Installed SDK, mocked HTTP transport, synthetic PIL image and generation settings |
| R16 | Groq defaults use `openai/gpt-oss-20b`/`openai/gpt-oss-120b`, retaining environment overrides. No provider/account change. | Installed Groq SDK: JSON routing, short/long chat, conversation summary |

Additional changes: omit conversation/file/vision/preference bodies from logs;
redact configured credentials; rotate logs; make diagnostics import-safe;
bound wake-word recording, pause its stream while recording, release the
microphone before callbacks and clean up partial startup; keep TTS audio in
memory; render GUI messages as literal text. Historical archive/dependency
files remain historical and are not the active installation manifest.

## Validation

- Clean Python 3.12.16 environment on Windows: installation from `requirements.txt` succeeded.
- 82 automated tests, including an offscreen Qt event loop with real worker threads.
- `python -m pip check`: no broken requirements.
- Resolved installed environment audited with pip-audit: 67 distributions, zero known vulnerabilities, zero skips on 2026-11-06.
- Ruff undefined/unused-name checks and Python compilation pass.
- Windows Python 3.12 CI installs dependencies, checks them and runs the suite on pull requests.

SDK tests use synthetic HTTP transports and test keys, not authenticated calls.
No live provider access, model quality, real microphone/wake-word hardware,
ffmpeg playback or actual desktop process termination was tested. The Qt check
is headless, not an interactive usability/device certification. A clean audit
does not establish absence of unknown vulnerabilities.

## Model migration references

- [Groq model deprecations](https://console.groq.com/docs/deprecations): Llama defaults retired for free/developer usage; enterprise committed-spend contracts have an exception.
- [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/): supported client and `generate_content` interface.
- [Gemini model deprecations](https://ai.google.dev/gemini-api/docs/deprecations).

Existing `.env` overrides continue to win. Update retired model names there when
adopting the change; the repository does not rewrite local credentials/settings.
Access, quotas and model pricing depend on the configured provider/account and
were not verified with a live account.
