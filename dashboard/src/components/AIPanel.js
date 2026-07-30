import { useState, useRef, useEffect } from 'react';

const API_URL = 'http://127.0.0.1:8000';

function ChatMessage({ msg }) {
  return (
    <div className={`chat-msg chat-msg-${msg.role}`}>
      <div className="chat-msg-label">
        {msg.role === 'user' ? 'YOU' : 'SYNAPSE AI'}
      </div>
      <div className="chat-msg-text">{msg.text}</div>
    </div>
  );
}

export default function AIPanel({ onClose, fullscreen, onToggleFullscreen }) {
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      text: "Synapse AI ready. Ask me about your sensor data, anomalies, or anything that looks off in your system."
    }
  ]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage() {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: question }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'ai', text: data.response }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'ai',
        text: 'Could not reach the server. Make sure the Synapse server is running.'
      }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className={`ai-panel ${fullscreen ? 'ai-panel-fullscreen' : ''}`}>
      {/* HEADER */}
      <div className="ai-panel-header">
        <div className="panel-title"><span>◆</span> Synapse AI</div>
        <div className="ai-panel-header-actions">
          {/* Fullscreen toggle */}
          <button
            className="ai-panel-icon-btn"
            onClick={onToggleFullscreen}
            title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {fullscreen ? '⊡' : '⊞'}
          </button>
          <button className="tl-detail-close" onClick={onClose}>✕</button>
        </div>
      </div>

      {/* MESSAGES */}
      <div className="ai-panel-messages">
        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}
        {loading && (
          <div className="chat-msg chat-msg-ai">
            <div className="chat-msg-label">SYNAPSE AI</div>
            <div className="chat-thinking">
              <span /><span /><span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* INPUT */}
      <div className="ai-panel-input-wrap">
        <textarea
          className="ai-panel-input"
          placeholder="Ask about your sensor data... (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
        />
        <button
          className="ai-panel-send"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          {loading ? '...' : '→'}
        </button>
      </div>
    </div>
  );
}