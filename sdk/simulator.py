"""
Synapse - Enhanced Device Simulator
Simulates a realistic multi-device embedded system with:
  - Raspberry Pi (main controller + sensors)
  - ESP32 (motor controller)
  - Arduino Mega (environmental station)
  - ESP32-CAM (camera node)

Each device has multiple sensors with realistic drift, and errors
are injected at different intervals to test anomaly detection.

Every emit includes role + behavior metadata, matching how a real
device would use synapse.emit(). This lets the AI tell the difference
between normal variance (a light sensor changing, a battery draining)
and a genuine fault (a motor stalling, a sensor disconnecting).
"""

import requests
import time
import random
import math
import threading

SERVER = "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Core emit function — each device calls this with its own ID
# role and behavior are optional metadata, same as the real Arduino/Pi clients
# ---------------------------------------------------------------------------

def emit(device_id, event_name, value, unit=None, role=None, behavior=None, noisy=False):
    payload = {
        "device_id": device_id,
        "event_name": event_name,
        "value": round(value, 3) if isinstance(value, float) else value,
        "unit": unit,
        # Simulate clock drift per device — each has its own offset
        "device_timestamp": time.time() + DEVICE_CLOCK_OFFSETS.get(device_id, 0)
    }
    if role:
        payload["role"] = role
    if behavior:
        payload["behavior"] = behavior

    try:
        requests.post(f"{SERVER}/event", json=payload, timeout=2)
        status = "⚠" if noisy else "→"
        meta = f" [{role}]" if role else ""
        print(f"  {status} [{device_id}] {event_name}: {payload['value']} {unit or ''}{meta}")
    except Exception as e:
        print(f"  ✗ [{device_id}] Failed: {e}")


# Each device has a slightly different clock — this is what Synapse's
# server-side timestamping is designed to correct for
DEVICE_CLOCK_OFFSETS = {
    "pi-1":        0.0,     # Pi is closest to true time (NTP synced)
    "esp32-motor": 0.245,   # ESP32 runs 245ms fast
    "arduino-env": -0.180,  # Arduino runs 180ms slow
    "esp32-cam":   0.089,   # CAM module runs 89ms fast
}


# ---------------------------------------------------------------------------
# Device 1 — Raspberry Pi (main controller)
# Sensors: BME280 (temp/humidity/pressure), BH1750 (light), CPU stats
# ---------------------------------------------------------------------------

def run_pi(tick):
    device = "pi-1"

    # Realistic sensor drift with sine waves
    temp     = 23.0 + math.sin(tick * 0.04) * 3 + random.uniform(-0.15, 0.15)
    humidity = 58.0 + math.cos(tick * 0.03) * 8 + random.uniform(-0.4, 0.4)
    pressure = 1013.25 + math.sin(tick * 0.01) * 3 + random.uniform(-0.05, 0.05)
    lux      = 320.0 + math.sin(tick * 0.07) * 100 + random.uniform(-8, 8)
    cpu_temp = 45.0 + math.sin(tick * 0.02) * 5 + random.uniform(-0.5, 0.5)
    cpu_load = max(0, min(100, 30 + math.sin(tick * 0.06) * 20 + random.uniform(-5, 5)))

    emit(device, "bme280_temp",     temp,     "C",   role="ambient_temperature",   behavior="variable")
    emit(device, "bme280_humidity", humidity, "%",   role="ambient_humidity",      behavior="variable")
    emit(device, "bme280_pressure", pressure, "hPa", role="barometric_pressure",   behavior="stable")
    emit(device, "bh1750_lux",      lux,      "lux", role="ambient_light",         behavior="variable")
    emit(device, "cpu_temp",        cpu_temp, "C",   role="cpu_temperature",       behavior="variable")
    emit(device, "cpu_load",        cpu_load, "%",   role="cpu_load",              behavior="variable")

    # Error: I2C address conflict causes BME280 to return garbage every 25 ticks
    # This is a genuine fault — value is physically impossible regardless of metadata
    if tick % 25 == 0 and tick > 0:
        print(f"  ⚠ [{device}] I2C conflict — BME280 returning garbage")
        emit(device, "bme280_temp", -127.0, "C", role="ambient_temperature", behavior="variable", noisy=True)
        emit(device, "bme280_humidity", 0.0, "%", role="ambient_humidity", behavior="variable", noisy=True)

    # Error: BH1750 sensor disconnect every 40 ticks
    if tick % 40 == 0 and tick > 0:
        print(f"  ⚠ [{device}] BH1750 disconnect — reading 0")
        emit(device, "bh1750_lux", 0.0, "lux", role="ambient_light", behavior="variable", noisy=True)

    # Error: CPU spike every 35 ticks (simulates a heavy process)
    # NOTE: a single CPU spike alone is often legitimate (compiling, GC, etc).
    # The AI should treat this cautiously unless sustained or paired with other signals.
    if tick % 35 == 0 and tick > 0:
        print(f"  ⚠ [{device}] CPU spike")
        emit(device, "cpu_load", 98.5, "%", role="cpu_load", behavior="variable", noisy=True)
        emit(device, "cpu_temp", 82.0, "C", role="cpu_temperature", behavior="variable", noisy=True)


