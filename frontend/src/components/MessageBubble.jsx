import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ToolBadge from './ToolBadge';
import ConfirmAction from './ConfirmAction';

export default function MessageBubble({ message, onConfirmDone }) {
  const isUser = message.role === 'user';
  const avatar = isUser ? '👤' : '🤖';
  const roleClass = isUser ? 'user' : 'agent';
  const timeStr = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={`message-row ${roleClass}`}>
      <div className={`msg-avatar ${roleClass}`}>{avatar}</div>
      <div className="msg-content">
        <div className={`msg-bubble ${roleClass}`}>
          {isUser ? (
            // User messages don't need full GFM/table support, simple text is fine
            <p>{message.content}</p>
          ) : (
            // Agent messages get full Markdown rendering (bold, lists, tables)
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="sources-tray">
              <span className="sources-label">📚 Cited Sources:</span>
              {message.sources.map((src, idx) => (
                <span key={idx} className="source-pill" title={src}>
                  {src.replace('.pdf', '').replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
          
          {message.proposed_action && (
            <ConfirmAction
              proposedAction={message.proposed_action}
              onDone={(status, resultMsg) => onConfirmDone?.(message, status, resultMsg)}
            />
          )}
        </div>
        <div className="msg-meta">
          {timeStr && <span className="msg-time">{timeStr}</span>}
          {!isUser && message.tools_used && message.tools_used.length > 0 && (
            <ToolBadge tools={message.tools_used} />
          )}
        </div>
      </div>
    </div>
  );
}
