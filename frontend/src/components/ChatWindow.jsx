import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import ThinkingIndicator from './ThinkingIndicator';

const SUGGESTIONS = {
  'ACCT-001': [
    'What is our cancellation fee?',
    'Why is our bulk upload failing?',
    'Our SwiftShip order still shows BOOKED after driver pickup. What should we do?'
  ],
  'ACCT-002': [
    'What credit do we receive for a failed pickup?',
    'Show my open tickets.',
    'Our SwiftShip webhook notifications are delayed. Is this a known problem?',
  ],
  'ACCT-003': [
    'What is our cancellation fee?',
    'How do we change the billing contact?',
  ],
  'ACCT-004': [
    'What are the response time SLAs for each priority level?',
    'Show details for order ORD-4001.',
  ],
  'ACCT-005': [
    'What is our cancellation fee?',
    'Show my open tickets.',
    'Show details for order ORD-5001.',
  ],
  'ACCT-006': [
    'What are the response time SLAs for each priority level?',
    'Show my open tickets.',
    'Show details for order ORD-6001.',
  ],
  'INTERNAL-OPERATIONS': [
    'List all support tickets across the platform.',
    'SLA Audit: Do we have any unresolved tickets approaching or exceeding SLA response limits?',
    'Issue Detection: Inspect tickets to find recurring complaints or patterns of carrier failure.',
    'Compare the contract cancellation terms of Northstar (ACCT-001) vs. LumenWorks (ACCT-002).',
  ],
};

export default function ChatWindow({ account, messages, setMessages, onLogout }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [queue, setQueue] = useState([]);
  const messagesEndRef = useRef(null);
  const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

  const loadQueue = async () => {
    if (account.id !== 'INTERNAL-OPERATIONS') return;
    try {
      const res = await fetch(`${BACKEND}/internal/tickets`);
      if (res.ok) {
        const data = await res.json();
        setQueue(data.tickets || []);
      }
    } catch (e) {
      console.error('Failed to load tickets queue:', e);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [account]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const text = textToSend || input.trim();
    if (!text) return;

    if (!textToSend) {
      setInput('');
    }

    const userMessage = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setLoading(true);

    try {
      // Build history payload: standard openai-compatible array of {role, content}
      // LangChain/LangGraph backend expects: history: list[dict]
      const historyPayload = messages.map(m => ({
        role: m.role,
        content: m.content
      }));

      const res = await fetch(`${BACKEND}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: account.id,
          message: text,
          history: historyPayload,
        }),
      });

      if (!res.ok) {
        throw new Error('Server error or invalid response.');
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          tools_used: data.tools_used || [],
          sources: data.sources || [],
          proposed_action: data.proposed_action || null,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, something went wrong: ${err.message}. Please check that the backend server is running and configured correctly.`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleActionCompletion = (targetMessage, status, resultMsg) => {
    if (status === 'success') {
      setTimeout(() => { loadQueue(); }, 200);
    }
    setMessages((prev) => {
      // Clear proposed_action so the card disappears
      const updated = prev.map((m) => {
        if (m === targetMessage) {
          return { ...m, proposed_action: null };
        }
        return m;
      });

      // Define outcome message based on confirm / cancel status
      const outcomeContent =
        status === 'success'
          ? `Your escalation request has been submitted successfully (${resultMsg || 'Ticket Escalated'}). Someone from our support team will reach out shortly. How else can I help you?`
          : 'Human escalation has been cancelled. How else can I help you today?';

      return [
        ...updated,
        {
          role: 'assistant',
          content: outcomeContent,
          timestamp: new Date().toISOString(),
        },
      ];
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = SUGGESTIONS[account.id] || SUGGESTIONS['ACCT-003'];

  const isInternal = account.id === 'INTERNAL-OPERATIONS';

  return (
    <div className="chat-layout">
      {/* Header */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">
            <img src="/logo.png" alt="ParcelPilot Logo" />
          </div>
          <div>
            <div className="header-title">ParcelPilot Support Agent</div>
            <div className="header-subtitle">LangGraph Core • Policy Precedence</div>
          </div>
        </div>
        <button className="header-account-badge" onClick={onLogout}>
          <div className="header-account-dot" />
          <span>{account.name} ({account.plan})</span>
          <span style={{ marginLeft: '8px', color: 'var(--danger)', fontWeight: '500' }}>✕ Logout</span>
        </button>
      </header>

      {/* Split Layout for Internal Admin vs. Single Chat for normal Customer */}
      <div className={isInternal ? "internal-split-layout" : "internal-chat-area"}>

        {/* Main Chat Flow (left side if split) */}
        <div className="internal-chat-area">
          <main className="messages-area">
            <div className="messages-inner">
              {messages.length === 0 ? (
                <div className="welcome-msg">
                  <h2>Welcome to ParcelPilot Support, {account.name}!</h2>
                  <p style={{ marginTop: '4px' }}>
                    You are logged in with account ID <strong>{account.id}</strong>. Custom agreement rules for your <strong>{account.plan}</strong> account will be applied automatically.
                  </p>
                  <p style={{ marginTop: '16px', fontSize: '11px', color: 'var(--text-muted)' }}>
                    SUGGESTED INQUIRIES
                  </p>
                  <div className="welcome-suggestions">
                    {suggestions.map((sug, idx) => (
                      <button
                        key={idx}
                        className="suggestion-chip"
                        onClick={() => handleSend(sug)}
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, index) => (
                  <MessageBubble
                    key={index}
                    message={msg}
                    onConfirmDone={handleActionCompletion}
                  />
                ))
              )}

              {loading && <ThinkingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          </main>

          <footer className="input-area">
            <div className="input-inner">
              <textarea
                className="input-box"
                placeholder="Type your support query here... (Shift+Enter for new line)"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <button
                className="send-btn"
                onClick={() => handleSend()}
                disabled={loading || !input.trim()}
              >
                🚀
              </button>
            </div>
          </footer>
        </div>

        {/* Active Support Tickets Sidebar Queue (Right side - Admin Context Only) */}
        {isInternal && (
          <aside className="internal-queue-panel">
            <div className="queue-header">
              <div className="queue-title">🛡️ Active Platform Queue</div>
              <span className="queue-count-badge">{queue.length} Active</span>
            </div>
            <div className="queue-list">
              {queue.length === 0 ? (
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', marginTop: '20px' }}>
                  No active escalated tickets.
                </p>
              ) : (
                queue.map((t) => (
                  <div className="queue-card" key={t.ticket_id}>
                    <div className="queue-card-header">
                      <span className="queue-user-name">{t.account_name || 'Walk-in User'}</span>
                      <span className={`queue-prio-badge prio-${t.priority || '3'}`}>
                        P{t.priority || '3'} {t.priority === '1' ? 'Urgent' : t.priority === '2' ? 'High' : 'Normal'}
                      </span>
                    </div>
                    <p className="queue-subject" style={{ fontWeight: '500', color: 'var(--text-primary)' }}>
                      {t.subject}
                    </p>
                    <p className="queue-subject" style={{ fontSize: '11px', opacity: 0.8 }}>
                      {t.description}
                    </p>
                    <div className="queue-meta">
                      <span>{t.ticket_id}</span>
                      {t.deadline_at && (
                        <span className="queue-deadline">SLA Target: {t.deadline_at}</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
