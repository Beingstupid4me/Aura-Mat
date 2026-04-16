// #include <Wire.h>
// #include <Adafruit_PN532.h>

// #define SDA_PIN 21
// #define SCL_PIN 22

// Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);

// void setup(void) {
//   Serial.begin(115200);
//   nfc.begin();
//   nfc.SAMConfig();
//   Serial.println("Aura System: Online. Waiting for Story Cube...");
// }

// void loop(void) {
//   uint8_t success;
//   uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
//   uint8_t uidLength; 

//   success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength);
  
//   if (success) {
//     // We print the UID in a simple format for Python to read
//     Serial.print("TAG_ID:");
//     for (uint8_t i=0; i < uidLength; i++) {
//       Serial.print(uid[i], HEX);
//     }
//     Serial.println(""); 
//     delay(2000); // Wait 2 seconds so it doesn't spam the AI
//   }
// }

// #include "Arduino.h"
// #include "WiFi.h"
// #include "Audio.h"

// #define I2S_DOUT 4
// #define I2S_BCLK 15
// #define I2S_LRC  2

// Audio audio;

// String ssid = "Harshit";
// String password = "87654321";

// void setup() {
//   Serial.begin(115200);

//   WiFi.disconnect();
//   WiFi.mode(WIFI_STA);
//   WiFi.begin(ssid.c_str(), password.c_str());

//   while (WiFi.status() != WL_CONNECTED) {
//     delay(500);
//     Serial.print(".");
//   }

//   Serial.println("\nWiFi Connected!");

//   audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
//   audio.setVolume(70);

//   // audio.connecttohost("http://icecast.omroep.nl/radio1-bb-mp3");
//   audio.connecttospeech("Hello testing audio output", "en");
// }

// void loop() {
//   audio.loop();
// }

// #include <Arduino.h>
// #include <driver/i2s.h>

// // Your specific pin setup
// #define I2S_WS  27
// #define I2S_SD  26
// #define I2S_SCK 14

// // Use I2S Port 0
// #define I2S_PORT I2S_NUM_0

// // Buffer settings
// #define bufferLen 64
// int16_t sBuffer[bufferLen];

// void setup() {
//   Serial.begin(115200);
  
//   // 1. I2S Configuration
//   const i2s_config_t i2s_config = {
//     .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX), // Receive mode, ESP32 is Master
//     .sample_rate = 44100,
//     .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
//     .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,       // Matches L/R -> GND
//     .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
//     .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
//     .dma_buf_count = 8,
//     .dma_buf_len = bufferLen,
//     .use_apll = false
//   };

//   // 2. Pin Configuration
//   const i2s_pin_config_t pin_config = {
//     .bck_io_num = I2S_SCK,
//     .ws_io_num = I2S_WS,
//     .data_out_num = I2S_PIN_NO_CHANGE, 
//     .data_in_num = I2S_SD
//   };

//   // 3. Install and start driver
//   esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
//   if (err != ESP_OK) {
//     Serial.printf("Failed to install driver: %d\n", err);
//     while (true);
//   }

//   err = i2s_set_pin(I2S_PORT, &pin_config);
//   if (err != ESP_OK) {
//     Serial.printf("Failed to set pins: %d\n", err);
//     while (true);
//   }

//   i2s_start(I2S_PORT);
//   Serial.println("I2S started successfully");
// }

// void loop() {
//   size_t bytesIn = 0;
//   int16_t sample;
//   int32_t maxSample = -32768;
//   int32_t minSample = 32767;

//   // Read a chunk of samples
//   esp_err_t result = i2s_read(I2S_PORT, &sBuffer, sizeof(sBuffer), &bytesIn, portMAX_DELAY);

//   if (result == ESP_OK) {
//     int samplesRead = bytesIn / 2;
//     for (int i = 0; i < samplesRead; i++) {
//       sample = sBuffer[i];
//       if (sample > maxSample) maxSample = sample;
//       if (sample < minSample) minSample = sample;
//     }

//     // Calculate the "volume" (peak-to-peak)
//     int32_t peakToPeak = maxSample - minSample;

//     // Only print if there is a significant volume (filters out background noise)
//     // You can adjust '500' based on your room's noise level
//     if (peakToPeak > 500) {
//       Serial.print("Sound Detected! Level: ");
//       Serial.println(peakToPeak);
//     }
//   }
// }

#include <Arduino.h>
#include <driver/i2s.h>

// Speaker Pins
#define I2S_DOUT      4
#define I2S_BCLK     15
#define I2S_LRC       2

#define I2S_PORT I2S_NUM_0

void setup() {
  // We use a very high baud rate to handle the audio data stream
  Serial.begin(921600); 

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 22050, // We will send 22.05kHz audio from Python
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCLK,
    .ws_io_num = I2S_LRC,
    .data_out_num = I2S_DOUT,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

void loop() {
  if (Serial.available() > 0) {
    // Read serial data into a buffer
    uint8_t serialBuf[512];
    size_t bytesRead = Serial.readBytes(serialBuf, sizeof(serialBuf));
    
    // We need to convert 8-bit serial data to 16-bit for the I2S DAC
    int16_t i2sBuf[512];
    for (int i = 0; i < bytesRead; i++) {
      // Map 0-255 uint8 to -32768 to 32767 int16
      i2sBuf[i] = (int16_t)((serialBuf[i] - 128) << 8);
    }

    size_t bytesWritten;
    i2s_write(I2S_PORT, i2sBuf, bytesRead * 2, &bytesWritten, portMAX_DELAY);
  }
}