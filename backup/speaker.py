import serial
from playsound import playsound
import time

# Ensure this matches your ESP32's COM port
ser = serial.Serial('COM4', 115200, timeout=1)

# Clear the "boot-up garbage" before we start
ser.flushInput()

print("Aura BT System Ready... Waiting for Cube.")

while True:
    try:
        if ser.in_waiting > 0:
            # Added errors='ignore' to prevent the UnicodeDecodeError
            raw_data = ser.readline()
            line = raw_data.decode('utf-8', errors='ignore').strip()
            
            if "TAG_ID:" in line:
                tag_id = line.split(":")[1]
                print(f"Cube Detected: {tag_id}")
                
                print("Playing audio via Bluetooth...")
                # Note: Windows must be paired with "Aura_Story_Speaker" 
                # and set as the 'Default Output' for this to work.
                playsound("gadi_wala_aaya.mp3") 
                
    except Exception as e:
        # This catches any other random errors without crashing the script
        print(f"Serial Error: {e}")
        
    time.sleep(0.1)