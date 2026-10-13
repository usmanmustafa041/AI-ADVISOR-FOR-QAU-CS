import { useCallback, useEffect, useMemo, useState } from 'react'

// Admin → Chatbot Engine → Timetable. Lets the department correct or fully enter the timetable by hand.
// The PDF-derived data is never modified: edits are stored separately and merged when students ask.

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
const dayLabel = (d) => d.charAt(0) + d.slice(1).toLowerCase()
const SECTIONS = [['', 'Not specified'], ['R', 'Regular (morning)'], ['S', 'Self-support (evening)'], ['RS', 'Both sections'], ['Rep', 'Repeaters']]
const PROGRAMS = ['BS', 'MS-DS', 'MS-IST', 'MPhil/PhD', 'Deficiency']
const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
const MODES = [
  ['pdf_plus_edits', 'PDF + my edits', 'Uses the department\'s timetable PDF and applies your corrections on top. Recommended.'],
  ['manual_only', 'Manual only', 'Ignores the PDF completely. Only sessions you add or import are used.'],
  ['pdf_only', 'PDF only', 'Uses the PDF exactly as printed. Your edits are kept but paused.'],
]
const SRC = { pdf: ['PDF', 'mute'], edited: ['Edited', 'info'], manual: ['Added', 'ok'], hidden: ['Hidden', 'warn'] }
const blank = { day: 'MONDAY', start: '', end: '', room: '', program: 'BS', semester: '', section: '', code: '', title: '', teacher: '', note: '' }

const toBase64 = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(String(reader.result).split(',')[1])
  reader.onerror = reject
  reader.readAsDataURL(file)
})

function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const when = (iso) => { try { return new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) } catch { return iso } }
const classLabel = (program, sem) => (program === 'BS' || sem ? `${program} · Semester ${ROMAN[sem] || sem}` : program)

