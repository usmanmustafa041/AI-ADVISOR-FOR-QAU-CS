import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import './styles.css'
import { TimetableView } from './components/TimetableView'
import { AnswerFeedback } from './components/AnswerFeedback'
import { KnowledgeReview } from './components/KnowledgeReview'
import { ChatV3 } from './rebuild/ChatV3'
import { TimetableManagement } from './rebuild/TimetableManagement'
import { AdvisorChat, plainAnswer } from './advisor/AdvisorChat'
import { AdvisorAdmin } from './advisor/AdvisorAdmin'
import { advisorHealth, advisorRequest } from './advisor/advisorApi'

const API = import.meta.env.VITE_API_URL || '/api/v1'
// 'advisor' = the new chatbot engine (default). 'legacy' keeps the portal's original chat engine.
const CHAT_ENGINE = import.meta.env.VITE_CHAT_ENGINE || 'advisor'
const suggestions = [
  ['Prerequisites', 'I have not passed PSP, can I take DSA?'],
  ['Credit hours', 'How many credit hours can I take this semester?'],
  ['Fees', 'What is the BSCS morning semester fee?'],
  ['Policy', 'What are the FYP submission rules?'],
  ['Timetable', 'Monday classes for 8th semester'],
]

function savedAuth() {
  try { return JSON.parse(localStorage.getItem('qau-auth')) || null } catch { return null }
}

