import React, { useState } from 'react'

export function AnswerFeedback({ messageId, request }) {
  const [vote, setVote] = useState(null)
  const [reason, setReason] = useState('incorrect')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  async function save(rating) {
    setBusy(true); setStatus('')
    try {
      await request(`/feedback/${messageId}`, { method: 'PUT', body: JSON.stringify({ rating, reason: rating === 1 ? 'helpful' : reason }) })
      setVote(rating); setStatus('Feedback saved')
    } catch (e) { setStatus(e.message) }
    finally { setBusy(false) }
  }
  async function remove() {
    setBusy(true)
    try { await request(`/feedback/${messageId}`, { method: 'DELETE' }); setVote(null); setStatus('Feedback removed') }
    catch (e) { setStatus(e.message) }
    finally { setBusy(false) }
  }
  return <div className="answer-feedback" aria-label="Answer feedback">
    <button disabled={busy} aria-pressed={vote === 1} onClick={() => save(1)}>Helpful</button>
    <label><span className="sr-only">Feedback reason</span><select aria-label="Feedback reason" value={reason} onChange={e => setReason(e.target.value)}>
      <option value="incorrect">Incorrect</option><option value="outdated">Outdated</option><option value="missing_information">Missing information</option><option value="unclear">Unclear</option>
    </select></label>
    <button disabled={busy} aria-pressed={vote === -1} onClick={() => save(-1)}>Report issue</button>
    {vote && <button disabled={busy} onClick={remove}>Remove feedback</button>}
    <small role="status">{status}</small>
  </div>
}
