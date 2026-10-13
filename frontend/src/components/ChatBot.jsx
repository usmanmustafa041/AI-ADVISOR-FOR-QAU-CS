import React, { useState, useRef, useEffect } from 'react';
import '../styles/chatbot.css';

export default function ChatBot() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  
  const initialMessage = {
    id: 'welcome',
    type: 'assistant',
    content: 'Assalamu Alaikum! 👋 Welcome to QAU CS Academic Advisor. I can help you with course schedules, academic information, and more. What would you like to know?',
    timestamp: new Date(),
    verified: true
  };
  
  const [messages, setMessages] = useState([initialMessage]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Load sessions from localStorage on mount
  useEffect(() => {
    const savedSessionIds = JSON.parse(localStorage.getItem('chat_sessions') || '[]');
    if (savedSessionIds.length > 0) {
      fetchSessions(savedSessionIds);
    }
  }, []);

  const fetchSessions = async (sessionIds) => {
    try {
      const response = await fetch('/api/v1/history/sessions/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_ids: sessionIds })
      });
      if (response.ok) {
        const data = await response.json();
        setSessions(data);
      }
    } catch (error) {
      console.error('Error fetching sessions:', error);
    }
  };

  const loadSessionMessages = async (sessionId) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/history/sessions/${sessionId}`);
      if (response.ok) {
        const history = await response.json();
        const formattedMessages = history.map(msg => ({
          id: msg.id,
          type: msg.role === 'user' ? 'user' : 'assistant',
          content: msg.content,
          timestamp: new Date(msg.created_at),
          verified: msg.role === 'assistant'
        }));
        if (formattedMessages.length === 0) {
          setMessages([initialMessage]);
        } else {
          setMessages(formattedMessages);
        }
      }
    } catch (error) {
      console.error('Error loading session messages:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSession = (sessionId) => {
    setActiveSessionId(sessionId);
    loadSessionMessages(sessionId);
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([initialMessage]);
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await fetch(`/api/v1/history/sessions/${sessionId}`, { method: 'DELETE' });
      const newSessions = sessions.filter(s => s.id !== sessionId);
      setSessions(newSessions);
      
      const sessionIds = newSessions.map(s => s.id);
      localStorage.setItem('chat_sessions', JSON.stringify(sessionIds));
      
      if (activeSessionId === sessionId) {
        handleNewChat();
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const payload = {
        message: input,
        session_id: activeSessionId,
        context_course_code: null
      };

      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const data = await response.json();
      
      // Update activeSessionId and localStorage if this is a new session
      if (!activeSessionId && data.session_id) {
        setActiveSessionId(data.session_id);
        const savedSessionIds = JSON.parse(localStorage.getItem('chat_sessions') || '[]');
        if (!savedSessionIds.includes(data.session_id)) {
          const newSessionIds = [data.session_id, ...savedSessionIds];
          localStorage.setItem('chat_sessions', JSON.stringify(newSessionIds));
          // Refetch sessions to get the new title
          fetchSessions(newSessionIds);
        }
      } else if (activeSessionId) {
        // Just refresh the sessions list to update timestamps
        const savedSessionIds = JSON.parse(localStorage.getItem('chat_sessions') || '[]');
        fetchSessions(savedSessionIds);
      }

      const assistantMessage = {
        id: `msg_${Date.now()}`,
        type: 'assistant',
        content: data.answer,
        timestamp: new Date(),
        intent: data.intent,
        confidence: data.confidence,
        verified: data.verified,
        response_type: data.response_type,
        response_time_ms: data.response_time_ms,
        metadata: data.metadata,
        suggestions: data.suggestions,
        escalation: data.escalation
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: `msg_${Date.now()}`,
        type: 'assistant',
        content: '❌ Error: Could not reach the server. Please try again.',
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="app-container">
      <div className="chatbot-sidebar">
        <button className="new-chat-btn" onClick={handleNewChat}>
          <span>+</span> New Chat
        </button>
        <div className="sessions-list-title">Recent Chats</div>
        <div className="sessions-list">
          {sessions.map(session => (
            <div 
              key={session.id} 
              className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
              onClick={() => handleSelectSession(session.id)}
            >
              <div className="session-title">{session.title || 'New Chat'}</div>
              <button 
                className="session-delete-btn" 
                onClick={(e) => handleDeleteSession(e, session.id)}
                title="Delete Chat"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="chatbot-container">
        <div className="chatbot-header">
          <h1>🎓 QAU CS Academic Advisor</h1>
          <p>Professional AI Academic Guidance</p>
        </div>

        <div className="chatbot-messages">
          {messages.map((message) => (
            <div key={message.id} className={`message message-${message.type}`}>
              <div className="message-avatar">{message.type === 'user' ? '👤' : '🤖'}</div>
              <div className="message-body">
                <p className="message-text">{message.content}</p>
                {message.verified && <span className="badge verified">✓ Verified</span>}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message message-assistant">
              <div className="message-avatar">🤖</div>
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="chatbot-input-area">
          <div className="input-wrapper">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about courses, schedules, or policies..."
              className="chat-input"
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              className="send-button"
              disabled={loading || !input.trim()}
            >
              {loading ? '⏳' : '→'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
