# 🧠 Atlas – Multimodal Personal Assistant

**Italiano**

Atlas è un assistente personale vocale basato su intelligenza artificiale, progettato per aiutarti nella gestione quotidiana attraverso comandi vocali. È scritto in Python e include funzionalità modulari come:

- Pianificazione dei pasti (in sviluppo)
- Sintesi vocale (TTS)
- Riconoscimento vocale
- Comandi personalizzati
- Interazione con modelli LLM (es. Groq/Mistral)

Attualmente il progetto è fermo, sto dando la priorità ad altri progetti, non escludo di continuare lo sviluppo in futuro.

**English**

Atlas is a voice-controlled personal assistant powered by artificial intelligence, written in Python. It's designed to help with everyday tasks through vocal interaction. Current features include:

- Meal plan generator (in development)
- Text-to-speech (TTS)
- Speech recognition
- Custom command support
- LLM integration (e.g. Groq/Mistral)

Currently the project is stopped, I am giving priority to other projects, I do not exclude continuing the development in the future.

---

## 📦 Project Structure

- `main.py`: main entry point
- `atlas/buildMealPlan.py`: meal plan logic
- `atlas/audioProcessing.py`: speech-to-text
- `atlas/tts.py`: text-to-speech
- `atlas/config.py`: global state and preferences
- `atlas/core.py`: system orchestration

---

## ⚙️ Requirements

- Python 3.x
- openai-whisper (or equivalent STT lib)
- a TTS engine
- Groq/Mistral or other LLM backend

---

## 🚀 Running the Project

```bash
git clone https://github.com/Ho3pLi/atlas.git
cd atlas
pip install -r requirements.txt
python main.py
```

---

## ✨ Current Status

- ✅ Working speech recognition and synthesis
- ✅ Voice input collection for meal preferences
- 🔄 Meal plan generation (`askForMeal`) prepared but commented out
- 🕒 Project temporarily paused – documentation ready for future development

---

## 📧 Support

For support or questions: **daniele.barile.lavoro@gmail.com**  
Or open an issue on GitHub.

---

## 📄 License

[GPL v3](https://choosealicense.com/licenses/gpl-3.0/)

---

## 👤 Author

- [@Ho3pLi](https://www.github.com/Ho3pLi)
