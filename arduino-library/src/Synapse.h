#ifndef SYNAPSE_H
#define SYNAPSE_H

#include <Arduino.h>

// ── Auto-detect board type ───────────────────────────────────────────────────
// This lets the same library work on ESP32, ESP8266, and Arduino WiFi boards
// without the user having to change anything.

#if defined(ESP32)
  #include <WiFi.h>
  #include <HTTPClient.h>
  #define SYNAPSE_WIFI_ESP32
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
  #define SYNAPSE_WIFI_ESP8266
#elif defined(ARDUINO_SAMD_NANO_33_IOT) || defined(ARDUINO_SAMD_MKRWIFI1010)
  #include <WiFiNINA.h>
  #include <ArduinoHttpClient.h>
  #define SYNAPSE_WIFI_NINA
#endif

// ── WiFi mode ────────────────────────────────────────────────────────────────
#if defined(SYNAPSE_WIFI_ESP32) || defined(SYNAPSE_WIFI_ESP8266) || defined(SYNAPSE_WIFI_NINA)

class Synapse {
public:
  // WiFi constructor — pass server IP and port
  Synapse(const char* host, int port, const char* deviceId);

  // Call in setup() after WiFi.begin()
  void begin();

  void emit(const char* eventName, float value, const char* unit = "");
  void emit(const char* eventName, int value,   const char* unit = "");

private:
  const char* _host;
  int         _port;
  const char* _deviceId;
  void _post(const char* eventName, String value, const char* unit);
};

// ── Serial mode ──────────────────────────────────────────────────────────────
// For boards without WiFi (Uno, Nano, Mega).
// Sends a compact CSV line over Serial that the bridge script reads and forwards.
#else

class Synapse {
public:
  // Serial constructor — pass the Serial port and device ID
  Synapse(HardwareSerial& serial, const char* deviceId);

  // Call in setup() — just initializes the serial port label
  void begin();

  void emit(const char* eventName, float value, const char* unit = "");
  void emit(const char* eventName, int value,   const char* unit = "");

private:
  HardwareSerial& _serial;
  const char*     _deviceId;
  void _send(const char* eventName, String value, const char* unit);
};

#endif
#endif // SYNAPSE_H
