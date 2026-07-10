import { useRef, useEffect } from 'react';

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

export default function Feed({ events, newestId, scrollMode }) {
  const feedRef = useRef(null);
  const userScrolled = useRef(false);

  useEffect(() => {
    const feed = feedRef.current;
    if (!feed || userScrolled.current) return;
    if (scrollMode === 'top' || scrollMode === 'autoscroll') {
      feed.scrollTop = 0;
    }
  }, [events, scrollMode]);

  useEffect(() => {
    const feed = feedRef.current;
    if (!feed) return;
    const handleScroll = () => {
      userScrolled.current = feed.scrollTop > 50;
    };
    feed.addEventListener('scroll', handleScroll);
    return () => feed.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    userScrolled.current = false;
  }, [scrollMode]);

  return (
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
  );
}