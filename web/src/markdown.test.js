import { describe, expect, it } from 'vitest'
import { isRtl, renderAnswer } from './markdown'

describe('renderAnswer', () => {
  it('turns citations into markers and renders tables', () => {
    const html = renderAnswer('Prereq is **CSC-121** [1].\n\n| a | b |\n|---|---|\n| 1 | 2 |')
    expect(html).toContain('<sup class="cite" data-cite="1">1</sup>')
    expect(html).toContain('<table>')
  })

  it('strips scripts, event handlers and javascript: links (model output is untrusted)', () => {
    const html = renderAnswer('<img src=x onerror=alert(1)><script>alert(1)</script>[x](javascript:alert(1)) <b onclick="x()">b</b>')
    expect(html).not.toMatch(/<script|onerror|onclick|javascript:/i)
  })

  it('opens external links safely', () => {
    const html = renderAnswer('[site](https://cs.qau.edu.pk)')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })
})

describe('isRtl', () => {
  it('detects Urdu script but not Roman Urdu or English', () => {
    expect(isRtl('پی ایچ ڈی کی مدت')).toBe(true)
    expect(isRtl('phd ki muddat kya hai')).toBe(false)
    expect(isRtl('What is it?')).toBe(false)
  })
})
