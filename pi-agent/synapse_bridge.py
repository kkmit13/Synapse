#!/usr/bin/env python3
"""
Synapse Serial Bridge
----------------------
Reads SYNAPSE events from an Arduino over USB Serial
and forwards them to the Synapse server as HTTP POSTs.

Usage:
  python3 synapse_bridge.py --port /dev/ttyUSB0 --server http://192.168.x.x:8000

On Mac/Linux, find your port with:   ls /dev/tty.*
On Windows, find your port with:     Device Manager → Ports (COM & LPT)
"""

import argparse
import serial
import requests
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Synapse Serial Bridge")
    parser.add_argument("--port",   required=True, help="Serial port (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument("--server", required=True, help="Synapse server URL (e.g. http://192.168.x.x:8000)")
    parser.add_argument("--baud",   default=9600, type=int, help="Baud rate (default: 9600)")
    return parser.parse_args()


def main():
    args = parse_args()
    server = args.server.rstrip("/")

    print(f"Synapse Serial Bridge")
    print(f"  Port:   {args.port} @ {args.baud} baud")
    print(f"  Server: {server}")
    print(f"  Waiting for Arduino...\n")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=2)
    except Exception as e:
        print(f"Could not open serial port: {e}")
        return

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            continue

        if not line.startswith("SYNAPSE,"):
            if line:
                print(f"  [Arduino] {line}")
            continue

        # Format: SYNAPSE,device_id,event_name,value,unit,millis[,role,behavior]
        # role and behavior are optional — appended only when emit() includes them
        parts = line.split(",")
        if len(parts) < 6:
            print(f"  [Bridge] Malformed line: {line}")
            continue

        _, device_id, event_name, value, unit, device_millis = parts[:6]
        role     = parts[6] if len(parts) > 6 else ""
        behavior = parts[7] if len(parts) > 7 else ""

        payload = {
            "device_id":        device_id,
            "event_name":       event_name,
            "value":            float(value),
            "unit":             unit,
            "device_timestamp": float(device_millis) / 1000.0,
        }
        # Only include metadata if present
        if role:
            payload["role"] = role
        if behavior:
            payload["behavior"] = behavior

        try:
            r = requests.post(f"{server}/event", json=payload, timeout=3)
            meta = f" [{role}]" if role else ""
            print(f"  → [{device_id}] {event_name}: {value} {unit}{meta} → HTTP {r.status_code}")
        except Exception as e:
            print(f"  ✗ Failed to send to server: {e}")


if __name__ == "__main__":
    main()
