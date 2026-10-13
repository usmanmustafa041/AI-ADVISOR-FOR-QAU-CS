import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TimetableAdmin } from './AdvisorTimetable'

const session = (o) => ({ id: 'a1', src: 'pdf', day: 'MONDAY', start: '11:55', end: '13:25', room: '217', section: 'S', code: 'CS-413', title: 'Introduction to Information Security', teacher: 'Dr. Muazzam Khattak', class: 'BS Semester VIII · Self-support (evening)', program: 'BS', semester: 8, note: '', ...o })
const view = (o = {}) => ({
  version: 1, mode: 'pdf_plus_edits', term: 'Fall 2026', effective: '', meta: { term: '', effective: '' },
  pdf: { available: true, term: 'Fall 2026', effective: 'Monday 28th September, 2026', sessions: 2 },
  counts: { total: 2, pdf: 2, edited: 0, manual: 0, hidden: 0 }, orphans: [], updated: '', history: [], can_undo: false,
  classes: [['BS', 8]], courses: [{ group: 'BS Semester VIII Self Support', label: 'CS-413 IIS', code: 'CS-413', title: 'Introduction to Information Security', teacher: 'Dr. Muazzam Khattak', edited: false }],
  sessions: [session({}), session({ id: 'a2', day: 'WEDNESDAY', code: 'CS-535', title: 'Cloud DevOps', teacher: 'Dr. Imran', room: '235' })],
  ...o,
})

