// Thin API client. Streaming uses fetch + ReadableStream because EventSource cannot POST.

const BASE = import.meta.env.VITE_API_BASE || ''

export class ApiError extends Error {
  constructor(message, status, retryAfter) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function parseError(res) {
  let detail = `Request failed (${res.status})`
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') detail = data.detail
    else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join('; ')
    else if (data.detail?.message) detail = [data.detail.message, ...(data.detail.errors || [])].join(' — ')
  } catch { /* not JSON */ }
  return new ApiError(detail, res.status, Number(res.headers.get('Retry-After')) || undefined)
}

export async function getJson(path, token) {
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function sendJson(method, path, body, token) {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

/** Parse a text/event-stream body into {event, data} objects. */
export function parseSse(buffer) {
  const events = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() // incomplete tail
  for (const part of parts) {
    let event = 'message'
    const data = []
    for (const line of part.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (data.length) {
      try { events.push({ event, data: JSON.parse(data.join('\n')) }) } catch { /* skip malformed */ }
    }
  }
  return { events, rest }
}

export async function streamChat({ message, conversationId, signal, onEvent }) {
  const res = await fetch(`${BASE}/api/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId || null }),
    signal,
  })
  if (!res.ok) throw await parseError(res)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { events, rest } = parseSse(buffer)
    buffer = rest
    events.forEach(onEvent)
  }
}
