// ToolBadge.jsx — Small chip showing which tool(s) the agent used

export default function ToolBadge({ tools }) {
  if (!tools || tools.length === 0) return null;

  const TOOL_META = {
    search_docs:    { icon: '📄', label: 'search_docs' },
    query_data:     { icon: '🗄️',  label: 'query_data' },
    propose_action: { icon: '⚡',  label: 'propose_action' },
  };

  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {tools.map((tool) => {
        const meta = TOOL_META[tool] || { icon: '🔧', label: tool };
        return (
          <span key={tool} className="tool-badge">
            {meta.icon} {meta.label}
          </span>
        );
      })}
    </div>
  );
}
