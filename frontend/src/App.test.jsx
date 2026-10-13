import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './main.jsx'

const studentAuth = { access_token: 'test-token', user: { id: '1', email: 'student@qau.edu.pk', role: 'student', active: true } }

describe('academic advisor interface', () => {
  afterEach(() => { cleanup(); localStorage.clear() })
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url.endsWith('/health')) return Promise.resolve({ ok: true, json: async () => ({ status: 'ok' }) })
      return Promise.resolve({ ok: true, json: async () => ({}) })
    }))
  })

  it('requires authentication and offers student registration', () => {
    render(<App />)
    expect(screen.getByText('Sign in to your advisor')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create an account/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Continue without signing in/i })).toBeInTheDocument()
  })

  it('allows guest advising without exposing saved history', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    expect(screen.getByText(/Guest conversation · not saved/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'History' })).not.toBeInTheDocument()
    expect(screen.getByText(/Sign in to save and revisit/i)).toBeInTheDocument()
  })

  it('renders private authenticated chat and Urdu toggle', () => {
    localStorage.setItem('qau-auth', JSON.stringify(studentAuth))
    render(<App />)
    expect(screen.getByText('Private authenticated conversation · history enabled')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask an academic question/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'اردو' })).toBeInTheDocument()
  })

  it('renders cited evidence and removes unsafe model HTML', async () => {
    vi.stubGlobal('fetch', vi.fn(url => Promise.resolve({ ok: true, json: async () => url.endsWith('/chat') ? {
      answer: '<img src=x onerror="alert(1)"> **134 credit hours** [unsafe](javascript:alert)',
      language: 'english', entities: {}, citations: [{ number: 1, chunk_id: 'scheme', title: 'BSCS scheme', page_number: 1, source_url: 'https://cs.qau.edu.pk/doc/scheme-2025.pdf', quotes: ['Calculated total: 134 credit hours.'] }],
      grounding_status: 'cited_generation', response_time_ms: 1200, notices: [],
    } : { status: 'ok' } })))
    const { container } = render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: 'BSCS credit hours?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
    expect(await screen.findByText('134 credit hours')).toBeInTheDocument()
    expect(screen.getByText(/BSCS scheme · p. 1/)).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
    expect(screen.queryByText(/% confidence/)).not.toBeInTheDocument()
  })

  it('sends the Urdu preference and bounded guest conversation context', async () => {
    vi.stubGlobal('fetch', vi.fn(url => Promise.resolve({ ok: true, json: async () => url.endsWith('/chat') ? {
      answer: 'دستیاب معلومات', entities: {}, grounding_status: 'cited_generation', response_time_ms: 20, citations: [], notices: [],
    } : { status: 'ok' } })))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    fireEvent.click(screen.getByRole('button', { name: 'اردو' }))
    fireEvent.change(screen.getByPlaceholderText('اپنا تعلیمی سوال پوچھیں…'), { target: { value: 'BSCS فیس' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
    await screen.findByText('دستیاب معلومات')
    const call = fetch.mock.calls.find(([url]) => url.endsWith('/chat'))
    const payload = JSON.parse(call[1].body)
    expect(payload.language).toBe('urdu')
    expect(payload.history).toEqual([])
    expect(payload.session_id).toBeNull()
  })

  it('renders the reported greeting as a short conversation without sources', async () => {
    vi.stubGlobal('fetch', vi.fn(url => Promise.resolve({ ok: true, json: async () => url.endsWith('/chat') ? {
      answer: 'Hi! How can I help you with QAU today?', entities: {}, grounding_status: 'conversational', response_time_ms: 1, citations: [], notices: [],
    } : { status: 'ok' } })))
    const { container } = render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: "hi'" } })
    fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
    expect(await screen.findByText('Hi! How can I help you with QAU today?')).toBeInTheDocument()
    expect(container.querySelector('.evidence-source')).toBeNull()
    expect(screen.getByText('Conversation · 0.0s')).toBeInTheDocument()
  })

  it('keeps outage passages collapsed and outside the answer bubble', async () => {
    const passage = 'A long source passage that should only appear inside its source card.'
    vi.stubGlobal('fetch', vi.fn(url => Promise.resolve({ ok: true, json: async () => url.endsWith('/chat') ? {
      answer: "I couldn't produce a reliable answer just now.", entities: {}, grounding_status: 'source_excerpts', response_time_ms: 25000,
      citations: [{ number: 1, chunk_id: 'related', title: 'Related university source', quotes: [passage] }], notices: [],
    } : { status: 'ok' } })))
    const { container } = render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: 'research areas' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
    await screen.findByText("I couldn't produce a reliable answer just now.")
    expect(container.querySelector('details.evidence-source')).not.toHaveAttribute('open')
    expect(container.querySelector('details.evidence-source blockquote')).toHaveTextContent(passage)
    expect([...container.querySelectorAll('.message-bubble')].some(el => el.textContent.includes(passage))).toBe(false)
    expect(screen.getByText(/Answer unavailable · related sources/)).toBeInTheDocument()
  })

  it('keeps course context through greetings and clears it when the topic changes', async () => {
    const turns = [
      ['CSC-483 prerequisites?', 'Course answer', { course_code: ['CSC-483'] }, 'cited_generation'],
      ["hi'", 'Hello again', {}, 'conversational'],
      ['Tell me about MS Data Science', 'Programme answer', {}, 'cited_generation'],
      ['How long is it?', 'Duration answer', {}, 'insufficient_evidence'],
    ]
    vi.stubGlobal('fetch', vi.fn((url, options) => Promise.resolve({ ok: true, json: async () => {
      if (!url.endsWith('/chat')) return { status: 'ok' }
      const turn = turns.find(([question]) => question === JSON.parse(options.body).message)
      return { answer: turn[1], entities: turn[2], grounding_status: turn[3], response_time_ms: 1, citations: [], notices: [] }
    } })))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /Continue without signing in/i }))
    for (const [question, answer] of turns) {
      fireEvent.change(screen.getByPlaceholderText(/Ask an academic question/i), { target: { value: question } })
      fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
      await screen.findByText(answer)
    }
    const payloads = fetch.mock.calls.filter(([url]) => url.endsWith('/chat')).map(([, options]) => JSON.parse(options.body))
    expect(payloads.map(p => p.context_course_code)).toEqual([null, 'CSC-483', 'CSC-483', null])
  })
})
