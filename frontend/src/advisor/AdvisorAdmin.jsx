import { useCallback, useEffect, useState } from 'react'
import { AdvisorError, advisorRequest } from './advisorApi'
import { TimetableAdmin } from './AdvisorTimetable'
import './advisor-admin.css'

const TOKEN_KEY = 'qau-advisor-admin-token'
const TABS = [['overview', 'Overview'], ['ai', 'AI providers'], ['knowledge', 'Knowledge'], ['timetable', 'Timetable'], ['questions', 'Questions'], ['feedback', 'Feedback'], ['content', 'Notices & rules'], ['account', 'Account']]

/** Calls the engine's admin API. Preference order: (1) the portal admin's own session (single sign-on),
 *  (2) a separate engine-admin login if single sign-on is not configured. */
function useAdmin(portalAuth) {
  const [engineToken, setEngineToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || '')
  const [needsLogin, setNeedsLogin] = useState(false)
  const token = engineToken || portalAuth?.access_token || ''
  const signOut = useCallback(() => { sessionStorage.removeItem(TOKEN_KEY); setEngineToken(''); setNeedsLogin(true) }, [])
  const call = useCallback(async (method, path, body) => {
    try {
      return await advisorRequest(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }, { access_token: token })
    } catch (e) {
      if (e instanceof AdvisorError && e.status === 401) setNeedsLogin(true)
      throw e
    }
  }, [token])
  const signIn = (t) => { sessionStorage.setItem(TOKEN_KEY, t); setEngineToken(t); setNeedsLogin(false) }
  return { token, call, signIn, signOut, needsLogin }
}

function Login({ onSignedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError('')
    try { onSignedIn((await advisorRequest('/admin/login', { method: 'POST', body: JSON.stringify({ username, password }) })).token) }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <form className="card login" onSubmit={submit}>
      <h2>Administrator sign-in</h2>
      <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required /></label>
      <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
      {error && <p className="err" role="alert">{error}</p>}
      <button className="adv-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      <p className="muted">Single sign-on with the portal is not configured, so the chatbot engine needs its own administrator login.</p>
    </form>
  )
}

function Stat({ label, value, sub }) {
  return <div className="stat"><div className="stat-v">{value ?? '—'}</div><div className="stat-l">{label}</div>{sub && <div className="stat-s">{sub}</div>}</div>
}

function Overview({ call }) {
  const [days, setDays] = useState(7)
  const [s, setS] = useState(null)
  useEffect(() => { call('GET', `/admin/stats?days=${days}`).then(setS).catch(() => {}) }, [call, days])
  if (!s) return <p className="muted">Loading…</p>
  const o = s.outcomes
  const answered = (o.answered || 0) + (o.cached || 0)
  const max = Math.max(1, ...s.daily.map((d) => d.n))
  return (
    <div>
      <div className="row"><label>Period <select value={days} onChange={(e) => setDays(+e.target.value)}>{[1, 7, 30, 90].map((d) => <option key={d} value={d}>{d} day{d > 1 ? 's' : ''}</option>)}</select></label></div>
      <div className="stats">
        <Stat label="Questions" value={s.total} />
        <Stat label="Answered" value={answered} sub={s.total ? `${Math.round((100 * answered) / s.total)}%` : ''} />
        <Stat label="Couldn't find" value={o.abstained || 0} sub="see Questions tab" />
        <Stat label="Median speed" value={s.latency_ms.p50 ? `${(s.latency_ms.p50 / 1000).toFixed(1)}s` : '—'} sub={s.latency_ms.p95 ? `p95 ${(s.latency_ms.p95 / 1000).toFixed(1)}s` : ''} />
        <Stat label="👍 / 👎" value={`${s.feedback.up} / ${s.feedback.down}`} />
        <Stat label="Errors" value={(o.error || 0) + (o.degraded || 0)} sub="incl. fallback answers" />
      </div>
      <div className="grid2">
        <div className="card"><h3>Questions per day</h3>
          <div className="bars">{s.daily.map((d) => <div key={d.day} className="bar" title={`${d.day}: ${d.n}`}><i style={{ height: `${(100 * d.n) / max}%` }} /><span>{d.day.slice(5)}</span></div>)}</div>
        </div>
        <div className="card"><h3>Answered by</h3>
          <ul className="kv">{Object.entries(s.providers).map(([k, v]) => <li key={k}><b>{k}</b><span>{v}</span></li>)}</ul>
          <h3>Languages</h3>
          <ul className="kv">{Object.entries(s.languages).map(([k, v]) => <li key={k}><b>{k}</b><span>{v}</span></li>)}</ul>
        </div>
      </div>
    </div>
  )
}

