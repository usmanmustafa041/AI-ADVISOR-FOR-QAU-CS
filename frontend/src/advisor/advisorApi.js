// Client for the new chatbot engine ("advisor").
//
// It lives under its own base path so it can never collide with the portal's own /api/v1 routes:
//   dev  : Vite proxies  /advisor/*  ->  the advisor server (see vite.config.js)
//   prod : nginx routes  /advisor/*  ->  the advisor server (see deploy/advisor/nginx.conf)
export const ADVISOR_BASE = import.meta.env.VITE_ADVISOR_URL || '/advisor/api/v1'

export class AdvisorError extends Error {
  constructor(message, status, retryAfter) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

const authHeader = (auth) => (auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {})

async function toError(res) {
  let detail = `Request failed (${res.status})`
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') detail = data.detail
    else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join('; ')
    else if (data.detail?.message) detail = [data.detail.message, ...(data.detail.errors || [])].join(' — ')
  } catch { /* not JSON */ }
  return new AdvisorError(detail, res.status, Number(res.headers.get('Retry-After')) || undefined)
}

/** JSON request. `auth` is the portal session (its bearer token proves who the student is). */
export async function advisorRequest(path, options = {}, auth = null) {
  const res = await fetch(`${ADVISOR_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...authHeader(auth),
      ...options.headers,
    },
  })
  if (!res.ok) throw await toError(res)
  return res.json()
}

/** Parse a text/event-stream buffer into events; returns the unparsed tail. */
export function parseSse(buffer) {
  const events = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop()
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

/** Stream one question. Calls onEvent({event, data}) as the answer is written. */
export async function streamAdvisorChat({ body, auth, signal, onEvent }) {
  const res = await fetch(`${ADVISOR_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(auth) },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw await toError(res)
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

export async function advisorHealth() {
  const res = await fetch(`${ADVISOR_BASE}/health`)
  if (!res.ok) throw new Error('advisor offline')
  return res.json()
}
