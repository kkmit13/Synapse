/*
  Synapse Library — LED Demo (ESP32 / WiFi boards)
  -------------------------------------------------
  Fades an LED up and down using PWM and emits the
  brightness value to Synapse every second.

  Wiring:
    GPIO 13 → resistor (220Ω) → LED (+) → LED (-) → GND

  Install:
    1. Download the Synapse library folder
    2. Copy it to Documents/Arduino/libraries/Synapse/
    3. Restart Arduino IDE

  Usage:
    1. Fill in your WiFi credentials and Synapse server IP below
    2. Select your ESP32 board under Tools → Board
    3. Flash and open Serial Monitor at 115200 baud
*/

#include <WiFi.h>
#include <Synapse.h>

// ── CONFIG ─────────────────────────────────────────────
const char* WIFI_SSID    = "your-wifi-name";
const char* WIFI_PASS    = "your-wifi-password";
const char* SYNAPSE_IP   = "192.168.x.x";   // IP of the machine running Synapse
const int   SYNAPSE_PORT = 8000;
const char* DEVICE_ID    = "esp32-led";
// ───────────────────────────────────────────────────────

const int LED_PIN  = 13;
const int PWM_CH   = 0;
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;      // 8-bit: 0-255

Synapse synapse(SYNAPSE_IP, SYNAPSE_PORT, DEVICE_ID);

void setup() {
  Serial.begin(115200);

  ledcSetup(PWM_CH, PWM_FREQ, PWM_RES);
  ledcAttachPin(LED_PIN, PWM_CH);

  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  synapse.begin();
}

unsigned long lastEmit = 0;
float angle = 0.0;

void loop() {
  // Smooth sine-wave fade
  angle += 0.05;
  if (angle > TWO_PI) angle -= TWO_PI;

  int brightness = (int)((sin(angle) + 1.0) / 2.0 * 255);
  ledcWrite(PWM_CH, brightness);

  // Emit to Synapse every second
  if (millis() - lastEmit >= 1000) {
    lastEmit = millis();
    float pct = (brightness / 255.0) * 100.0;
    synapse.emit("led_brightness", pct, "%");
    synapse.emit("led_pwm", brightness, "pwm");
  }

  delay(20);
}