function Field({ spec, value, onChange }) {
  const id = `f-${spec.key}`
  if (spec.type === 'bool') return <label className="adv-check"><input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} /> {spec.label}</label>
  if (spec.type === 'choice') return <label>{spec.label}<select value={value} onChange={(e) => onChange(e.target.value)}>{spec.choices.map((c) => <option key={c}>{c}</option>)}</select></label>
  if (spec.type === 'text') return <label>{spec.label}<textarea id={id} rows={4} value={value ?? ''} onChange={(e) => onChange(e.target.value)} /></label>
  if (spec.type === 'int' || spec.type === 'float') return <label>{spec.label}<input id={id} type="number" step={spec.type === 'float' ? '0.05' : '1'} min={spec.min ?? undefined} max={spec.max ?? undefined} value={value ?? ''} onChange={(e) => onChange(e.target.value)} /></label>
  return <label>{spec.label}<input id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value)} /></label>
}

function SettingsForm({ call, group, title, children }) {
  const [specs, setSpecs] = useState([])
  const [draft, setDraft] = useState({})
  const [msg, setMsg] = useState('')
  const load = useCallback(() => call('GET', '/admin/settings').then((r) => { setSpecs(r.settings.filter((s) => s.group === group)); setDraft({}) }), [call, group])
  useEffect(() => { load() }, [load])
  const save = async () => {
    setMsg('')
    try { await call('PUT', '/admin/settings', { values: draft }); setMsg('Saved.'); load() } catch (e) { setMsg(e.message) }
  }
  const clearSecret = async (key) => { await call('PUT', '/admin/settings', { values: {}, clear: [key] }); load() }
  return (
    <div className="card">
      <h3>{title}</h3>
      {specs.map((s) => (
        <div key={s.key} className="field">
          {s.secret ? (
            <label>{s.label}
              <input type="password" autoComplete="off" placeholder={s.configured ? `Saved (${s.hint}) — type to replace` : 'Paste key…'}
                value={draft[s.key] ?? ''} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} />
              {s.configured && <button type="button" className="link" onClick={() => clearSecret(s.key)}>Remove saved key</button>}
            </label>
          ) : <Field spec={s} value={s.key in draft ? draft[s.key] : s.value} onChange={(v) => setDraft({ ...draft, [s.key]: v })} />}
          {s.help && <small>{s.help}</small>}
        </div>
      ))}
      {children}
      <div className="row"><button className="adv-primary" onClick={save} disabled={!Object.keys(draft).length}>Save changes</button>{msg && <span className="muted">{msg}</span>}</div>
    </div>
  )
}

