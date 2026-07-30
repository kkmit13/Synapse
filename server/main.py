"""
Synapse - Central Server (Phase 1 + Phase 4)

What this file does, in order:
1. Sets up a SQLite database to permanently store every event
2. Exposes an HTTP endpoint (/event) that devices POST events to
3. Stamps every incoming event with ONE authoritative server timestamp
4. Broadcasts every new event to all connected dashboard clients over WebSocket
5. Runs anomaly detection every 15 seconds via background scheduler
6. Exposes a /chat endpoint for the AI chat panel
7. Exposes a /clear endpoint to wipe all data and start fresh
8. Exposes a /snoozed endpoint so the dashboard can sync the snooze list
"""

import sqlite3
import time
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai import check_anomalies, chat as ai_chat

DB_PATH = "synapse.db"

# In-memory anomaly log — keeps last 50 anomalies
anomaly_log: list[dict] = []

# In-memory snoozed list — [{device_id, event_name}] pairs the user marked as expected
snoozed_list: list[dict] = []


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            value TEXT,
            unit TEXT,
            device_timestamp REAL,
            server_timestamp REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_event(event: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO events (device_id, event_name, value, unit, device_timestamp, server_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event["device_id"],
            event["event_name"],
            str(event.get("value")),
            event.get("unit"),
            event.get("device_timestamp"),
            event["server_timestamp"],
        ),
    )
    conn.commit()
    conn.close()


def get_recent_events_from_db(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events ORDER BY server_timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Anomaly detection scheduler
# ---------------------------------------------------------------------------

async def anomaly_scheduler():
    print("[AI] Anomaly detection scheduler started.")
    while True:
        await asyncio.sleep(15)
        try:
            recent = get_recent_events_from_db(limit=20)
            if not recent:
                continue

            print(f"[AI] Running anomaly check on {len(recent)} events... ({len(snoozed_list)} snoozed)")
            anomalies = check_anomalies(recent, snoozed=snoozed_list)

            if anomalies:
                print(f"[AI] Found {len(anomalies)} anomalie(s).")
                for anomaly in anomalies:
                    anomaly["detected_at"] = time.time()
                    anomaly_log.append(anomaly)
                    if len(anomaly_log) > 50:
                        anomaly_log.pop(0)
                    await manager.broadcast({
                        "type": "anomaly",
                        "anomaly": anomaly
                    })
            else:
                print("[AI] No anomalies detected.")

        except Exception as e:
            print(f"[AI] Scheduler error: {e}")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Synapse server starting up. Database ready.")
    task = asyncio.create_task(anomaly_scheduler())
    yield
    task.cancel()
    print("Synapse server shutting down.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class EventIn(BaseModel):
    device_id: str
    event_name: str
    value: float | str | None = None
    unit: str | None = None
    device_timestamp: float | None = None


class ChatIn(BaseModel):
    question: str


class SnoozedItem(BaseModel):
    device_id: str
    event_name: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Synapse server is running"}


@app.post("/event")
async def receive_event(event: EventIn):
    enriched_event = event.model_dump()
    enriched_event["server_timestamp"] = time.time()
    enriched_event["type"] = "event"
    save_event(enriched_event)
    await manager.broadcast(enriched_event)
    return {"status": "received", "server_timestamp": enriched_event["server_timestamp"]}


@app.get("/events")
def get_recent_events(limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events ORDER BY server_timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/anomalies")
def get_anomalies():
    return anomaly_log


@app.post("/snoozed")
async def update_snoozed(items: list[SnoozedItem]):
    """
    Dashboard POSTs the current snooze list here whenever it changes.
    Server stores it so the anomaly scheduler uses it on the next check.
    """
    global snoozed_list
    snoozed_list = [item.model_dump() for item in items]
    print(f"[SNOOZE] Updated: {len(snoozed_list)} snoozed item(s)")
    return {"status": "ok", "snoozed": len(snoozed_list)}


@app.post("/clear")
async def clear_all():
    """Wipes all events, anomalies, and snoozed items. Broadcasts reset to dashboard."""
    global anomaly_log, snoozed_list

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM events")
    conn.commit()
    conn.close()

    anomaly_log.clear()
    snoozed_list.clear()

    await manager.broadcast({"type": "clear"})

    print("[CLEAR] All data wiped. Fresh session started.")
    return {"status": "cleared"}


@app.post("/chat")
async def chat_endpoint(body: ChatIn):
    recent = get_recent_events_from_db(limit=100)
    response = ai_chat(body.question, recent, anomaly_log)
    return {"response": response}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)