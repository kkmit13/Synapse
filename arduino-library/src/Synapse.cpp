#include "Synapse.h"

// ── WiFi mode implementation (ESP32 / ESP8266 / Arduino WiFi) ────────────────

#if defined(SYNAPSE_WIFI_ESP32) || defined(SYNAPSE_WIFI_ESP8266) || defined(SYNAPSE_WIFI_NINA)

Synapse::Synapse(const char* host, int port, const char* deviceId) {
  _host     = host;
  _port     = port;
  _deviceId = deviceId;
}

void Synapse::begin() {
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[Synapse] WiFi connected. Server: http://");
    Serial.print(_host);
    Serial.print(":");
    Serial.println(_port);
  } else {
    Serial.println("[Synapse] WARNING: WiFi not connected — emits will be skipped.");
  }
}

void Synapse::emit(const char* eventName, float value, const char* unit) {
  _post(eventName, String(value, 3), unit);
}

void Synapse::emit(const char* eventName, int value, const char* unit) {
  _post(eventName, String(value), unit);
}

void Synapse::_post(const char* eventName, String value, const char* unit) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Synapse] Skipping emit — WiFi not connected.");
    return;
  }

  String url = String("http://") + _host + ":" + _port + "/event";

  // Build JSON payload without any external library
  String payload = "{";
  payload += "\"device_id\":\""     + String(_deviceId)           + "\",";
  payload += "\"event_name\":\""    + String(eventName)           + "\",";
  payload += "\"value\":"           + value                       + ",";
  payload += "\"unit\":\""          + String(unit)                + "\",";
  payload += "\"device_timestamp\":" + String(millis() / 1000.0, 3);
  payload += "}";

#if defined(SYNAPSE_WIFI_ESP32)
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code > 0) {
    Serial.print("[Synapse] ");
    Serial.print(eventName);
    Serial.print(": ");
    Serial.print(value);
    Serial.print(" ");
    Serial.print(unit);
    Serial.print(" → HTTP ");
    Serial.println(code);
  } else {
    Serial.print("[Synapse] POST failed: ");
    Serial.println(http.errorToString(code));
  }
  http.end();

#elif defined(SYNAPSE_WIFI_ESP8266)
  WiFiClient client;
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code > 0) {
    Serial.print("[Synapse] ");
    Serial.print(eventName);
    Serial.print(": ");
    Serial.print(value);
    Serial.print(" ");
    Serial.print(unit);
    Serial.print(" → HTTP ");
    Serial.println(code);
  } else {
    Serial.print("[Synapse] POST failed: ");
    Serial.println(http.errorToString(code));
  }
  http.end();

#elif defined(SYNAPSE_WIFI_NINA)
  HttpClient http(WiFiClient(), _host, _port);
  http.post("/event", "application/json", payload);
  Serial.print("[Synapse] ");
  Serial.print(eventName);
  Serial.print(": ");
  Serial.print(value);
  Serial.print(" ");
  Serial.println(unit);
  http.stop();
#endif
}

// ── Serial mode implementation (Uno / Nano / Mega) ───────────────────────────
// Sends one CSV line per emit: SYNAPSE,device_id,event_name,value,unit,timestamp
// The bridge script reads this and POSTs it to the Synapse server.

#else

Synapse::Synapse(HardwareSerial& serial, const char* deviceId)
  : _serial(serial), _deviceId(deviceId) {}

void Synapse::begin() {
  // Serial should already be initialized by the user's setup()
  // Just print a confirmation so they know it's ready
  _serial.println("[Synapse] Serial mode ready. Run synapse_bridge.py on your computer.");
}

void Synapse::emit(const char* eventName, float value, const char* unit) {
  _send(eventName, String(value, 3), unit);
}

void Synapse::emit(const char* eventName, int value, const char* unit) {
  _send(eventName, String(value), unit);
}

void Synapse::_send(const char* eventName, String value, const char* unit) {
  // Format: SYNAPSE,device_id,event_name,value,unit,millis
  // Prefix "SYNAPSE," lets the bridge ignore other Serial.println() debug output
  _serial.print("SYNAPSE,");
  _serial.print(_deviceId);
  _serial.print(",");
  _serial.print(eventName);
  _serial.print(",");
  _serial.print(value);
  _serial.print(",");
  _serial.print(unit);
  _serial.print(",");
  _serial.println(millis());
}

#endif
