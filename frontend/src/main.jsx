import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { marked } from 'marked'
import './styles.css'

const API = import.meta.env.VITE_API_URL || '/api/v1'
const suggestions = [
  ['Prerequisites', 'What are the prerequisites for CSC-483?'],
  ['Credit hours', 'How many credit hours can I take this semester?'],
  ['Fees', 'What is the BSCS morning semester fee?'],
  ['Policy', 'What are the FYP submission rules?'],
]

function savedAuth() {
  try { return JSON.parse(localStorage.getItem('qau-auth')) || null } catch { return null }
}

async function api(path, options = {}, auth = null) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {}),
      ...options.headers,
    },
  })
  let data = null
  try { data = await response.json() } catch { data = null }
  if (response.status === 401 && auth?.access_token) window.dispatchEvent(new Event('qau-auth-expired'))
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`)
  return data
}

export function App() {
  const [auth, setAuth] = useState(savedAuth)
  const [online, setOnline] = useState(false)
  useEffect(() => { api('/health').then(() => setOnline(true)).catch(() => setOnline(false)) }, [])
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
  const adminNav = ['Dashboard', 'Courses', 'Prerequisites', 'Fees', 'Timetables', 'Policies', 'Knowledge', 'Query Logs', 'Users', 'Model', 'Settings', 'Reports']
  const items = admin ? adminNav : studentNav
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">Q</div><div><strong>QAU CS</strong><small>Academic Advisor</small></div></div><div className="profile-card"><div className="avatar">{admin ? 'AD' : guest ? 'GU' : 'ST'}</div><div><strong>{auth.user.email}</strong><small>{admin ? 'Administrator' : guest ? 'Guest · history off' : 'Student account'}</small></div><span className="status-dot" /></div><nav>{items.map((item) => <button key={item} className={active === item ? 'nav-item active' : 'nav-item'} onClick={() => setActive(item)}><span className="icon" aria-hidden="true">{admin ? '◇' : '•'}</span>{item}</button>)}</nav><div className="sidebar-bottom"><div className="source-note"><span>✓</span><div><strong>Mixed knowledge base</strong><small>Official + clearly marked demo data</small></div></div>{guest && <div className="guest-save-note">Sign in to save and revisit your conversations.</div>}<button className="nav-item" onClick={onLogout}><span className="icon">↪</span>{guest ? 'Sign in' : 'Log out'}</button></div></aside><main className="main-content"><div className="demo-banner"><strong>Demonstration mode</strong><span>Synthetic Fall 2026 records are included for testing and are not official QAU notices.</span></div><header className="topbar"><div><p className="eyebrow">{admin ? 'ADMINISTRATION' : guest ? 'GUEST ADVISOR' : 'STUDENT PORTAL'} / {active.toUpperCase()}</p><h1>{active}</h1></div><div className="top-actions"><span className={online ? 'connection online' : 'connection'}><i />{online ? 'API connected' : 'Offline'}</span><div className="mini-avatar">{admin ? 'AD' : guest ? 'GU' : 'ST'}</div></div></header>{children}</main></div>
}

function StudentPortal({ auth, online, onLogout }) {
  const [active, setActive] = useState('Chat')
  return <Shell {...{ auth, online, active, setActive, onLogout }}>
    {active === 'Chat' && <Chat auth={auth} />}
    {active !== 'Chat' && <div className="page-content-wrapper">
      {active === 'Study Plan' && <StudyPlan auth={auth} />}
      {active === 'Courses' && <CourseSearch auth={auth} />}
      {active === 'Fees' && <Fees auth={auth} />}
      {active === 'Timetable' && <Timetable auth={auth} />}
      {active === 'Policies' && <Policies auth={auth} />}
      {active === 'History' && <History auth={auth} />}
    </div>}
  </Shell>
}

function Fees({ auth }) {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api('/fees?program_code=BSCS', {}, auth).then(setData).catch((e) => setError(e.message)) }, [])
  const core = data?.fees.filter((f) => f.official_fee_category === 'BS Computer Science - National Students') || []
  const service = data?.fees.filter((f) => f.official_fee_category.includes('Category C')) || []
  const formatRows = (rows) => rows.map((f) => ({ ...f, fee_type: f.fee_type.replaceAll('_', ' '), amount: `${f.currency} ${Number(f.amount).toLocaleString()}`, source: f.source?.verification_status === 'verified' ? 'Verified QAU' : f.source?.verification_status }))
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">OFFICIAL QAU · FALL 2026</p><h3>BS Computer Science fee structure</h3></div><span className="verified-label">✓ Verified 17 Aug 2026</span></div><div className="official-notice"><strong>National students</strong><span>Amounts below come from the official QAU bachelor fee page. Taxes, field work, laboratory, hostel, or other applicable charges may be additional.</span></div>{error && <div className="form-error">{error}</div>}{core.length ? <><h4 className="table-title">Admission and semester totals</h4><DataTable columns={['shift', 'fee_type', 'amount', 'source']} rows={formatRows(core)} /><h4 className="table-title">Published service and one-time charges</h4><DataTable columns={['shift', 'fee_type', 'amount']} rows={formatRows(service)} /></> : !error && <Empty text="Loading the official fee structure…" />}<a className="source-link" href="https://qau.edu.pk/bachelor-fee-structure/" target="_blank" rel="noreferrer">View the official QAU fee page ↗</a></section>
}

function Chat({ auth }) {
  const [messages, setMessages] = useState([{ role: 'assistant', text: 'Assalam-o-Alaikum. Ask me about courses, prerequisites, fees, schedules, exams, policies, or research requirements.' }])
  const [input, setInput] = useState(''); const [sending, setSending] = useState(false); const [sessionId, setSessionId] = useState(null); const [contextCourseCode, setContextCourseCode] = useState(null); const [language, setLanguage] = useState('en')
  const [showScrollButton, setShowScrollButton] = useState(false)
  const scrollRef = React.useRef(null)
  const urdu = language === 'ur'
  
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
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
      const result = await api('/chat', { method: 'POST', body: JSON.stringify({ message: query, session_id: sessionId, context_course_code: contextCourseCode }) }, auth)
      const backendLabel = result.model_backend === 'ollama' ? `${result.model_name || 'Ollama LLM'}` : result.model_backend === 'multilingual_distilbert' ? 'Multilingual DistilBERT' : 'offline NLP fallback'
      setContextCourseCode(result.entities?.course_code?.[0] || contextCourseCode); setSessionId(result.session_id || sessionId); setMessages((m) => [...m, { role: 'assistant', text: result.answer, meta: `${result.language} · ${Math.round(result.confidence * 100)}% confidence · ${backendLabel} · ${result.verified ? 'verified' : 'confirmation advised'}`, citations: result.citations }])
    } catch (reason) { setMessages((m) => [...m, { role: 'assistant', text: reason.message, meta: 'Unable to process query' }]) }
    finally { setSending(false) }
  }
  const guest = auth.user.role === 'guest'
  return <section className="chat-layout" dir={urdu ? 'rtl' : 'ltr'}><div className="chat-panel"><div className="chat-toolbar"><span>{guest ? 'Guest conversation · not saved' : 'Private authenticated conversation · history enabled'}</span><button className="language-toggle" onClick={() => setLanguage(urdu ? 'en' : 'ur')}>{urdu ? 'English' : 'اردو'}</button></div><div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>{messages.map((m, i) => <div key={i} className={`message-row ${m.role}`}><div className="message-avatar">{m.role === 'assistant' ? 'Q' : guest ? 'GU' : 'ST'}</div><div>{m.role === 'assistant' ? <div className="message-bubble" dangerouslySetInnerHTML={{ __html: marked.parse(m.text) }} /> : <div className="message-bubble">{m.text}</div>}{m.meta && <small className="message-meta">{m.meta}</small>}{m.citations?.map((c) => <a className="citation" key={c.source_code} href={c.source_url} target="_blank" rel="noreferrer">{c.title || c.source_code}</a>)}</div></div>)}{sending && <div className="message-row assistant"><div className="message-avatar">Q</div><div className="message-bubble typing"><span /><span /><span /></div></div>}</div><button className={`scroll-to-bottom ${showScrollButton ? 'visible' : ''}`} onClick={scrollToBottom} aria-label="Scroll to bottom">↓</button><div className="composer-wrapper"><div className="composer"><input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} placeholder={urdu ? 'اپنا تعلیمی سوال پوچھیں…' : 'Ask an academic question…'} /><button onClick={() => send()} disabled={sending} aria-label="Send query">↑</button></div><small className="privacy">{guest ? 'This guest conversation is not stored. Sign in to enable History. ' : ''}Answers use available records and clearly identify demo or unverified information.</small></div></div><aside className="suggestions"><p className="eyebrow">QUICK START</p><h3>Popular questions</h3>{suggestions.map(([label, q]) => <button key={label} onClick={() => send(q)}><span>{label}</span><b>›</b><small>{q}</small></button>)}</aside></section>
}

function CourseSearch({ auth }) {
  const [search, setSearch] = useState(''); const [courses, setCourses] = useState([]); const [selected, setSelected] = useState(null); const [prerequisites, setPrerequisites] = useState(null); const [error, setError] = useState('')
  async function load(event) { event?.preventDefault(); setError(''); try { const rows = await api(`/courses?search=${encodeURIComponent(search)}&limit=100`, {}, auth); setCourses(rows); if (!rows.length) setError('Course not found. Try a course code or a different title keyword.') } catch (e) { setError(e.message) } }
  useEffect(() => { load() }, [])
  async function selectCourse(course) { setSelected(course); setPrerequisites(null); try { setPrerequisites(await api(`/courses/${encodeURIComponent(course.code)}/prerequisites`, {}, auth)) } catch (e) { setPrerequisites({ error: e.message, prerequisites: [] }) } }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">UC8 · VERIFIED CATALOGUE</p><h3>Search course by name or code</h3></div></div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. Data Structures or CSC-211" aria-label="Course name or code" /><button className="primary">Search</button></form>{error && <div className="notice">{error}</div>}<div className="course-list">{courses.map((course) => <button className="course-row" key={course.code} onClick={() => selectCourse(course)}><div className="course-code">{course.code}</div><div><strong>{course.title}</strong><small>{course.total_credit_hours} credit hours</small></div><span>View details ›</span></button>)}</div>{selected && <div className="detail-drawer"><button className="close-button" onClick={() => setSelected(null)}>×</button><p className="eyebrow">{selected.code}</p><h3>{selected.title}</h3><p>{selected.description || 'No expanded description is stored.'}</p><p><strong>Credits:</strong> {selected.theory_credit_hours} theory + {selected.lab_credit_hours} lab</p><h4>Prerequisite / progression guidance</h4>{prerequisites?.prerequisites?.length ? <ul className="prerequisite-list">{prerequisites.prerequisites.map((p) => <li key={p.course_code}><strong>{p.course_code}</strong> {p.course_title}<span className={p.verified ? 'verified-chip' : 'guidance-chip'}>{p.verified ? 'Published prerequisite' : 'Inferred sequence'}</span></li>)}</ul> : <p>{prerequisites ? 'No stored prerequisite link.' : 'Loading…'}</p>}{prerequisites?.notice && <div className="drawer-notice">{prerequisites.notice}</div>}<p><strong>Source:</strong> {selected.source?.title || 'Catalogue record pending source metadata'}</p></div>}</section>
}

function StudyPlan({ auth }) {
  const [plan, setPlan] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api('/programs/BSCS/study-plan', {}, auth).then(setPlan).catch((e) => setError(e.message)) }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">OFFICIAL FALL 2025 SCHEME</p><h3>BSCS eight-semester study plan</h3></div>{plan && <span className="verified-label">✓ {plan.total_credit_hours} credit hours</span>}</div>{error && <div className="form-error">{error}</div>}{plan ? <><div className="plan-grid">{plan.semesters.map((semester) => <article className="semester-card" key={semester.semester}><header><strong>Semester {semester.semester}</strong><span>{semester.credit_hours} credits</span></header>{semester.courses.map((course, index) => <div className="plan-course" key={course.code || `${semester.semester}-${index}`}><b>{course.code || 'Elective'}</b><span>{course.title}</span><small>{course.total_credit_hours} CH</small></div>)}</article>)}</div><div className="official-notice"><strong>Internship</strong><span>{plan.internship}</span></div><p className="plan-caution">Semester order is an official study plan. It does not automatically make every earlier course a formal prerequisite; inferred progression guidance is labeled separately.</p></> : !error && <Empty text="Loading the official BSCS scheme…" />}</section>
}

function Timetable({ auth }) {
  const [year, setYear] = useState(2026); const [term, setTerm] = useState('Fall'); const [course, setCourse] = useState(''); const [data, setData] = useState(null); const days = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
  async function load(event) { event?.preventDefault(); const query = `academic_year=${year}&term=${term}${course ? `&course_code=${encodeURIComponent(course)}` : ''}`; setData(await api(`/timetable?${query}`, {}, auth)) }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">CLASS SCHEDULE</p><h3>Class timetable</h3></div></div><form className="filter-form" onSubmit={load}><label>Year<input type="number" value={year} onChange={(e) => setYear(e.target.value)} /></label><label>Term<select value={term} onChange={(e) => setTerm(e.target.value)}><option>Spring</option><option>Summer</option><option>Fall</option><option>Winter</option></select></label><label>Course (optional)<input value={course} onChange={(e) => setCourse(e.target.value)} placeholder="CSC-211" /></label><button className="primary">View timetable</button></form>{data?.demo_data && <div className="notice">DEMO DATA - this synthetic timetable is provided only to exercise the completed workflow.</div>}{data && (data.entries.length ? <DataTable columns={['course_code', 'course_title', 'day_of_week', 'starts_at', 'ends_at', 'room', 'instructor']} rows={data.entries.map((r) => ({ ...r, day_of_week: days[r.day_of_week] }))} /> : <Empty text={data.notice} />)}</section>
}

function Policies({ auth }) {
  const [search, setSearch] = useState(''); const [rows, setRows] = useState([]); const [loaded, setLoaded] = useState(false)
  async function load(event) { event?.preventDefault(); setRows(await api(`/policies?search=${encodeURIComponent(search)}`, {}, auth)); setLoaded(true) }
  useEffect(() => { load() }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">POLICIES & GUIDELINES</p><h3>Verified academic rules</h3></div></div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search attendance, FYP, thesis…" /><button className="primary">Search</button></form>{rows.map((r) => <article className="policy-card" key={r.rule_code}><span>{r.category}</span><h3>{r.title}</h3><p>{r.description}</p><small>Effective {r.effective_from} · {r.source?.title}</small></article>)}{loaded && !rows.length && <Empty text="No matching verified policy was found. Contact the department for unpublished guidance." />}</section>
}

function History({ auth }) {
  const [rows, setRows] = useState([]); const [error, setError] = useState(''); const [search, setSearch] = useState('')
  async function load(event) { event?.preventDefault(); try { setRows(await api(`/history?search=${encodeURIComponent(search)}`, {}, auth)) } catch (e) { setError(e.message) } }
  async function clear() { if (!confirm('Delete all of your saved conversations?')) return; await api('/history', { method: 'DELETE' }, auth); setRows([]) }
  useEffect(() => { load() }, [])
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">UC5 · PRIVATE RECORD</p><h3>Query history</h3></div>{rows.length > 0 && <button className="danger" onClick={clear}>Clear history</button>}</div><form className="search-form" onSubmit={load}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search questions, answers, or intents" /><button className="primary">Search history</button></form>{error && <div className="form-error">{error}</div>}{rows.length ? <div className="history-list">{rows.map((r) => <div className={`history-row ${r.role}`} key={r.message_id}><span>{r.role}</span><p>{r.content}</p><small>{r.intent || 'response'} · {new Date(r.created_at).toLocaleString()}</small></div>)}</div> : <Empty text="No matching history. Authenticated conversations are saved here." />}</section>
}

function AdminPortal({ auth, online, onLogout }) {
  const [active, setActive] = useState('Dashboard')
  return <Shell {...{ auth, online, active, setActive, onLogout }}>
    <div className="page-content-wrapper">
      {active === 'Dashboard' ? <AdminDashboard auth={auth} setActive={setActive} /> : active === 'Reports' ? <Reports auth={auth} /> : active === 'Query Logs' ? <QueryLogs auth={auth} /> : active === 'Model' ? <ModelManager auth={auth} /> : active === 'Settings' ? <SettingsManager auth={auth} /> : <AdminRecords auth={auth} module={active} />}
    </div>
  </Shell>
}

const adminConfig = {
  Courses: { path: 'courses', columns: ['code', 'title', 'theory_credit_hours', 'lab_credit_hours', 'active'] },
  Prerequisites: { path: 'prerequisites', columns: ['course_code', 'prerequisite_course_code', 'relation_type', 'minimum_grade', 'verified', 'source_code'] },
  Fees: { path: 'fees', columns: ['program_code', 'official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from'] },
  Timetables: { path: 'timetables', columns: ['offering_id', 'course_code', 'term', 'academic_year', 'day_of_week', 'starts_at', 'room'] },
  Policies: { path: 'policies', columns: ['rule_code', 'category', 'title', 'effective_from', 'active'] },
  Knowledge: { path: 'knowledge', columns: ['title', 'category', 'source_code', 'verification_status', 'chunks', 'processing_status'], noEdit: true },
  Users: { path: 'users', columns: ['full_name', 'email', 'role', 'active', 'last_login_at', 'created_at'] },
}

function AdminDashboard({ auth, setActive }) {
  const [report, setReport] = useState(null); useEffect(() => { api('/admin/report', {}, auth).then(setReport).catch(() => {}) }, [])
  return <div className="page-grid"><section className="welcome-card"><div><p className="eyebrow">ADMIN CONTROL CENTRE</p><h2>Academic data operations</h2><p>Manage source-backed records, student access, query logs, and usage reporting.</p></div></section><div className="stat-grid"><Stat label="Student queries" value={report?.total_messages ?? '—'} note="Recorded messages" /><Stat label="Conversations" value={report?.total_sessions ?? '—'} note="Unique sessions" /><Stat label="Detected intents" value={report?.intents_seen ?? '—'} note="Academic categories" /></div><section className="section-card"><div className="section-heading"><div><p className="eyebrow">USE CASES UC11–UC17</p><h3>Management modules</h3></div></div><div className="module-grid">{Object.keys(adminConfig).map((m) => <button key={m} onClick={() => setActive(m)}><strong>{m}</strong><span>Open module →</span></button>)}</div></section></div>
}

function AdminRecords({ auth, module }) {
  const config = adminConfig[module]; const [rows, setRows] = useState([]); const [error, setError] = useState(''); const [showForm, setShowForm] = useState(false); const [editing, setEditing] = useState(null)
  async function load() { setError(''); try { setRows(await api(`/admin/${config.path}`, {}, auth)) } catch (e) { setError(e.message) } }
  useEffect(() => { load() }, [module])
  async function toggleUser(row) { try { await api(`/admin/users/${row.id}`, { method: 'PATCH', body: JSON.stringify({ active: !row.active }) }, auth); load() } catch (e) { setError(e.message) } }
  async function remove(row) { const id = row.id || row.code; if (!confirm(`Disable/delete ${id}?`)) return; try { await api(`/admin/${config.path}/${encodeURIComponent(id)}`, { method: 'DELETE' }, auth); load() } catch (e) { setError(e.message) } }
  return <section className="section-card full"><div className="section-heading"><div><p className="eyebrow">ADMINISTRATOR ONLY</p><h3>Manage {module.toLowerCase()}</h3></div>{!config.readonly && module !== 'Users' && <button className="primary" onClick={() => setShowForm(!showForm)}>+ Add record</button>}</div>{showForm && <AdminCreateForm module={module} auth={auth} onSaved={() => { setShowForm(false); load() }} />}{editing && <AdminEditForm module={module} row={editing} auth={auth} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}{error && <div className="form-error">{error}</div>}<DataTable columns={config.columns} rows={rows} actions={!config.readonly ? (row) => <div className="row-actions">{!config.noEdit && <button className="small-button" onClick={() => setEditing(row)}>Edit</button>}{module === 'Users' ? <button className="small-button" onClick={() => toggleUser(row)}>{row.active ? 'Disable' : 'Enable'}</button> : <button className="danger small" onClick={() => remove(row)}>{module === 'Courses' || module === 'Policies' ? 'Disable' : 'Delete'}</button>}</div> : null} empty={`No ${module.toLowerCase()} are currently available.`} /></section>
}

function AdminCreateForm({ module, auth, onSaved }) {
  const [values, setValues] = useState({}); const [error, setError] = useState(''); const [sources, setSources] = useState([]); const [offerings, setOfferings] = useState([]); const fields = useMemo(() => ({ Courses: ['code', 'title', 'description', 'theory_credit_hours', 'lab_credit_hours', 'source_id'], Prerequisites: ['course_code', 'prerequisite_course_code', 'curriculum', 'relation_type', 'minimum_grade', 'waiver_condition', 'source_id', 'verified'], Fees: ['program_code', 'official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from', 'source_id'], Timetables: ['offering_id', 'session_type', 'day_of_week', 'starts_at', 'ends_at', 'room', 'lab_group'], Policies: ['rule_code', 'category', 'title', 'description', 'effective_from', 'source_id'], Knowledge: ['source_id', 'title', 'category', 'content'] }[module] || []), [module])
  useEffect(() => { if (fields.includes('source_id')) api('/admin/sources', {}, auth).then(setSources).catch((e) => setError(e.message)); if (fields.includes('offering_id')) api('/admin/offerings', {}, auth).then(setOfferings).catch((e) => setError(e.message)) }, [module])
  async function submit(event) { event.preventDefault(); setError(''); try { const numeric = new Set(['theory_credit_hours', 'lab_credit_hours', 'amount', 'day_of_week']); const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, numeric.has(k) ? Number(v) : k === 'verified' ? v === true || v === 'true' : v])); await api(`/admin/${adminConfig[module].path}`, { method: 'POST', body: JSON.stringify(payload) }, auth); onSaved() } catch (e) { setError(e.message) } }
  return <form className="admin-form" onSubmit={submit}>{fields.map((field) => <label key={field}>{field.replaceAll('_', ' ')}{field === 'source_id' ? <select required value={values[field] || ''} onChange={(e) => setValues({ ...values, [field]: e.target.value })}><option value="">Select source (status is retained)</option>{sources.map((s) => <option key={s.id} value={s.id}>{s.source_code} · {s.verification_status} · {s.title}</option>)}</select> : field === 'offering_id' ? <select required value={values[field] || ''} onChange={(e) => setValues({ ...values, [field]: e.target.value })}><option value="">Select course offering</option>{offerings.map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.term} {o.academic_year} · {o.section}</option>)}</select> : ['session_type', 'relation_type'].includes(field) ? <select required value={values[field] || ''} onChange={(e) => setValues({ ...values, [field]: e.target.value })}><option value="">Select type</option>{field === 'session_type' ? <><option>class</option><option>lab</option><option>tutorial</option></> : <><option>prerequisite</option><option>corequisite</option></>}</select> : field === 'verified' ? <select value={String(values[field] || false)} onChange={(e) => setValues({ ...values, [field]: e.target.value })}><option value="false">Unverified / planning guidance</option><option value="true">Verified published rule</option></select> : ['description', 'content', 'waiver_condition'].includes(field) ? <textarea required={['description', 'content'].includes(field)} value={values[field] || ''} onChange={(e) => setValues({ ...values, [field]: e.target.value })} /> : <input required={!['description', 'lab_group', 'program_code', 'minimum_grade', 'waiver_condition'].includes(field)} placeholder={field === 'curriculum' ? 'Fall 2025 onward' : ''} type={field.includes('date') ? 'date' : field.includes('time') ? 'time' : ['amount', 'day_of_week', 'theory_credit_hours', 'lab_credit_hours'].includes(field) ? 'number' : 'text'} value={values[field] || ''} onChange={(e) => setValues({ ...values, [field]: e.target.value })} />}</label>)}{error && <div className="form-error">{error}</div>}<button className="primary">Save record</button></form>
}

function AdminEditForm({ module, row, auth, onCancel, onSaved }) {
  const fields = { Courses: ['title', 'description', 'theory_credit_hours', 'lab_credit_hours', 'active'], Prerequisites: ['relation_type', 'minimum_grade', 'waiver_condition', 'verified'], Fees: ['official_fee_category', 'shift', 'fee_type', 'amount', 'effective_from', 'effective_to'], Timetables: ['session_type', 'day_of_week', 'starts_at', 'ends_at', 'room', 'lab_group'], Policies: ['category', 'title', 'description', 'effective_from', 'priority', 'active'], Users: ['full_name', 'email', 'role', 'active'] }[module] || []
  const [values, setValues] = useState(Object.fromEntries(fields.map((f) => [f, row[f] ?? '']))); const [error, setError] = useState('')
  async function submit(event) { event.preventDefault(); setError(''); try { const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, ['amount', 'day_of_week', 'theory_credit_hours', 'lab_credit_hours', 'priority'].includes(k) ? Number(v) : ['active', 'verified'].includes(k) ? v === true || v === 'true' : v || null])); await api(`/admin/${adminConfig[module].path}/${encodeURIComponent(row.id || row.code)}`, { method: 'PATCH', body: JSON.stringify(payload) }, auth); onSaved() } catch (e) { setError(e.message) } }
  return <form className="admin-form" onSubmit={submit}><div className="form-title">Editing {row.code || row.email || row.id}</div>{fields.map((field) => <label key={field}>{field.replaceAll('_', ' ')}{['active', 'verified'].includes(field) ? <select value={String(values[field])} onChange={(e) => setValues({ ...values, [field]: e.target.value })}><option value="true">Yes</option><option value="false">No</option></select> : field === 'description' || field === 'waiver_condition' ? <textarea value={values[field]} onChange={(e) => setValues({ ...values, [field]: e.target.value })} /> : <input type={field.includes('date') ? 'date' : field.includes('time') ? 'time' : ['amount', 'day_of_week', 'theory_credit_hours', 'lab_credit_hours', 'priority'].includes(field) ? 'number' : 'text'} value={values[field]} onChange={(e) => setValues({ ...values, [field]: e.target.value })} />}</label>)}{error && <div className="form-error">{error}</div>}<button className="primary">Save changes</button><button type="button" className="secondary" onClick={onCancel}>Cancel</button></form>
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

function DataTable({ columns, rows = [], actions, empty = 'No records found.' }) { if (!rows.length) return <Empty text={empty} />; return <div className="table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c.replaceAll('_', ' ')}</th>)}{actions && <th>Actions</th>}</tr></thead><tbody>{rows.map((row, i) => <tr key={row.id || row.code || i}>{columns.map((c) => <td key={c}>{row[c] == null ? '—' : typeof row[c] === 'boolean' ? (row[c] ? 'Yes' : 'No') : String(row[c])}</td>)}{actions && <td>{actions(row)}</td>}</tr>)}</tbody></table></div> }
function Empty({ text }) { return <div className="empty-state"><span>◇</span><h3>No records to display</h3><p>{text}</p></div> }
function Stat({ label, value, note }) { return <div className="stat-card"><small>{label}</small><strong>{value}</strong><span>{note}</span></div> }

if (document.getElementById('root')) createRoot(document.getElementById('root')).render(<App />)
