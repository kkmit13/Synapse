# Synapse

A debugging tool for embedded systems projects. Connect your Arduino, ESP32, or Raspberry Pi and see all your sensor data in real time, along with an AI that watches for actual hardware faults.

## What it does

- Real-time event feed from all connected devices
- Multi-device timeline with zoom and click to inspect any reading
- AI anomaly detection that runs every 15 seconds and looks for anything that could be an issue (anomalies)
- Snooze and feedback system so you can tell the AI what's normal for your project and it stops flagging it
- Works with Raspberry Pi over I2C, ESP32/ESP8266 over WiFi, and Arduino Uno/Nano/Mega over USB serial
- Runs entirely on your local network

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Kkmit13/synapse
cd synapse
```

### 2. Start the server

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the `server` folder with your Anthropic API key:

ANTHROPIC_API_KEY=your-key-here


Then run the server. Use `--host 0.0.0.0` so other devices on your network can reach it:

```bash
uvicorn main:app --reload --host 0.0.0.0
```

### 3. Start the dashboard

```bash
cd dashboard
npm install
npm start
```

### 4. Find your server's local IP

You'll need this to point your devices at the server.

Mac: `ipconfig getifaddr en0`
Windows: `ipconfig` and look for IPv4 address
Linux: `hostname -I`

## Connecting a device

### Raspberry Pi

Edit `pi-agent/synapse_config.yaml` with your server IP, device name, and the sensors you have wired up. No Python knowledge needed, it's a plain config file.

```bash
cd pi-agent
pip3 install pyyaml adafruit-circuitpython-bme280 adafruit-circuitpython-bh1750 requests
python3 synapse_agent.py
```

Currently supports BME280 and BH1750 out of the box. To add a new sensor type, add a loader function to `synapse_agent.py`.

### ESP32 / ESP8266

Install the SynapseDebugger library through Arduino IDE: Tools → Manage Libraries → search "SynapseDebugger" → Install.

```cpp
#include <WiFi.h>
#include <Synapse.h>

Synapse synapse("192.168.x.x", 8000, "my-device");

void setup() {
  WiFi.begin("wifi-name", "wifi-password");
  while (WiFi.status() != WL_CONNECTED) delay(500);
  synapse.begin();
}

void loop() {
  synapse.emit("temperature", 24.3, "C");
  delay(1000);
}
```

### Arduino Uno / Nano / Mega

These boards don't have WiFi, so they send data over USB to a bridge script running on your computer, which forwards it to Synapse.

Install SynapseDebugger the same way as above, then flash:

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

Then on your computer, run the bridge:

```bash
pip install pyserial requests
python3 pi-agent/synapse_bridge.py --port /dev/ttyUSB0 --server http://192.168.x.x:8000
```

Find your port with `ls /dev/tty.*` on Mac/Linux or Device Manager on Windows.

## Improving AI accuracy with metadata

Every `emit()` call can optionally include a `role` and `behavior` so the AI knows what your sensor actually represents instead of guessing from raw numbers.

```cpp
// Basic
synapse.emit("motor_rpm", 1200.4, "RPM");

// With metadata
synapse.emit("motor_rpm", 1200.4, "RPM", "motor_rpm", "variable");
```

**role** examples: `motor_rpm`, `motor_current`, `battery_voltage`, `power_rail`, `ambient_temperature`, `ambient_humidity`, `ambient_light`, `heap_memory`, `wifi_signal`

**behavior** options: `stable`, `variable`, `cyclic`, `increasing`, `decreasing`

For the Pi agent, role and behavior are set per sensor reading directly in `synapse_config.yaml`, no code changes needed.

## Using the dashboard

- **Feed tab** shows every event as it arrives
- **Timeline tab** shows all devices on a synchronized timeline, click any marker for details
- **Anomalies button** opens the anomaly log. Each detected fault can be snoozed (stop flagging this specific issue this session) or marked with feedback (real issue or false positive), which the AI uses on its next check
- **Synapse AI button** opens a chat panel where you can ask questions about your data directly
- **Clear button** wipes all events, anomalies, and feedback to start a fresh session

## Arduino Library

SynapseDebugger is available in the Arduino Library Manager, search "SynapseDebugger" to install.

Library source: https://github.com/Kkmit13/synapse-arduino
