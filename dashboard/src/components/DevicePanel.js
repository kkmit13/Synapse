function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().split(' ')[0] + '.' + String(d.getMilliseconds()).padStart(3, '0');
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

export default function DevicePanel({ deviceMap }) {
  return (
    <div className="device-panel">
      <div className="panel-header">
        <div className="panel-title"><span>◈</span> Devices</div>
      </div>
      {Object.keys(deviceMap).length === 0 ? (
        <div style={{ padding: '20px 12px' }}>
          <div className="empty-feed-label" style={{ textAlign: 'center' }}>
            No devices yet
          </div>
        </div>
      ) : (
        Object.entries(deviceMap).map(([deviceId, devEvents]) => (
          <DeviceCard key={deviceId} deviceId={deviceId} events={devEvents} />
        ))
      )}
    </div>
  );
}