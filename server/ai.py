"""
Synapse - AI Layer

Two jobs:
1. Passive anomaly detection — runs every 15 seconds, scans recent events,
   flags anything suspicious and returns structured alerts
2. Active chat — takes a user question + recent event context, returns a
   compact technical explanation from Claude Haiku

Key design principle:
  The AI's job is NOT to find unusual numbers — it's to PROVE a genuine
  hardware, electrical, communication, or software fault exists using
  objective evidence from the event stream. Single readings are rarely
  sufficient. Corroboration across signals is required for most categories.
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

ANOMALY_CATEGORIES = [
    "out_of_range",       # value is physically impossible for this sensor type
    "motor_stall",        # RPM near 0 AND current spike AND motor should be running
    "heap_exhaustion",    # free memory critically near 0
    "wifi_dropout",       # RSSI drops to 0 or connection fully lost
    "sensor_disconnect",  # sensor returns known error code (e.g. -127, -999, exactly 0 when impossible)
    "correlated_failure", # multiple independent sensors fail at the same timestamp
    "spike",              # value jumps impossibly far outside physical limits then returns
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

# Evidence requirements per category — used in the prompt to enforce corroboration
EVIDENCE_REQUIREMENTS = {
    "motor_stall":
        "REQUIRES: RPM near 0 AND motor current spiking above normal AND motor was previously running. "
        "RPM=0 alone is NOT a stall — motor may simply be stopped.",
    "out_of_range":
        "REQUIRES: value outside the absolute physical limits of this sensor type "
        "(e.g. temperature sensor returning -127C or 999C, not just an unusual reading). "
        "High ADC values, voltage changes, or bright light readings are NOT out of range.",
    "heap_exhaustion":
        "REQUIRES: free heap memory at or critically near 0 bytes. "
        "Low but non-zero memory is not exhaustion.",
    "wifi_dropout":
        "REQUIRES: RSSI value of exactly 0 or connection fully lost. "
        "Weak signal or fluctuating RSSI is normal WiFi behavior.",
    "sensor_disconnect":
        "REQUIRES: sensor returning a known hardware error value (-127, -999, 65535, exactly 0 "
        "when the sensor physically cannot read 0). Unusual but plausible readings are not disconnects.",
    "correlated_failure":
        "REQUIRES: two or more independent sensors from different subsystems failing "
        "within the same 1-2 second window with no plausible shared cause other than a fault.",
    "spike":
        "REQUIRES: value exceeds the absolute physical maximum or minimum for this sensor type, "
        "not just a high reading. A potentiometer at 4.98V or a light sensor spiking are NOT spikes.",
}


def format_event_line(ev: dict) -> str:
    """
    Format one event for the AI prompt.
    Includes role and behavior metadata when available so the AI knows
    what the sensor represents and what its normal pattern looks like.
    """
    base = (
        f"[{ev['device_id']}] {ev['event_name']}: {ev['value']} "
        f"{ev.get('unit', '')} @ {ev['server_timestamp']:.3f}"
    )
    context_parts = []
    if ev.get('role'):
        context_parts.append(f"role={ev['role']}")
    if ev.get('behavior'):
        context_parts.append(f"behavior={ev['behavior']}")
    if context_parts:
        base += f"  [{', '.join(context_parts)}]"
    return base


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

def check_anomalies(
    recent_events: list[dict],
    snoozed: list[dict] = [],
    feedback: list[dict] = []
) -> list[dict]:
    """
    Takes the last N events, a snoozed list, and a feedback list.
    Uses evidence-based, corroboration-required prompting to minimize
    false positives. Role/behavior metadata enriches context when available.
    """

    if not recent_events:
        return []

    events_text = "\n".join(format_event_line(ev) for ev in recent_events)

    # Snoozed section
    if snoozed:
        snoozed_lines = [
            f"- {s['device_id']} / {s['event_name']} / category: {s.get('category', 'any')}"
            for s in snoozed
        ]
        snoozed_text = (
            "SNOOZED — do NOT flag these under any circumstances:\n" +
            "\n".join(snoozed_lines)
        )
    else:
        snoozed_text = "SNOOZED: none"

    # Feedback section
    if feedback:
        false_positives = [f for f in feedback if f["verdict"] == "false_positive"]
        confirmed       = [f for f in feedback if f["verdict"] == "confirmed"]
        feedback_lines  = []

        if false_positives:
            feedback_lines.append("USER-CONFIRMED FALSE POSITIVES — never flag these again:")
            for f in false_positives:
                note = f" ({f['note']})" if f.get("note") else ""
                feedback_lines.append(
                    f"  - {f['device_id']} / {f['event_name']} / {f['category']}{note}"
                )
        if confirmed:
            feedback_lines.append("USER-CONFIRMED REAL ISSUES — keep watching for these:")
            for f in confirmed:
                note = f" ({f['note']})" if f.get("note") else ""
                feedback_lines.append(
                    f"  - {f['device_id']} / {f['event_name']} / {f['category']}{note}"
                )
        feedback_text = "\n".join(feedback_lines)
    else:
        feedback_text = "USER FEEDBACK: none yet"

    # Per-category evidence requirements
    evidence_text = "\n".join(
        f"  {cat}: {req}" for cat, req in EVIDENCE_REQUIREMENTS.items()
    )

    categories_list = "\n".join(f'  - "{c}"' for c in ANOMALY_CATEGORIES)

    prompt = f"""You are analyzing sensor events from an embedded system.
