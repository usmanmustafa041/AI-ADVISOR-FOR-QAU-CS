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

  it('renders authenticated chat, verified-source notice, and Urdu toggle', () => {
    localStorage.setItem('qau-auth', JSON.stringify(studentAuth))
    render(<App />)
    expect(screen.getByText('Mixed knowledge base')).toBeInTheDocument()
    expect(screen.getByText('Demonstration mode')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask an academic question/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'اردو' })).toBeInTheDocument()
  })
})
