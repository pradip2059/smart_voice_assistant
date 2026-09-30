"""Gemini voice assistant without GPIO LEDs.

Project adaptation by Pradip Sapkota.
Based on the TechMakerAI Raspberry Pi Gemini voice chatbot project.
See LICENSE and NOTICE for attribution and licensing details.
"""

import os
from datetime import date
from io import BytesIO

import google.generativeai as genai
import speech_recognition as sr
from gtts import gTTS
from pygame import mixer

WAKE_WORD = "jack"
EXIT_PHRASE = "that's all"
LANGUAGE = "en-US"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-pro")
MAX_OUTPUT_TOKENS = 168

mixer.init()


def configure_gemini():
    """Configure Gemini using an API key stored in the environment."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Export it before starting the assistant."
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    return model, model.start_chat()


def speak_text(text):
    """Convert assistant text to speech and play it through the default output."""
    mp3_file = BytesIO()

    try:
        tts = gTTS(text=text, lang="en", tld="us")
        tts.write_to_fp(mp3_file)
        mp3_file.seek(0)

        mixer.music.load(mp3_file, "mp3")
        mixer.music.play()
        while mixer.music.get_busy():
            pass
    finally:
        mixer.music.stop()
        mp3_file.close()


def append_to_log(text):
    """Append one interaction to a date-stamped local chat log."""
    filename = f"chatlog-{date.today()}.txt"
    with open(filename, "a", encoding="utf-8") as log_file:
        log_file.write(text + "\n")


def main():
    model, chat = configure_gemini()
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 400

    sleeping = True
    print(f"Voice assistant ready. Say '{WAKE_WORD}' to wake it.")

    while True:
        try:
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Listening ...")
                audio = recognizer.listen(source, timeout=20, phrase_time_limit=30)

            text = recognizer.recognize_google(audio, language=LANGUAGE)
            request = text.lower().strip()
            print(f"Heard: {text}")

            if sleeping:
                if WAKE_WORD not in request:
                    continue

                request = request.split(WAKE_WORD, 1)[1].strip()
                sleeping = False
                append_to_log("_" * 40)
                chat = model.start_chat()

                if len(request) < 2:
                    greeting = "Hi there, how can I help?"
                    speak_text(greeting)
                    append_to_log(f"AI: {greeting}")
                    continue
            else:
                if EXIT_PHRASE in request:
                    append_to_log(f"You: {request}")
                    speak_text("Bye now")
                    append_to_log("AI: Bye now.")
                    print("Bye now")
                    sleeping = True
                    continue

                if WAKE_WORD in request:
                    request = request.split(WAKE_WORD, 1)[1].strip()

            if not request:
                continue

            append_to_log(f"You: {request}")
            print(f"You: {request}\nAI: ", end="")

            response = chat.send_message(
                request,
                stream=True,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS
                ),
            )

            response_chunks = []
            for chunk in response:
                chunk_text = getattr(chunk, "text", "")
                if not chunk_text:
                    continue
                response_chunks.append(chunk_text)
                print(chunk_text, end="", flush=True)
                speak_text(chunk_text.replace("*", ""))

            print()
            append_to_log(f"AI: {''.join(response_chunks)}")

        except sr.WaitTimeoutError:
            print("Listening timed out.")
        except sr.UnknownValueError:
            print("Speech was not understood.")
        except KeyboardInterrupt:
            print("\nAssistant stopped.")
            break
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
