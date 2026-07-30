import { useState, useEffect, useRef } from 'react';
import './App.css';
import Feed from './components/Feed';
import DevicePanel from './components/DevicePanel';
import Timeline from './components/Timeline';
import AnomalyLog from './components/AnomalyLog';
import AIPanel from './components/AIPanel';

const WS_URL = 'ws://127.0.0.1:8000/ws';
const API_URL = 'http://127.0.0.1:8000';

const SCROLL_MODES = [
  { id: 'autoscroll', label: 'Auto' },
  { id: 'top',        label: 'Top'  },
  { id: 'none',       label: 'Off'  },
];

// Snooze key is now device_id + event_name + category
// category is stable (picked from a fixed list in ai.py) so matching is reliable
function snoozeMatch(s, anomaly) {
  return s.device_id  === anomaly.device_id  &&
         s.event_name === anomaly.event_name &&
         s.category   === anomaly.category;
}

export default function App() {
  const [events, setEvents]                 = useState([]);
  const [connected, setConnected]           = useState(false);
  const [newestId, setNewestId]             = useState(null);
  const [scrollMode, setScrollMode]         = useState('autoscroll');
  const [activeTab, setActiveTab]           = useState('feed');
  const [anomalies, setAnomalies]           = useState([]);
  const [snoozed, setSnoozed]               = useState([]); // [{device_id, event_name, category}]
  const [showAnomalyLog, setShowAnomalyLog] = useState(false);
  const [showAIPanel, setShowAIPanel]       = useState(false);
  const [aiFullscreen, setAiFullscreen]     = useState(false);
  const [notification, setNotification]     = useState(null);
  const [clearing, setClearing]             = useState(false);

  const wsRef          = useRef(null);
  const notifTimer     = useRef(null);
  const anomalyLogOpen = useRef(false);
  const snoozedRef     = useRef([]);

  useEffect(() => {
    anomalyLogOpen.current = showAnomalyLog;
  }, [showAnomalyLog]);

  useEffect(() => {
    snoozedRef.current = snoozed;
    fetch(`${API_URL}/snoozed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(snoozed)
    }).catch(() => {});
  }, [snoozed]);

  useEffect(() => {
    fetch(`${API_URL}/events`)
      .then(r => r.json())
      .then(data => setEvents(data.reverse()))
      .catch(() => {});

    fetch(`${API_URL}/anomalies`)
      .then(r => r.json())
      .then(data => setAnomalies(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);

      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);

        if (data.type === 'clear') {
          setEvents([]);
          setAnomalies([]);
          setSnoozed([]);
          setNewestId(null);
          setNotification(null);
        } else if (data.type === 'anomaly') {
          setAnomalies(prev => [...prev, data.anomaly].slice(-50));
          const isSnoozing = snoozedRef.current.some(s => snoozeMatch(s, data.anomaly));
          if (!anomalyLogOpen.current && !isSnoozing) {
            showNotif(data.anomaly);
          }
        } else {
          setNewestId(data.server_timestamp);
          setEvents(prev => [data, ...prev].slice(0, 500));
        }
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

  function showNotif(anomaly) {
    setNotification(anomaly);
    clearTimeout(notifTimer.current);
    notifTimer.current = setTimeout(() => setNotification(null), 5000);
  }

  function handleSnooze(anomaly) {
    setSnoozed(prev => {
      const already = prev.some(s => snoozeMatch(s, anomaly));
      if (already) return prev;
      return [...prev, {
        device_id:  anomaly.device_id,
        event_name: anomaly.event_name,
        category:   anomaly.category,
      }];
    });
    if (notification && snoozeMatch(notification, anomaly)) {
      setNotification(null);
    }
  }

  function handleUnsnooze(anomaly) {
    setSnoozed(prev => prev.filter(s => !snoozeMatch(s, anomaly)));
  }

  async function handleClear() {
    const confirmed = window.confirm(
      'Clear all events and anomalies? This starts a fresh session.'
    );
    if (!confirmed) return;

    setClearing(true);
    try {
      await fetch(`${API_URL}/clear`, { method: 'POST' });
    } catch (e) {
      console.error('Clear failed:', e);
    } finally {
      setClearing(false);
    }
  }

  const deviceMap = events.reduce((acc, ev) => {
    if (!acc[ev.device_id]) acc[ev.device_id] = [];
    acc[ev.device_id].push(ev);
    return acc;
  }, {});

  return (
    <div>
      <div className="topbar">
        <div className="topbar-left">
          <div>
            <div className="logo">Synapse</div>
            <div className="logo-sub">Embedded Debugger</div>
          </div>
          <div className="tab-bar">
            <button
              className={`tab-btn ${activeTab === 'feed' ? 'active' : ''}`}
              onClick={() => setActiveTab('feed')}
            >Feed</button>
            <button
              className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >Timeline</button>
          </div>
        </div>
        <div className="topbar-right">

          <button
            className={`topbar-ai-btn ${showAIPanel ? 'active' : ''}`}
            onClick={() => { setShowAIPanel(v => !v); setAiFullscreen(false); }}
          >
            ◆ Synapse AI
          </button>

          <button
            className={`topbar-anomaly-btn ${showAnomalyLog ? 'active' : ''}`}
            onClick={() => setShowAnomalyLog(v => !v)}
          >
            ⚠ Anomalies
            {anomalies.length > 0 && (
              <span className="anomaly-badge">{anomalies.length}</span>
            )}
          </button>

          <button
            className="topbar-clear-btn"
            onClick={handleClear}
            disabled={clearing}
            title="Wipe all events and anomalies — start fresh"
          >
            {clearing ? '...' : '⟳ Clear'}
          </button>

          <div className="scroll-toggle">
            <span className="scroll-toggle-label">SCROLL</span>
            <div className="scroll-toggle-group">
              {SCROLL_MODES.map(mode => (
                <button
                  key={mode.id}
                  className={`scroll-btn ${scrollMode === mode.id ? 'active' : ''}`}
                  onClick={() => setScrollMode(mode.id)}
                >{mode.label}</button>
              ))}
            </div>
          </div>

          <div className="status-pill">
            <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
            {connected ? 'LIVE' : 'RECONNECTING'}
          </div>
          <div className="stat-chip">EVENTS <span>{events.length}</span></div>
          <div className="stat-chip">DEVICES <span>{Object.keys(deviceMap).length}</span></div>
        </div>
      </div>

      {notification && (
        <div
          className={`anomaly-toast anomaly-toast-${notification.severity}`}
          onClick={() => { setShowAnomalyLog(true); setNotification(null); }}
        >
          <span className="anomaly-toast-icon">⚠</span>
          <div className="anomaly-toast-content">
            <div className="anomaly-toast-title">{notification.title}</div>
            <div className="anomaly-toast-sub">
              {notification.device_id} — {notification.event_name}
            </div>
          </div>
          <button
            className="anomaly-toast-close"
            onClick={e => { e.stopPropagation(); setNotification(null); }}
          >✕</button>
        </div>
      )}

      <div className="app-body">

        {!aiFullscreen && (
          <div className="main">
            {activeTab === 'feed' ? (
              <>
                <Feed events={events} newestId={newestId} scrollMode={scrollMode} />
                <DevicePanel deviceMap={deviceMap} />
              </>
            ) : (
              <Timeline events={events} anomalies={anomalies} />
            )}
          </div>
        )}

        {showAnomalyLog && !aiFullscreen && (
          <AnomalyLog
            anomalies={anomalies}
            snoozed={snoozed}
            onSnooze={handleSnooze}
            onUnsnooze={handleUnsnooze}
            onClose={() => setShowAnomalyLog(false)}
          />
        )}

        {showAIPanel && (
          <AIPanel
            fullscreen={aiFullscreen}
            onToggleFullscreen={() => setAiFullscreen(v => !v)}
            onClose={() => { setShowAIPanel(false); setAiFullscreen(false); }}
          />
        )}

      </div>
    </div>
  );
}