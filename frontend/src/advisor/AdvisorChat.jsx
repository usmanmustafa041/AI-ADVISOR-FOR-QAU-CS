import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { AnswerFeedback } from '../components/AnswerFeedback'
import { AdvisorError, advisorRequest, streamAdvisorChat } from './advisorApi'
import './advisor-chat.css'

// Same look, same layout and same class names as the portal's original chat panel; only the engine
// behind it is new. Guests are "ephemeral": the browser keeps the conversation and nothing is stored.

const WELCOME = 'Assalam-o-Alaikum. Ask me about courses, prerequisites, fees, schedules, exams, policies, or research requirements.'
const OUTCOME_LABEL = {
  answered: 'Answer with source citations',
  cached: 'Answer with source citations',
  abstained: 'Not found in the department sources',
  degraded: 'Answer unavailable · related sources',
  smalltalk: 'Conversation',
  refused: 'Assistant unavailable',
  error: 'Unable to process query',
}
const STAGE = {
  en: { searching: 'Searching department records…', writing: 'Writing your answer…' },
  ur: { searching: 'محکمہ کے ریکارڈ میں تلاش جاری ہے…', writing: 'آپ کا جواب لکھا جا رہا ہے…' },
}
const SAFE = { FORBID_TAGS: ['img', 'iframe', 'style', 'form', 'input', 'button'], FORBID_ATTR: ['style', 'onerror', 'onclick'] }

/** Model output is untrusted: sanitise it, mark [n] citations, open links safely. */
export function renderAnswerHtml(text) {
  const withCites = (text || '').replace(/\[(\d{1,2})\]/g, (_m, n) => `<sup class="cite-mark">${n}</sup>`)
  const clean = DOMPurify.sanitize(marked.parse(withCites), { ...SAFE, ADD_ATTR: ['target'] })
  const box = document.createElement('div')
  box.innerHTML = clean
  box.querySelectorAll('a').forEach((a) => { a.setAttribute('target', '_blank'); a.setAttribute('rel', 'noopener noreferrer') })
  // wide tables (timetables) scroll inside the bubble instead of stretching the page
  box.querySelectorAll('table').forEach((table) => {
    const wrap = document.createElement('div')
    wrap.className = 'table-scroll'
    table.replaceWith(wrap)
    wrap.appendChild(table)
  })
  return box.innerHTML
}

function AnswerBubble({ text, error }) {
  const html = useMemo(() => renderAnswerHtml(text), [text])
  const tabular = html.includes('table-scroll')
  return <div className={`message-bubble ${error ? 'is-error' : ''} ${tabular ? 'has-table' : ''}`} dangerouslySetInnerHTML={{ __html: html }} />
}

