import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, getJson, sendJson, streamChat } from './api'
import { isRtl, renderAnswer } from './markdown'

const STORE_KEY = 'qau-advisor-conversation'
const STAGES = { searching: 'Searching department records…', writing: 'Writing the answer…' }

function Sources({ sources }) {
  const [open, setOpen] = useState(false)
  if (!sources?.length) return null
  const cited = sources.filter((s) => s.cited)
  const shown = cited.length ? cited : sources
  return (
    <div className="sources">
      <button type="button" className="sources-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {cited.length ? 'Sources' : 'Related pages'} ({shown.length}) <span aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>
      {open && (
        <ol className="sources-list">
          {shown.map((s) => (
            <li key={`${s.n}-${s.url}`} value={s.n}>
              {/^https?:/.test(s.url)
                ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
                : <strong>{s.title}</strong>}
              <span className="src-kind">{s.kind}</span>
              {s.note && <div className="src-note">{s.note}</div>}
              <div className="src-snippet">{s.snippet}…</div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function Feedback({ messageId }) {
  const [state, setState] = useState(null)
  const send = async (rating) => {
    setState(rating)
    try { await sendJson('POST', '/api/v1/feedback', { message_id: messageId, rating }) } catch { setState(null) }
  }
  return (
    <div className="feedback" role="group" aria-label="Was this answer helpful?">
      <button type="button" aria-pressed={state === 1} className={state === 1 ? 'on' : ''} onClick={() => send(1)} title="Helpful">👍</button>
      <button type="button" aria-pressed={state === -1} className={state === -1 ? 'on' : ''} onClick={() => send(-1)} title="Not helpful">👎</button>
      {state === -1 && <span className="fb-note">Thanks — we'll review this answer.</span>}
    </div>
  )
}

function Message({ m, last, busy }) {
  const rtl = isRtl(m.content)
  const html = useMemo(() => (m.role === 'assistant' ? renderAnswer(m.content || '') : null), [m.role, m.content])
  const copy = () => navigator.clipboard?.writeText(m.content)
  if (m.role === 'user') {
    return <div className="msg user"><div className="bubble" dir={rtl ? 'rtl' : 'auto'}>{m.content}</div></div>
  }
  return (
    <div className="msg assistant">
      <div className="avatar" aria-hidden="true">Q</div>
      <div className="body">
        {m.stage && !m.content && <div className="stage"><span className="dots" aria-hidden="true" />{STAGES[m.stage] || 'Thinking…'}</div>}
        {m.content && <div className={`bubble answer ${m.error ? 'is-error' : ''}`} dir={rtl ? 'rtl' : 'auto'} dangerouslySetInnerHTML={{ __html: html }} />}
        {m.degraded && <div className="degraded">The AI service is temporarily unavailable; showing passages from official pages.</div>}
        {m.error && m.retry && <button type="button" className="retry" onClick={m.retry}>Try again</button>}
        {!busy || !last ? <Sources sources={m.sources} /> : null}
        {m.id && !m.error && (!busy || !last) && (
          <div className="actions">
            <Feedback messageId={m.id} />
            <button type="button" className="copy" onClick={copy} title="Copy answer">Copy</button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const [config, setConfig] = useState({ starters: [], notice: '', chat_enabled: true, max_chars: 1200 })
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const conversationId = useRef(null)
  const abortRef = useRef(null)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { getJson('/api/v1/config').then(setConfig).catch(() => {}) }, [])

  useEffect(() => {
    const saved = localStorage.getItem(STORE_KEY)
    if (!saved) return
    getJson(`/api/v1/conversations/${saved}`)
      .then((c) => {
        conversationId.current = saved
        setMessages(c.messages.map((m) => ({
          id: m.id, role: m.role, content: m.content,
          sources: (m.sources || []).map((u, i) => ({ n: i + 1, url: u, title: u.replace(/^https?:\/\//, ''), kind: '', snippet: '', cited: true })),
        })))
      })
      .catch(() => localStorage.removeItem(STORE_KEY))
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages])

  const update = useCallback((patch) => {
    setMessages((prev) => {
      const next = prev.slice()
      next[next.length - 1] = { ...next[next.length - 1], ...patch }
      return next
    })
  }, [])

  const send = useCallback(async (text) => {
    const question = (text ?? input).trim()
    if (!question || busy) return
    setInput('')
    setBusy(true)
    const controller = new AbortController()
    abortRef.current = controller
    setMessages((prev) => [...prev, { role: 'user', content: question }, { role: 'assistant', content: '', stage: 'searching' }])
    let answer = ''
    try {
      await streamChat({
        message: question,
        conversationId: conversationId.current,
        signal: controller.signal,
        onEvent: ({ event, data }) => {
          if (event === 'meta') {
            conversationId.current = data.conversation_id
            localStorage.setItem(STORE_KEY, data.conversation_id)
          } else if (event === 'status') update({ stage: data.stage })
          else if (event === 'delta') { answer += data.text; update({ content: answer, stage: null }) }
          else if (event === 'reset') { answer = ''; update({ content: '', stage: 'writing' }) }
          else if (event === 'replace') { answer = data.text; update({ content: answer }) }
          else if (event === 'sources') update({ sources: data.sources })
          else if (event === 'done') update({ id: data.message_id, stage: null, degraded: data.outcome === 'degraded' })
          else if (event === 'error') update({ content: data.message, error: true, stage: null, retry: () => retry(question) })
        },
      })
    } catch (err) {
      if (err.name === 'AbortError') update({ stage: null, content: answer || 'Stopped.' })
      else {
        const msg = err instanceof ApiError && err.status === 429
          ? `${err.message} (try again in ${err.retryAfter || 10}s)`
          : err instanceof ApiError ? err.message : 'Could not reach the server. Check your connection and try again.'
        update({ content: msg, error: true, stage: null, retry: () => retry(question) })
      }
    } finally {
      setBusy(false)
      abortRef.current = null
      inputRef.current?.focus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, busy, update])

  const retry = (q) => {
    setMessages((prev) => prev.slice(0, -2))
    setTimeout(() => send(q), 0)
  }

  const newChat = () => {
    abortRef.current?.abort()
    localStorage.removeItem(STORE_KEY)
    conversationId.current = null
    setMessages([])
    setBusy(false)
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() }
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <div className="logo" aria-hidden="true">Q</div>
          <div>
            <h1>QAU CS Advisor</h1>
            <p>Department of Computer Sciences · Quaid-i-Azam University</p>
          </div>
        </div>
        <button type="button" className="ghost" onClick={newChat} disabled={!messages.length}>New chat</button>
      </header>

      {config.notice && <div className="notice" role="status"><strong>Notice:</strong> {config.notice}</div>}

      <main className="thread" aria-live="polite">
        {!messages.length ? (
          <section className="welcome">
            <h2>How can I help?</h2>
            <p>Ask about courses and prerequisites, schemes of study, admissions, fees, faculty, the academic calendar, timetables and the department's rules. You can write in English, Urdu or Roman Urdu.</p>
            <div className="chips">
              {config.starters.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </section>
        ) : (
          messages.map((m, i) => <Message key={i} m={m} last={i === messages.length - 1} busy={busy} />)
        )}
        <div ref={endRef} />
      </main>

      <footer className="composer">
        {!config.chat_enabled && <div className="notice warn">The assistant is switched off for maintenance.</div>}
        <div className="box">
          <textarea
            ref={inputRef}
            value={input}
            rows={1}
            maxLength={config.max_chars}
            placeholder="Ask a question…  (Shift+Enter for a new line)"
            aria-label="Your question"
            onChange={(e) => { setInput(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px' }}
            onKeyDown={onKey}
            disabled={!config.chat_enabled}
          />
          {busy ? (
            <button type="button" className="send stop" onClick={() => abortRef.current?.abort()} aria-label="Stop">■</button>
          ) : (
            <button type="button" className="send" onClick={() => send()} disabled={!input.trim()} aria-label="Send">➤</button>
          )}
        </div>
        <p className="fineprint">
          Answers come from the department's published pages and documents{config.knowledge_updated ? ` (updated ${config.knowledge_updated})` : ''}. For important decisions, confirm with the department office.
        </p>
      </footer>
    </div>
  )
}
