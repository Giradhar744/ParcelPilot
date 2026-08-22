// ThinkingIndicator.jsx
// Cycles through a fixed label sequence while a request is in flight.
// Not driven by backend events — purely client-side timer for perceived progress.
// Stops on the last label if response takes longer than the sequence.

import { useState, useEffect } from 'react';

const LABELS = [
  'Thinking...',
  'Searching policies...',
  'Fetching order data...',
  'Comparing results...',
];

const INTERVAL_MS = 1800;

export default function ThinkingIndicator() {
  const [labelIdx, setLabelIdx] = useState(0);

  useEffect(() => {
    if (labelIdx >= LABELS.length - 1) return; // stop at last label
    const t = setTimeout(() => setLabelIdx((i) => i + 1), INTERVAL_MS);
    return () => clearTimeout(t);
  }, [labelIdx]);

  return (
    <div className="thinking-row">
      <div className="msg-avatar agent">🤖</div>
      <div className="thinking-bubble">
        <div className="thinking-dots">
          <span /><span /><span />
        </div>
        <span className="thinking-label">{LABELS[labelIdx]}</span>
      </div>
    </div>
  );
}
