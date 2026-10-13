import React, { useEffect, useRef, useState } from 'react'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { streamChat } from './stream'

function renderAnswer(message) {
  const text = (message.text || '').replace(/\[(\d+)\]/g, (label, number) => {
    const source = message.cited_sources?.find(s => s.number === Number(number))
    if (!source?.canonical_url?.startsWith('https://')) return label
    const target = source.canonical_url + (source.page && source.canonical_url.endsWith('.pdf') ? `#page=${source.page}` : '')
    return `[${number}](${target})`
  })
  return DOMPurify.sanitize(marked.parse(text, { breaks: true }), { FORBID_TAGS: ['img', 'iframe', 'style', 'form', 'input', 'button'] })
}

function observedResources(sources = []) {
  const links = new Map()
  for (const source of sources) for (const resource of source.resources || []) {
    try {
      const url = new URL(resource.url)
      if (url.protocol === 'https:' && !url.username && !url.password && ['cs.qau.edu.pk', 'qau.edu.pk', 'www.qau.edu.pk'].includes(url.hostname)) links.set(url.href, resource)
    } catch { /* Ignore malformed source links. */ }
  }
  return [...links.values()].slice(0, 10)
}

export function ChatV3({ auth }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [language, setLanguage] = useState('')
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState('')
  const [conversationId, setConversationId] = useState(null)
  const [sessions, setSessions] = useState([])
  const controller = useRef(null)
  const scroll = useRef(null)
  const signedIn = Boolean(auth?.access_token)
  const headers = auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {}

  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight }) }, [messages, status])
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (signedIn) fetch('/api/v3/history', { headers }).then(r => r.ok ? r.json() : []).then(setSessions).catch(() => {})
  }, [conversationId, signedIn])

  async function loadSession(id) {
    if (sending) return
    const response = await fetch(`/api/v3/history/${id}`, { headers })
    if (!response.ok) { setStatus('Saved conversation could not be loaded.'); return }
    const rows = await response.json()
    setMessages(rows.map(row => ({ role: row.role, text: row.content, ...row.metadata, message_id: row.role === 'assistant' ? row.id : null })))
    setConversationId(id)
  }

  async function deleteSession(session) {
    if (sending || !window.confirm(`Delete “${session.title}” and its saved messages?`)) return
    const response = await fetch(`/api/v3/history/${session.id}`, { method: 'DELETE', headers })
    if (!response.ok) { setStatus('Conversation could not be deleted.'); return }
    setSessions(old => old.filter(s => s.id !== session.id))
    if (conversationId === session.id) { setConversationId(null); setMessages([]) }
  }

  async function send(value = input) {
    const question = value.trim()
    if (!question || sending) return
    const turnId = crypto.randomUUID()
    setInput(''); setSending(true); setStatus('Connecting…')
    setMessages(old => [...old, { role: 'user', text: question }, { role: 'assistant', text: '', localId: turnId, cited_sources: [] }])
    controller.current = new AbortController()
    const update = fn => setMessages(old => old.map(m => m.localId === turnId ? fn(m) : m))
    try {
      await streamChat({ message: question, ...(conversationId ? { conversation_id: conversationId } : {}), ...(language ? { preferred_language: language } : {}) }, {
        signal: controller.current.signal, token: auth?.access_token,
        onEvent(event, data) {
          if (event === 'status') setStatus(data.message)
          if (event === 'token') update(m => ({ ...m, text: m.text + data.text }))
          if (event === 'citation') update(m => ({ ...m, cited_sources: [...m.cited_sources, data] }))
          if (event === 'warning') update(m => ({ ...m, warnings: [...(m.warnings || []), data.message] }))
          if (event === 'done') {
            setConversationId(data.conversation_id)
            update(m => ({ ...m, ...data, text: data.answer }))
          }
        },
      })
    } catch (error) {
      update(m => ({ ...m, error: error.name === 'AbortError' ? 'Answer stopped. You can ask another question.' : error.message }))
    } finally { setSending(false); setStatus(''); controller.current = null }
  }

  async function feedback(message, helpful) {
    const reason = helpful ? null : window.prompt('What should the answer improve?')
    if (!helpful && reason === null) return
    const response = await fetch('/api/v3/feedback', { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify({ message_id: message.message_id, helpful, reason }) })
    setStatus(response.ok ? 'Feedback saved for review.' : 'Feedback could not be saved.')
  }

  return <section className={`chat-layout ${signedIn ? 'with-sidebar' : ''}`} dir={language === 'urdu' ? 'rtl' : 'ltr'}>
    {signedIn && <aside className="chat-history-sidebar"><h3>Conversations</h3>{sessions.map(s => <div key={s.id}><button className="session-item" onClick={() => loadSession(s.id)} disabled={sending}>{s.title}</button><button onClick={() => deleteSession(s)} disabled={sending} aria-label={`Delete conversation ${s.title}`}>Delete</button></div>)}</aside>}
    <div className="chat-panel">
      <div className="chat-toolbar"><span>Replacement preview · {signedIn ? 'Private saved history' : 'Temporary guest conversation'}</span><button disabled={sending} onClick={() => { setConversationId(null); setMessages([]) }}>New chat</button><label>Language <select aria-label="Response language" value={language} onChange={e => setLanguage(e.target.value)}><option value="">Match my message</option><option value="english">English</option><option value="roman_urdu">Roman Urdu</option><option value="urdu">اردو</option></select></label></div>
      <div className="chat-scroll" ref={scroll} aria-live="polite" aria-busy={sending}>
        {!messages.length && <div className="message-row assistant"><div className="message-avatar">Q</div><div className="message-bubble">Hi! Ask me about your QAU CS studies, or a computing concept you want explained.</div></div>}
        {messages.map((m, i) => <div className={`message-row ${m.role}`} key={m.localId || i}><div className="message-avatar">{m.role === 'assistant' ? 'Q' : 'You'}</div><div>
          {m.role === 'assistant' ? <div className="message-bubble" dangerouslySetInnerHTML={{ __html: renderAnswer(m) }} /> : <div className="message-bubble">{m.text}</div>}
          {m.error && <p role="alert" className="form-error">{m.error}</p>}
          {m.latency_ms != null && <small className="message-meta">{m.groundedness_status === 'general_explanation' ? 'General explanation' : m.groundedness_status === 'clarification' ? 'Clarification' : m.cited_sources?.length ? 'Answer with source citations' : 'Source information unavailable'} · {(m.latency_ms / 1000).toFixed(1)}s</small>}
          {!!observedResources(m.cited_sources).length && <div className="evidence-notices"><strong>Official forms and services</strong><ul>{observedResources(m.cited_sources).map(r => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a></li>)}</ul></div>}
          {!!m.cited_sources?.length && <details className="evidence-notices"><summary>What source was used?</summary>{m.cited_sources.map(c => <details className="evidence-source" key={c.chunk_id}><summary>[{c.number}] {c.document_title}{c.page ? ` · p. ${c.page}` : ''}{c.effective_term ? ` · ${c.effective_term}` : ''}</summary><p>{c.section}</p><small>{c.review_status.replaceAll('_', ' ')} · Captured {c.captured_at?.slice(0, 10)}</small>{c.canonical_url?.startsWith('https://') && <a className="citation" href={c.canonical_url + (c.page && c.canonical_url.endsWith('.pdf') ? `#page=${c.page}` : '')} target="_blank" rel="noreferrer">Open official source ↗</a>}{c.source_id?.startsWith('tt-') && <a className="citation" href={`/api/v3/timetables/versions/${c.source_version_id}/pdf#page=${c.page || 1}`} target="_blank" rel="noreferrer">Open original timetable PDF</a>}<a className="citation" href={`/api/v3/sources/${c.source_id}?version=${c.source_version_id}`} target="_blank" rel="noreferrer">View captured passage</a></details>)}</details>}
          {!!m.warnings?.length && <details className="evidence-notices"><summary>Source notes</summary><ul>{m.warnings.map((w, n) => <li key={n}>{w}</li>)}</ul></details>}
          {signedIn && m.message_id && <div><button onClick={() => feedback(m, true)} aria-label="Helpful answer">Helpful</button><button onClick={() => feedback(m, false)} aria-label="Unhelpful answer">Needs improvement</button></div>}
        </div></div>)}
        {!!status && <p role="status" className="message-meta">{status}</p>}
      </div>
      <form className="composer-wrapper" onSubmit={e => { e.preventDefault(); send() }}><div className="composer"><input aria-label="Ask an academic question" maxLength={4000} value={input} onChange={e => setInput(e.target.value)} placeholder="Ask an academic question…" />{sending ? <button type="button" onClick={() => controller.current?.abort()} aria-label="Stop answer">■</button> : <button type="submit" aria-label="Send query" disabled={!input.trim()}>↑</button>}</div><small className="privacy">{signedIn ? 'Saved conversations are visible only to your account.' : 'Guest history expires and is not saved to disk.'} Check the cited scheme, term and review status.</small></form>
    </div>
    <aside className="suggestions"><p className="eyebrow">TRY A CONVERSATION</p><h3>Start here</h3>{['5th sem ke subjects btado fall 2024 batch', 'CS ki faculty me NLP research kon karta ha', 'What is recursion? Explain with an example.'].map(q => <button key={q} disabled={sending} onClick={() => send(q)}>{q}</button>)}</aside>
  </section>
}
