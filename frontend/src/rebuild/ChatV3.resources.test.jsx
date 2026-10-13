import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ChatV3 } from './ChatV3'
import { streamChat } from './stream'

vi.mock('./stream', () => ({ streamChat: vi.fn() }))
const nativeScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollTo')
beforeEach(() => { Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() }) })
afterEach(() => {
  cleanup(); vi.resetAllMocks()
  if (nativeScroll) Object.defineProperty(HTMLElement.prototype, 'scrollTo', nativeScroll)
  else delete HTMLElement.prototype.scrollTo
})

it('shows observed official form links while excluding unsafe source links', async () => {
  const source = { number: 1, chunk_id: 'records-form', source_id: 'records', document_title: 'Records office', review_status: 'observed_official', captured_at: '2026-10-12', canonical_url: 'https://qau.edu.pk/downloads/', resources: [
    { title: 'Certificate correction application', url: 'https://qau.edu.pk/Downloads/correction.pdf' },
    { title: 'Fake mirror', url: 'https://attacker.example/correction.pdf' },
    { title: 'Unsafe action', url: 'javascript:alert(1)' },
  ] }
  streamChat.mockImplementation(async (_body, { onEvent }) => {
    onEvent('citation', source)
    onEvent('token', { text: 'Use the published correction form. [1]' })
    onEvent('done', { answer: 'Use the published correction form. [1]', cited_sources: [source], groundedness_status: 'cited_generation', latency_ms: 100 })
  })
  const { container } = render(<ChatV3 auth={{ user: { role: 'guest' } }} />)
  fireEvent.change(screen.getByRole('textbox', { name: 'Ask an academic question' }), { target: { value: 'Where is the certificate correction form?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send query' }))
  expect(await screen.findByRole('link', { name: /Certificate correction application/ })).toHaveAttribute('href', 'https://qau.edu.pk/Downloads/correction.pdf')
  expect(screen.getByText('Official forms and services')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Fake mirror|Unsafe action/ })).not.toBeInTheDocument()
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
})
