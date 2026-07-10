import { useState, useEffect, useRef, useCallback } from 'react';

const DEFAULT_WINDOW = 60;
const MIN_WINDOW = 5;
const MAX_WINDOW = 300;
const LANE_HEIGHT = 70;
const LABEL_WIDTH = 140;

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().split(' ')[0] + '.' +
    String(d.getMilliseconds()).padStart(3, '0');
}

function formatDrift(server, device) {
  if (!device) return 'N/A';
  const ms = Math.round((server - device) * 1000);
  return `${ms > 0 ? '+' : ''}${ms}ms`;
}

function tsToPercent(ts, windowStart, windowEnd) {
  return ((ts - windowStart) / (windowEnd - windowStart)) * 100;
}

function Marker({ event, windowStart, windowEnd, onClick, isSelected }) {
  const pct = tsToPercent(event.server_timestamp, windowStart, windowEnd);
  if (pct < 0 || pct > 100) return null;

  return (
    <div
      className="tl-marker-hit"
      style={{ left: `${pct}%` }}
      onClick={(e) => { e.stopPropagation(); onClick(event); }}
      title={`${event.event_name}: ${event.value}${event.unit ? ' ' + event.unit : ''}`}
    >
      <div className={`tl-marker ${isSelected ? 'selected' : ''}`} />
    </div>
  );
}

function Lane({ label, events, windowStart, windowEnd, selectedEvent, onMarkerClick }) {
  return (
    <div className="tl-lane">
      <div className="tl-lane-label">{label}</div>
      <div className="tl-lane-canvas" style={{ height: LANE_HEIGHT }}>
        <div className="tl-lane-line" />
        {events.map((ev, i) => (
          <Marker
            key={`${ev.server_timestamp}-${i}`}
            event={ev}
            windowStart={windowStart}
            windowEnd={windowEnd}
            onClick={onMarkerClick}
            isSelected={selectedEvent?.server_timestamp === ev.server_timestamp}
          />
        ))}
      </div>
    </div>
  );
}

function TimeAxis({ windowStart, windowEnd }) {
  const ticks = [];
  const duration = windowEnd - windowStart;
  const intervals = [1, 2, 5, 10, 15, 30, 60, 120];
  const target = 8;
  const interval = intervals.find(i => duration / i <= target) || 120;

  const first = Math.ceil(windowStart / interval) * interval;
  for (let t = first; t <= windowEnd; t += interval) {
    const pct = tsToPercent(t, windowStart, windowEnd);
    ticks.push({ pct, label: formatTime(t) });
  }

  return (
    <div className="tl-axis" style={{ marginLeft: LABEL_WIDTH }}>
      {ticks.map(({ pct, label }) => (
        <div key={label} className="tl-axis-tick" style={{ left: `${pct}%` }}>
          <div className="tl-axis-tick-line" />
          <div className="tl-axis-tick-label">{label}</div>
        </div>
      ))}
    </div>
  );
}

function DetailCard({ event, onClose }) {
  if (!event) return null;
  const drift = formatDrift(event.server_timestamp, event.device_timestamp);
  return (
    <div className="tl-detail-card">
      <div className="tl-detail-header">
        <span className="tl-detail-title">Event Detail</span>
        <button className="tl-detail-close" onClick={onClose}>✕</button>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Device</span>
        <span className="tl-detail-value amber">{event.device_id}</span>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Event</span>
        <span className="tl-detail-value">{event.event_name}</span>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Value</span>
        <span className="tl-detail-value cyan">
          {event.value}{event.unit ? ` ${event.unit}` : ''}
        </span>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Server time</span>
        <span className="tl-detail-value">{formatTime(event.server_timestamp)}</span>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Device time</span>
        <span className="tl-detail-value">
          {event.device_timestamp ? formatTime(event.device_timestamp) : 'N/A'}
        </span>
      </div>
      <div className="tl-detail-row">
        <span className="tl-detail-label">Clock drift</span>
        <span className={`tl-detail-value ${drift !== 'N/A' && drift !== '+0ms' ? 'amber' : 'green'}`}>
          {drift}
        </span>
      </div>
    </div>
  );
}

export default function Timeline({ events }) {
  const [windowDuration, setWindowDuration] = useState(DEFAULT_WINDOW);
  const [windowEnd, setWindowEnd]           = useState(() => Date.now() / 1000);
  const [laneMode, setLaneMode]             = useState('device');
  const [selectedEvent, setSelectedEvent]   = useState(null);
  const tickRef = useRef(null);

  useEffect(() => {
    tickRef.current = setInterval(() => {
      setWindowEnd(Date.now() / 1000);
    }, 1000);
    return () => clearInterval(tickRef.current);
  }, []);

  const windowStart = windowEnd - windowDuration;

  const zoomIn  = useCallback(() =>
    setWindowDuration(d => Math.max(MIN_WINDOW, d - (d > 30 ? 10 : 2))), []);
  const zoomOut = useCallback(() =>
    setWindowDuration(d => Math.min(MAX_WINDOW, d + (d >= 30 ? 10 : 2))), []);

  const handleWheel = useCallback((e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    if (e.deltaY < 0) zoomIn(); else zoomOut();
  }, [zoomIn, zoomOut]);

  // Build lane map from events
  const laneMap = events.reduce((acc, ev) => {
    const key = laneMode === 'device' ? ev.device_id : ev.event_name;
    if (!acc[key]) acc[key] = [];
    acc[key].push(ev);
    return acc;
  }, {});

  // Sort lanes alphabetically so order never changes as new events arrive
  const sortedLanes = Object.entries(laneMap).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="tl-root" onClick={() => setSelectedEvent(null)}>
      <div className="tl-toolbar">
        <div className="tl-toolbar-left">
          <div className="scroll-toggle">
            <span className="scroll-toggle-label">LANES</span>
            <div className="scroll-toggle-group">
              <button
                className={`scroll-btn ${laneMode === 'device' ? 'active' : ''}`}
                onClick={() => setLaneMode('device')}
              >Device</button>
              <button
                className={`scroll-btn ${laneMode === 'sensor' ? 'active' : ''}`}
                onClick={() => setLaneMode('sensor')}
              >Sensor</button>
            </div>
          </div>
          <span className="tl-window-label">
            Window: <span>{windowDuration}s</span>
          </span>
          <span className="tl-zoom-hint">Ctrl + scroll to zoom</span>
        </div>
        <div className="tl-toolbar-right">
          <div className="tl-zoom">
            <button className="tl-zoom-btn" onClick={zoomOut}>−</button>
            <span className="tl-zoom-label">ZOOM</span>
            <button className="tl-zoom-btn" onClick={zoomIn}>+</button>
          </div>
        </div>
      </div>

      <div className="tl-canvas-wrap" onWheel={handleWheel}>
        <TimeAxis windowStart={windowStart} windowEnd={windowEnd} />
        <div className="tl-lanes">
          {sortedLanes.length === 0 ? (
            <div className="empty-feed" style={{ height: 200 }}>
              <div className="empty-feed-label">No events in window</div>
              <div className="empty-feed-sub">Events will appear as they arrive</div>
            </div>
          ) : (
            sortedLanes.map(([label, laneEvents]) => (
              <Lane
                key={label}
                label={label}
                events={laneEvents}
                windowStart={windowStart}
                windowEnd={windowEnd}
                selectedEvent={selectedEvent}
                onMarkerClick={setSelectedEvent}
              />
            ))
          )}
        </div>
      </div>

      <DetailCard
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
      />
    </div>
  );
}