function Providers({ call }) {
  const [list, setList] = useState([])
  const [verify, setVerify] = useState(null)
  const [test, setTest] = useState(null)
  const [busy, setBusy] = useState('')
  const [keyDraft, setKeyDraft] = useState('')
  const refresh = useCallback(() => call('GET', '/admin/providers').then((r) => setList(r.providers)).catch(() => {}), [call])
  useEffect(() => { refresh() }, [refresh])
  const doVerify = async () => {
    setBusy('verify'); setVerify(null)
    try { setVerify(await call('POST', '/admin/providers/gemini/verify', { api_key: keyDraft || null })) } catch (e) { setVerify({ ok: false, detail: e.message }) } finally { setBusy('') }
  }
  const doTest = async () => { setBusy('test'); setTest(null); try { setTest(await call('POST', '/admin/providers/test')) } finally { setBusy(''); refresh() } }
  return (
    <div>
      <div className="grid2">
        {list.map((p) => (
          <div key={p.name} className={`card prov ${p.healthy ? 'ok' : 'bad'}`}>
            <h3>{p.name === 'gemini' ? 'Google Gemini' : 'Ollama (local)'} <span className={`pill ${p.healthy ? 'ok' : 'bad'}`}>{p.healthy ? 'ready' : p.configured ? 'problem' : 'not set up'}</span></h3>
            <p className="muted">Model: <b>{p.model}</b></p>
            <p>{p.detail}</p>
            {p.stats?.ok !== undefined && <p className="muted">{p.stats.ok} ok · {p.stats.failed} failed{p.stats.paused ? ' · paused after errors' : ''}{p.stats.p50_ms ? ` · median ${(p.stats.p50_ms / 1000).toFixed(1)}s` : ''}</p>}
            {p.stats?.last_error && <p className="err small">Last error: {p.stats.last_error}</p>}
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Check a Gemini key</h3>
        <p className="muted">Paste a key to test it before saving, or leave blank to test the saved key.</p>
        <div className="row"><input type="password" autoComplete="off" placeholder="AIza…" value={keyDraft} onChange={(e) => setKeyDraft(e.target.value)} /><button onClick={doVerify} disabled={busy === 'verify'}>{busy === 'verify' ? 'Checking…' : 'Check key'}</button></div>
        {verify && <p className={verify.ok ? 'okmsg' : 'err'}>{verify.ok ? `Key works. ${verify.models.length} models available.` : verify.detail}</p>}
        {verify?.models?.length > 0 && <details><summary>Available models</summary><p className="models">{verify.models.join(' · ')}</p></details>}
      </div>
      <SettingsForm call={call} group="ai" title="AI settings" />
      <div className="card">
        <h3>Live test</h3>
        <p className="muted">Sends a tiny request through the configured providers in order, exactly as a student's question would be routed.</p>
        <button onClick={doTest} disabled={busy === 'test'}>{busy === 'test' ? 'Testing…' : 'Run test'}</button>
        {test && <ul className="kv">{test.results.map((r) => <li key={r.provider}><b>{r.provider} · {r.model}</b><span>{r.ok ? `✓ ${r.ms} ms` : `✗ ${r.error}`}</span></li>)}{test.active && <li><b>Answering provider</b><span>{test.active}</span></li>}</ul>}
      </div>
    </div>
  )
}

function Knowledge({ call }) {
  const [k, setK] = useState(null)
  const [msg, setMsg] = useState('')
  const load = useCallback(() => call('GET', '/admin/knowledge').then(setK).catch(() => {}), [call])
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t) }, [load])
  if (!k) return <p className="muted">Loading…</p>
  const running = k.jobs.find((j) => j.status === 'running')
  const refresh = async (crawl) => { setMsg(''); try { await call('POST', '/admin/knowledge/refresh', { crawl }); load() } catch (e) { setMsg(e.message) } }
  const rollback = async (id) => { if (confirm(`Switch the live index to ${id}?`)) { await call('POST', '/admin/knowledge/rollback', { build_id: id }); load() } }
  return (
    <div>
      <div className="card">
        <h3>Live index</h3>
        {k.info.ready ? <ul className="kv"><li><b>Build</b><span>{k.info.build_id}</span></li><li><b>Passages</b><span>{k.info.chunks}</span></li><li><b>Embedding model</b><span>{k.info.embedding_model}</span></li><li><b>Re-ranker</b><span>{k.info.reranker || 'off'}</span></li></ul> : <p className="err">No index loaded.</p>}
        <div className="row">
          <button className="adv-primary" onClick={() => refresh(true)} disabled={!!running}>{running ? 'Refresh running…' : 'Re-crawl website & rebuild'}</button>
          <button onClick={() => refresh(false)} disabled={!!running}>Rebuild only</button>
          {msg && <span className="err">{msg}</span>}
        </div>
        {running && <p className="muted">{running.detail}</p>}
        <p className="muted">A refresh downloads the department website and linked PDFs, builds a new index, and switches to it only if it succeeds. The previous index stays available for rollback.</p>
      </div>
      <div className="card"><h3>Recent refreshes</h3>
        <ul className="kv">{k.jobs.map((j) => <li key={j.id}><b>#{j.id} · {j.status}</b><span>{j.started_at.replace('T', ' ').slice(0, 16)}</span></li>)}</ul>
        <h3>Index versions</h3>
        <ul className="kv">{k.builds.map((b) => <li key={b}><b>{b}{b === k.info.build_id ? ' (live)' : ''}</b>{b !== k.info.build_id && <button className="link" onClick={() => rollback(b)}>Switch to this</button>}</li>)}</ul>
      </div>
      <DepartmentDocuments call={call} />
      <PrerequisiteData call={call} />
      <div className="card"><h3>Indexed sources ({k.documents.length})</h3>
        <div className="adv-table-wrap"><table><thead><tr><th>Type</th><th>Source</th><th>Passages</th></tr></thead>
          <tbody>{k.documents.map((d) => <tr key={d.url}><td>{d.kind}</td><td>{/^https?:/.test(d.url) ? <a href={d.url} target="_blank" rel="noopener noreferrer">{d.title || d.url}</a> : (d.title || d.url)}</td><td>{d.chunks}</td></tr>)}</tbody></table></div>
      </div>
    </div>
  )
}

function PrerequisiteData({ call }) {
  const [info, setInfo] = useState(null)
  const [msg, setMsg] = useState('')
  const load = useCallback(() => call('GET', '/admin/prerequisites').then(setInfo).catch(() => {}), [call])
  useEffect(() => { load() }, [load])
  const upload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setMsg('')
    try {
      const content = JSON.parse(await file.text())
      const r = await call('POST', '/admin/prerequisites', { filename: file.name, content })
      setMsg(`Saved ${r.saved} (${r.stats.prerequisite_rows} prerequisite rows). Press "Rebuild only" above to apply it.`)
      load()
    } catch (err) {
      const d = err.message
      setMsg(typeof d === 'string' ? d : 'Upload failed')
    }
  }
  const remove = async (name) => { if (confirm(`Remove ${name}?`)) { await call('DELETE', `/admin/prerequisites/${name}`); load() } }
  if (!info) return null
  return (
    <div className="card"><h3>Prerequisite data</h3>
      <p className="muted">Official prerequisite lists (JSON in the agreed format) are used to calculate chains such as PSP → OOP → Data Structures. Every row is checked on upload; when the original document is stored next to the file, each quoted line is also checked against it.</p>
      {info.live && <p>Live graph: <b>{info.live.courses}</b> courses, <b>{info.live.edges}</b> prerequisite links from: {info.live.sources.join('; ')}</p>}
      <ul className="kv">{info.files.map((f) => (
        <li key={f.name}><b>{f.name}{f.bundled ? ' (built in)' : ''}</b>
          <span>{f.stats.prerequisite_rows} rows · {f.stats.quotes_checked_against_source ? 'verified against source document' : 'format check only'}
            {f.errors.length ? ` · ${f.errors.length} errors` : ''}{!f.bundled && <> · <button className="link" onClick={() => remove(f.name)}>remove</button></>}</span></li>
      ))}</ul>
      <label>Add a prerequisite file (.json)<input type="file" accept="application/json,.json" onChange={upload} /></label>
      {msg && <p className={msg.startsWith('Saved') ? 'okmsg' : 'err'}>{msg}</p>}
      {info.conflicts.length > 0 && (<details open><summary>{info.conflicts.length} places where the sources disagree</summary>
        <ul className="kv">{info.conflicts.map((c) => (<li key={c.course}><b>{c.course}</b><span>{Object.entries(c.lists).map(([k, v]) => `${k}: ${v.join(', ')}`).join(' | ')}{c.silent_in.length ? ` | silent in: ${c.silent_in.join(', ')}` : ''}</span></li>))}</ul></details>)}
    </div>
  )
}

function DepartmentDocuments({ call }) {
  const [docs, setDocs] = useState([])
  const [form, setForm] = useState({ title: '', note: '', effective: '' })
  const [msg, setMsg] = useState('')
  const load = useCallback(() => call('GET', '/admin/documents').then((r) => setDocs(r.documents)).catch(() => {}), [call])
  useEffect(() => { load() }, [load])
  const toBase64 = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
  const upload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setMsg('')
    try {
      const r = await call('POST', '/admin/documents', {
        filename: file.name, content_base64: await toBase64(file),
        title: form.title || null, note: form.note || null, effective: form.effective || null,
      })
      setMsg(`Saved ${r.saved}. Press "Rebuild only" above to apply it.`)
      setForm({ title: '', note: '', effective: '' })
      load()
    } catch (err) { setMsg(err.message) }
  }
  const remove = async (name) => { if (confirm(`Remove ${name}?`)) { await call('DELETE', `/admin/documents/${encodeURIComponent(name)}`); load() } }
  return (
    <div className="card"><h3>Department documents (not on the website)</h3>
      <p className="muted">Add official files such as FYP submission rules, SOPs or circulars (PDF, Word, text). They are used as official sources and cited by title.</p>
      <ul className="kv">{docs.map((d) => (<li key={d.name}><b>{d.title || d.name}</b><span>{d.name} · {Math.round(d.size / 1024)} KB{d.effective ? ` · ${d.effective}` : ''} · <button className="link" onClick={() => remove(d.name)}>remove</button></span></li>))}
        {!docs.length && <li className="muted">No documents added yet.</li>}</ul>
      <div className="grid2">
        <label>Title (shown in citations)<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. BS Final Year Project submission rules" /></label>
        <label>Effective from (optional)<input value={form.effective} onChange={(e) => setForm({ ...form, effective: e.target.value })} placeholder="e.g. Fall 2026 onwards" /></label>
      </div>
      <label>Note for students (optional)<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="e.g. Approved by the Board of Studies, Aug 2026" /></label>
      <label>Choose file<input type="file" accept=".pdf,.docx,.txt,.md" onChange={upload} /></label>
      {msg && <p className={msg.startsWith('Saved') ? 'okmsg' : 'err'}>{msg}</p>}
    </div>
  )
}

