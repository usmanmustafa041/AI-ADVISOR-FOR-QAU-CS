import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const ALLOWED = {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'a', 'code', 'pre', 'h3', 'h4', 'h5', 'blockquote', 'hr', 'sup', 'span'],
  ALLOWED_ATTR: ['href', 'title', 'class', 'data-cite'],
}

/** Markdown -> safe HTML, with [n] citations turned into small clickable markers. */
export function renderAnswer(text) {
  const withCites = text.replace(/\[(\d{1,2})\]/g, (_m, n) => `<sup class="cite" data-cite="${n}">${n}</sup>`)
  const html = marked.parse(withCites)
  const clean = DOMPurify.sanitize(html, ALLOWED)
  const tmp = document.createElement('div')
  tmp.innerHTML = clean
  tmp.querySelectorAll('a').forEach((a) => {
    a.setAttribute('target', '_blank')
    a.setAttribute('rel', 'noopener noreferrer')
  })
  return tmp.innerHTML
}

export const isRtl = (text) => {
  const letters = [...text].filter((c) => /\p{L}/u.test(c))
  if (!letters.length) return false
  return letters.filter((c) => /[؀-ۿ]/.test(c)).length / letters.length > 0.3
}
