import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdvisorChat, renderAnswerHtml } from './AdvisorChat'
import { parseSse } from './advisorApi'

const sse = (events) => events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
const streamOf = (text) => {
  const bytes = new TextEncoder().encode(text)
  let sent = false
  return { getReader: () => ({ read: async () => (sent ? { done: true } : ((sent = true), { done: false, value: bytes })) }) }
}
const guest = { access_token: null, user: { id: 'guest', email: 'Guest', role: 'guest' } }
const student = { access_token: 'tok', user: { id: '1', email: 's@qau.edu.pk', role: 'student' } }

describe('parseSse', () => {
  it('parses complete events and keeps the unfinished tail', () => {
    const { events, rest } = parseSse('event: delta\ndata: {"text":"Hi"}\n\nevent: done\ndata: {"o')
    expect(events).toEqual([{ event: 'delta', data: { text: 'Hi' } }])
    expect(rest).toBe('event: done\ndata: {"o')
  })
  it('skips malformed payloads instead of failing the stream', () => {
    expect(parseSse('event: x\ndata: {oops\n\n').events).toEqual([])
  })
})

describe('renderAnswerHtml', () => {
  it('marks citations and strips unsafe markup', () => {
    const html = renderAnswerHtml('Fees are listed [1]. <img src=x onerror=alert(1)><script>alert(1)</script>[link](https://qau.edu.pk)')
    expect(html).toContain('<sup class="cite-mark">1</sup>')
    expect(html).not.toMatch(/<img|<script|onerror/)
    expect(html).toContain('rel="noopener noreferrer"')
  })
})

describe('timetable answers', () => {
  it('wraps tables so they scroll inside the bubble and keeps the time chip', () => {
    const html = renderAnswerHtml('| Time | Course |\n|---|---|\n| `8:30 – 10:00 AM` | **CS-413** · Information Security |')
    expect(html).toContain('class="table-scroll"')
    expect(html).toContain('<code>8:30 – 10:00 AM</code>')
  })
})

describe('AdvisorChat', () => {
  let fetchMock
  beforeEach(() => {
    window.HTMLElement.prototype.scrollTo = () => {}
    fetchMock = vi.fn((url) => {
      if (String(url).endsWith('/chat/stream')) {
        return Promise.resolve({ ok: true, body: streamOf(sse([
          ['meta', { conversation_id: 'c1' }],
          ['delta', { text: 'PSP is a prerequisite of OOP [1].' }],
          ['sources', { sources: [{ n: 1, title: 'Scheme of Study', url: 'https://cs.qau.edu.pk/x', kind: 'web', snippet: 'PSP then OOP', cited: true }] }],
          ['done', { message_id: 'm1', outcome: 'answered', latency_ms: 1200 }],
        ])) })
      }
      return Promise.resolve({ ok: true, json: async () => ({ conversations: [] }) })
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  const chatCall = () => fetchMock.mock.calls.find(([u]) => String(u).endsWith('/chat/stream'))

  it('streams an answer with a collapsed source and sends guests as ephemeral', async () => {
    render(<AdvisorChat auth={guest} suggestions={[]} />)
    fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: 'Is PSP needed for OOP?' } })
    fireEvent.click(screen.getByRole('button', { name: /Send query/i }))
    expect(await screen.findByText(/PSP is a prerequisite of OOP/)).toBeInTheDocument()
    const body = JSON.parse(chatCall()[1].body)
    expect(body).toMatchObject({ message: 'Is PSP needed for OOP?', ephemeral: true, conversation_id: null })
    expect(chatCall()[1].headers.Authorization).toBeUndefined()
    const source = document.querySelector('details.evidence-source')
    expect(source).not.toBeNull()
    expect(source.open).toBe(false)
    expect(screen.queryByText('Helpful')).not.toBeInTheDocument() // guests have nothing stored to rate
  })

  it('sends the portal token and conversation id for signed-in students, with feedback', async () => {
    render(<AdvisorChat auth={student} suggestions={[]} />)
    fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: 'hello' } })
    fireEvent.click(screen.getByRole('button', { name: /Send query/i }))
    expect(await screen.findByRole('button', { name: 'Helpful' })).toBeInTheDocument()
    const [, init] = chatCall()
    expect(init.headers.Authorization).toBe('Bearer tok')
    const body = JSON.parse(init.body)
    expect(body.ephemeral).toBeUndefined()
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, o]) => String(u).endsWith('/feedback/m1') && o.method === 'PUT')).toBe(true))
  })

  it('shows follow-up chips from the engine and sends their text when clicked', async () => {
    fetchMock.mockImplementation((url) => {
      if (String(url).endsWith('/chat/stream')) {
        return Promise.resolve({ ok: true, body: streamOf(sse([
          ['meta', { conversation_id: null }],
          ['delta', { text: 'Monday timetable' }],
          ['followups', { title: 'Other days', items: [{ label: 'Wednesday', text: 'Wednesday classes for semester 8' }] }],
          ['done', { message_id: null, outcome: 'answered' }],
        ])) })
      }
      return Promise.resolve({ ok: true, json: async () => ({ conversations: [] }) })
    })
    render(<AdvisorChat auth={guest} suggestions={[]} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'monday 8th semester' } })
    fireEvent.click(screen.getByRole('button', { name: /Send query/i }))
    fireEvent.click(await screen.findByRole('button', { name: 'Wednesday' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chat/stream')).length).toBe(2))
    expect(JSON.parse(chatCall()[1].body).message).toBe('monday 8th semester')
    const second = fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chat/stream'))[1]
    expect(JSON.parse(second[1].body).message).toBe('Wednesday classes for semester 8')
  })

  it('asks for Urdu answers when the toggle is on', async () => {
    render(<AdvisorChat auth={guest} suggestions={[]} />)
    fireEvent.click(screen.getByRole('button', { name: 'اردو' }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'fee' } })
    fireEvent.click(screen.getByRole('button', { name: /Send query/i }))
    await screen.findByText(/PSP is a prerequisite/)
    expect(JSON.parse(chatCall()[1].body).language).toBe('urdu')
  })

  it('shows a friendly message when the engine is unreachable', async () => {
    fetchMock.mockImplementation(() => Promise.reject(new TypeError('fetch failed')))
    render(<AdvisorChat auth={guest} suggestions={[]} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: /Send query/i }))
    expect(await screen.findByText(/Could not reach the advisor service/)).toBeInTheDocument()
  })
})

describe('plainAnswer', () => {
  it('removes markdown decoration and citation marks for list views', async () => {
    const { plainAnswer } = await import('./AdvisorChat')
    expect(plainAnswer('**Total** is 5 PKR [1].\n- one *two*\n## Head')).toBe('Total is 5 PKR.\n• one two\nHead')
  })
})
