"""
Synapse - AI Layer (Phase 4)

Two jobs:
1. Passive anomaly detection — runs every 15 seconds, scans recent events,
   flags anything suspicious and returns structured alerts
2. Active chat — takes a user question + recent event context, returns a
   compact technical explanation from Claude Haiku
"""

import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Synapse AI, an embedded systems debugging assistant built into a multi-device monitoring tool.

You help hobbyist engineers debug their Arduino, ESP32, and Raspberry Pi projects.

Rules for all responses:
- Be direct and concise — no long preambles or summaries at the end
- Use real embedded systems terminology but briefly explain it if it's obscure
- Assume the user is a capable student or hobbyist, not a professional engineer
- Never be condescending
- If something is clearly wrong, say so directly with a likely cause and fix
- If data looks normal, say so briefly
"""

# Fixed category list — the AI must pick one of these.
# Using a fixed list means snoozing is stable regardless of how the AI words the title.
ANOMALY_CATEGORIES = [
    "out_of_range",       # value is physically impossible (e.g. -127C, -999)
    "motor_stall",        # RPM at 0 while current spikes
    "heap_exhaustion",    # free memory near 0
    "wifi_dropout",       # RSSI drops to 0 or signal lost
    "sensor_disconnect",  # sensor returns 0 or error code when it shouldn't
    "correlated_failure", # multiple devices fail at the same timestamp
    "spike",              # value jumps far outside its normal running range then returns
]

CATEGORY_LABELS = {
    "out_of_range":       "Out of range value",
    "motor_stall":        "Motor stall",
    "heap_exhaustion":    "Heap exhaustion",
    "wifi_dropout":       "WiFi dropout",
    "sensor_disconnect":  "Sensor disconnect",
    "correlated_failure": "Correlated failure",
    "spike":              "Abnormal spike",
}


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

def check_anomalies(recent_events: list[dict], snoozed: list[dict] = []) -> list[dict]:
    """
    Takes the last N events and a snoozed list, asks Haiku to flag anything suspicious.
    Snoozed is a list of {device_id, event_name, category} dicts the user marked as expected.
    Returns a list of anomaly dicts, empty if nothing found.
    """

    if not recent_events:
        return []

    event_lines = []
    for ev in recent_events:
        event_lines.append(
            f"[{ev['device_id']}] {ev['event_name']}: {ev['value']} {ev.get('unit', '')} "
            f"@ {ev['server_timestamp']:.3f}"
        )
    events_text = "\n".join(event_lines)

    # Build snoozed section with category so the AI knows exactly what to skip
    if snoozed:
        snoozed_lines = [
            f"- {s['device_id']} / {s['event_name']} / category: {s.get('category', 'any')}"
            for s in snoozed
        ]
        snoozed_text = (
            "SNOOZED (user has marked these as expected behavior this session — "
            "do NOT flag these under any circumstances):\n" +
            "\n".join(snoozed_lines)
        )
    else:
        snoozed_text = "SNOOZED: none"

    categories_list = "\n".join(f'  - "{c}"' for c in ANOMALY_CATEGORIES)

    prompt = f"""Analyze these sensor events from an embedded system and identify critical anomalies only.

EVENTS:
{events_text}

{snoozed_text}

Respond ONLY with a JSON array. Each element is an anomaly you found.
If nothing is wrong, respond with an empty array: []

Each anomaly must have these exact fields:
- device_id: which device
- event_name: which sensor/event
- value: the problematic value
- category: one of the categories listed below (pick the closest match)
- severity: "low", "medium", or "high"
- title: one short sentence naming the problem
- explanation: 1-2 sentences explaining what's wrong and likely cause
- suggestion: 1 sentence on how to fix it

Valid categories (you MUST use one of these exactly):
{categories_list}

ONLY flag an anomaly if it meets ALL of these criteria:
1. The value is clearly wrong for physical or electrical reasons — not just unusual
2. It would actually prevent the system from working correctly
3. It is NOT something that could be explained by normal environment changes
   (lights turning on/off, temperature fluctuating, someone walking past a sensor)

STRICT rules — do NOT flag these under any circumstances:
- A sensor reading a constant value (this is normal in stable environments)
- A single value that is slightly higher or lower than recent readings
- Light, temperature, or humidity changing gradually or suddenly (environmental)
- Values that are stable and repeating — that is normal sensor behavior
- Any reading that is within a physically plausible range for that sensor type
- Mild spikes that return to normal immediately

Only flag things like:
- Values that are physically impossible (temp = -127, humidity = -999, RSSI = 0 meaning disconnected)
- RPM = 0 AND current spiking at the same time (motor stall pattern)
- Heap memory at or near 0 bytes free
- Multiple sensors failing at exactly the same timestamp (correlated failure)
- A value that stays at exactly 0.0 for a sensor that should never read 0

When in doubt, return an empty array. False positives are worse than missed detections.
Never flag anything in the SNOOZED list regardless of how unusual the value looks."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        anomalies = json.loads(raw)

        # Normalize category — if AI returns something not in the list, default to out_of_range
        for a in anomalies:
            if a.get('category') not in ANOMALY_CATEGORIES:
                a['category'] = 'out_of_range'

        # Belt-and-suspenders filter: strip snoozed items by device+sensor+category
        if snoozed:
            anomalies = [
                a for a in anomalies
                if not any(
                    s['device_id'] == a.get('device_id') and
                    s['event_name'] == a.get('event_name') and
                    s.get('category', 'any') in ('any', a.get('category'))
                    for s in snoozed
                )
            ]

        return anomalies if isinstance(anomalies, list) else []

    except Exception as e:
        print(f"[AI] Anomaly check failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat(question: str, recent_events: list[dict], anomaly_log: list[dict]) -> str:
    """
    Takes a user question, recent event context, and the anomaly log.
    Returns a compact technical response from Claude Haiku.
    """

    event_lines = []
    for ev in recent_events[-100:]:
        event_lines.append(
            f"[{ev['device_id']}] {ev['event_name']}: {ev['value']} "
            f"{ev.get('unit', '')} @ {ev['server_timestamp']:.3f}"
        )
    events_text = "\n".join(event_lines) if event_lines else "No recent events."

    if anomaly_log:
        anomaly_lines = []
        for a in anomaly_log[-10:]:
            anomaly_lines.append(
                f"[{a['severity'].upper()}] {a['device_id']} — {a['title']}"
            )
        anomaly_text = "\n".join(anomaly_lines)
    else:
        anomaly_text = "No anomalies detected yet."

    prompt = f"""RECENT SENSOR DATA (last 100 events):
{events_text}

RECENT ANOMALIES DETECTED:
{anomaly_text}

USER QUESTION:
{question}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    except Exception as e:
        return f"AI unavailable: {e}"