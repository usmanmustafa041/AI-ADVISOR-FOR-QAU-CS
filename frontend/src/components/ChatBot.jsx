import React, { useState, useRef, useEffect } from 'react';
import '../styles/chatbot.css';

export default function ChatBot() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      type: 'assistant',
      content: 'Assalamu Alaikum! 👋 Welcome to QAU CS Academic Advisor. I can help you with course schedules, academic information, and more. What would you like to know?',
      timestamp: new Date(),
      verified: true
    }
  ]);
  
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [sessionId] = useState(() => `session_${Date.now()}`);

  const suggestedQueries = [
    "When is CS-104?",
    "What classes on Monday?",
    "Tell me about CS-211",
    "Show Friday schedule"
  ];

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
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
          context_course_code: null
        })
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const data = await response.json();

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
  );
}
