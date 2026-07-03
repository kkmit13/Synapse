"""
Synapse - Device Simulator
Pretends to be a Raspberry Pi with a BME280 and BH1750 sensor,
firing realistic fake readings at the server every second.
"""

import requests
import time
import random
import math

SERVER = "http://127.0.0.1:8000"
DEVICE_ID = "pi-1"

def emit(event_name, value, unit=None):
    payload = {
        "device_id": DEVICE_ID,
        "event_name": event_name,
        "value": round(value, 2),
        "unit": unit,
        "device_timestamp": time.time()
    }
    try:
        r = requests.post(f"{SERVER}/event", json=payload)
        print(f"  → {event_name}: {round(value,2)} {unit or ''}")
    except Exception as e:
        print(f"  ✗ Failed to send {event_name}: {e}")

def simulate():
    print(f"Synapse Simulator — sending as '{DEVICE_ID}' to {SERVER}")
    print("Press Ctrl+C to stop.\n")

    tick = 0
    base_temp = 22.0
    base_lux = 300.0
    base_humidity = 55.0

    while True:
        # Simulate realistic sensor drift using sine waves + noise
        temp = base_temp + math.sin(tick * 0.05) * 2 + random.uniform(-0.2, 0.2)
        humidity = base_humidity + math.cos(tick * 0.03) * 5 + random.uniform(-0.5, 0.5)
        lux = base_lux + math.sin(tick * 0.08) * 80 + random.uniform(-10, 10)
        pressure = 1013.25 + math.sin(tick * 0.01) * 2 + random.uniform(-0.1, 0.1)

        print(f"[tick {tick}]")
        emit("bme280_temp", temp, "C")
        emit("bme280_humidity", humidity, "%")
        emit("bme280_pressure", pressure, "hPa")
        emit("bh1750_lux", lux, "lux")

        # Every 10 ticks, simulate a second device (ESP32)
        if tick % 10 == 0:
            esp_payload = {
                "device_id": "esp32-1",
                "event_name": "heartbeat",
                "value": tick,
                "unit": "tick",
                "device_timestamp": time.time()
            }
            try:
                requests.post(f"{SERVER}/event", json=esp_payload)
                print(f"  → [esp32-1] heartbeat: {tick}")
            except:
                pass

        # Every 30 ticks, inject a fake anomaly so we can test AI detection later
        if tick % 30 == 0 and tick > 0:
            print("  ⚠ Injecting anomaly...")
            emit("bme280_temp", -40.0, "C")  # clearly wrong reading

        tick += 1
        time.sleep(1)

if __name__ == "__main__":
    simulate()