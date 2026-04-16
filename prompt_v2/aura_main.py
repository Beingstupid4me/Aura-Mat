import serial
import os
import json
import pyaudio
from vosk import Model, KaldiRecognizer

from google import genai
from google.genai import types
from dotenv import load_dotenv
from gtts import gTTS
from playsound import playsound
import hashlib
import time
import random

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

# --- 3. TTS SETUP ---
CACHE_DIR = "tts_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def speak(text):
    try:
        clean_text = text.replace("\n", " ").strip()
        file_hash = hashlib.md5(clean_text.encode()).hexdigest()
        filename = os.path.join(CACHE_DIR, f"{file_hash}.mp3")
        if not os.path.exists(filename):
            tts = gTTS(text=clean_text, lang='en', tld='co.in', slow=False)
            tts.save(filename)
        playsound(filename)
    except Exception as e:
        print("TTS Error:", e)

# --- 4. STT SETUP ---
vosk_model = Model(r"C:\Users\AARUSHI\DAIDP\vosk-model-en-in-0.5")

def listen():
    print("\nSpeak now (or wait to type)...")
    try:
        recognizer = KaldiRecognizer(vosk_model, 16000)
        mic = pyaudio.PyAudio()
        stream = mic.open(format=pyaudio.paInt16, channels=1, rate=16000,
                          input=True, frames_per_buffer=8192)
        stream.start_stream()
        text = ""
        for _ in range(80):
            data = stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    print(f"Child said: {text}")
                    break
        stream.stop_stream()
        stream.close()
        mic.terminate()
        if text:
            return text
    except Exception as e:
        print("Mic error:", e)
    return input("Child's answer (type): ")

# --- 5. CARD MAPPINGS ---
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

# --- 6. SEED LIBRARY ---
def load_seeds():
    """Load story seeds from JSON file."""
    seed_path = os.path.join(os.path.dirname(__file__), "story_seeds.json")
    with open(seed_path, "r") as f:
        return json.load(f)["seeds"]

def pick_seed(seeds):
    """
    Randomly pick an emotional theme seed.
    Cards determine WHO and WHERE. The seed determines WHAT THE STORY IS ABOUT.
    Same card combination will never tell the same story twice.
    """
    return random.choice(seeds)

# --- 7. STORY ENGINE ---

SYSTEM_PERSONA = """You are Aura, a warm and magical storyteller for children aged 4 to 8.

YOUR STORYTELLING STYLE:
- Write like you are sitting next to the child and telling them a story. Warm, slow, and descriptive.
- Use vivid but simple sensory details (what does it smell like? what sound does it make?).
- Characters have clear, lovable personalities. Give them funny little habits or quirks.
- Sentences can vary — some short for drama, some longer and flowing for wonder.
- Never use bullet points or lists. Only flowing, spoken-word storytelling.
- Do not use emojis in the story text itself.

INTERACTION RULES:
- When the child answers, weave their exact idea into the story, even if it sounds silly or random.
  Example: if they say "a banana", make the banana appear and do something useful or funny in the story.
- Never dismiss or ignore their answer. Their choices MATTER and change the story.
- After every phase, ask ONE warm, open-ended question that invites real reflection.
  Not just "what happens next?" — ask things like:
  "Have you ever felt that way too? What did you do?"
  "What would YOU have done if you were there?"
  "Why do you think [character] was feeling scared?"

SAFETY RULES:
- No violence, fear, weapons, or dark themes.
- If a child suggests something aggressive, turn it playfully into something silly (e.g., a sword becomes a giant spoon used for a soup competition).
- Keep the tone always safe, cozy, and encouraging."""


def build_phase_1_prompt(seed, chars, places, things):
    return f"""
A new story is beginning! Here is what this story is secretly about:

EMOTIONAL THEME: {seed['theme']}
THE MORAL THIS STORY WILL ARRIVE AT NATURALLY: {seed['moral']}

The child has chosen these story ingredients:
- Characters: {', '.join(chars) if chars else 'a mystery traveller'}
- Place: {', '.join(places) if places else 'a magical land'}
- Objects or things: {', '.join(things) if things else 'something special'}

YOUR TASK - PHASE 1 (The Beginning):
Write 2 to 3 paragraphs that:
1. Invent a vivid, original world that suits these characters and place. What does it look, smell, sound like?
2. Introduce the character(s) warmly. Give them a small, funny personality detail or habit.
3. Set up that something interesting is about to happen — a letter arrives, a strange sound is heard, something is discovered.

Do NOT state the theme or moral directly. Let the story just begin naturally.

End with this warm reflection question for the child:
"{seed['reflection_hook']}"
Then follow it immediately with a simple story-choice question like "So — what do you think they should do first?"
"""

def build_phase_2_prompt(seed, things, child_answer):
    return f"""
The child said: "{child_answer}"

Remember: weave their idea naturally into the story, even if unexpected. Make their answer feel important.

YOUR TASK - PHASE 2 (The Journey Begins):
Write 2 to 3 paragraphs that:
1. Continue the story using the child's idea in a meaningful way.
2. Bring the object(s) into the story now: {', '.join(things) if things else 'something magical'}.
   Each object should have a moment — show how it looks, feels, or what it does.
3. The characters start moving toward something — a destination, a mystery, a friend who needs help.

This phase should feel like an adventure is building. Things are getting more interesting.

End with a question that invites the child to think about feelings or choices:
"How do you think [character] was feeling right now? Have you ever felt that way?"
or "If you had [object], what is the most helpful thing you would do with it?"
"""

