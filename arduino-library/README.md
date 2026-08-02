# Synapse Arduino Library

Send sensor data from any Arduino-compatible board to the [Synapse](https://github.com/Kkmit13/synapse) embedded debugger — one line of code per reading.

## Installation

1. Download this folder as a ZIP
2. In Arduino IDE: Sketch → Include Library → Add .ZIP Library
3. Select the ZIP file
4. Done — Synapse now appears under File → Examples → Synapse

## Supported Boards

| Board | Mode | How it works |
|-------|------|-------------|
| ESP32 | WiFi | Direct HTTP POST over WiFi |
| ESP8266 | WiFi | Direct HTTP POST over WiFi |
| Arduino Nano 33 IoT | WiFi | Direct HTTP POST over WiFi |
| Arduino Uno / Nano / Mega | Serial bridge | USB → Python bridge script → Synapse |

## WiFi Mode (ESP32 / ESP8266)

```cpp
#include <WiFi.h>
#include <SynapseDebugger.h>

Synapse synapse("192.168.x.x", 8000, "my-device");

void setup() {
  WiFi.begin("wifi-name", "wifi-password");
  synapse.begin();
}

void loop() {
  synapse.emit("temperature", 24.3, "C");
  synapse.emit("humidity",    58.0, "%");
  delay(1000);
}
```

## Serial Bridge Mode (Arduino Uno / Nano / Mega)

**Step 1 — Sketch:**
```cpp
#include <Synapse.h>

Synapse synapse(Serial, "my-arduino");

void setup() {
  Serial.begin(9600);
  synapse.begin();
}

void loop() {
  synapse.emit("sensor_value", analogRead(A0), "raw");
  delay(1000);
}
```

**Step 2 — Run the bridge script on your computer:**
```bash
pip install pyserial requests
python3 synapse_bridge.py --port /dev/ttyUSB0 --server http://192.168.x.x:8000
```

Find your serial port:
- **Mac/Linux:** `ls /dev/tty.*`
- **Windows:** Device Manager → Ports (COM & LPT)

## API

```cpp
// WiFi constructor
Synapse synapse(host, port, deviceId);

// Serial constructor
Synapse synapse(Serial, deviceId);

// Call once in setup()
synapse.begin();

// Send a reading — call anywhere in your code
synapse.emit("event_name", floatValue, "unit");
synapse.emit("event_name", intValue,   "unit");
```