/** Markdown stripped for plain-text lists such as the History page. */
export function plainAnswer(text) {
  return (text || '')
    .replace(/^#{1,6}\s+/gm, '').replace(/\*\*(.+?)\*\*/g, '$1').replace(/(?<![\w*])\*(?!\s)(.+?)\*(?![\w*])/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '• ').replace(/\s*\[(\d{1,2})\]/g, '').replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1').replace(/[ \t]+\n/g, '\n').trim()
}

function Sources({ sources }) {
  if (!sources?.length) return null
  const shown = sources.some((s) => s.cited) ? sources.filter((s) => s.cited) : sources
  return shown.map((s) => (
    <details className="evidence-source" key={`${s.n}-${s.url}-${s.heading}`}>
      <summary>[{s.n}] {s.title}{s.kind ? ` · ${s.kind}` : ''}</summary>
      {s.snippet && <blockquote>{s.snippet}…</blockquote>}
      {/^https?:\/\//i.test(s.url || '') && <a className="citation" href={s.url} target="_blank" rel="noreferrer">Open official source ↗</a>}
    </details>
  ))
}

const toRow = (m, guest) => ({
  messageId: m.role === 'assistant' ? m.id : null,
  role: m.role,
  text: m.content,
  sources: (m.sources || []).map((u, i) => ({ n: i + 1, url: u, title: String(u).replace(/^https?:\/\//, ''), cited: true })),
  guest,
})

export function AdvisorChat({ auth, suggestions = [] }) {
  const guest = auth.user.role === 'guest'
  const [messages, setMessages] = useState([{ role: 'assistant', text: WELCOME }])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [language, setLanguage] = useState('en')
  const [sessions, setSessions] = useState([])
  const [showScrollButton, setShowScrollButton] = useState(false)
  const scrollRef = useRef(null)
  const urdu = language === 'ur'

  const refreshSessions = useCallback(() => {
    if (guest) return
    advisorRequest('/me/conversations', {}, auth).then((r) => setSessions(r.conversations || [])).catch(() => {})
  }, [guest, auth])
  useEffect(() => { refreshSessions() }, [refreshSessions, conversationId])

  const scrollToBottom = () => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }
  const onScroll = () => {
    const el = scrollRef.current
    if (el) setShowScrollButton(el.scrollHeight - el.scrollTop - el.clientHeight > 100)
  }
  useEffect(scrollToBottom, [messages])

  const patchLast = useCallback((patch) => {
    setMessages((prev) => {
      const next = prev.slice()
      next[next.length - 1] = { ...next[next.length - 1], ...(typeof patch === 'function' ? patch(next[next.length - 1]) : patch) }
      return next
    })
  }, [])

  async function loadSession(id) {
    if (id === conversationId || sending) return
    setConversationId(id)
    setMessages([{ role: 'assistant', text: 'Loading conversation...' }])
    try {
      const data = await advisorRequest(`/conversations/${id}`, {}, auth)
      setMessages(data.messages.map((m) => toRow(m, guest)))
    } catch {
      setMessages([{ role: 'assistant', text: 'Failed to load conversation.' }])
    }
  }

  function newChat() {
    if (sending) return
    setConversationId(null)
    setMessages([{ role: 'assistant', text: WELCOME }])
  }

  async function send(value = input) {
    const query = value.trim()
    if (!query || sending) return
    setInput('')
    const context = guest ? messages.filter((m) => m.text !== WELCOME && !m.error).slice(-8).map((m) => ({ role: m.role, content: m.text.slice(0, 2000) })) : undefined
    setMessages((m) => [...m, { role: 'user', text: query }, { role: 'assistant', text: '', stage: 'searching', streaming: true }])
    setSending(true)
    let answer = ''
    try {
      await streamAdvisorChat({
        auth: guest ? null : auth,
        body: {
          message: query,
          conversation_id: guest ? null : conversationId,
          ...(guest ? { ephemeral: true, history: context } : {}),
          ...(urdu ? { language: 'urdu' } : {}),
        },
        onEvent: ({ event, data }) => {
          if (event === 'meta' && data.conversation_id) setConversationId(data.conversation_id)
          else if (event === 'status') patchLast({ stage: data.stage })
          else if (event === 'delta') { answer += data.text; patchLast({ text: answer, stage: null }) }
          else if (event === 'reset') { answer = ''; patchLast({ text: '', stage: 'writing' }) }
          else if (event === 'replace') { answer = data.text; patchLast({ text: answer }) }
          else if (event === 'followups') patchLast({ followups: data.items, followupTitle: data.title })
          else if (event === 'sources') {
            const notes = [...new Set(data.sources.map((s) => s.note).filter(Boolean))]
            patchLast({ sources: data.sources, notices: notes })
          } else if (event === 'done') {
            patchLast({
              messageId: guest ? null : data.message_id, stage: null, streaming: false,
              meta: `${OUTCOME_LABEL[data.outcome] || 'Academic guidance'}${data.latency_ms ? ` · ${(data.latency_ms / 1000).toFixed(1)}s` : ''}`,
            })
          } else if (event === 'error') patchLast({ text: data.message, error: true, stage: null, streaming: false, meta: 'Unable to process query' })
        },
      })
    } catch (reason) {
      const text = reason instanceof AdvisorError && reason.status === 429
        ? `${reason.message} (try again in ${reason.retryAfter || 10}s)`
        : reason instanceof AdvisorError ? reason.message : 'Could not reach the advisor service. Please check your connection and try again.'
      patchLast({ text, error: true, stage: null, streaming: false, meta: 'Unable to process query' })
    } finally {
      setSending(false)
    }
  }

  const feedbackRequest = useCallback((path, options) => advisorRequest(path, options, auth), [auth])
  const stageText = (s) => (STAGE[urdu ? 'ur' : 'en'][s] || '')

  return <section className={`chat-layout ${!guest ? 'with-sidebar' : ''}`} dir={urdu ? 'rtl' : 'ltr'}>
    {!guest && <aside className="chat-history-sidebar">
      <div className="chat-sidebar-header">
        <h3>Conversations</h3>
        <button onClick={newChat} className="new-chat-btn" disabled={sending}>+ New Chat</button>
      </div>
      <div className="session-list">
        {sessions.map((s) => (
          <button key={s.id} className={`session-item ${s.id === conversationId ? 'active' : ''}`} onClick={() => loadSession(s.id)}>
            <div className="session-title">{s.title || `Chat ${new Date(s.created_at).toLocaleDateString()}`}</div>
            <div className="session-time">{new Date(s.updated_at).toLocaleTimeString()}</div>
          </button>
        ))}
      </div>
    </aside>}
    <div className="chat-panel">
      <div className="chat-toolbar"><span>{guest ? 'Guest conversation · not saved' : 'Private authenticated conversation · history enabled'}</span><button className="language-toggle" onClick={() => setLanguage(urdu ? 'en' : 'ur')}>{urdu ? 'English' : 'اردو'}</button></div>
      <div className="chat-scroll" ref={scrollRef} onScroll={onScroll} aria-live="polite">
        {messages.map((m, i) => <div key={i} className={`message-row ${m.role}`}>
          <div className="message-avatar">{m.role === 'assistant' ? 'Q' : guest ? 'GU' : 'ST'}</div>
          <div>
            {m.role === 'assistant'
              ? (m.text
                ? <AnswerBubble text={m.text} error={m.error} />
                : m.streaming && <div className="message-bubble typing" aria-hidden="true"><span /><span /><span /></div>)
              : <div className="message-bubble">{m.text}</div>}
            {m.streaming && m.stage && <small className="message-meta" role="status">{stageText(m.stage)}</small>}
            {m.meta && <small className="message-meta">{m.meta}</small>}
            {!m.streaming && <Sources sources={m.sources} />}
            {!m.streaming && !!m.followups?.length && <div className="followups" role="group" aria-label={m.followupTitle || 'Related questions'}>
              {m.followupTitle && <small>{m.followupTitle}</small>}
              {m.followups.map((f) => <button key={f.label} type="button" disabled={sending} onClick={() => send(f.text)}>{f.label}</button>)}
            </div>}
            {!m.streaming && !!m.notices?.length && <details className="evidence-notices"><summary>Source and availability notes</summary><ul>{m.notices.map((n, k) => <li key={k}>{n}</li>)}</ul></details>}
            {!guest && m.role === 'assistant' && m.messageId && !m.streaming && <AnswerFeedback messageId={m.messageId} request={feedbackRequest} />}
          </div>
        </div>)}
      </div>
      <button className={`scroll-to-bottom ${showScrollButton ? 'visible' : ''}`} onClick={scrollToBottom} aria-label="Scroll to bottom">↓</button>
      <div className="composer-wrapper">
        <div className="composer">
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent?.isComposing && send()} placeholder={urdu ? 'اپنا تعلیمی سوال پوچھیں…' : 'Ask an academic question…'} maxLength={1200} />
          <button onClick={() => send()} disabled={sending} aria-label="Send query">↑</button>
        </div>
        <small className="privacy">{guest ? 'This guest conversation is not stored. Sign in to enable History. ' : ''}Answers come from the department's published pages and documents, with sources. Please confirm important decisions with the department office.</small>
      </div>
    </div>
    <aside className="suggestions"><p className="eyebrow">QUICK START</p><h3>Popular questions</h3>{suggestions.map(([label, q]) => <button key={label} onClick={() => send(q)}><span>{label}</span><b>›</b><small>{q}</small></button>)}</aside>
  </section>
}