Your job is NOT to find unusual numbers. Your job is to PROVE that a genuine hardware,
electrical, communication, or software fault exists using objective evidence from the event stream.

EVENTS (format: [device] sensor: value unit @ timestamp  [role=..., behavior=...] when known):
{events_text}

{snoozed_text}

{feedback_text}

---
EVIDENCE REQUIREMENTS — each category requires specific corroborating evidence:
{evidence_text}

---
Respond ONLY with a JSON array of confirmed faults. Empty array [] if nothing is proven.

Each fault must have:
- device_id: which device
- event_name: which sensor/event  
- value: the problematic value
- category: one of the valid categories below
- severity: "low", "medium", or "high"
- title: one short sentence naming the fault
- explanation: 1-2 sentences — state the specific evidence that proves this is a fault, not just an observation
- suggestion: 1 sentence on how to fix it

Valid categories:
{categories_list}

ABSOLUTE RULES — return [] if any of these apply:
- You only have one data point suggesting a problem (single-signal detections are almost always false positives)
- The value is unusual but physically plausible for that sensor type
- A role or behavior hint explains the reading (e.g. behavior=variable means fluctuation is expected)
- The reading could be explained by normal environment changes (light, temperature, user interaction)
- A potentiometer, ADC input, or analog sensor reading any value in its full range — that is normal
- PWM values, brightness percentages, or duty cycles at any level — that is normal operation
- Voltage rails or battery readings changing gradually — that is normal
- Any sensor with behavior=variable showing variation — that is expected
- WiFi RSSI fluctuating but not at exactly 0 — that is normal
- You are not certain. Uncertainty means return [].

Only flag when you have clear, specific, corroborated evidence of a genuine fault.
When in doubt, return []. A missed detection is better than a false alarm."""

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

        # Normalize category
        for a in anomalies:
            if a.get('category') not in ANOMALY_CATEGORIES:
                a['category'] = 'out_of_range'

        # Belt-and-suspenders: strip snoozed
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

        # Belt-and-suspenders: strip confirmed false positives
        if feedback:
            fp_keys = {
                (f['device_id'], f['event_name'], f['category'])
                for f in feedback if f['verdict'] == 'false_positive'
            }
            anomalies = [
                a for a in anomalies
                if (a.get('device_id'), a.get('event_name'), a.get('category')) not in fp_keys
            ]

        return anomalies if isinstance(anomalies, list) else []

    except Exception as e:
        print(f"[AI] Anomaly check failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat(question: str, recent_events: list[dict], anomaly_log: list[dict]) -> str:
    event_lines = []
    for ev in recent_events[-100:]:
        event_lines.append(format_event_line(ev))
    events_text = "\n".join(event_lines) if event_lines else "No recent events."

    if anomaly_log:
        anomaly_lines = [
            f"[{a['severity'].upper()}] {a['device_id']} — {a['title']}"
            for a in anomaly_log[-10:]
        ]
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