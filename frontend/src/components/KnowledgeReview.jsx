import React, { useEffect, useState } from 'react'

export function KnowledgeReview({ request }) {
  const [summary, setSummary] = useState(null)
  const [versions, setVersions] = useState({ items: [], total: 0 })
  const [runs, setRuns] = useState([])
  const [feedback, setFeedback] = useState([])
  const [selected, setSelected] = useState(null)
  const [coverage, setCoverage] = useState(null)
  const [offset, setOffset] = useState(0)
  const [note, setNote] = useState('')
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [snapshot, setSnapshot] = useState('')
  const [publicationNote, setPublicationNote] = useState('')
  const [status, setStatus] = useState('')
  async function load() {
    setError('')
    try {
      const [a, b, c, d] = await Promise.all([request('/knowledge-review'), request(`/knowledge-review/versions?offset=${offset}`), request('/knowledge-review/runs'), request('/feedback')])
      setSummary(a); setVersions(b); setRuns(c); setFeedback(d)
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { load() }, [offset])
  async function choose(id) {
    try { setSelected(await request(`/knowledge-review/versions/${id}`)); setNote(''); setAck(false) }
    catch (e) { setError(e.message) }
  }
  async function review(decision) {
    setBusy(true); setError('')
    try {
      await request(`/knowledge-review/versions/${selected.version_id}`, { method: 'PUT', body: JSON.stringify({ decision, note, acknowledge_warnings: ack }) })
      await choose(selected.version_id); await load(); setStatus(`Source ${decision}`)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  async function publish(e) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await request('/knowledge-review/publish', { method: 'POST', body: JSON.stringify({ snapshot_id: snapshot, note: publicationNote }) })
      setStatus('Reviewed snapshot published. Rollback copy retained.')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  async function downloadOriginal() {
    try {
      const blob = await request(`/knowledge-review/versions/${selected.version_id}/original`, { responseType: 'blob' })
      const url = URL.createObjectURL(blob)
      const extension = { 'application/pdf': '.pdf', 'text/html': '.html', 'text/plain': '.txt', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx' }[selected.document.mime_type] || '.raw'
      const link = document.createElement('a'); link.href = url; link.download = `source-${selected.version_id}${extension}`
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setError(e.message) }
  }
  return <div className="knowledge-review">
    <section className="section-card full"><div className="section-heading"><h3>Knowledge ingestion review</h3><button onClick={load}>Refresh</button></div>
      <p>Approval applies to one exact document version. Check applicability, extracted values and conflicts before approving.</p>
      {summary && <p>{summary.versions} versions · {summary.reviews.pending || 0} pending · {summary.reviews.approved || 0} approved · {summary.reviews.rejected || 0} rejected</p>}
      {error && <div className="form-error" role="alert">{error}</div>}<p role="status">{status}</p>
      <div className="review-versions">{versions.items.map(v => <button key={v.version_id} onClick={() => choose(v.version_id)} className="course-row"><div><strong>{v.title}</strong><small>{v.metadata.effective_term || 'Applicability unknown'} · {v.review.decision} · {v.records} records · {v.warnings.length} warnings</small><small>{v.url}</small></div></button>)}</div>
      <div className="review-pagination"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 30))}>Previous</button><span>{offset + 1}–{Math.min(offset + 30, versions.total)} / {versions.total}</span><button disabled={offset + 30 >= versions.total} onClick={() => setOffset(offset + 30)}>Next</button></div>
    </section>
    {selected && <section className="section-card full"><h3>{selected.document.title}</h3><p>{selected.url}</p><small>SHA-256: {selected.sha256}</small><p><button onClick={downloadOriginal}>Download exact archived original</button></p>
      {!!selected.document.warnings.length && <pre className="review-json">{JSON.stringify(selected.document.warnings, null, 2)}</pre>}
      <details><summary>Metadata and academic records</summary><pre className="review-json">{JSON.stringify({ metadata: selected.document.metadata, records: selected.document.records }, null, 2)}</pre></details>
      <details><summary>Source text and page references</summary>{selected.document.pages.map((p, i) => <div key={i}><h4>{p.page_number ? `Page ${p.page_number}` : 'Document text'} · {p.extraction_method}</h4><pre className="review-json">{p.content}</pre></div>)}</details>
      <details><summary>Changes from earlier versions</summary><pre className="review-json">{JSON.stringify(selected.changes, null, 2)}</pre></details>
      {selected.truncated && <p>Preview is truncated. Check the original document before approving.</p>}
      <label className="review-note">Review note<textarea value={note} onChange={e => setNote(e.target.value)} minLength={5} maxLength={2000} /></label>
      <label><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} /> I checked the extraction warnings against the original.</label>
      <div className="review-actions">{['approved', 'rejected', 'pending'].map(d => <button key={d} disabled={busy || note.trim().length < 5} onClick={() => review(d)}>{d === 'approved' ? 'Approve exact version' : d === 'rejected' ? 'Reject version' : 'Return to pending'}</button>)}</div>
    </section>}
    <section className="section-card full"><h3>Crawl coverage and failures</h3>{runs.map(r => <button className="course-row" key={r.file} onClick={async () => { try { setCoverage(await request(`/knowledge-review/runs/${r.file}`)) } catch(e) { setError(e.message) } }}><span>{r.file.slice(0, 12)} · {r.visited ?? 'import'} visited · {r.pending ?? 0} pending</span></button>)}
      {coverage && <pre className="review-json">{JSON.stringify(coverage, null, 2)}</pre>}
      <details><summary>Workspace documents and policy conflicts</summary><pre className="review-json">{JSON.stringify({ workspace: summary?.workspace, cohort_changes: summary?.conflicts, source_conflicts: summary?.source_conflicts }, null, 2)}</pre></details>
    </section>
    <section className="section-card full"><h3>Answer feedback</h3>{feedback.length ? feedback.map(f => <p key={`${f.rating}-${f.reason}`}>{f.reason}: {f.votes}</p>) : <p>No answer feedback yet.</p>}</section>
    <section className="section-card full"><h3>Publish reviewed knowledge</h3><p>Publication requires approved source versions, matching embeddings and a passed retrieval gate. Pending extractions cannot replace the active library.</p><form className="stack-form" onSubmit={publish}><label>Snapshot ID<input pattern="[a-f0-9]{32}" value={snapshot} onChange={e => setSnapshot(e.target.value)} required /></label><label>Publication note<textarea minLength={10} value={publicationNote} onChange={e => setPublicationNote(e.target.value)} required /></label><button className="primary" disabled={busy}>Publish reviewed snapshot</button></form></section>
  </div>
}
