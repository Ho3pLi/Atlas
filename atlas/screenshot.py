import logging
from PIL import ImageGrab, Image

from atlas.config import model

def takeScreenshot():
    path = f'screenshot.png'
    logging.info(f"Taking a screenshot in {path}...")
    screenshot = ImageGrab.grab()
    rgbScreenshot = screenshot.convert('RGB')
    rgbScreenshot.save(path, quality=15)
    logging.info("Screenshot successfully saved.")

def visionPrompt(prompt, photoPath):
    img = Image.open(photoPath)
    prompt = (
        'You are the vision analysis AI that provides semtantic meaning from images to provide context '
        'to send to another AI that will create a response to the user. Do not respond as the AI assistant '
        'to the user. Instead take the user prompt input and try to extract meaning from the photo '
        'relevant to the user prompt. Then generate as much objective data about the image for the AI '
        f'assistant who will respond to the user. \nUSER PROMPT: {prompt}'
    )
    response = model.generate_content([prompt, img])
    return response.text