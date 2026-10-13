import React, { useEffect, useState } from 'react'
import './timetable.css'

const BASE = '/api/v3/admin/timetables'
const PROGRAMMES = ['BSCS', 'MPhil', 'PhD', 'MS-DS', 'MS-IST', 'deficiency']

export function TimetableManagement({ auth }) {
  const [versions, setVersions] = useState([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [pdf, setPdf] = useState('')
  const [page, setPage] = useState(1)
  const [pageImage, setPageImage] = useState('')
  const [reviewed, setReviewed] = useState([])
  const [complete, setComplete] = useState(false)
  const [reason, setReason] = useState('')
  const [editing, setEditing] = useState(null)
  const [filters, setFilters] = useState({ programme: '', semester: '', section: '', room: '', teacher: '', weekday: '' })
  const [meta, setMeta] = useState({ department: 'CS', campus: 'QAU', academic_term: 'Spring 2026', kind: 'classes', programmes: ['BSCS', 'MPhil', 'PhD', 'MS-DS', 'deficiency'], time_zone: 'Asia/Karachi', effective_from: '2026-04-20', effective_until: null, origin: 'admin provided' })
  const headers = { Authorization: `Bearer ${auth?.access_token || ''}` }

  async function request(path, options = {}) {
    const response = await fetch(BASE + path, { ...options, headers: { ...headers, ...(options.body && !(options.body instanceof File) ? { 'Content-Type': 'application/json' } : {}), ...options.headers } })
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
    return data
  }
  async function load(id = selected) {
    const list = await request('/versions'); setVersions(list)
    if (id) setDetail(await request(`/versions/${id}`))
  }
  useEffect(() => { load().catch(e => setError(e.message)) }, [])
  useEffect(() => {
    setDetail(null); setReviewed([]); setComplete(false); setPage(1)
    if (selected) load(selected).catch(e => setError(e.message))
  }, [selected])
  useEffect(() => {
    if (!selected || !['queued', 'parsing'].includes(detail?.status)) return
    const timer = setInterval(() => load(selected).catch(e => setError(e.message)), 1500)
    return () => clearInterval(timer)
  }, [selected, detail?.status])
  useEffect(() => {
    if (!selected) return
    let disposed = false, url
    fetch(`${BASE}/versions/${selected}/pdf`, { headers }).then(r => { if (!r.ok) throw new Error('PDF unavailable'); return r.blob() }).then(blob => { url = URL.createObjectURL(blob); if (!disposed) setPdf(url) }).catch(e => setError(e.message))
    return () => { disposed = true; if (url) URL.revokeObjectURL(url); setPdf('') }
  }, [selected])
  useEffect(() => {
    if (!selected) return
    let disposed = false, url
    fetch(`${BASE}/versions/${selected}/pages/${page}`, { headers }).then(r => { if (!r.ok) throw new Error('Page preview unavailable'); return r.blob() }).then(blob => { url = URL.createObjectURL(blob); if (!disposed) setPageImage(url) }).catch(e => setError(e.message))
    return () => { disposed = true; if (url) URL.revokeObjectURL(url) }
  }, [selected, page])

  async function action(work) {
    setError(''); setNotice(''); setBusy(true)
    try { await work(); await load(); } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function upload(event) {
    event.preventDefault()
    const file = new FormData(event.currentTarget).get('pdf')
    if (!(file instanceof File) || !file.size) { setError('Choose a PDF'); return }
    await action(async () => {
      const result = await request('/versions', { method: 'POST', body: file, headers: { 'Content-Type': 'application/pdf', 'X-Filename': encodeURIComponent(file.name), 'X-Timetable-Metadata': encodeURIComponent(JSON.stringify(meta)) } })
      setSelected(result.version_id); setNotice(result.created ? 'Uploaded. Extraction started automatically.' : 'This PDF already exists in the same scope.')
    })
  }
  async function resolve(issue) {
    const note = window.prompt('What did you verify or correct against the PDF?')
    if (!note) return
    await action(() => request(`/versions/${selected}/issues/${issue.id}/resolve`, { method: 'POST', body: JSON.stringify({ expected_revision: detail.revision, reason: note }) }))
  }
  async function saveEdit(event) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const changes = { class_kind: values.get('class_kind'), start_time: values.get('start_time'), end_time: values.get('end_time'), room: values.get('room'), mode: values.get('mode'), omitted: values.get('omitted') === 'on' }
    if (values.get('annotation')) {
      try { changes.source_annotation = { page: Number(values.get('annotation_page')), bbox: JSON.parse(values.get('annotation_bbox')), raw: values.get('annotation') } }
      catch { setError('Use four numeric annotation coordinates as JSON: [x0, top, x1, bottom]'); return }
    }
    const offerings = values.getAll('offerings')
    if (offerings.length) changes.offering_ids = offerings
    await action(async () => {
      await request(`/versions/${selected}/meetings/${editing.id}`, { method: 'PATCH', body: JSON.stringify({ expected_revision: detail.revision, reason: values.get('reason'), changes }) }); setEditing(null)
    })
  }
  async function correctOffering(offering) {
    const initial = { title: offering.title, programme: offering.programme, semester: offering.semester, section: offering.section, aliases: JSON.parse(offering.aliases), teachers: offering.teachers }
    const entered = window.prompt('Correct these printed legend fields as JSON. Keep faculty/TA roles separate.', JSON.stringify(initial, null, 2))
    if (!entered) return
    const note = window.prompt('What did you verify against the original legend?')
    if (!note) return
    await action(() => request(`/versions/${selected}/offerings/${offering.id}`, { method: 'PATCH', body: JSON.stringify({ expected_revision: detail.revision, reason: note, changes: JSON.parse(entered) }) }))
  }
  async function publish(rollback = false) {
    await action(async () => {
      await request(`/versions/${selected}/${rollback ? 'rollback' : 'publish'}`, { method: 'POST', body: JSON.stringify({ expected_revision: detail.revision, expected_active_version: detail.active_version, reviewed_pages: reviewed, confirm_complete: complete, reason }) }); setNotice(rollback ? 'Previous timetable restored in the V3 preview.' : 'Published to the V3 preview. Subsequent questions read this version.')
    })
  }
  const filtered = (detail?.meetings || []).filter(m => (!filters.weekday || m.weekday.toLowerCase() === filters.weekday.toLowerCase()) && (!filters.room || m.room === filters.room) && m.courses.some(c => (!filters.programme || c.programme === filters.programme) && (!filters.semester || String(c.semester) === filters.semester) && (!filters.section || c.section === filters.section) && (!filters.teacher || detail.offerings.find(o => o.id === c.offering_id)?.teachers.some(t => t.name.toLowerCase().includes(filters.teacher.toLowerCase())))))
  const unresolved = detail?.issues.filter(i => !i.resolution) || []
  if (auth?.user?.role !== 'admin') return <p role="alert">Administrator access required.</p>
  return <div className="tt-manager">
    <p>V3 preview · Uploads stay staged until reviewed and published. Active versions are separate from the administrator-confirmed current academic term.</p>
    {error && <p role="alert" className="form-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form className="tt-upload" onSubmit={upload}>
      <h2>Upload timetable (PDF)</h2>
      <label>Original PDF<input required name="pdf" type="file" accept="application/pdf,.pdf" /></label>
      {['department', 'campus', 'academic_term', 'effective_from', 'effective_until'].map(key => <label key={key}>{key.replaceAll('_', ' ')}<input required={key !== 'effective_until'} type={key.includes('effective') ? 'date' : 'text'} value={meta[key] || ''} onChange={e => setMeta({ ...meta, [key]: e.target.value || null })} /></label>)}
      <label>Kind<select value={meta.kind} onChange={e => setMeta({ ...meta, kind: e.target.value })}><option value="classes">Classes</option><option value="exams">Exams</option></select></label>
      <label>Source status<select value={meta.origin} onChange={e => setMeta({ ...meta, origin: e.target.value })}><option>admin provided</option><option>official URL</option></select></label>
      {meta.origin === 'official URL' && <label>Official URL<input type="url" required value={meta.source_url || ''} onChange={e => setMeta({ ...meta, source_url: e.target.value })} /></label>}
      <fieldset><legend>Programme ownership of this upload</legend>{PROGRAMMES.map(p => <label key={p}><input type="checkbox" checked={meta.programmes.includes(p)} onChange={e => setMeta({ ...meta, programmes: e.target.checked ? [...meta.programmes, p] : meta.programmes.filter(x => x !== p) })} />{p}</label>)}</fieldset>
      <button disabled={busy}>Upload and extract</button>
    </form>
    <details><summary>Confirm current academic term</summary><form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); action(() => request('/current-term', { method: 'POST', body: JSON.stringify(Object.fromEntries(f)) })) }}><p>Set only from authorized academic calendar information. Spring 2026 is historical in October 2026.</p>{['department', 'campus', 'academic_term', 'valid_from', 'valid_until', 'reason'].map(k => <label key={k}>{k.replaceAll('_', ' ')}<input name={k} required type={k.startsWith('valid') ? 'date' : 'text'} defaultValue={k === 'department' ? 'CS' : k === 'campus' ? 'QAU' : ''} /></label>)}<button disabled={busy}>Confirm term and date interval</button></form></details>
    <label>Uploaded versions<select aria-label="Uploaded versions" value={selected} onChange={e => setSelected(e.target.value)}><option value="">Choose an upload</option>{versions.map(v => <option key={v.id} value={v.id}>{v.metadata.academic_term} · {v.status} · {v.meeting_count} meetings · {v.filename} · {v.id.slice(0, 8)}</option>)}</select></label>
    {detail && <>
      <h2>{detail.metadata.academic_term} · {detail.status} · {detail.meetings.length} extracted meetings · {unresolved.length} unresolved flags</h2>
      <p>{detail.extraction?.error || detail.extraction?.title} · Effective {detail.metadata.effective_from} · Revision {detail.revision}</p>
      <div className="tt-split"><div className="tt-source">
        <label>Source page<select aria-label="Source page" value={page} onChange={e => setPage(Number(e.target.value))}>{Array.from({ length: detail.pages }, (_, i) => <option key={i}>{i + 1}</option>)}</select></label>
        {pageImage && <a href={pageImage} target="_blank" rel="noreferrer"><img src={pageImage} alt={`Original timetable page ${page}`} /></a>}
        {pdf && <a href={`${pdf}#page=${page}`} target="_blank" rel="noreferrer">Open original PDF</a>}
      </div><div className="tt-records">
        <div className="tt-filters">{['programme', 'semester', 'section', 'room', 'teacher', 'weekday'].map(k => <label key={k}>Filter {k}<input aria-label={`Filter ${k}`} value={filters[k]} onChange={e => setFilters({ ...filters, [k]: e.target.value })} placeholder={k === 'section' ? 'regular / self support' : ''} /></label>)}</div>
        <p>{filtered.filter(m => !m.omitted).length} visible meetings. Click a row to inspect its source page.</p>
        <table><thead><tr><th>Day/time</th><th>Course / group / teachers</th><th>Venue/source</th><th>Review</th></tr></thead><tbody>{filtered.map(m => <tr key={m.id} className={m.omitted ? 'tt-omitted' : ''} onClick={() => setPage(m.page)}><td>{m.weekday}<br />{m.start_time}–{m.end_time}<br />{m.time_source}</td><td>{m.courses.map((c, i) => <div key={i}>{c.code} {c.title}<br /><small>{c.programme || 'Unresolved'} / {c.semester || '?'} / {c.section || '?'} · {detail.offerings.find(o => o.id === c.offering_id)?.teachers.map(t => t.name).join('; ')}</small></div>)}</td><td>{m.mode === 'online' ? 'Online' : m.room}<br />PDF p. {m.page}<details><summary>Raw cell / coordinates</summary>{m.raw}<pre>{JSON.stringify(m.provenance, null, 2)}</pre></details></td><td>{detail.status === 'review' && <button onClick={() => { setEditing(m); setPage(m.page) }}>Correct / link</button>}{detail.issues.filter(i => i.meeting_id === m.id && !i.resolution).map(i => <small key={i.id}>{i.kind.replaceAll('_', ' ')}</small>)}</td></tr>)}</tbody></table>
      </div></div>
      {editing && <form className="tt-edit" onSubmit={saveEdit}><h3>Correct extracted meeting</h3><pre>{editing.raw}</pre>{['start_time', 'end_time', 'room'].map(k => <label key={k}>{k}<input required name={k} type={k.includes('time') ? 'time' : 'text'} defaultValue={editing[k]} /></label>)}<label>Mode<select name="mode" defaultValue={editing.mode}><option>physical</option><option>online</option></select></label><label>Class kind<select name="class_kind" defaultValue={editing.class_kind}><option>unknown</option><option>lecture</option><option>lab</option></select></label><label>Printed correction annotation (optional)<input name="annotation" /></label><label>Annotation page<input name="annotation_page" type="number" min="1" max={detail.pages} defaultValue={editing.page} /></label><label>Annotation bounding box [x0, top, x1, bottom]<input name="annotation_bbox" defaultValue={JSON.stringify(editing.bbox)} /></label><label>Verified legend offering(s)<select multiple name="offerings" defaultValue={editing.courses.map(c => c.offering_id).filter(Boolean)}>{detail.offerings.map(o => <option key={o.id} value={o.id}>{o.code} · {o.programme} / {o.semester} / {o.section} · {o.title}</option>)}</select></label><label><input name="omitted" type="checkbox" defaultChecked={!!editing.omitted} />Omit erroneous extracted meeting (retain audit)</label><label>Correction reason<input name="reason" required minLength={5} /></label><button disabled={busy}>Save correction</button><button type="button" onClick={() => setEditing(null)}>Cancel</button></form>}
      <details open={unresolved.length > 0}><summary>Extraction issues ({unresolved.length} unresolved)</summary>{detail.issues.map(i => <div key={i.id} className="tt-issue"><strong>{i.kind.replaceAll('_', ' ')}</strong><p>{i.detail}</p>{i.resolution ? <small>Verified by {i.resolved_by}: {i.resolution}</small> : <button disabled={busy || detail.status !== 'review'} onClick={() => resolve(i)}>Record verification / resolution</button>}</div>)}</details>
      <details><summary>Course and faculty legend ({detail.offerings.length})</summary><table><thead><tr><th>Course</th><th>Programme / semester / section</th><th>Printed instructors / TA</th><th>Source / correction</th></tr></thead><tbody>{detail.offerings.map(o => <tr key={o.id}><td>{o.code} {o.title}</td><td>{o.programme} / {o.semester || '?'} / {o.section}</td><td>{o.teachers.map(t => <div key={t.name}>{t.role}: {t.name}</div>)}</td><td><button onClick={() => setPage(JSON.parse(o.provenance).page)}>Show legend page</button>{detail.status === 'review' && <button onClick={() => correctOffering(o)}>Correct legend</button>}</td></tr>)}</tbody></table></details>
      <details><summary>Diff from active version · {detail.diff.added.length} added / {detail.diff.removed.length} removed mappings</summary><pre>{JSON.stringify(detail.diff, null, 2)}</pre></details>
      <div className="tt-publish"><h3>Verify and publish to the V3 preview</h3>{Array.from({ length: detail.pages }, (_, i) => i + 1).map(p => <label key={p}><input type="checkbox" checked={reviewed.includes(p)} onChange={e => setReviewed(e.target.checked ? [...reviewed, p] : reviewed.filter(x => x !== p))} />I inspected page {p}</label>)}<label><input type="checkbox" checked={complete} onChange={e => setComplete(e.target.checked)} />I verified the complete schedule, ownership, legend and diff</label><label>Publication / rollback reason<input value={reason} minLength={5} onChange={e => setReason(e.target.value)} /></label><button disabled={busy || unresolved.length > 0 || !complete || reviewed.length !== detail.pages || reason.length < 5 || !['review', 'archived'].includes(detail.status)} onClick={() => publish(detail.status === 'archived')}>{detail.status === 'archived' ? 'Rollback to this version' : 'Publish this version'}</button><button disabled={busy || !['review', 'failed'].includes(detail.status)} onClick={() => { const note = window.prompt('Why re-extract? Corrections will be preserved in the audit.'); if (note) action(() => request(`/versions/${selected}/reextract`, { method: 'POST', body: JSON.stringify({ expected_revision: detail.revision, reason: note }) })) }}>Re-extract draft</button></div>
      <details><summary>Audit history</summary><pre>{JSON.stringify(detail.audit, null, 2)}</pre></details>
    </>}
  </div>
}
