// ConfirmAction.jsx
// Displays a proposed action (from agent) and blocks execution until user confirms.
// On Confirm → calls POST /confirm with action_id.
// On Cancel  → dismisses silently.

import { useState } from 'react';

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default function ConfirmAction({ proposedAction, onDone }) {
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [resultMsg, setResultMsg] = useState('');

  if (!proposedAction) return null;

  const handleConfirm = async () => {
    setStatus('loading');
    try {
      const res = await fetch(`${BACKEND}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_id: proposedAction.action_id }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Confirmation failed');
      setStatus('success');
      setResultMsg(data.result?.result?.message || 'Action completed successfully.');
      setTimeout(() => {
        onDone?.('success', data.result?.result?.message);
      }, 800);
    } catch (err) {
      setStatus('error');
      setResultMsg(err.message);
    }
  };

  const handleCancel = () => {
    onDone?.('cancelled');
  };

  return (
    <div className="confirm-card">
      <div className="confirm-header">
        <span className="confirm-icon">⚡</span>
        <span className="confirm-title">Action Requires Confirmation</span>
      </div>
      <p className="confirm-desc">{proposedAction.description}</p>

      {status === 'idle' && (
        <div className="confirm-actions">
          <button
            className="confirm-btn yes"
            onClick={handleConfirm}
          >
            ✓ Confirm
          </button>
          <button
            className="confirm-btn no"
            onClick={handleCancel}
          >
            ✕ Cancel
          </button>
        </div>
      )}

      {status === 'loading' && (
        <div className="confirm-actions">
          <button className="confirm-btn yes" disabled>Confirming...</button>
        </div>
      )}

      {status === 'success' && (
        <div className="confirm-result success">✓ {resultMsg}</div>
      )}

      {status === 'error' && (
        <div className="confirm-result error">✕ {resultMsg}</div>
      )}
    </div>
  );
}
