#include <Arduino.h>
#include "BluetoothA2DPSink.h"
#include <Adafruit_PN532.h>
#include "soc/soc.h"           // For Brownout protection
#include "soc/rtc_cntl_reg.h"  // For Brownout protection

// --- PINS ---
#define I2S_DOUT 4
#define I2S_BCLK 15
#define I2S_LRC 2
#define SDA_PIN 33
#define SCL_PIN 32

BluetoothA2DPSink a2dp_sink;
Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 
    Serial.begin(115200);
    delay(1000);

    // 1. STABLE I2C
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(50000); 
    
    nfc.begin();
    nfc.SAMConfig();

    // 2. I2S PINS
    i2s_pin_config_t my_pin_config = { 
        .bck_io_num = I2S_BCLK, 
        .ws_io_num = I2S_LRC, 
        .data_out_num = I2S_DOUT, 
        .data_in_num = I2S_PIN_NO_CHANGE 
    };
    a2dp_sink.set_pin_config(my_pin_config);

    // 3. STARTUP TONE (Diagnostic)
    // This forces sound through the wires before Bluetooth starts
    Serial.println("TESTING_SPEAKER_HARDWARE...");
    const i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 44100,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .dma_buf_count = 8,
        .dma_buf_len = 64
    };
    i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &my_pin_config);
    
    int16_t sample = 5000;
    size_t written;
    for(int i = 0; i < 5000; i++) {
        sample = (i % 20 < 10) ? 5000 : -5000;
        i2s_write(I2S_NUM_0, &sample, 2, &written, portMAX_DELAY);
    }
    i2s_driver_uninstall(I2S_NUM_0); // Release for Bluetooth
    
    // 4. START BLUETOOTH
    a2dp_sink.start("Aura_Story_Mat");
    Serial.println("SYSTEM_STATUS:AURA_READY");
}

void loop() {
    uint8_t success;
    uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
    uint8_t uidLength; 

    // We use a short 50ms timeout to keep the Bluetooth loop smooth
    success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 50);
    
    if (success) {
        // Send the tag data to your laptop via the USB CABLE
        Serial.print("TAG_ID:");
        for (uint8_t i=0; i < uidLength; i++) {
            if (uid[i] < 0x10) Serial.print("0");
            Serial.print(uid[i], HEX);
        }
        Serial.println(""); 
        
        delay(2000); // Prevent duplicate triggers
    }
}