import logging

import atlas.config as config


def takeScreenshot():
    logging.info("Entering takeScreenshot() function...")
    logging.info(f"Taking a screenshot in {config.app.screenshot_path}...")
    try:
        from PIL import ImageGrab

        with ImageGrab.grab() as screenshot:
            with screenshot.convert("RGB") as rgb_screenshot:
                rgb_screenshot.save(config.app.screenshot_path, quality=15)
        logging.info("Screenshot successfully saved.")
        return {
            "status": "ok",
            "path": config.app.screenshot_path,
            "message": "Screenshot captured successfully.",
        }
    except OSError as exc:
        logging.warning("Screenshot not available (%s)", type(exc).__name__)
    except Exception as exc:
        logging.error("Unexpected screenshot error (%s)", type(exc).__name__)
    return {
        "status": "error",
        "path": None,
        "message": "Non sono riuscito a catturare lo screenshot.",
    }


def visionPrompt(prompt, photoPath):
    logging.info("Entering visionPrompt() function...")
    if not photoPath:
        return None

    try:
        from PIL import Image

        prompt = (
            "You are the vision analysis AI that provides semantic meaning from images to provide context "
            "to send to another AI that will create a response to the user. Do not respond as the AI assistant "
            "to the user. Instead take the user prompt input and try to extract meaning from the photo "
            "relevant to the user prompt. Then generate as much objective data about the image for the AI "
            f"assistant who will respond to the user. \nUSER PROMPT: {prompt}"
        )
        with Image.open(photoPath) as img:
            response = config.get_gemini_model().generate_content([prompt, img])
        logging.info("Vision analysis completed.")
        return response.text
    except Exception as exc:
        logging.error("Vision prompt failed (%s)", type(exc).__name__)
        return None
