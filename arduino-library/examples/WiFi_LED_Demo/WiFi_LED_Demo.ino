/*
  Synapse WiFi LED Demo
  ----------------------
  For ESP32, ESP8266, Arduino Nano 33 IoT

  Fades an LED up and down and streams brightness
  data live to the Synapse dashboard.

  Wiring:
    GPIO 13 → resistor (220Ω) → LED (+) → LED (-) → GND

  Setup:
    1. Install the Synapse library (Sketch → Include Library → Add .ZIP Library)
    2. Fill in your WiFi credentials and Synapse server IP below
    3. Select your board and flash
*/

#include <WiFi.h>
#include <Synapse.h>

// ── CONFIG ──────────────────────────────────────────────
const char* WIFI_SSID    = "your-wifi-name";
const char* WIFI_PASS    = "your-wifi-password";
const char* SYNAPSE_IP   = "192.168.x.x";   // your computer's local IP
const int   SYNAPSE_PORT = 8000;
const char* DEVICE_ID    = "esp32-led";
// ────────────────────────────────────────────────────────

const int LED_PIN  = 13;
const int PWM_CH   = 0;
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;

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
  // Smooth sine wave fade
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