# ---------------------------------------------------------------------------
# Device 2 — ESP32 Motor Controller
# Sensors: motor RPM, current draw, temperature, encoder position
# Fires every 2 seconds (motors don't need 1Hz updates)
# ---------------------------------------------------------------------------

def run_esp32_motor(tick):
    if tick % 2 != 0:
        return  # only fires every other tick

    device = "esp32-motor"

    rpm      = 1200 + math.sin(tick * 0.05) * 200 + random.uniform(-10, 10)
    current  = 2.4 + math.sin(tick * 0.05) * 0.6 + random.uniform(-0.05, 0.05)
    temp     = 38.0 + math.sin(tick * 0.03) * 4 + random.uniform(-0.3, 0.3)
    position = (tick * 15) % 36000 / 100  # degrees, cycles around

    emit(device, "motor_rpm",     rpm,      "RPM", role="motor_rpm",     behavior="variable")
    emit(device, "motor_current", current,  "A",   role="motor_current", behavior="variable")
    emit(device, "motor_temp",    temp,     "C",   role="motor_temperature", behavior="variable")
    emit(device, "encoder_pos",   position, "deg", role="encoder_position",  behavior="cyclic")

    # Error: motor stall — RPM drops to 0 AND current spikes at the same time.
    # This is the textbook motor_stall evidence pattern — two corroborating signals.
    if tick % 45 == 0 and tick > 0:
        print(f"  ⚠ [{device}] Motor stall detected")
        emit(device, "motor_rpm",     0.0,  "RPM", role="motor_rpm",     behavior="variable", noisy=True)
        emit(device, "motor_current", 8.9,  "A",   role="motor_current", behavior="variable", noisy=True)
        emit(device, "motor_temp",    75.0, "C",   role="motor_temperature", behavior="variable", noisy=True)

    # Error: encoder dropout (position jumps to -1 = invalid, physically impossible for degrees)
    if tick % 60 == 0 and tick > 0:
        print(f"  ⚠ [{device}] Encoder signal lost")
        emit(device, "encoder_pos", -1.0, "deg", role="encoder_position", behavior="cyclic", noisy=True)


# ---------------------------------------------------------------------------
# Device 3 — Arduino Mega Environmental Station
# Sensors: DHT22 (temp/humidity), MQ135 (air quality), rain sensor, UV index
# Fires every 3 seconds (environmental data changes slowly)
# ---------------------------------------------------------------------------

