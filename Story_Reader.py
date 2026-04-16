import serial
import os
# import pyttsx3
import json
import pyaudio
from vosk import Model, KaldiRecognizer

from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- 1. SETUP ENVIRONMENT & API ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY not found. Please check your .env file!")
    exit()

client = genai.Client(api_key=API_KEY)

# --- 2. HARDWARE CONFIG ---
ESP32_PORT = 'COM11'
BAUD_RATE = 115200
CARDS_NEEDED = 5

# --- 🔊 SPEECH SETUP (ADDED ONLY) ---

# # TTS (offline)
# engine = pyttsx3.init()
# engine.setProperty('rate', 150)

# def speak(text):
#     try:
#         engine = pyttsx3.init()   # re-init every time (IMPORTANT FIX)
#         engine.setProperty('rate', 150)
#         engine.say(text)
#         engine.runAndWait()
#         engine.stop()
#     except Exception as e:
#         print("TTS Error:", e)
from gtts import gTTS
from playsound import playsound
import os
import hashlib

CACHE_DIR = "tts_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def speak(text):
    try:
        # Clean text (important for kids clarity)
        clean_text = text.replace("\n", " ").strip()

        # Create hash (same text = no regeneration)
        file_hash = hashlib.md5(clean_text.encode()).hexdigest()
        filename = os.path.join(CACHE_DIR, f"{file_hash}.mp3")

        # Generate only if not exists
        if not os.path.exists(filename):
            tts = gTTS(text=clean_text, lang='en', tld='co.in', slow=False)
            tts.save(filename)

        playsound(filename)

    except Exception as e:
        print("TTS Error:", e)
# STT (offline - Vosk)
vosk_model = Model(r"C:\Users\AARUSHI\DAIDP\vosk-model-en-in-0.5")

def listen():
    print("\n🎤 Speak now (or wait to type)...")

    try:
        recognizer = KaldiRecognizer(vosk_model, 16000)
        mic = pyaudio.PyAudio()

        stream = mic.open(format=pyaudio.paInt16,
                          channels=1,
                          rate=16000,
                          input=True,
                          frames_per_buffer=8192)

        stream.start_stream()

        text = ""

        for _ in range(80):
            data = stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    print(f"👧🏽 CHILD (voice): {text}")
                    break

        # ✅ CRITICAL FIX (release mic properly)
        stream.stop_stream()
        stream.close()
        mic.terminate()

        if text:
            return text

    except Exception as e:
        print("Mic error:", e)

    return input("👧🏽 CHILD'S ANSWER (type): ")
# --- 3. DICTIONARIES & CATEGORIES ---
card_mappings = {
    "B3B0F16": "Princess",
    "61DD07": "Castle",
    "85D950FC": "Dragon",
    "7164FD6": "Rabbit",
    "BDC4F36B": "Pencil",
    "DEAF23B": "Telephone",
    "8484A8A9": "Astronaut",
    "FD23596B": "Spaceship",
    "633ACD1D": "Moon",
    "574648B5": "Village",
    "2DE3E86B": "Magic Wand",
    "74F5A3FF": "School"
}

word_categories = {
    "Characters": ["Princess", "Dragon", "Rabbit", "Astronaut"],
    "Places": ["Castle", "Spaceship", "Village", "School"],
    "Things": ["Magic Wand", "Pencil", "Telephone", "Moon"]
}

