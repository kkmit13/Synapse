const CATEGORY_LABELS = {
  out_of_range:       'Out of range value',
  motor_stall:        'Motor stall',
  heap_exhaustion:    'Heap exhaustion',
  wifi_dropout:       'WiFi dropout',
  sensor_disconnect:  'Sensor disconnect',
  correlated_failure: 'Correlated failure',
  spike:              'Abnormal spike',
};

function severityColor(severity) {
  switch (severity) {
    case 'high':   return 'crimson';
    case 'medium': return 'amber';
    case 'low':    return 'cyan';
    default:       return 'cyan';
  }
}

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().split(' ')[0] + '.' +
    String(d.getMilliseconds()).padStart(3, '0');
}

// Key used to match feedback entries to anomaly cards
function feedbackKey(anomaly) {
  return `${anomaly.device_id}|${anomaly.event_name}|${anomaly.category}`;
}

function AnomalyCard({ anomaly, isSnoozed, onSnooze, onUnsnooze, feedbackVerdict, onFeedback }) {
  const color         = severityColor(anomaly.severity);
  const categoryLabel = CATEGORY_LABELS[anomaly.category] || anomaly.category || 'Unknown';

  return (
    <div className={`anomaly-card anomaly-${color} ${isSnoozed ? 'anomaly-snoozed' : ''}`}>
      <div className="anomaly-card-header">
        <div className="anomaly-header-left">
          <span className={`anomaly-severity anomaly-severity-${color}`}>
            {anomaly.severity.toUpperCase()}
          </span>
          <span className="anomaly-device">{anomaly.device_id}</span>
          <span className="anomaly-event">{anomaly.event_name}</span>
        </div>
        <div className="anomaly-card-actions">
          <span className="anomaly-time">
            {anomaly.detected_at ? formatTime(anomaly.detected_at) : ''}
          </span>
          <button
            className={`anomaly-snooze-btn ${isSnoozed ? 'anomaly-snooze-btn-active' : ''}`}
            onClick={() => isSnoozed ? onUnsnooze(anomaly) : onSnooze(anomaly)}
            title={isSnoozed
              ? 'Unsnooze — AI will flag this again'
              : 'Snooze — tell AI this is expected this session'}
          >
            {isSnoozed ? '↺ Unsnooze' : '— Snooze'}
          </button>
        </div>
      </div>

      <div className="anomaly-category-tag">{categoryLabel}</div>
      <div className="anomaly-title">{anomaly.title}</div>

      {isSnoozed && (
        <div className="anomaly-snoozed-label">
          Snoozed this session — AI will not flag "{categoryLabel}" on {anomaly.device_id} / {anomaly.event_name} again until you clear or unsnooze
        </div>
      )}

      {!isSnoozed && (
        <>
          <div className="anomaly-explanation">{anomaly.explanation}</div>
          <div className="anomaly-suggestion">
            <span className="anomaly-suggestion-label">Fix: </span>
            {anomaly.suggestion}
          </div>

          {/* Feedback buttons */}
          <div className="anomaly-feedback-row">
            <span className="anomaly-feedback-label">Was this correct?</span>
            <div className="anomaly-feedback-btns">
              <button
                className={`anomaly-feedback-btn anomaly-feedback-confirm
                  ${feedbackVerdict === 'confirmed' ? 'anomaly-feedback-confirm-active' : ''}`}
                onClick={() => onFeedback(anomaly, feedbackVerdict === 'confirmed' ? null : 'confirmed')}
                title="Confirm — this is a real issue, keep watching for it"
              >
                ✓ Real
              </button>
              <button
                className={`anomaly-feedback-btn anomaly-feedback-fp
                  ${feedbackVerdict === 'false_positive' ? 'anomaly-feedback-fp-active' : ''}`}
                onClick={() => onFeedback(anomaly, feedbackVerdict === 'false_positive' ? null : 'false_positive')}
                title="False positive — this is expected behavior, stop flagging it"
              >
                ✗ False positive
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function AnomalyLog({ anomalies, snoozed, feedback, onSnooze, onUnsnooze, onFeedback, onClose }) {
  function isSnoozed(anomaly) {
    return snoozed.some(
      s => s.device_id  === anomaly.device_id  &&
           s.event_name === anomaly.event_name &&
           s.category   === anomaly.category
    );
  }

  function getVerdict(anomaly) {
    const entry = feedback.find(f =>
      f.device_id  === anomaly.device_id  &&
      f.event_name === anomaly.event_name &&
      f.category   === anomaly.category
    );
    return entry ? entry.verdict : null;
  }

  return (
    <div className="anomaly-log">
      <div className="anomaly-log-header">
        <div className="panel-title">
          <span>⚠</span> Anomaly Log
        </div>
        <div className="anomaly-log-header-right">
          {snoozed.length > 0 && (
            <span className="anomaly-snoozed-count">{snoozed.length} snoozed</span>
          )}
          <span className="anomaly-count">{anomalies.length} detected</span>
          <button className="tl-detail-close" onClick={onClose}>✕</button>
        </div>
      </div>
      <div className="anomaly-log-body">
        {anomalies.length === 0 ? (
          <div className="empty-feed" style={{ height: 160 }}>
            <div className="empty-feed-label">No anomalies detected</div>
            <div className="empty-feed-sub">AI is monitoring your devices</div>
          </div>
        ) : (
          [...anomalies].reverse().map((a, i) => (
            <AnomalyCard
              key={i}
              anomaly={a}
              isSnoozed={isSnoozed(a)}
              feedbackVerdict={getVerdict(a)}
              onSnooze={onSnooze}
              onUnsnooze={onUnsnooze}
              onFeedback={onFeedback}
            />
          ))
        )}
      </div>
    </div>
  );
}