function Questions({ call }) {
  const [outcome, setOutcome] = useState('abstained')
  const [rows, setRows] = useState([])
  useEffect(() => { call('GET', `/admin/questions?outcome=${outcome}&limit=200`).then((r) => setRows(r.questions)).catch(() => {}) }, [call, outcome])
  return (
    <div className="card">
      <div className="row"><label>Show <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
        {[['abstained', "Couldn't find an answer"], ['', 'All'], ['answered', 'Answered'], ['degraded', 'Fallback (no AI)'], ['error', 'Errors'], ['cached', 'Cached']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label></div>
      <p className="muted">Questions the assistant couldn't answer show where the website or documents are missing information.</p>
      <div className="adv-table-wrap"><table><thead><tr><th>When</th><th>Question</th><th>Lang</th><th>Outcome</th><th>By</th><th>ms</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id}><td>{r.created_at.replace('T', ' ').slice(5, 16)}</td><td dir="auto">{r.question}</td><td>{r.language}</td><td>{r.outcome}</td><td>{r.provider}</td><td>{r.latency_ms}</td></tr>)}</tbody></table></div>
    </div>
  )
}

function Feedback({ call }) {
  const [rows, setRows] = useState([])
  useEffect(() => { call('GET', '/admin/feedback?limit=200').then((r) => setRows(r.feedback)).catch(() => {}) }, [call])
  return (
    <div className="card"><h3>Student feedback</h3>
      {!rows.length && <p className="muted">No feedback yet.</p>}
      {rows.map((r) => (
        <div key={r.id} className={`fb ${r.rating < 0 ? 'neg' : 'pos'}`}>
          <b>{r.rating < 0 ? '👎' : '👍'} {r.created_at.replace('T', ' ').slice(0, 16)}</b>
          <div dir="auto"><em>Q:</em> {r.question}</div>
          <div dir="auto" className="ans"><em>A:</em> {r.answer}</div>
          {r.comment && <div className="comment">“{r.comment}”</div>}
        </div>
      ))}
    </div>
  )
}