describe('TimetableAdmin', () => {
  let call
  beforeEach(() => {
    call = vi.fn(async (method, path) => (method === 'GET' && path === '/admin/timetable' ? view() : { ok: true, saved: true }))
    vi.stubGlobal('confirm', vi.fn(() => true))
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('lists the sessions grouped by day with their source and the three modes', async () => {
    const { container } = render(<TimetableAdmin call={call} />)
    expect(await screen.findByText('Weekly sessions')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /PDF \+ my edits/ })).toBeChecked()
    const tableText = () => [...container.querySelectorAll('.tt-day table tbody tr')].map((r) => r.textContent).join('|')
    expect(tableText()).toContain('Introduction to Information Security')
    expect(tableText()).toContain('Cloud DevOps')
    expect([...container.querySelectorAll('.tt-day')].filter((d) => d.querySelector('table')).map((d) => d.querySelector('h4').textContent.split(' ')[0])).toEqual(['Monday', 'Wednesday'])
    expect(screen.getAllByText('PDF').length).toBeGreaterThan(0)
    expect(screen.getByText(/Showing to students/)).toHaveTextContent('2 sessions')
  })

  it('filters by day', async () => {
    const { container } = render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.change(screen.getByLabelText('Day'), { target: { value: 'WEDNESDAY' } })
    const rows = [...container.querySelectorAll('.tt-day table tbody tr')].map((r) => r.textContent)
    expect(rows).toHaveLength(1)
    expect(rows[0]).toContain('Cloud DevOps')
  })

  it('adds a session, then asks before saving a clashing one and saves it only after "Save anyway"', async () => {
    call.mockImplementation(async (method, path, body) => {
      if (method === 'GET') return view()
      if (method === 'POST' && path === '/admin/timetable/sessions') return body.force ? { saved: true, id: 'n1', warnings: [] } : { saved: false, warnings: ['Room 217 is already used by CS-103 ICO S (Monday 1:35-3:05, room 217).'] }
      return { ok: true }
    })
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.click(screen.getByRole('button', { name: '+ Add session' }))
    const form = screen.getByRole('group', { name: 'Add session' })
    fireEvent.change(within(form).getByLabelText('Room'), { target: { value: '217' } })
    fireEvent.change(within(form).getByLabelText('Start time'), { target: { value: '13:35' } })
    fireEvent.change(within(form).getByLabelText('End time'), { target: { value: '15:05' } })
    fireEvent.change(within(form).getByLabelText('Semester'), { target: { value: '8' } })
    fireEvent.change(within(form).getByLabelText('Course code'), { target: { value: 'CS-499' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Add session' }))
    expect(await screen.findByText(/Room 217 is already used/)).toBeInTheDocument()
    const first = call.mock.calls.find(([m, p]) => m === 'POST' && p === '/admin/timetable/sessions')[2]
    expect(first).toMatchObject({ day: 'MONDAY', room: '217', start: '13:35', end: '15:05', semester: 8, code: 'CS-499', force: false })
    fireEvent.click(screen.getByRole('button', { name: 'Save anyway' }))
    await waitFor(() => expect(call.mock.calls.filter(([m, p]) => m === 'POST' && p === '/admin/timetable/sessions')[1][2].force).toBe(true))
    expect(await screen.findByText(/Saved\. Students see the change/)).toBeInTheDocument()
  })

  it('shows a server validation message instead of closing the form', async () => {
    call.mockImplementation(async (method) => { if (method === 'GET') return view(); throw new Error('The end time must be after the start time.') })
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.click(screen.getByRole('button', { name: '+ Add session' }))
    fireEvent.click(within(screen.getByRole('group', { name: 'Add session' })).getByRole('button', { name: 'Add session' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('end time must be after')
    expect(screen.getByRole('group', { name: 'Add session' })).toBeInTheDocument()
  })

  it('editing a PDF class only sends when/where/teacher fields', async () => {
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit' })[0])
    const form = screen.getByRole('group', { name: 'Edit session' })
    expect(within(form).getByLabelText('Course code')).toBeDisabled()
    fireEvent.change(within(form).getByLabelText('Room'), { target: { value: 'Lab 3' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(call).toHaveBeenCalledWith('PUT', '/admin/timetable/sessions/a1', expect.objectContaining({ room: 'Lab 3', force: false })))
    const body = call.mock.calls.find(([m]) => m === 'PUT')[2]
    expect(body).not.toHaveProperty('code')
    expect(body).not.toHaveProperty('program')
  })

  it('hides a PDF class after confirmation and restores a hidden one', async () => {
    call.mockImplementation(async (method, path) => (method === 'GET' && path === '/admin/timetable'
      ? view({ sessions: [session({}), session({ id: 'h1', src: 'hidden', code: 'CS-535', title: 'Cloud DevOps' })], counts: { total: 1, pdf: 1, edited: 0, manual: 0, hidden: 1 } })
      : { ok: true }))
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.click(screen.getByRole('button', { name: 'Hide' }))
    await waitFor(() => expect(call).toHaveBeenCalledWith('DELETE', '/admin/timetable/sessions/a1'))
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }))
    await waitFor(() => expect(call).toHaveBeenCalledWith('POST', '/admin/timetable/sessions/h1/restore'))
  })

  it('does not hide anything when the admin cancels the confirmation', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    fireEvent.click(screen.getAllByRole('button', { name: 'Hide' })[0])
    expect(call.mock.calls.some(([m]) => m === 'DELETE')).toBe(false)
  })

  it('previews an import before applying it, and blocks applying while rows have problems', async () => {
    call.mockImplementation(async (method, path, body) => {
      if (method === 'GET') return view()
      if (path === '/admin/timetable/import') return { ok_rows: 2, error_count: 1, errors: [{ row: 4, message: 'Day must be Monday–Sunday.' }], warnings: [], sample: [], applied: !body.dry_run }
      return { ok: true }
    })
    render(<TimetableAdmin call={call} />)
    await screen.findByText('Weekly sessions')
    const file = new File(['day,start\nMonday,9'], 't.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('Import CSV / Excel'), { target: { files: [file] } })
    expect(await screen.findByText(/Import preview/)).toBeInTheDocument()
    expect(screen.getByText('Row 4')).toBeInTheDocument()
    const apply = screen.getByRole('button', { name: /Import 2 row/ })
    expect(apply).toBeDisabled()
    fireEvent.click(screen.getByLabelText(/Skip the rows with problems/))
    expect(apply).toBeEnabled()
    fireEvent.click(apply)
    await waitFor(() => expect(call.mock.calls.some(([, p, b]) => p === '/admin/timetable/import' && b.dry_run === false && b.skip_errors === true)).toBe(true))
  })

  it('warns about stale edits and switching to manual-only needs confirmation', async () => {
    call.mockImplementation(async (method) => (method === 'GET' ? view({ orphans: [{ id: 'x', kind: 'edited' }] }) : { ok: true }))
    vi.stubGlobal('confirm', vi.fn(() => false))
    render(<TimetableAdmin call={call} />)
    expect(await screen.findByText(/no longer match the current PDF/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: /Manual only/ }))
    expect(call.mock.calls.some(([m]) => m === 'PUT')).toBe(false)
  })

  it('undo is only enabled when there is something to undo', async () => {
    call.mockImplementation(async (method) => (method === 'GET' ? view({ can_undo: true, history: [{ id: 1, at: '2026-10-14T10:00:00Z', by: 'head@qau.edu.pk', action: 'add session', detail: 'TUESDAY CS-499', undone: false }] }) : { ok: true }))
    render(<TimetableAdmin call={call} />)
    const undo = await screen.findByRole('button', { name: /Undo last change/ })
    expect(undo).toBeEnabled()
    fireEvent.click(undo)
    await waitFor(() => expect(call).toHaveBeenCalledWith('POST', '/admin/timetable/undo'))
  })
})
