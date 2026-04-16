import asyncio
import websockets
from playsound import playsound
import os

# --- 1. SETTINGS ---
# Use "0.0.0.0" to listen to all devices on your WiFi network
LISTENING_IP = "0.0.0.0"
PORT = 8765
AUDIO_FILE = "gadi_wala_aaya.mp3"

async def aura_server(websocket):
    """
    This is the handler. In newer 'websockets' versions, 
    we only need the 'websocket' argument.
    """
    print(f"Aura Mat connected from: {websocket.remote_address}")
    
    try:
        async for tag_id in websocket:
            print(f"Cube Detected over WiFi: {tag_id}")
            
            # Check if the file exists before trying to play it
            if os.path.exists(AUDIO_FILE):
                print(f"Playing '{AUDIO_FILE}' via Bluetooth...")
                playsound(AUDIO_FILE)
            else:
                print(f"Error: Could not find '{AUDIO_FILE}' in the folder.")
                
    except websockets.ConnectionClosed:
        print("Aura Mat disconnected.")

async def main():
    print(f"Laptop 'Aura Brain' is listening on {LISTENING_IP}:{PORT}...")
    # The 'path' is no longer needed in newer library versions
    async with websockets.serve(aura_server, LISTENING_IP, PORT):
        await asyncio.Future()  # This keeps the server running forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Aura Brain...")