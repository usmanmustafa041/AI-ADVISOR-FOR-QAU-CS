// Fetch SSE supports POST, bearer auth, cancellation and UTF-8 boundaries.
export async function streamChat(body, { signal, token, onEvent }) {
  const response = await fetch('/api/v3/chat/stream', {
    method: 'POST', credentials: 'same-origin', signal,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    if (response.status === 401 && token) window.dispatchEvent(new Event('qau-auth-expired'))
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${response.status})`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = '', finished = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      pending += decoder.decode(value, { stream: !done }).replaceAll('\r\n', '\n')
      let boundary
      while ((boundary = pending.indexOf('\n\n')) !== -1) {
        const frame = pending.slice(0, boundary); pending = pending.slice(boundary + 2)
        const lines = frame.split('\n')
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim()
        const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
        if (event && data) {
          const payload = JSON.parse(data)
          if (event === 'error') throw new Error(payload.message || 'The answer could not be completed.')
          if (event === 'done') finished = true
          onEvent(event, payload)
        }
      }
      if (done) break
    }
    if (!finished) throw new Error('The connection ended before the answer was complete. Please retry.')
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
}
