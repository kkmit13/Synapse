"""
Synapse - Raspberry Pi Polling Agent
-------------------------------------
Reads sensors listed in synapse_config.yaml and sends
real sensor data to the Synapse server on a schedule.

To add a new sensor type:
  1. Wire it up and confirm it shows in: i2cdetect -y 1
  2. Add it to synapse_config.yaml
  3. Add a loader function below (search for "SENSOR LOADERS")

Usage:
  python3 synapse_agent.py
  python3 synapse_agent.py --config /path/to/other_config.yaml
"""

import time
import argparse
import board
import busio
import requests
import yaml

# ── SENSOR LOADERS ────────────────────────────────────────────
# Each function takes the I2C bus and config dict for one sensor
# and returns a dict mapping field name → callable that returns
# the current reading. Add new sensor types here.

def load_bme280(i2c, cfg):
    import adafruit_bme280.basic as adafruit_bme280
    address = int(cfg["address"], 16)
    sensor  = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=address)
    sensor.sea_level_pressure = cfg.get("sea_level_pressure", 1013.25)
    return {
        "temperature": lambda: sensor.temperature,
        "humidity":    lambda: sensor.humidity,
        "pressure":    lambda: sensor.pressure,
        "altitude":    lambda: sensor.altitude,
    }

def load_bh1750(i2c, cfg):
    import adafruit_bh1750
    address = int(cfg["address"], 16)
    sensor  = adafruit_bh1750.BH1750(i2c, address=address)
    return {
        "lux": lambda: sensor.lux,
    }

# Registry — maps sensor type string → loader function
SENSOR_REGISTRY = {
    "bme280": load_bme280,
    "bh1750": load_bh1750,
}

# ── HELPERS ───────────────────────────────────────────────────

def emit(server, device_id, event_name, value, unit=None, role=None, behavior=None):
    payload = {
        "device_id":        device_id,
        "event_name":       event_name,
        "value":            round(float(value), 3),
        "unit":             unit,
        "device_timestamp": time.time(),
    }
    # Include metadata if provided — used by AI for context-aware anomaly detection
    if role:
        payload["role"] = role
    if behavior:
        payload["behavior"] = behavior

    try:
        requests.post(f"{server}/event", json=payload, timeout=2)
        meta = f" [{role}]" if role else ""
        print(f"  → [{device_id}] {event_name}: {payload['value']} {unit or ''}{meta}")
    except Exception as e:
        print(f"  ✗ Failed to send {event_name}: {e}")


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ── MAIN ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Synapse Pi Agent")
    parser.add_argument(
        "--config", default="synapse_config.yaml",
        help="Path to config file (default: synapse_config.yaml)"
    )
    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"✗ Config file not found: {args.config}")
        print("  Make sure synapse_config.yaml is in the same folder as this script.")
        return

    server        = config["server"]
    device_id     = config["device_id"]
    poll_interval = config.get("poll_interval", 2)
    sensors_cfg   = config.get("sensors", [])

    print("Synapse Pi Agent")
    print(f"  Server:   {server}")
    print(f"  Device:   {device_id}")
    print(f"  Interval: {poll_interval}s")
    print(f"  Sensors:  {len(sensors_cfg)} configured\n")

    # Set up I2C bus once — shared by all sensors
    i2c = busio.I2C(board.SCL, board.SDA)

    # Load each sensor from config
    loaded_sensors = []
    for sensor_cfg in sensors_cfg:
        sensor_type = sensor_cfg.get("type", "").lower()
        if sensor_type not in SENSOR_REGISTRY:
            print(f"  ⚠ Unknown sensor type: {sensor_type} — skipping")
            continue
        try:
            reader = SENSOR_REGISTRY[sensor_type](i2c, sensor_cfg)
            loaded_sensors.append({
                "reader":   reader,
                "readings": sensor_cfg.get("readings", []),
            })
            print(f"  ✓ Loaded {sensor_type} @ {sensor_cfg.get('address')}")
        except Exception as e:
            print(f"  ✗ Failed to load {sensor_type}: {e}")

    if not loaded_sensors:
        print("\n✗ No sensors loaded — check your config and wiring.")
        return

    print(f"\nPolling every {poll_interval}s. Press Ctrl+C to stop.\n")

    # Poll loop
    while True:
        for sensor in loaded_sensors:
            reader   = sensor["reader"]
            readings = sensor["readings"]

            for reading in readings:
                field    = reading["field"]
                event    = reading["event"]
                unit     = reading.get("unit")
                role     = reading.get("role")
                behavior = reading.get("behavior")

                try:
                    value = reader[field]()
                    emit(server, device_id, event, value, unit, role, behavior)
                except Exception as e:
                    print(f"  ✗ Read error ({event}): {e}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