async function api(path, options = {}, auth = null) {
  const { responseType, ...fetchOptions } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), path === '/chat' ? 75000 : 20000)
  try {
  const response = await fetch(`${API}${path}`, {
    ...fetchOptions,
    signal: options.signal || controller.signal,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {}),
      ...options.headers,
    },
  })
  let data = null
  try { data = response.ok && responseType === 'blob' ? await response.blob() : await response.json() } catch { data = null }
  if (response.status === 401 && auth?.access_token) window.dispatchEvent(new Event('qau-auth-expired'))
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`)
  return data
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('The request timed out. Please try again.')
    throw e
  } finally { clearTimeout(timer) }
}

export function App() {
  const [auth, setAuth] = useState(savedAuth)
  const [online, setOnline] = useState(false)
  
  useEffect(() => {
    // The portal is "online" when either its own backend or the chatbot engine answers.
    const check = () => Promise.allSettled([api('/health'), CHAT_ENGINE === 'advisor' ? advisorHealth() : Promise.reject()])
      .then((results) => setOnline(results.some((r) => r.status === 'fulfilled')))
    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const expired = () => { localStorage.removeItem('qau-auth'); setAuth(null) }
    window.addEventListener('qau-auth-expired', expired)
    return () => window.removeEventListener('qau-auth-expired', expired)
  }, [])

  function authenticated(value) {
    localStorage.setItem('qau-auth', JSON.stringify(value)); setAuth(value)
  }
  async function logout() {
    if (auth?.access_token) await api('/auth/logout', { method: 'POST' }, auth).catch(() => {})
    localStorage.removeItem('qau-auth'); setAuth(null)
  }

  if (!auth) return <AuthScreen online={online} onAuthenticated={authenticated} onGuest={() => setAuth({ user: { role: 'guest', email: 'Guest student' } })} />
  if (auth.user.role === 'admin') return <AdminPortal auth={auth} online={online} onLogout={logout} />
  return <StudentPortal auth={auth} online={online} onLogout={logout} />
}

function AuthScreen({ online, onAuthenticated, onGuest }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true)
    try {
      if (mode === 'forgot-password') {
        const result = await api('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) })
        setResetToken(result.demo_reset_token || ''); setNotice(result.message); setMode('reset-password')
      } else if (mode === 'reset-password') {
        const result = await api('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token: resetToken, password, confirm_password: confirmPassword }) })
        setNotice(result.message); setMode('login'); setPassword(''); setConfirmPassword('')
      } else {
        const payload = mode === 'register' ? { full_name: fullName, email, password, confirm_password: confirmPassword } : { email, password }
        onAuthenticated(await api(`/auth/${mode}`, { method: 'POST', body: JSON.stringify(payload) }))
      }
    }
    catch (reason) { setError(reason.message) }
    finally { setBusy(false) }
  }

  return <main className="auth-page">
    <section className="auth-hero"><div className="brand-mark large">Q</div><p className="eyebrow">QUAID-I-AZAM UNIVERSITY</p><h1>AI-powered academic guidance for every CS student.</h1><p>Ask about courses, prerequisites, fees, policies, class schedules, exams, and research requirements in English or Urdu.</p><div className="auth-features"><span>✓ Source-backed answers</span><span>✓ Private query history</span><span>✓ English + اردو</span></div></section>
    <section className="auth-card"><div className="connection-row"><span className={online ? 'connection online' : 'connection'}><i />{online ? 'Service online' : 'Service offline'}</span></div><p className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : mode === 'register' ? 'STUDENT REGISTRATION' : 'ACCOUNT RECOVERY'}</p><h2>{mode === 'login' ? 'Sign in to your advisor' : mode === 'register' ? 'Create your account' : mode === 'forgot-password' ? 'Reset your password' : 'Choose a new password'}</h2><p>{mode === 'login' ? 'Students and administrators use the same secure sign-in.' : mode === 'register' ? 'Register with your email and a secure password.' : 'Use the recovery token to securely replace your password.'}</p>
      <form onSubmit={submit} className="stack-form">{mode === 'register' && <label>Full name<input value={fullName} onChange={(e) => setFullName(e.target.value)} required autoComplete="name" /></label>}{mode !== 'reset-password' && <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>}{mode === 'reset-password' && <label>Reset token<input value={resetToken} onChange={(e) => setResetToken(e.target.value)} required /></label>}{!['forgot-password'].includes(mode) && <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength="8" required autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>}{['register', 'reset-password'].includes(mode) && <label>Confirm password<input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength="8" required autoComplete="new-password" /></label>}{notice && <div className="notice">{notice}</div>}{error && <div className="form-error" role="alert">{error}</div>}<button className="primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : mode === 'register' ? 'Register' : mode === 'forgot-password' ? 'Send reset token' : 'Save new password'}</button></form>
      <button className="guest-button" onClick={onGuest}>Continue without signing in</button>
      <small className="guest-note">Guest chat is available immediately. Sign in only when you want conversations saved in History.</small>
      {mode === 'login' && <button className="text-button" onClick={() => { setMode('forgot-password'); setError('') }}>Forgot password?</button>}
      <button className="text-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setNotice('') }}>{mode === 'login' ? 'New student? Create an account' : 'Back to sign in'}</button>
    </section>
  </main>
}

function Shell({ auth, online, active, setActive, onLogout, children }) {
  const admin = auth.user.role === 'admin'
  const guest = auth.user.role === 'guest'
  const studentNav = guest ? ['Chat', 'Study Plan', 'Courses', 'Fees', 'Timetable', 'Policies'] : ['Chat', 'Study Plan', 'Courses', 'Fees', 'Timetable', 'Policies', 'History']
  const adminNav = ['Dashboard', 'CMS', 'Courses', 'Prerequisites', 'Fees', 'Timetables', 'Policies', 'Knowledge', 'Ingestion Review', ...(import.meta.env.VITE_CHATBOT_REBUILD === 'true' ? ['Timetable Management'] : []), 'Query Logs', 'Users', 'Model', 'Settings', 'Reports']
  const items = admin ? adminNav : studentNav
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">Q</div><div><strong>QAU CS</strong><small>Academic Advisor</small></div></div><div className="profile-card"><div className="avatar">{admin ? 'AD' : guest ? 'GU' : 'ST'}</div><div><strong>{auth.user.email}</strong><small>{admin ? 'Administrator' : guest ? 'Guest · history off' : 'Student account'}</small></div><span className="status-dot" /></div><nav>{items.map((item) => <button key={item} className={active === item ? 'nav-item active' : 'nav-item'} onClick={() => setActive(item)}><span className="icon" aria-hidden="true">{admin ? '◇' : '•'}</span>{item}</button>)}</nav><div className="sidebar-bottom"><div className="source-note"><span>✓</span><div><strong>QAU source library</strong><small>Check source, scheme and date</small></div></div>{guest && <div className="guest-save-note">Sign in to save and revisit your conversations.</div>}<button className="nav-item" onClick={onLogout}><span className="icon">↪</span>{guest ? 'Sign in' : 'Log out'}</button></div></aside><main className="main-content"><header className="topbar"><div><p className="eyebrow">{admin ? 'ADMINISTRATION' : guest ? 'GUEST ADVISOR' : 'STUDENT PORTAL'} / {active.toUpperCase()}</p><h1>{active}</h1></div><div className="top-actions"><span className={online ? 'connection online' : 'connection'}><i />{online ? 'API connected' : 'Offline'}</span><div className="mini-avatar">{admin ? 'AD' : guest ? 'GU' : 'ST'}</div></div></header>{children}</main></div>
}

function StudentPortal({ auth, online, onLogout }) {
  const [active, setActive] = useState('Chat')
  return <Shell {...{ auth, online, active, setActive, onLogout }}>
    {active === 'Chat' && (CHAT_ENGINE === 'advisor' ? <AdvisorChat auth={auth} suggestions={suggestions} /> : import.meta.env.VITE_CHATBOT_REBUILD === 'true' ? <ChatV3 auth={auth} /> : <Chat auth={auth} />)}
    {active !== 'Chat' && <div className="page-content-wrapper">
      {active === 'Study Plan' && <StudyPlan auth={auth} />}
      {active === 'Courses' && <CourseSearch auth={auth} />}
      {active === 'Fees' && <Fees auth={auth} />}
      {active === 'Timetable' && <TimetableView auth={auth} />}
      {active === 'Policies' && <Policies auth={auth} />}
      {active === 'History' && <History auth={auth} />}
    </div>}
  </Shell>
}

function Fees({ auth }) {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api('/fees?program_code=BSCS', {}, auth).then(setData).catch((e) => setError(e.message)) }, [])
  const shifts = [...new Set((data?.fees || []).map(f => f.shift))]
  const formatRows = rows => rows.map(f => ({
    ...f,
    fee_type: (f.fee_type || '').replaceAll('_', ' '),
    amount: `${f.currency} ${Number(f.amount).toLocaleString()}`,
    source_status: f.source?.source_url ? f.source.verification_status : 'Source not authenticated',
  }))
  return <section className="section-card full">
    <div className="section-heading"><div><p className="eyebrow">FEE RECORDS</p><h3>BS Computer Science fee structure</h3></div>{data && <span className="guidance-chip">Requested date: {data.as_of}</span>}</div>
    <div className="official-notice"><strong>Check the applicable fee notice</strong><span>Fee categories, shifts, admission charges and additional costs vary. Stored records do not establish the amount payable today.</span></div>
    {data?.notice && <div className="notice">{data.notice}</div>}
    {error && <div className="form-error">{error}</div>}
    {shifts.map(shift => <React.Fragment key={shift}><h4 className="table-title">{shift}</h4><div className="table-wrap"><DataTable columns={['official_fee_category', 'fee_type', 'amount', 'effective_from', 'source_status']} rows={formatRows(data.fees.filter(f => f.shift === shift))} /></div></React.Fragment>)}
    {!shifts.length && !error && <Empty text={data ? 'No fee records are available for this date. Ask the advisor to search the archived fee page.' : 'Loading fee records…'} />}
    <a className="source-link" href="https://qau.edu.pk/bachelor-fee-structure/" target="_blank" rel="noreferrer">View the official QAU fee page ↗</a>
  </section>
}


function Chat({ auth }) {
  const guest = auth.user.role === 'guest'
  const defaultMessages = [{ role: 'assistant', text: 'Assalam-o-Alaikum. Ask me about courses, prerequisites, fees, schedules, exams, policies, or research requirements.' }]
  const [messages, setMessages] = useState(defaultMessages)
  const [input, setInput] = useState(''); const [sending, setSending] = useState(false); const [sessionId, setSessionId] = useState(null); const [contextCourseCode, setContextCourseCode] = useState(null); const [language, setLanguage] = useState('en')
  const [showScrollButton, setShowScrollButton] = useState(false)
  const scrollRef = React.useRef(null)
  const urdu = language === 'ur'
  
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    if (!guest) api('/history/sessions', {}, auth).then(setSessions).catch(() => {})
  }, [sessionId, guest])

  async function loadSession(id) {
    if (id === sessionId || sending) return
    setSessionId(id)
    setMessages([{ role: 'assistant', text: 'Loading conversation...' }])
    try {
      const history = await api(`/history/sessions/${id}`, {}, auth)
      setMessages(history.map(m => ({
        messageId: m.role === 'assistant' ? m.id : null,
        role: m.role,
        text: m.content,
        meta: m.role === 'assistant' ? `${m.response_metadata?.grounding_status?.replaceAll('_', ' ') || m.response_engine || 'system'}` : null,
        citations: m.response_metadata?.citations || [],
        notices: m.response_metadata?.notices || []
      })))
    } catch(e) {
      setMessages([{ role: 'assistant', text: 'Failed to load conversation.' }])
    }
  }

  function newChat() {
    if (sending) return
    setSessionId(null)
    setContextCourseCode(null)
    setMessages(defaultMessages)
  }
  
  const scrollToBottom = () => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }
  
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
      setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100)
    }
  }
  
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  
  async function send(value = input) {
    const query = value.trim(); if (!query || sending) return
    setInput(''); setMessages((m) => [...m, { role: 'user', text: query }]); setSending(true)
    try {
      const history = guest ? messages.filter(m => !defaultMessages.some(d => d.text === m.text)).slice(-8).map(m => ({ role: m.role, content: m.text.slice(0, 4000) })) : []
      const result = await api('/chat', { method: 'POST', body: JSON.stringify({ message: query, session_id: sessionId, context_course_code: contextCourseCode, history, ...(urdu ? { language: 'urdu' } : {}) }) }, auth)
      const evidenceLabel = { cited_generation: 'Answer with source citations', cited_lookup: 'Answer with source citations', source_excerpts: 'Answer unavailable · related sources', insufficient_evidence: 'More information needed', conversational: 'Conversation', calculated: 'Calculation from your inputs', educational: 'General CS explanation', source_conflict: 'Official sources disagree' }[result.grounding_status] || 'Academic guidance'
      setContextCourseCode(result.entities?.course_code?.[0] || (result.grounding_status === 'conversational' ? contextCourseCode : null)); setSessionId(result.session_id || sessionId); setMessages((m) => [...m, { role: 'assistant', messageId: result.message_id, text: result.answer, meta: `${evidenceLabel} · ${(result.response_time_ms / 1000).toFixed(1)}s`, citations: result.citations, notices: result.notices }])
    } catch (reason) { setMessages((m) => [...m, { role: 'assistant', text: reason.message, meta: 'Unable to process query' }]) }
    finally { setSending(false) }
  }
  
  return <section className={`chat-layout ${!guest ? 'with-sidebar' : ''}`} dir={urdu ? 'rtl' : 'ltr'}>
    {!guest && <aside className="chat-history-sidebar">
      <div className="chat-sidebar-header">
        <h3>Conversations</h3>
        <button onClick={newChat} className="new-chat-btn" disabled={sending}>+ New Chat</button>
      </div>
      <div className="session-list">
        {sessions.map(s => (
          <button key={s.id} className={`session-item ${s.id === sessionId ? 'active' : ''}`} onClick={() => loadSession(s.id)}>
            <div className="session-title">{s.title || `Chat ${new Date(s.created_at).toLocaleDateString()}`}</div>
            <div className="session-time">{new Date(s.updated_at).toLocaleTimeString()}</div>
          </button>
        ))}
      </div>
    </aside>}
    <div className="chat-panel">
      <div className="chat-toolbar"><span>{guest ? 'Guest conversation · not saved' : 'Private authenticated conversation · history enabled'}</span><button className="language-toggle" onClick={() => setLanguage(urdu ? 'en' : 'ur')}>{urdu ? 'English' : 'اردو'}</button></div>
      <div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>
        {messages.map((m, i) => <div key={i} className={`message-row ${m.role}`}>
          <div className="message-avatar">{m.role === 'assistant' ? 'Q' : guest ? 'GU' : 'ST'}</div>
          <div>
            {m.role === 'assistant' ? <div className="message-bubble" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(m.text), { FORBID_TAGS: ['img', 'iframe', 'style', 'form', 'input', 'button'] }) }} /> : <div className="message-bubble">{m.text}</div>}
            {m.meta && <small className="message-meta">{m.meta}</small>}
            {m.citations?.map((c, n) => <details className="evidence-source" key={c.chunk_id || `${c.source_code}-${n}`}><summary>[{c.number || n + 1}] {c.title || c.source_code}{c.page_number ? ` · p. ${c.page_number}` : ''}{c.effective_term ? ` · ${c.effective_term}` : ''}</summary>{c.quotes?.map((quote, i) => <blockquote key={i}>{quote}</blockquote>)}{c.captured_at && <small>Archived: {c.captured_at}</small>}{/^https?:\/\//i.test(c.source_url || '') && <a className="citation" href={c.source_url} target="_blank" rel="noreferrer">Open official source ↗</a>}</details>)}
            {!!m.notices?.length && <details className="evidence-notices"><summary>Source and availability notes</summary><ul>{m.notices.map((notice, n) => <li key={n}>{notice}</li>)}</ul></details>}
            {!guest && m.role === 'assistant' && m.messageId && <AnswerFeedback messageId={m.messageId} request={(path, options) => api(path, options, auth)} />}
          </div>
        </div>)}
        {sending && <div className="message-row assistant"><div className="message-avatar">Q</div><div><div className="message-bubble typing" aria-hidden="true"><span /><span /><span /></div><small className="message-meta" role="status">{urdu ? 'آپ کا جواب تیار ہو رہا ہے…' : 'Preparing your answer…'}</small></div></div>}
      </div>
      <button className={`scroll-to-bottom ${showScrollButton ? 'visible' : ''}`} onClick={scrollToBottom} aria-label="Scroll to bottom">↓</button>
      <div className="composer-wrapper">
        <div className="composer">
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} placeholder={urdu ? 'اپنا تعلیمی سوال پوچھیں…' : 'Ask an academic question…'} />
          <button onClick={() => send()} disabled={sending} aria-label="Send query">↑</button>
        </div>
        <small className="privacy">{guest ? 'This guest conversation is not stored. Sign in to enable History. ' : ''}Answers use available records and clearly identify demo or unverified information.</small>
      </div>
    </div>
    <aside className="suggestions"><p className="eyebrow">QUICK START</p><h3>Popular questions</h3>{suggestions.map(([label, q]) => <button key={label} onClick={() => send(q)}><span>{label}</span><b>›</b><small>{q}</small></button>)}</aside>
  </section>
}

function CourseSearch({ auth }) {
  const [search, setSearch] = useState(''); const [courses, setCourses] = useState([]); const [selected, setSelected] = useState(null); const [prerequisites, setPrerequisites] = useState(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  async function load(event) { event?.preventDefault(); setError(''); setLoading(true); try { const rows = await api(`/courses?search=${encodeURIComponent(search)}&limit=100`, {}, auth); setCourses(rows); if (!rows.length) setError('Course not found. Try a course code or a different title keyword.') } catch (e) { setError(e.message) } finally { setLoading(false) } }
  useEffect(() => { load() }, [])
  async function selectCourse(course) { setSelected(course); setPrerequisites(null); try { setPrerequisites(await api(`/courses/${encodeURIComponent(course.code)}/prerequisites`, {}, auth)) } catch (e) { setPrerequisites({ error: e.message, prerequisites: [] }) } }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">COURSE CATALOGUE</p><h3>Search course by name or code</h3></div></div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. Data Structures or CSC-211" aria-label="Course name or code" /><button className="primary" disabled={loading}>{loading ? 'Searching...' : 'Search'}</button></form>{error && <div className="notice">{error}</div>}<div className="course-list">{courses.map((course) => <button className="course-row" key={course.code} onClick={() => selectCourse(course)}><div className="course-code">{course.code}</div><div><strong>{course.title}</strong><small>{course.total_credit_hours} credit hours</small></div><span style={{color: '#1a5f57', fontWeight: 'bold'}}>View details ›</span></button>)}</div>{selected && <div className="detail-drawer"><button className="close-button" onClick={() => setSelected(null)}>×</button><p className="eyebrow">{selected.code}</p><h3 style={{fontSize: '28px', color: '#1a5f57', marginTop: '8px', marginBottom: '16px'}}>{selected.title}</h3><p style={{fontSize: '14px', lineHeight: '1.6'}}>{selected.description || 'No expanded description is stored.'}</p><div style={{display: 'inline-block', padding: '8px 16px', background: '#e6f0ed', borderRadius: '8px', margin: '16px 0'}}><strong style={{color: '#1a5f57'}}>Credits:</strong> {selected.theory_credit_hours} theory + {selected.lab_credit_hours} lab</div><h4 style={{borderBottom: '2px solid #e6f0ed', paddingBottom: '8px', marginBottom: '16px'}}>Prerequisite guidance</h4>{prerequisites?.prerequisites?.length ? <ul className="prerequisite-list">{prerequisites.prerequisites.map((p) => <li key={p.course_code} style={{display: 'flex', alignItems: 'center', gap: '8px'}}><strong>{p.course_code}</strong> {p.course_title}<span className={p.verified ? 'verified-chip' : 'guidance-chip'} style={{marginLeft: 'auto'}}>{p.verified ? 'Published prerequisite' : 'Unverified requirement'}</span></li>)}</ul> : <p>{prerequisites ? 'No stored prerequisite link.' : 'Loading prerequisites…'}</p>}{prerequisites?.notice && <div className="drawer-notice" style={{marginTop: '24px'}}>{prerequisites.notice}</div>}<p style={{marginTop: '32px', color: '#728c89', fontSize: '11px'}}><strong>Source:</strong> {selected.source?.title || 'Catalogue record pending source metadata'}</p></div>}</section>
}

function StudyPlan({ auth }) {
  const [plan, setPlan] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api('/programs/BSCS/study-plan', {}, auth).then(setPlan).catch((e) => setError(e.message)) }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">FALL 2025 CURRICULUM</p><h3>BSCS eight-semester study plan</h3></div>{plan && <span className="verified-label">{plan.total_credit_hours} credit hours · {plan.source?.verification_status || 'Source status unavailable'}</span>}</div>{error && <div className="form-error">{error}</div>}{plan ? <><div className="plan-grid">{plan.semesters.map((semester) => <article className="semester-card" key={semester.semester}><header><strong>Semester {semester.semester}</strong><span>{semester.credit_hours} credits</span></header>{semester.courses.map((course, index) => <div className="plan-course" key={course.code || `${semester.semester}-${index}`}><b>{course.code || 'Elective'}</b><span>{course.title}</span><small>{course.total_credit_hours} CH</small></div>)}</article>)}</div><div className="official-notice" style={{marginTop: '24px'}}><strong>Internship</strong><span>{plan.internship}</span></div><p className="plan-caution" style={{marginTop: '12px'}}>Semester order is an official study plan. It does not automatically make every earlier course a formal prerequisite; inferred progression guidance is labeled separately.</p></> : !error && <Empty text="Loading the official BSCS scheme…" />}</section>
}

function Timetable({ auth }) {
  const [year, setYear] = useState(2026); const [term, setTerm] = useState('Fall'); const [course, setCourse] = useState(''); const [data, setData] = useState(null); const days = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
  async function load(event) { event?.preventDefault(); const query = `academic_year=${year}&term=${term}${course ? `&course_code=${encodeURIComponent(course)}` : ''}`; setData(await api(`/timetable?${query}`, {}, auth)) }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">CLASS SCHEDULE</p><h3>Class timetable</h3></div></div><form className="search-form" style={{marginBottom: '24px', alignItems: 'center'}} onSubmit={load}><label style={{display: 'flex', flexDirection: 'column', gap: '4px', flex: 1}}><span style={{fontSize: '11px', fontWeight: 'bold', color: '#1a5f57'}}>Year</span><input type="number" value={year} onChange={(e) => setYear(e.target.value)} style={{margin: 0}}/></label><label style={{display: 'flex', flexDirection: 'column', gap: '4px', flex: 1}}><span style={{fontSize: '11px', fontWeight: 'bold', color: '#1a5f57'}}>Term</span><select value={term} onChange={(e) => setTerm(e.target.value)} style={{border: 'none', background: 'transparent', padding: '12px 16px', fontSize: '15px'}}><option>Spring</option><option>Summer</option><option>Fall</option><option>Winter</option></select></label><label style={{display: 'flex', flexDirection: 'column', gap: '4px', flex: 2}}><span style={{fontSize: '11px', fontWeight: 'bold', color: '#1a5f57'}}>Course (optional)</span><input value={course} onChange={(e) => setCourse(e.target.value)} placeholder="e.g. CSC-211" style={{margin: 0}}/></label><button className="primary" style={{alignSelf: 'flex-end', marginBottom: '4px'}}>View</button></form>{data?.demo_data && <div className="notice">DEMO DATA - this synthetic timetable is provided only to exercise the completed workflow.</div>}{data && (data.entries.length ? <div className="table-wrap"><DataTable columns={['course_code', 'course_title', 'day_of_week', 'starts_at', 'ends_at', 'room', 'instructor']} rows={data.entries.map((r) => ({ ...r, day_of_week: days[r.day_of_week] }))} /></div> : <Empty text={data.notice} />)}</section>
}

function Policies({ auth }) {
  const [search, setSearch] = useState(''); const [rows, setRows] = useState([]); const [loaded, setLoaded] = useState(false); const [loading, setLoading] = useState(false);
  async function load(event) { event?.preventDefault(); setLoading(true); try { setRows(await api(`/policies?search=${encodeURIComponent(search)}`, {}, auth)); setLoaded(true) } catch(e) {} finally { setLoading(false) } }
  useEffect(() => { load() }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">POLICIES & GUIDELINES</p><h3>Academic policy records</h3></div></div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search attendance, FYP, thesis…" /><button className="primary" disabled={loading}>{loading ? 'Searching...' : 'Search'}</button></form><div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px'}}>{rows.map((r) => <article className="policy-card" key={r.rule_code}><span>{r.category}</span><h3>{r.title}</h3><p style={{marginBottom: '16px'}}>{r.description}</p><small style={{color: '#728c89'}}>Effective {r.effective_from} · {r.source?.title} · {r.source?.source_url ? r.source.verification_status : 'Source not authenticated'}</small></article>)}</div>{loaded && !rows.length && <Empty text="No matching verified policy was found. Contact the department for unpublished guidance." />}</section>
}

function History({ auth }) {
  const [rows, setRows] = useState([]); const [error, setError] = useState(''); const [search, setSearch] = useState('')
  async function load(event) { event?.preventDefault(); try { setRows(CHAT_ENGINE === 'advisor' ? await advisorRequest(`/me/history?search=${encodeURIComponent(search)}`, {}, auth) : await api(`/history?search=${encodeURIComponent(search)}`, {}, auth)) } catch (e) { setError(e.message) } }
  async function clear() { if (!confirm('Delete all of your saved conversations?')) return; if (CHAT_ENGINE === 'advisor') await advisorRequest('/me/history', { method: 'DELETE' }, auth); else await api('/history', { method: 'DELETE' }, auth); setRows([]) }
  useEffect(() => { load() }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">UC5 · PRIVATE RECORD</p><h3>Query history</h3></div>{rows.length > 0 && <button className="danger" onClick={clear}>Clear history</button>}</div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search questions, answers, or intents" /><button className="primary">Search history</button></form>{error && <div className="form-error">{error}</div>}{rows.length ? <div className="history-list">{rows.map((r) => <div className={`history-row ${r.role}`} key={r.message_id}><span>{r.role}</span><p>{CHAT_ENGINE === 'advisor' ? plainAnswer(r.content) : r.content}</p><small>{r.intent || 'response'} · {new Date(r.created_at).toLocaleString()}</small></div>)}</div> : <Empty text="No matching history. Authenticated conversations are saved here." />}</section>
}

function AdminPortal({ auth, online, onLogout }) {
  const [active, setActive] = useState('Dashboard')
  const navIcons = { 'Chatbot Engine': '✨', Dashboard: '📊', CMS: '🧠', Courses: '📚', Prerequisites: '🔗', Fees: '💰', Timetables: '🗓️', Policies: '📋', Knowledge: '📖', 'Query Logs': '🔍', Users: '👥', Model: '🤖', Settings: '⚙️', Reports: '📈' }
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">Q</div><div><strong>QAU CS</strong><small>Admin Panel</small></div></div><div className="profile-card"><div className="avatar">AD</div><div><strong>{auth.user.email}</strong><small>Administrator</small></div><span className="status-dot" /></div><nav>{['Dashboard', ...(CHAT_ENGINE === 'advisor' ? ['Chatbot Engine'] : []), 'CMS', 'Courses', 'Prerequisites', 'Fees', 'Timetables', 'Policies', 'Knowledge', 'Ingestion Review', ...(import.meta.env.VITE_CHATBOT_REBUILD === 'true' ? ['Timetable Management'] : []), 'Query Logs', 'Users', 'Model', 'Settings', 'Reports'].map((item) => <button key={item} className={active === item ? 'nav-item active' : 'nav-item'} onClick={() => setActive(item)}><span className="icon" aria-hidden="true">{navIcons[item] || '◇'}</span>{item}</button>)}</nav><div className="sidebar-bottom"><div className="source-note"><span>✓</span><div><strong>Admin access</strong><small>Full system control</small></div></div><button className="nav-item" onClick={onLogout}><span className="icon">↪</span>Log out</button></div></aside><main className="main-content"><header className="topbar"><div><p className="eyebrow">ADMINISTRATION / {active.toUpperCase()}</p><h1>{active}</h1></div><div className="top-actions"><span className={online ? 'connection online' : 'connection'}><i />{online ? 'API connected' : 'Offline'}</span><div className="mini-avatar">AD</div></div></header><div className="page-content-wrapper">{active === 'Dashboard' ? <AdminDashboard auth={auth} setActive={setActive} /> : active === 'Chatbot Engine' ? <AdvisorAdmin auth={auth} /> : active === 'Timetable Management' && import.meta.env.VITE_CHATBOT_REBUILD === 'true' ? <TimetableManagement auth={auth} /> : active === 'Ingestion Review' ? <KnowledgeReview request={(path, options) => api(path, options, auth)} /> : active === 'CMS' ? <CMSManager auth={auth} /> : active === 'Reports' ? <Reports auth={auth} /> : active === 'Query Logs' ? <QueryLogs auth={auth} /> : active === 'Model' ? <ModelManager auth={auth} /> : active === 'Settings' ? <SettingsManager auth={auth} /> : <AdminRecords auth={auth} module={active} />}</div></main></div>
}

const adminConfig = {
  Courses: { path: 'courses', columns: ['code', 'title', 'theory_credit_hours', 'lab_credit_hours', 'active'] },
  Prerequisites: { path: 'prerequisites', columns: ['course_code', 'prerequisite_course_code', 'relation_type', 'minimum_grade', 'verified', 'source_code'] },
  Fees: { path: 'fees', columns: ['program_code', 'official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from'] },
  Timetables: { path: 'timetables', columns: ['course_code', 'term', 'academic_year', 'day_of_week', 'starts_at', 'ends_at', 'room'] },
  Policies: { path: 'policies', columns: ['rule_code', 'category', 'title', 'effective_from', 'active'] },
  Knowledge: { path: 'knowledge', columns: ['title', 'category', 'source_code', 'verification_status', 'chunks', 'processing_status'], noEdit: true },
  Users: { path: 'users', columns: ['full_name', 'email', 'role', 'active', 'last_login_at', 'created_at'], readonly: true },
}

const FIELD_META = {
  code: { label: 'Course Code', placeholder: 'e.g. CSC-301', help: 'Unique course code (e.g. CSC-201)' },
  title: { label: 'Title', placeholder: 'Full course or rule title' },
  description: { label: 'Description / Content', placeholder: 'Full text description…', multiline: true },
  theory_credit_hours: { label: 'Theory Credits', placeholder: '3', type: 'number', help: '0–9' },
  lab_credit_hours: { label: 'Lab Credits', placeholder: '0', type: 'number', help: '0–9' },
  source_id: { label: 'Source Record', help: 'Select the official source this data comes from' },
  course_code: { label: 'Course Code', placeholder: 'CSC-301', help: 'The course being described' },
  prerequisite_course_code: { label: 'Prerequisite Course', placeholder: 'CSC-201', help: 'Must be taken before the above course' },
  curriculum: { label: 'Curriculum', placeholder: 'Fall 2025 onward', help: 'Curriculum scheme this applies to' },
  relation_type: { label: 'Type', help: 'Prerequisite = must be done before; Corequisite = taken together' },
  minimum_grade: { label: 'Minimum Grade', placeholder: 'D', help: 'Optional minimum passing grade' },
  waiver_condition: { label: 'Waiver Condition', placeholder: 'e.g. Instructor approval required', multiline: true, help: 'When can this prerequisite be waived?' },
  verified: { label: 'Is Verified?', help: 'Mark Yes only if this is a published official prerequisite' },
  program_code: { label: 'Program Code', placeholder: 'BSCS', help: 'Leave blank for all programs' },
  official_fee_category: { label: 'Fee Category', placeholder: 'BS Computer Science - National Students', help: 'Official category name from QAU fee structure' },
  shift: { label: 'Shift', placeholder: 'Morning / Evening', help: 'Class shift this fee applies to' },
  fee_type: { label: 'Fee Type', placeholder: 'semester_fee', help: 'e.g. semester_fee, admission_fee, lab_fee' },
  amount: { label: 'Amount (PKR)', placeholder: '45000', type: 'number', help: 'Amount in Pakistani Rupees' },
  effective_from: { label: 'Effective From', type: 'date', help: 'Date this fee/policy became effective' },
  effective_to: { label: 'Effective To', type: 'date', help: 'Leave blank if still active' },
  offering_id: { label: 'Course Offering', help: 'Select the specific semester/section offering' },
  session_type: { label: 'Session Type', help: 'Class = lecture, Lab = practical, Tutorial = extra session' },
  day_of_week: { label: 'Day of Week', placeholder: '2 = Monday…7 = Saturday', type: 'number', help: '1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu, 6=Fri, 7=Sat' },
  starts_at: { label: 'Start Time', placeholder: '08:00', type: 'time' },
  ends_at: { label: 'End Time', placeholder: '09:30', type: 'time' },
  room: { label: 'Room / Building', placeholder: 'CS-101 or Online', help: 'Room number or location' },
  lab_group: { label: 'Lab Group (optional)', placeholder: 'A, B, or blank', help: 'Optional lab section group' },
  rule_code: { label: 'Rule Code', placeholder: 'ATTEND-001', help: 'Short unique identifier (e.g. EXAM-POLICY-01)' },
  category: { label: 'Category', placeholder: 'Attendance', help: 'e.g. Attendance, Grading, FYP, Eligibility' },
  content: { label: 'Knowledge Content', placeholder: 'Paste full text here. Use double newlines to create separate chunks.', multiline: true, help: 'Each paragraph (separated by blank lines) becomes a searchable RAG chunk.' },
  full_name: { label: 'Full Name', placeholder: 'Muhammad Ali' },
  email: { label: 'Email', placeholder: 'student@qau.edu.pk', type: 'email' },
  role: { label: 'Role', help: 'student or admin' },
  active: { label: 'Active?', help: 'Inactive records are hidden from students' },
  priority: { label: 'Priority (lower = higher)', placeholder: '100', type: 'number', help: '0 = highest priority, 1000 = lowest' },
}

function FieldInput({ field, value, onChange, sources = [], offerings = [] }) {
  const meta = FIELD_META[field] || { label: field.replaceAll('_', ' '), placeholder: '' }
  const commonStyle = { display: 'block', width: '100%', border: '1px solid #d5e4e0', borderRadius: '9px', padding: '10px 12px', marginTop: '5px', background: '#fbfdfc', color: '#274743', font: 'inherit' }
  let input
  if (field === 'source_id') {
    input = <select required style={commonStyle} value={value || ''} onChange={(e) => onChange(e.target.value)}><option value="">— Select source record —</option>{sources.map((s) => <option key={s.id} value={s.id}>{s.source_code} · {s.title} [{s.verification_status}]</option>)}</select>
  } else if (field === 'offering_id') {
    input = <select required style={commonStyle} value={value || ''} onChange={(e) => onChange(e.target.value)}><option value="">— Select course offering —</option>{offerings.map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.term} {o.academic_year} · Section {o.section}</option>)}</select>
  } else if (field === 'session_type') {
    input = <select required style={commonStyle} value={value || ''} onChange={(e) => onChange(e.target.value)}><option value="">— Select —</option><option value="class">Class (Lecture)</option><option value="lab">Lab (Practical)</option><option value="tutorial">Tutorial</option></select>
  } else if (field === 'relation_type') {
    input = <select required style={commonStyle} value={value || 'prerequisite'} onChange={(e) => onChange(e.target.value)}><option value="prerequisite">Prerequisite (must complete before)</option><option value="corequisite">Corequisite (taken together)</option></select>
  } else if (field === 'active' || field === 'verified') {
    input = <select style={commonStyle} value={String(value ?? (field === 'active' ? true : false))} onChange={(e) => onChange(e.target.value === 'true')}><option value="true">{field === 'verified' ? '✓ Verified (officially published)' : '✓ Active (visible to students)'}</option><option value="false">{field === 'verified' ? '✗ Unverified (planning guidance)' : '✗ Inactive (hidden)'}</option></select>
  } else if (field === 'role') {
    input = <select style={commonStyle} value={value || 'student'} onChange={(e) => onChange(e.target.value)}><option value="student">Student</option><option value="admin">Administrator</option></select>
  } else if (meta.multiline) {
    input = <textarea required={!['waiver_condition', 'lab_group', 'description'].includes(field)} placeholder={meta.placeholder || ''} style={{...commonStyle, minHeight: field === 'content' ? '180px' : '80px', resize: 'vertical'}} value={value || ''} onChange={(e) => onChange(e.target.value)} />
  } else {
    const isOptional = ['lab_group', 'program_code', 'minimum_grade', 'waiver_condition', 'effective_to', 'lab_credit_hours'].includes(field)
    input = <input required={!isOptional} type={meta.type || (field.includes('_at') || field.includes('date') ? 'date' : field.includes('time') ? 'time' : 'text')} placeholder={meta.placeholder || ''} style={commonStyle} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
  }
  return <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}><span style={{ fontSize: '11px', fontWeight: '700', color: '#1a5f57', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{meta.label}</span>{input}{meta.help && <small style={{ color: '#8fa4a0', fontSize: '10px', marginTop: '2px' }}>{meta.help}</small>}</label>
}

function AdminDashboard({ auth, setActive }) {
  const [report, setReport] = useState(null)
  useEffect(() => { api('/admin/report', {}, auth).then(setReport).catch(() => {}) }, [])
  const modules = [
    { key: 'Courses', icon: '📚', desc: 'Manage course catalogue' },
    { key: 'Prerequisites', icon: '🔗', desc: 'Course prerequisite chains' },
    { key: 'Fees', icon: '💰', desc: 'Fee structures & charges' },
    { key: 'Timetables', icon: '🗓️', desc: 'Class schedules & rooms' },
    { key: 'Policies', icon: '📋', desc: 'Academic rules & policies' },
    { key: 'Knowledge', icon: '📖', desc: 'RAG knowledge base entries' },
    { key: 'CMS', icon: '🧠', desc: 'Chatbot content management' },
    { key: 'Query Logs', icon: '🔍', desc: 'Student query history' },
    { key: 'Users', icon: '👥', desc: 'Student & admin accounts' },
    { key: 'Reports', icon: '📈', desc: 'Usage analytics' },
    { key: 'Model', icon: '🤖', desc: 'AI model controls' },
    { key: 'Settings', icon: '⚙️', desc: 'System configuration' },
  ]
  return <div className="page-grid"><section className="welcome-card"><div><p className="eyebrow">ADMIN CONTROL CENTRE</p><h2>Academic data operations</h2><p>Manage all academic data. Content added here flows directly into the RAG knowledge base and chatbot responses.</p></div></section><div className="stat-grid"><Stat label="Student queries" value={report?.total_messages ?? '—'} note="Recorded messages" /><Stat label="Conversations" value={report?.total_sessions ?? '—'} note="Unique sessions" /><Stat label="Active students" value={report?.active_users_30d ?? '—'} note="Last 30 days" /></div><section className="section-card" style={{maxWidth: '980px'}}><div className="section-heading"><div><p className="eyebrow">MANAGEMENT MODULES</p><h3>All modules</h3></div></div><div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '14px'}}>{modules.map(({key, icon, desc}) => <button key={key} onClick={() => setActive(key)} style={{textAlign: 'left', padding: '20px', border: '1px solid #dce9e5', borderRadius: '14px', background: 'white', cursor: 'pointer', transition: 'all 0.2s', display: 'flex', flexDirection: 'column', gap: '8px'}} onMouseOver={(e) => e.currentTarget.style.boxShadow='0 8px 20px rgba(26,95,87,0.12)'} onMouseOut={(e) => e.currentTarget.style.boxShadow='none'}><span style={{fontSize: '26px'}}>{icon}</span><strong style={{color: '#1a5f57', fontSize: '15px'}}>{key}</strong><span style={{color: '#78908c', fontSize: '12px', lineHeight: '1.4'}}>{desc}</span></button>)}</div></section></div>
}

function AdminRecords({ auth, module }) {
  const config = adminConfig[module]
  const [rows, setRows] = useState([]); const [error, setError] = useState(''); const [showForm, setShowForm] = useState(false); const [editing, setEditing] = useState(null); const [loading, setLoading] = useState(false); const [syncing, setSyncing] = useState(false); const [syncResult, setSyncResult] = useState(null)
  async function load() { setError(''); setLoading(true); try { setRows(await api(`/admin/${config.path}`, {}, auth)) } catch (e) { setError(e.message) } finally { setLoading(false) } }
  useEffect(() => { load() }, [module])
  async function toggleUser(row) { try { await api(`/admin/users/${row.id}`, { method: 'PATCH', body: JSON.stringify({ active: !row.active }) }, auth); load() } catch (e) { setError(e.message) } }
  async function remove(row) { const id = row.id || row.code; if (!confirm(`Disable/delete "${row.title || row.code || id}"?`)) return; try { await api(`/admin/${config.path}/${encodeURIComponent(id)}`, { method: 'DELETE' }, auth); load() } catch (e) { setError(e.message) } }
  async function ragSync() { setSyncing(true); setSyncResult(null); try { const result = await api('/admin/knowledge/reindex', { method: 'POST' }, auth); setSyncResult({ ok: true, msg: `✓ Re-indexed ${result.chunks_created} chunks from ${result.documents_processed} documents.` }) } catch (e) { setSyncResult({ ok: false, msg: e.message }) } finally { setSyncing(false) } }
  return <section className="section-card full"><div className="section-heading" style={{marginBottom: '20px'}}><div><p className="eyebrow">ADMINISTRATOR ONLY</p><h3>Manage {module}</h3></div><div style={{display:'flex', gap:'10px', alignItems:'center'}}>{module === 'Knowledge' && <><button className="secondary" onClick={ragSync} disabled={syncing}>{syncing ? 'Syncing…' : '🔄 Sync to RAG'}</button>{syncResult && <span style={{fontSize:'11px', color: syncResult.ok ? '#2d8b63' : '#a13b3b'}}>{syncResult.msg}</span>}</>}{!config.readonly && module !== 'Users' && <button className="primary" onClick={() => setShowForm(!showForm)}>{showForm ? '✕ Cancel' : '+ Add record'}</button>}</div></div>{showForm && <AdminCreateForm module={module} auth={auth} onSaved={() => { setShowForm(false); load() }} />}{editing && <AdminEditForm module={module} row={editing} auth={auth} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}{error && <div className="form-error">{error}</div>}{loading ? <div className="empty-state"><span>⏳</span><h3>Loading…</h3></div> : <DataTable columns={config.columns} rows={rows} actions={!config.readonly ? (row) => <div className="row-actions">{!config.noEdit && <button className="small-button" onClick={() => setEditing(row)}>✏️ Edit</button>}{module === 'Users' ? <button className="small-button" onClick={() => toggleUser(row)}>{row.active ? 'Disable' : 'Enable'}</button> : <button className="danger small" onClick={() => remove(row)}>{module === 'Courses' || module === 'Policies' ? 'Disable' : 'Delete'}</button>}</div> : null} empty={`No ${module.toLowerCase()} are currently available.`} />}</section>
}

function AdminCreateForm({ module, auth, onSaved }) {
  const [values, setValues] = useState({}); const [error, setError] = useState(''); const [saving, setSaving] = useState(false); const [sources, setSources] = useState([]); const [offerings, setOfferings] = useState([])
  const fields = useMemo(() => ({ Courses: ['code', 'title', 'description', 'theory_credit_hours', 'lab_credit_hours', 'source_id'], Prerequisites: ['course_code', 'prerequisite_course_code', 'curriculum', 'relation_type', 'minimum_grade', 'waiver_condition', 'source_id', 'verified'], Fees: ['program_code', 'official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from', 'source_id'], Timetables: ['offering_id', 'session_type', 'day_of_week', 'starts_at', 'ends_at', 'room', 'lab_group'], Policies: ['rule_code', 'category', 'title', 'description', 'effective_from', 'source_id'], Knowledge: ['source_id', 'title', 'category', 'content'] }[module] || []), [module])
  useEffect(() => { if (fields.includes('source_id')) api('/admin/sources', {}, auth).then(setSources).catch(() => {}); if (fields.includes('offering_id')) api('/admin/offerings', {}, auth).then(setOfferings).catch(() => {}) }, [module])
  function set(field, val) { setValues((prev) => ({ ...prev, [field]: val })) }
  async function submit(event) { event.preventDefault(); setError(''); setSaving(true); try { const numeric = new Set(['theory_credit_hours', 'lab_credit_hours', 'amount', 'day_of_week']); const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, numeric.has(k) ? Number(v) : v])); await api(`/admin/${adminConfig[module].path}`, { method: 'POST', body: JSON.stringify(payload) }, auth); onSaved() } catch (e) { setError(e.message) } finally { setSaving(false) } }
  return <div style={{background: '#f5f9f8', borderRadius: '16px', padding: '28px', marginBottom: '24px', border: '1px solid #dce9e5'}}><p style={{margin: '0 0 20px', fontWeight: '700', color: '#1a5f57', fontSize: '15px'}}>➕ New {module.slice(0,-1 > 0 ? -1 : undefined)} record</p><form style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '18px'}} onSubmit={submit}>{fields.map((f) => <FieldInput key={f} field={f} value={values[f]} onChange={(v) => set(f, v)} sources={sources} offerings={offerings} />)}{error && <div className="form-error" style={{gridColumn: '1 / -1'}}>{error}</div>}<div style={{gridColumn: '1 / -1', display: 'flex', gap: '10px', marginTop: '8px'}}><button className="primary" disabled={saving}>{saving ? 'Saving…' : '💾 Save record'}</button></div></form></div>
}

function AdminEditForm({ module, row, auth, onCancel, onSaved }) {
  const fieldDefs = { Courses: ['title', 'description', 'theory_credit_hours', 'lab_credit_hours', 'active'], Prerequisites: ['relation_type', 'minimum_grade', 'waiver_condition', 'verified'], Fees: ['official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from', 'effective_to'], Timetables: ['session_type', 'day_of_week', 'starts_at', 'ends_at', 'room', 'lab_group'], Policies: ['category', 'title', 'description', 'effective_from', 'priority', 'active'], Users: ['full_name', 'email', 'role', 'active'] }[module] || []
  const [values, setValues] = useState(Object.fromEntries(fieldDefs.map((f) => [f, row[f] ?? '']))); const [error, setError] = useState(''); const [saving, setSaving] = useState(false)
  function set(field, val) { setValues((prev) => ({ ...prev, [field]: val })) }
  async function submit(event) { event.preventDefault(); setError(''); setSaving(true); try { const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, ['amount', 'day_of_week', 'theory_credit_hours', 'lab_credit_hours', 'priority'].includes(k) ? Number(v) : v ?? null])); await api(`/admin/${adminConfig[module].path}/${encodeURIComponent(row.id || row.code)}`, { method: 'PATCH', body: JSON.stringify(payload) }, auth); onSaved() } catch (e) { setError(e.message) } finally { setSaving(false) } }
  return <div style={{background: '#fff8e8', borderRadius: '16px', padding: '28px', marginBottom: '24px', border: '2px solid #f2e0b5'}}><p style={{margin: '0 0 20px', fontWeight: '700', color: '#8b6a37', fontSize: '15px'}}>✏️ Editing: <code style={{background: '#eee', padding: '2px 8px', borderRadius: '4px', fontSize: '13px'}}>{row.code || row.email || row.title || row.id}</code></p><form style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '18px'}} onSubmit={submit}>{fieldDefs.map((f) => <FieldInput key={f} field={f} value={values[f]} onChange={(v) => set(f, v)} />)}{error && <div className="form-error" style={{gridColumn: '1 / -1'}}>{error}</div>}<div style={{gridColumn: '1 / -1', display: 'flex', gap: '10px', marginTop: '8px'}}><button className="primary" disabled={saving}>{saving ? 'Saving…' : '💾 Save changes'}</button><button type="button" className="secondary" onClick={onCancel}>Cancel</button></div></form></div>
}

function QueryLogs({ auth }) {
  const [rows, setRows] = useState([]); const [search, setSearch] = useState(''); const [email, setEmail] = useState(''); const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [offset, setOffset] = useState(0); const [error, setError] = useState(''); const limit = 50
  const params = () => new URLSearchParams({ limit, offset, ...(search && { search }), ...(email && { email }), ...(start && { start }), ...(end && { end }) })
  async function load(event, nextOffset = offset) { event?.preventDefault(); setError(''); const query = new URLSearchParams({ limit, offset: nextOffset, ...(search && { search }), ...(email && { email }), ...(start && { start }), ...(end && { end }) }); try { setRows(await api(`/admin/query-logs?${query}`, {}, auth)); setOffset(nextOffset) } catch (e) { setError(e.message) } }
  useEffect(() => { load() }, [])
  async function download() { const query = params(); query.delete('limit'); query.delete('offset'); const response = await fetch(`${API}/admin/query-logs-export?${query}`, { headers: { Authorization: `Bearer ${auth.access_token}` } }); if (!response.ok) { setError('Could not export logs'); return } const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = 'qau-query-logs.csv'; link.click(); URL.revokeObjectURL(url) }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">UC16 · AUDITABLE QUERIES</p><h3>Search and export query logs</h3></div><button className="secondary" onClick={download}>Export CSV</button></div><form className="filter-form" onSubmit={(e) => load(e, 0)}><label>Text or intent<input value={search} onChange={(e) => setSearch(e.target.value)} /></label><label>Student email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Start<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>End<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label><button className="primary">Filter</button></form>{error && <div className="form-error">{error}</div>}<DataTable columns={['email', 'content', 'intent', 'intent_confidence', 'response_time_ms', 'created_at']} rows={rows} /><div className="row-actions"><button className="secondary" disabled={!offset} onClick={() => load(null, Math.max(0, offset - limit))}>Previous</button><button className="secondary" disabled={rows.length < limit} onClick={() => load(null, offset + limit)}>Next</button></div></section>
}

function ModelManager({ auth }) {
  const [status, setStatus] = useState(null); const [error, setError] = useState(''); const load = () => api('/admin/model', {}, auth).then(setStatus).catch((e) => setError(e.message)); useEffect(load, [])
  async function reload() { try { setStatus(await api('/admin/model/reload', { method: 'POST' }, auth)) } catch (e) { setError(e.message) } }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">AI MODEL CONTROL</p><h3>Multilingual intent model</h3></div><button className="primary" onClick={reload}>Reload model artifact</button></div>{error && <div className="form-error">{error}</div>}{status && <DataTable columns={['requested_backend', 'active_backend', 'model_name', 'artifact_ready', 'fallback_active', 'error']} rows={[status]} />}</section>
}

function SettingsManager({ auth }) {
  const [rows, setRows] = useState([]); const [error, setError] = useState(''); const load = () => api('/admin/settings', {}, auth).then(setRows).catch((e) => setError(e.message)); useEffect(load, [])
  async function edit(row) { const entered = prompt(`New JSON value for ${row.key}`, JSON.stringify(row.value)); if (entered == null) return; try { await api(`/admin/settings/${encodeURIComponent(row.key)}`, { method: 'PATCH', body: JSON.stringify({ value: JSON.parse(entered) }) }, auth); load() } catch (e) { setError(`Use valid JSON. ${e.message}`) } }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">SYSTEM CONFIGURATION</p><h3>Runtime application settings</h3></div></div>{error && <div className="form-error">{error}</div>}<DataTable columns={['key', 'value', 'description', 'updated_at']} rows={rows.map((r) => ({ ...r, value: JSON.stringify(r.value) }))} actions={(row) => <button className="small-button" onClick={() => edit(rows.find((r) => r.key === row.key))}>Edit</button>} /></section>
}

function Reports({ auth }) {
  const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [report, setReport] = useState(null); const [error, setError] = useState('')
  async function generate(event) { event?.preventDefault(); setError(''); try { setReport(await api(`/admin/report?${new URLSearchParams({ ...(start && { start }), ...(end && { end }) })}`, {}, auth)) } catch (e) { setError(e.message) } }
  useEffect(() => { generate() }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">UC17 · USAGE ANALYTICS</p><h3>Generate report</h3></div><button className="secondary" onClick={() => window.print()}>Print report</button></div><form className="filter-form" onSubmit={generate}><label>Start date<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>End date<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label><button className="primary">Generate</button></form>{error && <div className="form-error">{error}</div>}{report && <><div className="stat-grid"><Stat label="Messages" value={report.total_messages} note="Student questions" /><Stat label="Sessions" value={report.total_sessions} note={`Average ${report.average_session_minutes ?? 0} min`} /><Stat label="Active students" value={report.active_users_30d} note={`${report.total_users} registered`} /><Stat label="Intents" value={report.intents_seen} note="Categories" /></div>{report.warning && <div className="notice">{report.warning}</div>}<DataTable columns={['intent', 'count']} rows={report.by_intent} /></>}</section>
}

function CMSManager({ auth }) {
  const [entries, setEntries] = useState([])
  const [stats, setStats] = useState(null)
  const [category, setCategory] = useState('')
  const [language, setLanguage] = useState('en')
  const [isActive, setIsActive] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 20
  
  const categories = ['scheme', 'admission', 'fee_structure', 'timetable', 'course', 'policy', 'general_notice', 'faq', 'contact', 'other']
  
  async function loadEntries() {
    setError('')
    const params = new URLSearchParams({ page, page_size: pageSize, language })
    if (category) params.append('category', category)
    if (isActive !== null) params.append('is_active', isActive)
    
    try {
      const result = await api(`/admin/cms/entries?${params}`, {}, auth)
      setEntries(result.items)
      setTotal(result.total)
    } catch (e) {
      setError(e.message)
    }
  }
  
  async function loadStats() {
    try {
      const result = await api('/admin/cms/stats', {}, auth)
      setStats(result)
    } catch (e) {
      console.error('Stats load error:', e)
    }
  }
  
  useEffect(() => { loadEntries(); loadStats() }, [page, category, language, isActive])
  
  async function toggleActive(entry) {
    try {
      if (entry.is_active) {
        await api(`/admin/cms/entries/${entry.id}`, { method: 'DELETE' }, auth)
      } else {
        await api(`/admin/cms/entries/${entry.id}/activate`, { method: 'POST' }, auth)
      }
      loadEntries()
      loadStats()
    } catch (e) {
      setError(e.message)
    }
  }
  
  async function invalidateCache() {
    if (!confirm('Invalidate prompt assembly cache? This will force re-assembly on next chat request.')) return
    try {
      await api('/admin/cms/cache/invalidate', { 
        method: 'POST', 
        body: JSON.stringify({ all: true }) 
      }, auth)
      alert('Cache invalidated successfully')
    } catch (e) {
      setError(e.message)
    }
  }
  
  return (
    <section className="section-card full">
      <div className="section-heading">
        <div>
          <p className="eyebrow">KNOWLEDGE BASE CMS</p>
          <h3>Dynamic Content Management</h3>
          <p>Manage knowledge entries that inject into the chatbot's system prompt</p>
        </div>
        <div className="row-actions">
          <button className="secondary" onClick={invalidateCache}>Clear Cache</button>
          <button className="primary" onClick={() => setShowForm(!showForm)}>+ Add Entry</button>
        </div>
      </div>
      
      {stats && (
        <div className="stat-grid">
          <Stat label="Total Entries" value={stats.total_entries} note={`${stats.active_entries} active`} />
          <Stat label="Pending Verification" value={stats.pending_verification} note="Needs review" />
          <Stat label="Categories" value={Object.keys(stats.by_category).length} note="In use" />
        </div>
      )}
      
      {showForm && <CMSCreateForm auth={auth} onCancel={() => setShowForm(false)} onSaved={() => { setShowForm(false); loadEntries(); loadStats() }} />}
      {editing && <CMSEditForm entry={editing} auth={auth} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); loadEntries(); loadStats() }} />}
      
      <form className="filter-form" onSubmit={(e) => { e.preventDefault(); setPage(1); loadEntries() }}>
        <label>Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {categories.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
          </select>
        </label>
        <label>Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="ur">Urdu</option>
          </select>
        </label>
        <label>Status
          <select value={String(isActive)} onChange={(e) => setIsActive(e.target.value === 'true')}>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </label>
        <button className="primary">Filter</button>
      </form>
      
      {error && <div className="form-error">{error}</div>}
      
      <div className="table-wrap">
        {entries.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Sub Key</th>
                <th>Category</th>
                <th>Title</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(entry => (
                <tr key={entry.id}>
                  <td><code>{entry.sub_key}</code></td>
                  <td>{entry.category}</td>
                  <td>{entry.title}</td>
                  <td>{entry.priority}</td>
                  <td>
                    {entry.is_active ? <span style={{color: 'green'}}>●</span> : <span style={{color: 'gray'}}>○</span>}
                    {entry.is_verified && <span style={{color: 'blue'}} title="Verified"> ✓</span>}
                  </td>
                  <td>{new Date(entry.updated_at).toLocaleDateString()}</td>
                  <td>
                    <div className="row-actions">
                      <button className="small-button" onClick={() => setEditing(entry)}>Edit</button>
                      <button 
                        className={entry.is_active ? "danger small" : "small-button"} 
                        onClick={() => toggleActive(entry)}
                      >
                        {entry.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty text="No knowledge entries found. Create your first entry to get started." />
        )}
      </div>
      
      <div className="row-actions">
        <button className="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>{page} of {Math.ceil(total / pageSize) || 1}</span>
        <button className="secondary" disabled={entries.length < pageSize} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </section>
  )
}

function CMSCreateForm({ auth, onCancel, onSaved }) {
  const [values, setValues] = useState({
    sub_key: '',
    category: 'scheme',
    title: '',
    content_markdown: '',
    structured_data: '{}',
    source_url: '',
    source_document: '',
    language: 'en',
    is_active: true,
    is_verified: false,
    priority: 100
  })
  const [error, setError] = useState('')
  
  const categories = ['scheme', 'admission', 'fee_structure', 'timetable', 'course', 'policy', 'general_notice', 'faq', 'contact', 'other']
  
  async function submit(event) {
    event.preventDefault()
    setError('')
    
    try {
      // Parse structured_data JSON
      const structuredData = values.structured_data ? JSON.parse(values.structured_data) : {}
      
      const payload = {
        ...values,
        structured_data: structuredData,
        is_active: values.is_active === true || values.is_active === 'true',
        is_verified: values.is_verified === true || values.is_verified === 'true',
        priority: Number(values.priority)
      }
      
      await api('/admin/cms/entries', { 
        method: 'POST', 
        body: JSON.stringify(payload) 
      }, auth)
      
      onSaved()
    } catch (e) {
      setError(e.message)
    }
  }
  
  return (
    <form className="admin-form" onSubmit={submit}>
      <div className="form-title">Create Knowledge Entry</div>
      
      <label>Sub Key (unique identifier)
        <input 
          required
          value={values.sub_key} 
          onChange={(e) => setValues({ ...values, sub_key: e.target.value })}
          placeholder="e.g., scheme_2025, admission_fall_2026"
          pattern="[a-z0-9_-]+"
          title="Only lowercase letters, numbers, underscores, and hyphens"
        />
      </label>
      
      <label>Category
        <select required value={values.category} onChange={(e) => setValues({ ...values, category: e.target.value })}>
          {categories.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
        </select>
      </label>
      
      <label>Title
        <input 
          required
          value={values.title} 
          onChange={(e) => setValues({ ...values, title: e.target.value })}
          placeholder="e.g., BSCS Scheme of Study 2025"
        />
      </label>
      
      <label>Content (Markdown)
        <textarea 
          required
          value={values.content_markdown} 
          onChange={(e) => setValues({ ...values, content_markdown: e.target.value })}
          rows={15}
          placeholder="Enter markdown content here..."
        />
      </label>
      
      <label>Structured Data (JSON, optional)
        <textarea 
          value={values.structured_data} 
          onChange={(e) => setValues({ ...values, structured_data: e.target.value })}
          rows={5}
          placeholder='{"key": "value"}'
        />
      </label>
      
      <label>Source URL (optional)
        <input 
          type="url"
          value={values.source_url} 
          onChange={(e) => setValues({ ...values, source_url: e.target.value })}
          placeholder="https://..."
        />
      </label>
      
      <label>Source Document (optional)
        <input 
          value={values.source_document} 
          onChange={(e) => setValues({ ...values, source_document: e.target.value })}
          placeholder="e.g., Scheme_2025.pdf"
        />
      </label>
      
      <label>Language
        <select value={values.language} onChange={(e) => setValues({ ...values, language: e.target.value })}>
          <option value="en">English</option>
          <option value="ur">Urdu</option>
        </select>
      </label>
      
      <label>Priority (lower = higher priority)
        <input 
          type="number"
          value={values.priority} 
          onChange={(e) => setValues({ ...values, priority: e.target.value })}
          min="0"
          max="1000"
        />
      </label>
      
      <label>Is Active
        <select value={String(values.is_active)} onChange={(e) => setValues({ ...values, is_active: e.target.value })}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      
      <label>Is Verified
        <select value={String(values.is_verified)} onChange={(e) => setValues({ ...values, is_verified: e.target.value })}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      
      {error && <div className="form-error">{error}</div>}
      
      <button className="primary">Create Entry</button>
      <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
    </form>
  )
}

function CMSEditForm({ entry, auth, onCancel, onSaved }) {
  const [values, setValues] = useState({
    title: entry.title || '',
    content_markdown: entry.content_markdown || '',
    structured_data: JSON.stringify(entry.structured_data || {}, null, 2),
    source_url: entry.source_url || '',
    source_document: entry.source_document || '',
    language: entry.language || 'en',
    is_active: entry.is_active,
    is_verified: entry.is_verified,
    priority: entry.priority || 100
  })
  const [error, setError] = useState('')
  
  async function submit(event) {
    event.preventDefault()
    setError('')
    
    try {
      // Parse structured_data JSON
      const structuredData = values.structured_data ? JSON.parse(values.structured_data) : {}
      
      const payload = {
        ...values,
        structured_data: structuredData,
        is_active: values.is_active === true || values.is_active === 'true',
        is_verified: values.is_verified === true || values.is_verified === 'true',
        priority: Number(values.priority)
      }
      
      await api(`/admin/cms/entries/${entry.id}`, { 
        method: 'PATCH', 
        body: JSON.stringify(payload) 
      }, auth)
      
      onSaved()
    } catch (e) {
      setError(e.message)
    }
  }
  
  return (
    <form className="admin-form" onSubmit={submit}>
      <div className="form-title">Editing {entry.sub_key}</div>
      
      <label>Title
        <input 
          required
          value={values.title} 
          onChange={(e) => setValues({ ...values, title: e.target.value })}
        />
      </label>
      
      <label>Content (Markdown)
        <textarea 
          required
          value={values.content_markdown} 
          onChange={(e) => setValues({ ...values, content_markdown: e.target.value })}
          rows={15}
        />
      </label>
      
      <label>Structured Data (JSON)
        <textarea 
          value={values.structured_data} 
          onChange={(e) => setValues({ ...values, structured_data: e.target.value })}
          rows={5}
        />
      </label>
      
      <label>Source URL
        <input 
          type="url"
          value={values.source_url} 
          onChange={(e) => setValues({ ...values, source_url: e.target.value })}
        />
      </label>
      
      <label>Source Document
        <input 
          value={values.source_document} 
          onChange={(e) => setValues({ ...values, source_document: e.target.value })}
        />
      </label>
      
      <label>Language
        <select value={values.language} onChange={(e) => setValues({ ...values, language: e.target.value })}>
          <option value="en">English</option>
          <option value="ur">Urdu</option>
        </select>
      </label>
      
      <label>Priority
        <input 
          type="number"
          value={values.priority} 
          onChange={(e) => setValues({ ...values, priority: e.target.value })}
          min="0"
          max="1000"
        />
      </label>
      
      <label>Is Active
        <select value={String(values.is_active)} onChange={(e) => setValues({ ...values, is_active: e.target.value })}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      
      <label>Is Verified
        <select value={String(values.is_verified)} onChange={(e) => setValues({ ...values, is_verified: e.target.value })}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      
      {error && <div className="form-error">{error}</div>}
      
      <button className="primary">Save Changes</button>
      <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
    </form>
  )
}

function DataTable({ columns, rows = [], actions, empty = 'No records found.' }) { if (!rows.length) return <Empty text={empty} />; return <div className="table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c.replaceAll('_', ' ')}</th>)}{actions && <th>Actions</th>}</tr></thead><tbody>{rows.map((row, i) => <tr key={row.id || row.code || i}>{columns.map((c) => <td key={c}>{row[c] == null ? '—' : typeof row[c] === 'boolean' ? (row[c] ? 'Yes' : 'No') : String(row[c])}</td>)}{actions && <td>{actions(row)}</td>}</tr>)}</tbody></table></div> }
function Empty({ text }) { return <div className="empty-state"><span>◇</span><h3>No records to display</h3><p>{text}</p></div> }
function Stat({ label, value, note }) { return <div className="stat-card"><small>{label}</small><strong>{value}</strong><span>{note}</span></div> }

if (document.getElementById('root')) createRoot(document.getElementById('root')).render(<App />)
