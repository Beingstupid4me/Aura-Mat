#include "BluetoothA2DPSink.h"
#include <Adafruit_PN532.h>
#include "soc/soc.h"           // Added for power management
#include "soc/rtc_cntl_reg.h"  // Added for power management

#define I2S_DOUT      4
#define I2S_BCLK     15
#define I2S_LRC       2
#define SDA_PIN 33
#define SCL_PIN 32

BluetoothA2DPSink a2dp_sink;
Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);

void setup() {
    // 1. DISABLE BROWNOUT (Stops the crashing)
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 
    
    Serial.begin(115200);
    delay(2000); // Wait for power to stabilize

    // 2. Setup Bluetooth Speaker
    i2s_pin_config_t my_pin_config = {
        .bck_io_num = I2S_BCLK,
        .ws_io_num = I2S_LRC,
        .data_out_num = I2S_DOUT,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    a2dp_sink.set_pin_config(my_pin_config);
    
    // Set volume to 180 (about 70%) to save power
    a2dp_sink.set_volume(180); 
    a2dp_sink.start("Aura_Story_Speak");
    Serial.println("Bluetooth Speaker Active.");

    delay(2000); // Wait before starting NFC

    // 3. Setup NFC
    Serial.println("Starting NFC...");
    nfc.begin();
    uint32_t versiondata = nfc.getFirmwareVersion();
    if (!versiondata) {
        Serial.println("NFC NOT FOUND - Check SDA/SCL wires!");
    } else {
        nfc.SAMConfig();
        Serial.println("NFC System Online!");
    }
}

void loop() {
    uint8_t success;
    uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
    uint8_t uidLength; 

    // Look for a tag
    success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);
    
    if (success) {
        Serial.print("TAG_ID:");
        for (uint8_t i=0; i < uidLength; i++) {
            if (uid[i] < 0x10) Serial.print("0");
            Serial.print(uid[i], HEX);
        }
        Serial.println(""); 
        delay(2000); 
    }
}