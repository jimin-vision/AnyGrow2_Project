# example_TTS.py
import pyttsx3
engine = pyttsx3.init()
engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)

def speak(text: str):
    if not text.strip():
        return
    engine.say(text)
    engine.runAndWait()