def run_arduino_env(tick):
    if tick % 3 != 0:
        return

    device = "arduino-env"

    temp      = 21.0 + math.sin(tick * 0.02) * 4 + random.uniform(-0.3, 0.3)
    humidity  = 62.0 + math.cos(tick * 0.025) * 10 + random.uniform(-1, 1)
    air_qual  = max(0, 150 + math.sin(tick * 0.04) * 50 + random.uniform(-10, 10))
    rain      = max(0, math.sin(tick * 0.015) * 50 + random.uniform(-2, 2))
    uv_index  = max(0, 3.0 + math.sin(tick * 0.03) * 2 + random.uniform(-0.1, 0.1))

    emit(device, "dht22_temp",     temp,     "C",   role="ambient_temperature", behavior="variable")
    emit(device, "dht22_humidity", humidity, "%",   role="ambient_humidity",    behavior="variable")
    emit(device, "mq135_aqi",      air_qual, "AQI", role="air_quality",         behavior="variable")
    emit(device, "rain_level",     rain,     "mm",  role="rain_sensor",         behavior="variable")
    emit(device, "uv_index",       uv_index, "UV",  role="uv_sensor",           behavior="variable")

    # Error: DHT22 checksum failure — returns fixed error values (physically impossible)
    if tick % 30 == 0 and tick > 0:
        print(f"  ⚠ [{device}] DHT22 checksum failure")
        emit(device, "dht22_temp",     -999.0, "C", role="ambient_temperature", behavior="variable", noisy=True)
        emit(device, "dht22_humidity", -999.0, "%", role="ambient_humidity",    behavior="variable", noisy=True)

    # Error: MQ135 warmup spike (gas sensor needs time to stabilize)
    # NOTE: single-sensor spikes on a variable-behavior sensor are usually NOT flagged
    # by the new evidence-based prompt unless the value is physically impossible.
    # 500 AQI is a real-world extreme but not impossible, so this tests the AI's judgment.
    if tick % 50 == 0 and tick > 0:
        print(f"  ⚠ [{device}] MQ135 warmup spike")
        emit(device, "mq135_aqi", 500.0, "AQI", role="air_quality", behavior="variable", noisy=True)


# ---------------------------------------------------------------------------
# Device 4 — ESP32-CAM Node
# Sensors: frame rate, inference latency, WiFi RSSI, memory usage
# Fires every 5 seconds (camera processing is intermittent)
# ---------------------------------------------------------------------------

def run_esp32_cam(tick):
    if tick % 5 != 0:
        return

    device = "esp32-cam"

    fps       = max(0, 15 + math.sin(tick * 0.04) * 5 + random.uniform(-1, 1))
    latency   = max(0, 120 + math.sin(tick * 0.03) * 40 + random.uniform(-5, 5))
    rssi      = -60 + math.sin(tick * 0.02) * 15 + random.uniform(-2, 2)
    mem_free  = max(0, 180 + math.sin(tick * 0.05) * 30 + random.uniform(-5, 5))

    emit(device, "cam_fps",      fps,     "fps", role="camera_framerate", behavior="variable")
    emit(device, "inference_ms", latency, "ms",  role="inference_latency", behavior="variable")
    emit(device, "wifi_rssi",    rssi,    "dBm", role="wifi_signal",      behavior="variable")
    emit(device, "heap_free",    mem_free, "KB", role="heap_memory",      behavior="variable")

    # Error: WiFi dropout — RSSI goes to exactly 0 (real disconnect signature) and FPS drops to 0
    if tick % 55 == 0 and tick > 0:
        print(f"  ⚠ [{device}] WiFi dropout")
        emit(device, "wifi_rssi", 0.0, "dBm", role="wifi_signal",      behavior="variable", noisy=True)
        emit(device, "cam_fps",   0.0, "fps",  role="camera_framerate", behavior="variable", noisy=True)

    # Error: heap exhaustion — memory runs out, latency spikes (two corroborating signals)
    if tick % 70 == 0 and tick > 0:
        print(f"  ⚠ [{device}] Heap exhaustion")
        emit(device, "heap_free",    2.0,   "KB", role="heap_memory",       behavior="variable", noisy=True)
        emit(device, "inference_ms", 850.0, "ms", role="inference_latency", behavior="variable", noisy=True)


# ---------------------------------------------------------------------------
# Main loop — runs all devices concurrently using threads
# ---------------------------------------------------------------------------

def simulate():
    print("=" * 55)
    print("  Synapse Enhanced Simulator")
    print("  4 devices · 20+ sensors · realistic error injection")
    print("  All events include role + behavior metadata")
    print("=" * 55)
    print(f"  Server: {SERVER}")
    print(f"  Devices: pi-1, esp32-motor, arduino-env, esp32-cam")
    print("  Press Ctrl+C to stop.\n")

    tick = 0

    while True:
        print(f"\n{'─' * 40} tick {tick} {'─' * 10}")

        # Run each device in its own thread so they fire simultaneously
        # rather than sequentially — more realistic to real hardware
        threads = [
            threading.Thread(target=run_pi,           args=(tick,)),
            threading.Thread(target=run_esp32_motor,  args=(tick,)),
            threading.Thread(target=run_arduino_env,  args=(tick,)),
            threading.Thread(target=run_esp32_cam,    args=(tick,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        tick += 1
        time.sleep(1)


if __name__ == "__main__":
    simulate()