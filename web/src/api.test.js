import { describe, expect, it } from 'vitest'
import { parseSse } from './api'

describe('parseSse', () => {
  it('parses complete events and keeps the incomplete tail', () => {
    const { events, rest } = parseSse('event: delta\ndata: {"text":"Hi"}\n\nevent: done\ndata: {"o')
    expect(events).toEqual([{ event: 'delta', data: { text: 'Hi' } }])
    expect(rest).toBe('event: done\ndata: {"o')
  })

  it('handles unicode and ignores malformed JSON', () => {
    const { events } = parseSse('event: delta\ndata: {"text":"السلام"}\n\nevent: x\ndata: {bad\n\n')
    expect(events).toHaveLength(1)
    expect(events[0].data.text).toBe('السلام')
  })
})