def build_phase_3_prompt(seed, child_answer):
    return f"""
The child said: "{child_answer}"

Weave their answer into what happens next.

YOUR TASK - PHASE 3 (The Big Challenge):
This is the heart of the story. Write 3 paragraphs that:
1. Introduce the gentle problem from the story world: "{seed['gentle_problem']}"
   Make it feel real and a little bit tricky, but NEVER scary. It can be funny and frustrating at the same time.
2. Show the characters trying something that does NOT work at first.
   This is important — the first attempt fails. Why? Because the story is about the theme: "{seed['theme']}".
3. Show the characters pausing, feeling a little stuck, and starting to THINK together.

This phase should feel emotionally warm. The characters support each other even when things are hard.

End with a deep, reflective question:
"Why do you think their first try did not work?"
"What do you think they forgot to think about?"
"What would YOU do differently if you were there with them?"
"""

def build_phase_4_prompt(seed, child_answer):
    return f"""
The child said: "{child_answer}"

This is the child's big idea to solve the problem. Make their idea the HERO of this ending.

YOUR TASK - PHASE 4 (The Ending and the Lesson):
Write 3 to 4 paragraphs that:
1. Show the characters using the child's idea (plus what they have learned) to gently solve the problem.
   Make the solution feel earned — not magic that just fixes everything, but a real moment of growth.
2. Describe what happens after — how does the world feel now? What do the characters notice is different?
3. Without being preachy, let the moral arrive naturally: "{seed['moral']}"
   Show it through ACTION and FEELING, not by explaining it.
4. End the story with a warm, final reflection question that connects the story to the child's real life.

Great final questions:
"Has anyone ever helped you when you were stuck? How did that feel?"
"Is there someone in YOUR life who might need a little help today?"
"What is one kind thing you could do tomorrow, just like {seed.get('trigger_words', ['our friend'])[0]} did today?"

Then warmly tell the child the story is over and they did a wonderful job.
"""


def play_interactive_story(scanned_words):
    print("\n" + "="*50)
    print("ALL CARDS READY! STARTING THE ADVENTURE...")
    print("="*50 + "\n")

    # Sort words into categories
    chars, places, things = [], [], []
    for word in scanned_words:
        if word in word_categories["Characters"]:
            chars.append(word)
        elif word in word_categories["Places"]:
            places.append(word)
        else:
            things.append(word)

    # Pick story seed
    seeds = load_seeds()
    seed = pick_seed(seeds)
    print(f"Story world selected: '{seed['id']}' — {seed['theme']}\n")

    # System config
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PERSONA,
        temperature=0.85,  # slightly higher = more creative, less repetitive
    )

    try:
        chat = client.chats.create(model='gemini-2.5-flash', config=config)

        # --- PHASE 1: The Beginning ---
        print("Generating the beginning of your story...\n")
        prompt_1 = build_phase_1_prompt(seed, chars, places, things)
        response = chat.send_message(prompt_1)
        print("AURA:")
        print(response.text)
        speak(response.text)
        time.sleep(0.3)

        child_answer_1 = listen()

        # --- PHASE 2: The Journey ---
        print("\nContinuing the adventure...\n")
        prompt_2 = build_phase_2_prompt(seed, things, child_answer_1)
        response = chat.send_message(prompt_2)
        print("AURA:")
        print(response.text)
        speak(response.text)
        time.sleep(0.3)

        child_answer_2 = listen()

        # --- PHASE 3: The Challenge ---
        print("\nThe big challenge is coming...\n")
        prompt_3 = build_phase_3_prompt(seed, child_answer_2)
        response = chat.send_message(prompt_3)
        print("AURA:")
        print(response.text)
        speak(response.text)
        time.sleep(0.3)

        child_answer_3 = listen()

        # --- PHASE 4: The Ending ---
        print("\nWrapping up the story...\n")
        prompt_4 = build_phase_4_prompt(seed, child_answer_3)
        response = chat.send_message(prompt_4)
        print("AURA:")
        print(response.text)
        speak(response.text)
        time.sleep(0.3)

        print("\n" + "="*50)
        print("THE END!")
        print("="*50 + "\n")

    except Exception as e:
        print(f"\nOops! Something went wrong with the AI: {e}")


# --- 8. MAIN LOOP ---
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
                            print(f"Tapped: {word.upper()} ({len(collected_words)}/{CARDS_NEEDED})")

                            if len(collected_words) == CARDS_NEEDED:
                                play_interactive_story(collected_words)
                                collected_words = []
                                print("Ready for a new adventure! Tap your first card...")
                        else:
                            print(f"You already scanned {word.upper()}! Please pick a different card.")
                    else:
                        print(f"Unmapped card! The ID is: {tag_uid}")

    except serial.SerialException:
        print("Could not connect to COM11. Make sure the serial monitor is closed!")
    except KeyboardInterrupt:
        print("\nExiting Aura System. Goodbye!")


if __name__ == '__main__':
    main()
