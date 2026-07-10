import { useState, useEffect, useRef } from 'react';
import './App.css';
import Feed from './components/Feed';
import DevicePanel from './components/DevicePanel';
import Timeline from './components/Timeline';

const WS_URL = 'ws://127.0.0.1:8000/ws';
const API_URL = 'http://127.0.0.1:8000';

const SCROLL_MODES = [
  { id: 'autoscroll', label: 'Auto' },
  { id: 'top',        label: 'Top'  },
  { id: 'none',       label: 'Off'  },
];

export default function App() {
  const [events, setEvents]         = useState([]);
  const [connected, setConnected]   = useState(false);
  const [newestId, setNewestId]     = useState(null);
  const [scrollMode, setScrollMode] = useState('autoscroll');
  const [activeTab, setActiveTab]   = useState('feed');
  const wsRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/events`)
      .then(r => r.json())
      .then(data => setEvents(data.reverse()))
      .catch(() => {});
  }, []);

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
          {/* TAB BAR */}
          <div className="tab-bar">
            <button
              className={`tab-btn ${activeTab === 'feed' ? 'active' : ''}`}
              onClick={() => setActiveTab('feed')}
            >
              Feed
            </button>
            <button
              className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              Timeline
            </button>
          </div>
        </div>
        <div className="topbar-right">
          <div className="scroll-toggle">
            <span className="scroll-toggle-label">SCROLL</span>
            <div className="scroll-toggle-group">
              {SCROLL_MODES.map(mode => (
                <button
                  key={mode.id}
                  className={`scroll-btn ${scrollMode === mode.id ? 'active' : ''}`}
                  onClick={() => setScrollMode(mode.id)}
                >
                  {mode.label}
                </button>
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

      {/* MAIN */}
      <div className="main">
        {activeTab === 'feed' ? (
          <>
            <Feed
              events={events}
              newestId={newestId}
              scrollMode={scrollMode}
            />
            <DevicePanel deviceMap={deviceMap} />
          </>
        ) : (
          <Timeline events={events} />
        )}
      </div>
    </div>
  );
}