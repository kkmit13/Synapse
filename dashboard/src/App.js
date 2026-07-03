import { useState, useEffect, useRef } from 'react';
import './App.css';

const WS_URL = 'ws://127.0.0.1:8000/ws';
const API_URL = 'http://127.0.0.1:8000';

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().split(' ')[0] + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function EventRow({ event, isNew }) {
  return (
    <div className={`event-row ${isNew ? 'new' : ''}`}>
      <span className="event-time">{formatTime(event.server_timestamp)}</span>
      <span className="event-device">{event.device_id}</span>
      <span className="event-name">{event.event_name}</span>
      <span className="event-value">
        {event.value}
        {event.unit && <span className="unit">{event.unit}</span>}
      </span>
    </div>
  );
}

function DeviceCard({ deviceId, events }) {
  const latest = events[0];
  return (
    <div className="device-card">
      <div className="device-card-header">
        <span className="device-name">{deviceId}</span>
        <div className="device-live-dot" />
      </div>
      <div className="device-stats">
        <div className="device-stat-row">
          <span className="device-stat-label">Events</span>
          <span className="device-stat-value">{events.length}</span>
        </div>
        <div className="device-stat-row">
          <span className="device-stat-label">Last seen</span>
          <span className="device-stat-value">
            {latest ? formatTime(latest.server_timestamp) : '—'}
          </span>
        </div>
        <div className="device-stat-row">
          <span className="device-stat-label">Last event</span>
          <span className="device-stat-value">
            {latest ? latest.event_name : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [newestId, setNewestId] = useState(null);
  const wsRef = useRef(null);
  const feedRef = useRef(null);
  const userScrolled = useRef(false);

  // Load history on mount
  useEffect(() => {
    fetch(`${API_URL}/events`)
      .then(r => r.json())
      .then(data => setEvents(data.reverse()))
      .catch(() => {});
  }, []);

  // WebSocket connection
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (msg) => {
        const event = JSON.parse(msg.data);
        setNewestId(event.server_timestamp);
        setEvents(prev => [event, ...prev].slice(0, 500));
      };

      ws.onclose = () => {
        setConnected(false);
        setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => wsRef.current?.close();
  }, []);

  // Auto-scroll to top when new events arrive, unless user is scrolling through history
  useEffect(() => {
    const feed = feedRef.current;
    if (!feed || userScrolled.current) return;
    feed.scrollTop = 0;
  }, [events]);

  // Detect when user manually scrolls down vs back to top
  useEffect(() => {
    const feed = feedRef.current;
    if (!feed) return;
    const handleScroll = () => {
      userScrolled.current = feed.scrollTop > 50;
    };
    feed.addEventListener('scroll', handleScroll);
    return () => feed.removeEventListener('scroll', handleScroll);
  }, []);

  // Group events by device for the right panel
  const deviceMap = events.reduce((acc, ev) => {
    if (!acc[ev.device_id]) acc[ev.device_id] = [];
    acc[ev.device_id].push(ev);
    return acc;
  }, {});

  return (
    <div>
      {/* TOP BAR */}
      <div className="topbar">
        <div className="topbar-left">
          <div>
            <div className="logo">Synapse</div>
            <div className="logo-sub">Embedded Debugger</div>
          </div>
        </div>
        <div className="topbar-right">
          <div className="status-pill">
            <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
            {connected ? 'LIVE' : 'RECONNECTING'}
          </div>
          <div className="stat-chip">EVENTS <span>{events.length}</span></div>
          <div className="stat-chip">DEVICES <span>{Object.keys(deviceMap).length}</span></div>
        </div>
      </div>

      {/* MAIN */}
      <div className="main">

        {/* LEFT — live event feed */}
        <div className="feed-panel">
          <div className="panel-header">
            <div className="panel-title"><span>▶</span> Live Event Feed</div>
            <div className="event-count">{events.length} events</div>
          </div>
          <div className="feed-list" ref={feedRef}>
            {events.length === 0 ? (
              <div className="empty-feed">
                <div className="empty-feed-label">Waiting for events</div>
                <div className="empty-feed-sub">Start a device SDK to see data here</div>
              </div>
            ) : (
              events.map((ev, i) => (
                <EventRow
                  key={`${ev.server_timestamp}-${i}`}
                  event={ev}
                  isNew={ev.server_timestamp === newestId && i === 0}
                />
              ))
            )}
          </div>
        </div>

        {/* RIGHT — per-device status */}
        <div className="device-panel">
          <div className="panel-header">
            <div className="panel-title"><span>◈</span> Devices</div>
          </div>
          {Object.keys(deviceMap).length === 0 ? (
            <div style={{ padding: '20px 12px' }}>
              <div className="empty-feed-label" style={{ textAlign: 'center' }}>No devices yet</div>
            </div>
          ) : (
            Object.entries(deviceMap).map(([deviceId, devEvents]) => (
              <DeviceCard key={deviceId} deviceId={deviceId} events={devEvents} />
            ))
          )}
        </div>

      </div>
    </div>
  );
}