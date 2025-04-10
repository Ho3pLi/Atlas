import logging
from PIL import ImageGrab, Image

from atlas.config import model, screenshotPath

def takeScreenshot():
    logging.info('Entering takeScreenshot() function...')
    logging.info(f"Taking a screenshot in {screenshotPath}...")
    try:
        screenshot = ImageGrab.grab()
    except OSError as e:
        logging.warning(f"Screenshot not avaible: {e}")
        return None

    rgbScreenshot = screenshot.convert('RGB')
    rgbScreenshot.save(screenshotPath, quality=15)
    logging.info("Screenshot successfully saved.")
    return True

def visionPrompt(prompt, photoPath):
    logging.info('Entering visionPrompt() function...')
    if photoPath:
        img = Image.open(photoPath)
        prompt = (
            'You are the vision analysis AI that provides semtantic meaning from images to provide context '
            'to send to another AI that will create a response to the user. Do not respond as the AI assistant '
            'to the user. Instead take the user prompt input and try to extract meaning from the photo '
            'relevant to the user prompt. Then generate as much objective data about the image for the AI '
            f'assistant who will respond to the user. \nUSER PROMPT: {prompt}'
        )
        response = model.generate_content([prompt, img])
        logging.info(f'Response in visionPrompt(): {response.text}')
        return response.text
    else:
        return None