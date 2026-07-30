/*
  Synapse Serial LED Demo
  ------------------------
  For Arduino Uno, Nano, Mega (no WiFi needed)

  Fades an LED up and down and sends brightness data
  over USB Serial to the Synapse bridge script running
  on your computer.

  Wiring:
    Pin 9 → resistor (220Ω) → LED (+) → LED (-) → GND

  Setup:
    1. Install the Synapse library
    2. Flash this sketch to your Arduino
    3. On your computer, run:
         python3 synapse_bridge.py --port /dev/ttyUSB0 --server http://192.168.x.x:8000
       (use the correct serial port for your system)
*/

#include <Synapse.h>

const char* DEVICE_ID = "arduino-led";
const int   LED_PIN   = 9;  // must be a PWM pin on Uno/Nano

Synapse synapse(Serial, DEVICE_ID);

void setup() {
  Serial.begin(9600);
  pinMode(LED_PIN, OUTPUT);
  synapse.begin();
}

unsigned long lastEmit = 0;
int brightness = 0;
int direction  = 1;

void loop() {
  // Simple linear fade (no sin() to keep it light on Uno)
  brightness += direction * 3;
  if (brightness >= 255) { brightness = 255; direction = -1; }
  if (brightness <= 0)   { brightness = 0;   direction =  1; }

  analogWrite(LED_PIN, brightness);

  // Emit to Synapse every second via Serial bridge
  if (millis() - lastEmit >= 1000) {
    lastEmit = millis();
    float pct = (brightness / 255.0) * 100.0;
    synapse.emit("led_brightness", pct, "%");
    synapse.emit("led_pwm", brightness, "pwm");
  }

  delay(20);
}
