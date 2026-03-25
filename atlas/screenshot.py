import logging

import atlas.config as config

def takeScreenshot():
    logging.info("Entering takeScreenshot() function...")
    logging.info(f"Taking a screenshot in {config.app.screenshot_path}...")
    try:
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()
        rgbScreenshot = screenshot.convert("RGB")
        rgbScreenshot.save(config.app.screenshot_path, quality=15)
        logging.info("Screenshot successfully saved.")
        return {"status": "ok", "path": config.app.screenshot_path, "message": "Screenshot captured successfully."}
    except OSError as exc:
        logging.warning(f"Screenshot not available: {exc}")
    except Exception as exc:
        logging.error(f"Unexpected screenshot error: {exc}")
    return {"status": "error", "path": None, "message": "I couldn't capture the screenshot."}

def visionPrompt(prompt, photoPath):
    logging.info("Entering visionPrompt() function...")
    if not photoPath:
        return None

    try:
        from PIL import Image

        img = Image.open(photoPath)
        prompt = (
            "You are the vision analysis AI that provides semantic meaning from images to provide context "
            "to send to another AI that will create a response to the user. Do not respond as the AI assistant "
            "to the user. Instead take the user prompt input and try to extract meaning from the photo "
            "relevant to the user prompt. Then generate as much objective data about the image for the AI "
            f"assistant who will respond to the user. \nUSER PROMPT: {prompt}"
        )
        response = config.get_gemini_model().generate_content([prompt, img])
        logging.info(f"Response in visionPrompt(): {response.text}")
        return response.text
    except Exception as exc:
        logging.error(f"Vision prompt failed: {exc}")
        return None
