#include <Wire.h>
#include <Adafruit_PN532.h>

#define SDA_PIN 33
#define SCL_PIN 32

Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);

void setup(void) {
  Serial.begin(115200);
  delay(1000); // Give the board time to wake up
  
  // Force a slower, more stable I2C speed
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); 

  Serial.println("Aura System: Initializing...");

  nfc.begin();

  uint32_t versiondata = nfc.getFirmwareVersion();
  if (! versiondata) {
    Serial.println("Error: Could not find PN532. Check wiring/power.");
    while (1) delay(10);
  }
  
  nfc.SAMConfig();
  Serial.println("Aura System: Online. Waiting for Story Cube...");
}

void loop(void) {
  uint8_t success;
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
  uint8_t uidLength; 

  // Look for a tag
  success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 500);
  
  if (success) {
    Serial.print("TAG_ID:");
    for (uint8_t i=0; i < uidLength; i++) {
      if (uid[i] < 0x10) Serial.print("0"); // Add leading zero for Python
      Serial.print(uid[i], HEX);
    }
    Serial.println(""); 
    delay(2000); 
  }
}