export function TimetableAdmin({ call }) {
  const [view, setView] = useState(null)
  const [msg, setMsg] = useState({ kind: '', text: '' })
  const [filters, setFilters] = useState({ day: '', cls: '', src: '', q: '' })
  const [form, setForm] = useState(null) // null = closed
  const [editing, setEditing] = useState(null) // the session being edited, or null when adding
  const [warnings, setWarnings] = useState([])
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [imp, setImp] = useState(null) // import preview state

  const load = useCallback(() => call('GET', '/admin/timetable').then(setView).catch((e) => setMsg({ kind: 'err', text: e.message })), [call])
  useEffect(() => { load() }, [load])

  const say = (text, kind = 'ok') => setMsg({ kind, text })
  const act = async (fn, okText) => {
    setBusy(true)
    try { await fn(); say(okText); await load() } catch (e) { say(e.message, 'err') } finally { setBusy(false) }
  }

  const rows = useMemo(() => {
    if (!view) return []
    const q = filters.q.trim().toLowerCase()
    return view.sessions.filter((r) => {
      if (filters.day && r.day !== filters.day) return false
      if (filters.src && r.src !== filters.src) return false
      if (filters.cls) { const [p, s] = filters.cls.split('|'); if (r.program !== p || String(r.semester ?? 0) !== s) return false }
      if (q && !`${r.code} ${r.title} ${r.teacher} ${r.room} ${r.class}`.toLowerCase().includes(q)) return false
      return true
    })
  }, [view, filters])
  const teachers = useMemo(() => [...new Set((view?.sessions || []).map((r) => r.teacher).filter(Boolean))].sort(), [view])

  if (!view) return <p className="muted">{msg.text || 'Loading…'}</p>

  const openAdd = () => { setEditing(null); setForm({ ...blank }); setWarnings([]); setFormError('') }
  const openEdit = (r) => {
    setEditing(r); setWarnings([]); setFormError('')
    setForm({ day: r.day, start: r.start, end: r.end, room: r.room, program: r.program || 'BS', semester: r.semester ?? '', section: r.section || '', code: r.code || '', title: r.title || '', teacher: r.teacher || '', note: r.note || '' })
  }
  const closeForm = () => { setForm(null); setEditing(null); setWarnings([]); setFormError('') }
  const isPdfCell = editing && editing.src !== 'manual'

  const save = async (force = false) => {
    setBusy(true); setFormError('')
    try {
      const common = { day: form.day, start: form.start, end: form.end, room: form.room, section: form.section, teacher: form.teacher, note: form.note }
      const full = { ...common, program: form.program, semester: form.semester === '' ? null : Number(form.semester), code: form.code, title: form.title }
      const r = editing
        ? await call('PUT', `/admin/timetable/sessions/${editing.id}`, { ...(isPdfCell ? common : full), force })
        : await call('POST', '/admin/timetable/sessions', { ...full, force })
      if (r.saved === false) { setWarnings(r.warnings || []); return }
      closeForm(); say('Saved. Students see the change on their next question.'); await load()
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }

  const hide = (r) => confirm(`Hide ${r.code || r.title} (${dayLabel(r.day)} ${r.start}) from students? You can restore it later.`)
    && act(() => call('DELETE', `/admin/timetable/sessions/${r.id}`), 'Hidden from students.')
  const del = (r) => confirm(`Delete ${r.code || r.title} (${dayLabel(r.day)} ${r.start})?`)
    && act(() => call('DELETE', `/admin/timetable/sessions/${r.id}`), 'Deleted.')
  const restore = (r) => act(() => call('POST', `/admin/timetable/sessions/${r.id}/restore`), 'Restored to the PDF version.')
  const setMode = (mode) => {
    if (mode === view.mode) return
    if (mode === 'manual_only' && !confirm(`Students will only see the ${view.counts.manual} session(s) you entered by hand, and nothing from the PDF. Continue?`)) return
    act(() => call('PUT', '/admin/timetable/settings', { mode }), 'Mode changed.')
  }
  const saveMeta = (e) => {
    e.preventDefault()
    const f = new FormData(e.target)
    act(() => call('PUT', '/admin/timetable/settings', { term: f.get('term'), effective: f.get('effective') }), 'Saved.')
  }
  const undo = () => act(() => call('POST', '/admin/timetable/undo'), 'Last change undone.')
  const reset = () => confirm('Remove ALL manual edits and added sessions and go back to the PDF? (You can still press Undo straight after.)')
    && act(() => call('POST', '/admin/timetable/reset'), 'Back to the PDF timetable.')
  const exportCsv = () => call('GET', '/admin/timetable/export').then((r) => download(r.filename, r.csv)).catch((e) => say(e.message, 'err'))
  const template = () => call('GET', '/admin/timetable/template').then((r) => download(r.filename, r.csv)).catch((e) => say(e.message, 'err'))

  const pickFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      const content_base64 = await toBase64(file)
      const r = await call('POST', '/admin/timetable/import', { filename: file.name, content_base64, dry_run: true })
      setImp({ file: file.name, content_base64, filename: file.name, result: r, replace: view.mode === 'manual_only', skip: false })
    } catch (err) { say(err.message, 'err') } finally { setBusy(false) }
  }
  const applyImport = () => act(async () => {
    await call('POST', '/admin/timetable/import', { filename: imp.filename, content_base64: imp.content_base64, dry_run: false, replace: imp.replace, skip_errors: imp.skip })
    setImp(null)
  }, 'Imported. Students see the new timetable now.')

  const byDay = DAYS.map((d) => [d, rows.filter((r) => r.day === d)]).filter(([, list]) => list.length)
  const groups = [...new Set(view.courses.map((c) => c.group))]
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const c = view.counts

  return (
    <div className="tt">
      <datalist id="tt-teachers">{teachers.map((t) => <option key={t} value={t} />)}</datalist>
      {msg.text && <p className={msg.kind === 'err' ? 'err' : 'okmsg'} role="status">{msg.text}</p>}

      <div className="card">
        <h3>Where the timetable comes from</h3>
        <div className="tt-modes" role="radiogroup" aria-label="Timetable source">
          {MODES.map(([id, label, help]) => (
            <label key={id} className={`tt-mode ${view.mode === id ? 'on' : ''}`}>
              <input type="radio" name="tt-mode" checked={view.mode === id} onChange={() => setMode(id)} disabled={busy || (id === 'pdf_only' && !view.pdf.available)} />
              <span><b>{label}</b><small>{help}</small></span>
            </label>
          ))}
        </div>
        <p className="muted small">
          PDF: {view.pdf.available ? `${view.pdf.sessions} sessions · ${view.pdf.term || 'term not named'}${view.pdf.effective ? ` (effective ${view.pdf.effective})` : ''}` : 'no timetable PDF has been read yet'}.
          {' '}Showing to students: <b>{c.total}</b> sessions ({c.pdf} from the PDF, {c.edited} edited, {c.manual} added){c.hidden ? `, ${c.hidden} hidden` : ''}.
        </p>
        {view.orphans.length > 0 && <p className="tt-warn">⚠ {view.orphans.length} earlier edit(s) no longer match the current PDF (the department changed that cell) and are being ignored. Review the list below or press “Reset to PDF”.</p>}
        <form className="row" onSubmit={saveMeta} key={`${view.term}|${view.effective}`}>
          <label>Term shown to students<input name="term" defaultValue={view.meta.term} placeholder={view.pdf.term || 'e.g. Spring 2027'} /></label>
          <label>Effective from<input name="effective" defaultValue={view.meta.effective} placeholder={view.pdf.effective || 'e.g. 1 February 2027'} /></label>
          <button className="adv-primary" disabled={busy}>Save</button>
        </form>
        <div className="row">
          <button onClick={undo} disabled={busy || !view.can_undo}>↶ Undo last change</button>
          <button onClick={reset} disabled={busy}>Reset to PDF</button>
          <button onClick={exportCsv}>Download CSV</button>
          <button onClick={template}>CSV template</button>
          <label className="tt-file">Import CSV / Excel<input type="file" accept=".csv,.txt,.xlsx" onChange={pickFile} disabled={busy} /></label>
        </div>
      </div>

      {imp && (
        <div className="card tt-import">
          <h3>Import preview — {imp.file}</h3>
          <p><b>{imp.result.ok_rows}</b> valid row(s){imp.result.error_count ? <>, <span className="err">{imp.result.error_count} with problems</span></> : ''}.</p>
          {imp.result.errors.length > 0 && <ul className="kv">{imp.result.errors.slice(0, 10).map((e) => <li key={e.row}><b>Row {e.row}</b><span className="err">{e.message}</span></li>)}</ul>}
          {imp.result.warnings.length > 0 && <div className="tt-warn"><b>Clashes in this file</b><ul>{imp.result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
          <label className="adv-check"><input type="checkbox" checked={imp.replace} onChange={(e) => setImp({ ...imp, replace: e.target.checked })} /> Replace the sessions I added earlier (the PDF is never touched)</label>
          {imp.result.error_count > 0 && <label className="adv-check"><input type="checkbox" checked={imp.skip} onChange={(e) => setImp({ ...imp, skip: e.target.checked })} /> Skip the rows with problems and import the rest</label>}
          <div className="row">
            <button className="adv-primary" onClick={applyImport} disabled={busy || !imp.result.ok_rows || (imp.result.error_count > 0 && !imp.skip)}>Import {imp.result.ok_rows} row(s)</button>
            <button onClick={() => setImp(null)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="row tt-head"><h3>Weekly sessions</h3><button className="adv-primary" onClick={openAdd} disabled={!!form}>+ Add session</button></div>
        <div className="row tt-filters">
          <select aria-label="Day" value={filters.day} onChange={(e) => setFilters({ ...filters, day: e.target.value })}><option value="">All days</option>{DAYS.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}</select>
          <select aria-label="Class" value={filters.cls} onChange={(e) => setFilters({ ...filters, cls: e.target.value })}><option value="">All classes</option>{view.classes.map(([p, s]) => <option key={`${p}|${s}`} value={`${p}|${s}`}>{classLabel(p, s)}</option>)}</select>
          <select aria-label="Source" value={filters.src} onChange={(e) => setFilters({ ...filters, src: e.target.value })}><option value="">All entries</option><option value="edited">Edited</option><option value="manual">Added by hand</option><option value="hidden">Hidden</option><option value="pdf">Unchanged from PDF</option></select>
          <input aria-label="Search" placeholder="Search course, teacher, room…" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        </div>

        {form && (
          <div className="tt-form" role="group" aria-label={editing ? 'Edit session' : 'Add session'}>
            <h4>{editing ? `Edit ${editing.code || editing.title}` : 'Add a session'}</h4>
            {isPdfCell && <p className="muted small">This class comes from the PDF. You can change when/where it meets and who teaches it. To change the course itself, hide it and add a new session.</p>}
            <div className="grid2">
              <label>Day<select value={form.day} onChange={set('day')}>{DAYS.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}</select></label>
              <label>Room<input value={form.room} onChange={set('room')} placeholder="e.g. 217, Lab 3, F6" /></label>
              <label>Start time<input type="time" value={form.start} onChange={set('start')} /></label>
              <label>End time<input type="time" value={form.end} onChange={set('end')} /></label>
              <label>Programme<select value={form.program} onChange={set('program')} disabled={isPdfCell}>{PROGRAMS.map((p) => <option key={p}>{p}</option>)}</select></label>
              <label>Semester<input type="number" min="1" max="12" value={form.semester} onChange={set('semester')} disabled={isPdfCell} placeholder="e.g. 8" /></label>
              <label>Section<select value={form.section} onChange={set('section')}>{SECTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
              <label>Teacher<input list="tt-teachers" value={form.teacher} onChange={set('teacher')} placeholder="e.g. Dr. Rabeeh Abbasi" /></label>
              <label>Course code<input value={form.code} onChange={set('code')} disabled={isPdfCell} placeholder="e.g. CS-413" /></label>
              <label>Course title<input value={form.title} onChange={set('title')} disabled={isPdfCell} placeholder="e.g. Information Security" /></label>
            </div>
            <label>Note (optional)<input value={form.note} onChange={set('note')} placeholder="e.g. make-up class" /></label>
            {formError && <p className="err" role="alert">{formError}</p>}
            {warnings.length > 0 && (
              <div className="tt-warn" role="alert"><b>Please check before saving</b><ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                <button className="adv-primary" onClick={() => save(true)} disabled={busy}>Save anyway</button></div>
            )}
            <div className="row">
              <button className="adv-primary" onClick={() => save(false)} disabled={busy}>{editing ? 'Save changes' : 'Add session'}</button>
              <button onClick={closeForm} disabled={busy}>Cancel</button>
            </div>
          </div>
        )}

        {byDay.length === 0 && <p className="muted">{view.counts.total || view.counts.hidden ? 'No sessions match these filters.' : 'No sessions yet. Add one, or import a CSV/Excel file.'}</p>}
        {byDay.map(([d, list]) => (
          <div key={d} className="tt-day">
            <h4>{dayLabel(d)} <span className="muted small">{list.length} session(s)</span></h4>
            <div className="adv-table-wrap"><table>
              <thead><tr><th>Time</th><th>Course</th><th>Class</th><th>Teacher</th><th>Room</th><th>Status</th><th /></tr></thead>
              <tbody>{list.map((r) => {
                const [label, tone] = SRC[r.src] || SRC.pdf
                return (
                  <tr key={r.id} className={r.src === 'hidden' ? 'tt-hidden' : ''}>
                    <td className="nowrap">{r.start}–{r.end}{r.orig?.time && <small className="muted"> (was {r.orig.time})</small>}</td>
                    <td><b>{r.code}</b> {r.title}</td>
                    <td>{r.class}</td>
                    <td>{r.teacher || '—'}{r.orig?.teacher !== undefined && <small className="muted"> (was {r.orig.teacher || 'course teacher'})</small>}</td>
                    <td>{r.room}{r.orig?.room && <small className="muted"> (was {r.orig.room})</small>}</td>
                    <td><span className={`tt-badge ${tone}`}>{label}</span></td>
                    <td className="tt-actions">
                      {r.src !== 'hidden' && <button className="link" onClick={() => openEdit(r)} disabled={!!form}>Edit</button>}
                      {r.src === 'edited' && <button className="link" onClick={() => restore(r)} disabled={busy}>Undo edit</button>}
                      {r.src === 'hidden' && <button className="link" onClick={() => restore(r)} disabled={busy}>Restore</button>}
                      {(r.src === 'pdf' || r.src === 'edited') && <button className="link" onClick={() => hide(r)} disabled={busy}>Hide</button>}
                      {r.src === 'manual' && <button className="link" onClick={() => del(r)} disabled={busy}>Delete</button>}
                    </td>
                  </tr>
                )
              })}</tbody>
            </table></div>
          </div>
        ))}
      </div>

      <details className="card">
        <summary><b>Teachers by course</b> <span className="muted small">— change who teaches a course for every session of that class</span></summary>
        {groups.map((g) => (
          <div key={g} className="tt-day"><h4>{g}</h4>
            {view.courses.filter((x) => x.group === g).map((x) => <CourseRow key={`${g}|${x.label}`} course={x} busy={busy}
              onSave={(teacher) => act(() => call('PUT', '/admin/timetable/courses', { group: g, label: x.label, teacher }), 'Teacher saved.')} />)}
          </div>
        ))}
      </details>

      <details className="card">
        <summary><b>Change history</b></summary>
        {view.history.length === 0 && <p className="muted">No changes yet.</p>}
        <ul className="kv">{view.history.map((h) => (
          <li key={h.id} className={h.undone ? 'tt-hidden' : ''}><b>{h.action}{h.undone ? ' (undone)' : ''}</b><span>{when(h.at)} · {h.by || 'admin'}{h.detail ? ` · ${h.detail}` : ''}</span></li>
        ))}</ul>
      </details>
    </div>
  )
}

function CourseRow({ course, busy, onSave }) {
  const [value, setValue] = useState(course.teacher)
  useEffect(() => { setValue(course.teacher) }, [course.teacher])
  const dirty = value.trim() !== (course.teacher || '')
  return (
    <div className="row tt-course">
      <span className="tt-course-name"><b>{course.code || course.label}</b> {course.title}</span>
      <input list="tt-teachers" value={value} onChange={(e) => setValue(e.target.value)} aria-label={`Teacher of ${course.label}`} placeholder="No teacher listed" />
      <button className="adv-primary" disabled={busy || !dirty} onClick={() => onSave(value)}>Save</button>
      {course.edited && <small className="muted">PDF says: {course.pdf_teacher || '—'}</small>}
    </div>
  )
}
