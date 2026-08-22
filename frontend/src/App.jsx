import { useState, useEffect } from 'react';
import LoginSelect from './components/LoginSelect';
import ChatWindow from './components/ChatWindow';
import './styles.css';

export default function App() {
  // Load account from localStorage if it exists on mount
  const [account, setAccount] = useState(() => {
    const saved = localStorage.getItem('parcelpilot_account');
    return saved ? JSON.parse(saved) : null;
  });

  // Load messages from localStorage if it exists on mount
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('parcelpilot_messages');
    return saved ? JSON.parse(saved) : [];
  });

  // Sync state to localStorage on state changes
  useEffect(() => {
    if (account) {
      localStorage.setItem('parcelpilot_account', JSON.stringify(account));
      localStorage.setItem('parcelpilot_messages', JSON.stringify(messages));
    } else {
      localStorage.removeItem('parcelpilot_account');
      localStorage.removeItem('parcelpilot_messages');
    }
  }, [account, messages]);

  const handleLogin = (selectedAccount) => {
    setAccount(selectedAccount);
    setMessages([]); // Start a fresh, clean chat section upon login
  };

  const handleLogout = () => {
    setAccount(null);
    setMessages([]); // Clear all message state
  };

  return (
    <div className="app">
      {!account ? (
        <LoginSelect onLogin={handleLogin} />
      ) : (
        <ChatWindow
          account={account}
          messages={messages}
          setMessages={setMessages}
          onLogout={handleLogout}
        />
      )}
    </div>
  );
}