function Account({ call, signOut }) {
  const [cur, setCur] = useState(''); const [nw, setNw] = useState(''); const [msg, setMsg] = useState('')
  const change = async (e) => {
    e.preventDefault(); setMsg('')
    try { await call('POST', '/admin/password', { current_password: cur, new_password: nw }); signOut() } catch (err) { setMsg(err.message) }
  }
  return (
    <form className="card login" onSubmit={change}>
      <h3>Change password</h3>
      <label>Current password<input type="password" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" required /></label>
      <label>New password (10+ characters)<input type="password" value={nw} minLength={10} onChange={(e) => setNw(e.target.value)} autoComplete="new-password" required /></label>
      {msg && <p className="err">{msg}</p>}
      <button className="adv-primary">Change password</button>
      <p className="muted">You'll be signed out on all devices.</p>
    </form>
  )
}

export function AdvisorAdmin({ auth }) {
  const { call, signIn, signOut, needsLogin, token } = useAdmin(auth)
  const [tab, setTab] = useState('overview')
  const [checked, setChecked] = useState(false)
  useEffect(() => { call('GET', '/admin/me').catch(() => {}).finally(() => setChecked(true)) }, [call])
  if (!checked) return <div className="advisor-admin"><p className="muted">Connecting to the chatbot engine…</p></div>
  if (needsLogin || !token) return <div className="advisor-admin"><Login onSignedIn={signIn} /></div>
  return (
    <div className="advisor-admin">
      <nav className="tabs" role="tablist">{TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>{label}</button>)}</nav>
      <section className="panel">
        {tab === 'overview' && <Overview call={call} />}
        {tab === 'ai' && <Providers call={call} />}
        {tab === 'knowledge' && <Knowledge call={call} />}
        {tab === 'timetable' && <TimetableAdmin call={call} />}
        {tab === 'questions' && <Questions call={call} />}
        {tab === 'feedback' && <Feedback call={call} />}
        {tab === 'content' && <div><SettingsForm call={call} group="content" title="Notice & assistant guidance" /><SettingsForm call={call} group="retrieval" title="Retrieval" /><SettingsForm call={call} group="operations" title="Operations" /></div>}
        {tab === 'account' && <Account call={call} signOut={signOut} />}
      </section>
    </div>
  )
}
