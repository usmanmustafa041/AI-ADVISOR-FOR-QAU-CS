import { describe, expect, it, vi } from 'vitest'
import { streamChat } from './stream'

describe('student streaming transport', () => {
  it('preserves Urdu across byte boundaries and requires a final event', async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text":"سلام"}\n\nevent: done\ndata: {"answer":"سلام"}\n\n')
    const body = new ReadableStream({ start(controller) { for (let i = 0; i < bytes.length; i += 3) controller.enqueue(bytes.slice(i, i + 3)); controller.close() } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body }))
    const events = []
    await streamChat({ message: 'سلام' }, { onEvent: (event, data) => events.push([event, data]) })
    expect(events[0]).toEqual(['token', { text: 'سلام' }])
    expect(events[1][0]).toBe('done')
    vi.unstubAllGlobals()
  })
  it('reports an interrupted answer instead of treating partial tokens as complete', async () => {
    const body = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('event: token\ndata: {"text":"Partial"}\n\n')); c.close() } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body }))
    await expect(streamChat({ message: 'question' }, { onEvent: () => {} })).rejects.toThrow('before the answer was complete')
    vi.unstubAllGlobals()
  })
})
