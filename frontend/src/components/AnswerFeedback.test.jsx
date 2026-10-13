import React from 'react'
import { fireEvent, render, screen, cleanup } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AnswerFeedback } from './AnswerFeedback'

afterEach(cleanup)

it('sends the selected issue and lets the owner remove feedback', async () => {
  const request = vi.fn().mockResolvedValue({ saved: true })
  render(<AnswerFeedback messageId="answer-uuid" request={request} />)
  fireEvent.change(screen.getByRole('combobox', { name: 'Feedback reason' }), { target: { value: 'outdated' } })
  fireEvent.click(screen.getByRole('button', { name: 'Report issue' }))
  await screen.findByText('Feedback saved')
  expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({ rating: -1, reason: 'outdated' })
  fireEvent.click(screen.getByRole('button', { name: 'Remove feedback' }))
  await screen.findByText('Feedback removed')
  expect(request.mock.calls[1]).toEqual(['/feedback/answer-uuid', { method: 'DELETE' }])
})

it('reports an API error without claiming the vote was saved', async () => {
  render(<AnswerFeedback messageId="answer-uuid" request={vi.fn().mockRejectedValue(new Error('Feedback unavailable'))} />)
  fireEvent.click(screen.getByRole('button', { name: 'Helpful' }))
  await screen.findByText('Feedback unavailable')
  expect(screen.queryByText('Feedback saved')).not.toBeInTheDocument()
})
