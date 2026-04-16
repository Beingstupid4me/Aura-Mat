This is a comprehensive **Technical Roadmap and Plan Document** designed for you to hand over to an AI agent (like ChatGPT, Claude, or a specialized coding agent) to build the software stack for **Aura: The Story Mat**.

---

# 📜 Project Plan: Aura - Interactive AI Story Mat

## 1. Project Overview
**Aura** is a screen-free interactive storytelling toy for children.
*   **Physical Interaction:** A child places 3-5 "Story Cubes" (NFC tags) on a sensing mat.
*   **Backend Logic:** A laptop receives these Tag IDs via Serial (USB), maps them to characters/items, and uses **Google Gemini AI** to generate a personalized, reflective story.
*   **Audio Output:** The story is converted to speech (TTS) on the laptop and played through the ESP32’s 3W speaker via **Bluetooth A2DP**.
*   **Visual Dashboard:** A local web frontend shows real-time progress (cards detected, story being written, etc.).

## 2. Hardware Context (Already Functional)
*   **Controller:** ESP32 (DevKit V1).
*   **NFC Reader:** PN532 (I2C Mode, Pins 32/33).
*   **Audio Amp:** MAX98357A I2S Amp (Pins 4, 15, 2).
*   **Power:** Dual-rail (Laptop USB for ESP32/NFC; External 5V for Amp).
*   **Current ESP32 State:** Firmware is flashed. It acts as a BT Speaker and sends `TAG_ID:XXXXXXXX` strings over Serial at 115200 baud.

## 3. Software Stack Requirements
*   **Language:** Python 3.10+
*   **Backend Framework:** Flask or FastAPI.
*   **Real-time Communication:** Flask-SocketIO (to push Tag IDs to the UI).
*   **AI Engine:** `google-generativeai` (Gemini 1.5 Flash).
*   **Audio Pipeline:** `gTTS` (Google Text-to-Speech) or `pyttsx3`.
*   **Audio Playback:** `playsound` or `pygame`.
*   **Serial Communication:** `pyserial`.

---

## 4. Implementation Roadmap

### Phase 1: Data Mapping & Environment
*   **Goal:** Map raw Hexadecimal Tag IDs to human-readable names.
*   **Task:** Create a JSON dictionary of Tag IDs (e.g., `{"61DD0007": "Princess", "FD23596B": "Dragon"}`).
*   **Task:** Setup environment variables for the Gemini API Key.

### Phase 2: The Multi-Threaded Backend
*   **Goal:** Handle Serial data without freezing the Web Server.
*   **Task:** Implement a background thread in Python that constantly monitors the COM port.
*   **Task:** When a `TAG_ID` is detected, emit a SocketIO event to the frontend.

### Phase 3: The AI Story Orchestrator
*   **Goal:** Turn a list of tags into a "Reflective Narrative."
*   **Task:** Design a "System Prompt" for Gemini that:
    1.  Writes for a 5-year-old.
    2.  Is exactly 3-4 sentences long.
    3.  Includes a "Reflective Question" at the end (e.g., "How do you think the Dragon felt?").
*   **Task:** Implement the Gemini API call and save the response.

### Phase 4: Audio Execution
*   **Goal:** Speak the story through the Bluetooth link.
*   **Task:** Pass the Gemini text to a TTS engine.
*   **Task:** Play the resulting audio file. *Note: Since the laptop is paired to the ESP32 via Bluetooth, Python’s standard audio output will automatically route to the Story Mat.*

### Phase 5: The Frontend Dashboard (MVP UI)
*   **Goal:** Provide visual feedback for the "Internal Working."
*   **Task:** Create a single-page HTML/JS dashboard.
*   **Features:**
    *   **Slot View:** 3-5 empty slots that fill up with icons/names as cards are scanned.
    *   **Generation Pulse:** A visual "thinking" indicator while the AI works.
    *   **Transcript:** The story text appearing word-by-word on screen.


## 6. Design Constraints
*   **No Blocking:** The Serial listener must not block the Flask server.
*   **Debouncing:** If a tag is held on the mat, don't trigger the AI 100 times; wait for 3 *unique* tags.
*   **UI Style:** Minimalist, clean, and magical (using CSS animations or transitions).