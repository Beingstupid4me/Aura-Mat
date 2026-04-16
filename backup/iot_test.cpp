#include <WiFi.h>
#include <WebSocketsClient.h> // Install "WebSockets" by Markus Sattler
#include <BluetoothA2DPSink.h>
#include <Adafruit_PN532.h>

// --- CONFIG ---
const char* ssid = "OnePlus_15R"; // Your WiFi SSID
const char* password = "123amartya";
const char* laptop_ip = "10.26.98.134"; // Your Laptop's Local IP

// Pins
#define I2S_DOUT 4
#define I2S_BCLK 15
#define I2S_LRC 2
#define SDA_PIN 33
#define SCL_PIN 32

BluetoothA2DPSink a2dp_sink;
Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);
WebSocketsClient webSocket;

void setup() {
    Serial.begin(115200);
    
    // 1. WiFi Connect
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.println("WiFi Connected!");

    // 2. Bluetooth Speaker Start
    i2s_pin_config_t my_pin_config = { .bck_io_num = I2S_BCLK, .ws_io_num = I2S_LRC, .data_out_num = I2S_DOUT, .data_in_num = I2S_PIN_NO_CHANGE };
    a2dp_sink.set_pin_config(my_pin_config);
    a2dp_sink.start("Aura_Story_Mat");

    // 3. WebSocket Start (Connects to Python script)
    webSocket.begin(laptop_ip, 8765, "/");
    webSocket.setReconnectInterval(5000);

    // 4. NFC Start
    nfc.begin();
    nfc.SAMConfig();
}

void loop() {
    webSocket.loop();
    
    uint8_t success;
    uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
    uint8_t uidLength; 

    success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);
    if (success) {
        String tagID = "";
        for (uint8_t i=0; i < uidLength; i++) {
            tagID += String(uid[i], HEX);
        }
        // SEND DATA VIA WIFI INSTEAD OF SERIAL
        webSocket.sendTXT(tagID); 
        delay(2000);
    }
}