import React, { useState, useRef, useEffect } from 'react';

const ACCOUNTS = [
  {
    id: 'ACCT-001',
    name: 'Northstar Logistics',
    plan: 'Enterprise',
    icon: '🚀',
    contract: 'Custom SLA + No-fee cancel',
  },
  {
    id: 'ACCT-002',
    name: 'LumenWorks',
    plan: 'Growth',
    icon: '💡',
    contract: 'Custom service credits',
  },
  {
    id: 'ACCT-003',
    name: 'Beacon Retail',
    plan: 'Standard',
    icon: '🏪',
    contract: 'Standard policy',
  },
  {
    id: 'ACCT-004',
    name: 'Axis Labs',
    plan: 'Enterprise',
    icon: '🔬',
    contract: 'Standard Enterprise policy',
  },
  {
    id: 'ACCT-005',
    name: 'Horizon Trade',
    plan: 'Growth',
    icon: '🌐',
    contract: 'Standard Growth policy',
  },
  {
    id: 'ACCT-006',
    name: 'Summit Tech',
    plan: 'Enterprise',
    icon: '🏔️',
    contract: 'Enterprise Priority SLA policy',
  },
  {
    id: 'INTERNAL-OPERATIONS',
    name: 'Internal Support (Operations)',
    plan: 'Staff Admin',
    icon: '🛡️',
    contract: 'All-access auditing context',
  },
];

export default function LoginSelect({ onLogin }) {
  const [selected, setSelected] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown if clicked outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleEnter = () => {
    if (!selected) return;
    onLogin(selected);
  };

  const selectAccount = (acct) => {
    setSelected(acct);
    setIsOpen(false);
  };

  return (
    <div className="login-overlay">
      <div className="login-card">
        <div className="login-logo">📦</div>
        <h1>ParcelPilot Support</h1>
        <p>AI-powered support agent with policy-precedence reasoning.<br />Select your account to continue.</p>

        <div className="login-label">Select User Account</div>

        {/* Custom Select Dropdown */}
        <div className="dropdown-container" ref={dropdownRef}>
          <div
            className={`dropdown-header ${isOpen ? 'open' : ''}`}
            onClick={() => setIsOpen(!isOpen)}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {selected ? (
                <>
                  <span>{selected.icon}</span>
                  <span style={{ fontWeight: '500' }}>{selected.name}</span>
                </>
              ) : (
                <span style={{ color: 'var(--text-muted)' }}>Select User...</span>
              )}
            </span>
            <span className={`dropdown-arrow ${isOpen ? 'open' : ''}`}>▼</span>
          </div>

          {isOpen && (
            <ul className="dropdown-list">
              {ACCOUNTS.map((acct) => (
                <li
                  key={acct.id}
                  className={`dropdown-item ${selected?.id === acct.id ? 'selected' : ''}`}
                  onClick={() => selectAccount(acct)}
                >
                  <span style={{ fontSize: '18px' }}>{acct.icon}</span>
                  <div className="dropdown-item-details">
                    <span className="dropdown-item-title">{acct.name}</span>
                    <span className="dropdown-item-meta">{acct.plan} • {acct.id}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Selected Account Entitlements/Details Display */}
        {selected && (
          <div className="selected-details-card">
            <div className="details-row">
              <span className="details-label">CSM / Plan:</span>
              <span className="details-value">{selected.plan} Account</span>
            </div>
            <div className="details-row">
              <span className="details-label">Account ID:</span>
              <span className="details-value" style={{ fontFamily: 'monospace' }}>{selected.id}</span>
            </div>
            <div className="details-row">
              <span className="details-label">Agreement Policy:</span>
              <span className="details-value accent-text">{selected.contract}</span>
            </div>
          </div>
        )}

        <button
          className="login-enter-btn"
          disabled={!selected}
          onClick={handleEnter}
        >
          {selected ? `Login as ${selected.name} →` : 'Select an account to login'}
        </button>
      </div>
    </div>
  );
}
