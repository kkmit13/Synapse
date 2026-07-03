"""
Synapse - Central Server (Phase 1)

What this file does, in order:
1. Sets up a SQLite database to permanently store every event
2. Exposes an HTTP endpoint (/event) that devices POST events to
3. Stamps every incoming event with ONE authoritative server timestamp
4. Broadcasts every new event to all connected dashboard clients over WebSocket
"""

import sqlite3
import time
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DB_PATH = "synapse.db"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db():
    """Creates the events table if it doesn't already exist."""
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
    """Writes one event row into SQLite."""
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


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Keeps track of every dashboard browser tab currently connected,
    so we know who to push new events to."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sends a message to every connected dashboard. If a connection
        has gone stale, we quietly drop it instead of crashing."""
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
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Synapse server starting up. Database ready.")
    yield
    print("Synapse server shutting down.")


app = FastAPI(lifespan=lifespan)

# Allows the React dashboard (running on a different port) to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class EventIn(BaseModel):
    device_id: str
    event_name: str
    value: float | str | None = None
    unit: str | None = None
    device_timestamp: float | None = None  # the device's own clock, for comparison only


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Synapse server is running"}


@app.post("/event")
async def receive_event(event: EventIn):
    """This is the endpoint every device SDK sends events to."""

    # This is the core fix for the clock-drift problem: every event gets
    # ONE authoritative timestamp from the server's own clock, regardless
    # of what the device's clock says.
    enriched_event = event.model_dump()
    enriched_event["server_timestamp"] = time.time()

    save_event(enriched_event)
    await manager.broadcast(enriched_event)

    return {"status": "received", "server_timestamp": enriched_event["server_timestamp"]}


@app.get("/events")
def get_recent_events(limit: int = 100):
    """Lets the dashboard load recent history when it first connects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events ORDER BY server_timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """The dashboard connects here. Connection stays open, and we push
    new events through it the instant they arrive."""
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the dashboard to send anything, but this keeps
            # the connection alive and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)