def play_interactive_story(scanned_words):
    print("\n" + "="*50)
    print("✨ ALL TOYS READY! STARTING THE ADVENTURE... ✨")
    print("="*50 + "\n")

    chars, places, things = [], [], []
    for word in scanned_words:
        if word in word_categories["Characters"]: chars.append(word)
        elif word in word_categories["Places"]: places.append(word)
        else: things.append(word)

    str_chars = ', '.join(chars) if chars else 'None'
    str_places = ', '.join(places) if places else 'None'
    str_things = ', '.join(things) if things else 'None'

    system_persona = """You are Aura, a friendly, magical storyteller for children aged 4 to 8.
STRICT RULES:
1. Speak to a 4-year-old. Use very short sentences and basic vocabulary (like Peppa Pig or Dora).
2. NO violence, scary things, or weapons. If a child suggests violence, magically turn it into bubbles, a funny dance, or a silly joke.
3. Keep your responses to exactly 1 or 2 short paragraphs.
4. Always end your turn with ONE simple question giving the child an easy choice to make.
5. Do Not use Emojis in your stories."""

    config = types.GenerateContentConfig(
        system_instruction=system_persona,
        temperature=0.7,
    )

    try:
        chat = client.chats.create(model='gemini-2.5-flash', config=config)
        # chat = client.chats.create(model='gemini-3.1-flash-lite', config=config)
        
        # PHASE 1
        phase_1_prompt = f"""We are starting a new story! The child chose these tokens:
- Characters: {str_chars}
- Places: {str_places}
- Things: {str_things}

EXECUTE PHASE 1 (Introduction): 
Introduce yourself briefly. Write 1 paragraph introducing the characters in their place. 
End by asking the child a simple question to start the journey (e.g., "Which path should they take?")."""
        
        print("✍️ Generating Introduction...\n")
        response = chat.send_message(phase_1_prompt)
        print("🌟 AURA 🌟")
        print(response.text)
        speak(response.text)
        import time
        time.sleep(0.3)

        user_input = listen()

        # PHASE 2
        phase_2_prompt = f"""The child says: '{user_input}'. 

EXECUTE PHASE 2 (Development):
Use their answer (There may be some uncontextual words, try to relate them with the question asked ) to continue the story. Bring the "Things" ({str_things}) into the story now. 
Write 1 short paragraph. End by asking the child a question about how to use one of the items."""

        print("\n✍️ Generating Development...\n")
        response = chat.send_message(phase_2_prompt)
        print("🌟 AURA 🌟")
        print(response.text)
        speak(response.text)
        import time
        time.sleep(0.3)
        user_input = listen()

        # PHASE 3
        phase_3_prompt = f"""The child says: '{user_input}'. 

EXECUTE PHASE 3 (The Challenge):
Introduce a very gentle, silly problem (e.g., a path is blocked by a sleeping turtle, or someone lost their hat). 
Write 1 short paragraph. Ask the child: "How can our friends solve this problem using teamwork or kindness?"""

        print("\n✍️ Generating Challenge...\n")
        response = chat.send_message(phase_3_prompt)
        print("🌟 AURA 🌟")
        print(response.text)
        speak(response.text)
        import time
        time.sleep(0.3)

        user_input = listen()

        # PHASE 4
        phase_4_prompt = f"""The child says: '{user_input}'. 

EXECUTE PHASE 4 (Conclusion):
Use their kind solution to fix the silly problem. Write 1 to 2 paragraphs wrapping up the story. 
Include a gentle moral (like sharing or bravery). Tell them they did a great job and the story is finished."""

        print("\n✍️ Generating Conclusion...\n")
        response = chat.send_message(phase_4_prompt)
        print("🌟 AURA 🌟")
        print(response.text)
        speak(response.text)
        import time
        time.sleep(0.3)

        print("\n" + "="*50)
        print("✨ THE END! ✨")
        print("="*50 + "\n")

    except Exception as e:
        print(f"\n❌ Oops! Something went wrong with the AI: {e}")

def main():
    try:
        ser = serial.Serial(ESP32_PORT, BAUD_RATE, timeout=1)
        print(f"Connected! Aura System is ready.")
        print(f"Tap {CARDS_NEEDED} cards to create your story...")
        
        collected_words = []

        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                
                if line.startswith("TAG_ID:"):
                    tag_uid = line.split(":")[1] 
                    
                    if tag_uid in card_mappings:
                        word = card_mappings[tag_uid]
                        
                        if word not in collected_words:
                            collected_words.append(word)
                            print(f"🪄 Tapped: {word.upper()} ({len(collected_words)}/{CARDS_NEEDED})")
                            
                            if len(collected_words) == CARDS_NEEDED:
                                play_interactive_story(collected_words)
                                collected_words = []
                                print("Ready for a new adventure! Tap your first card...")
                        else:
                            print(f"⚠️ You already scanned {word.upper()}! Please pick a different card.")
                            
                    else:
                        print(f"Unmapped card! The ID is: {tag_uid}")

    except serial.SerialException:
        print("Could not connect to COM11. Make sure the serial monitor is closed!")
    except KeyboardInterrupt:
        print("\nExiting Aura System. Goodbye!")

if __name__ == '__main__':
    main()