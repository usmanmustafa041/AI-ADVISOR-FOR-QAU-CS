import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Node 25 exposes a partial global localStorage; supply the Storage contract.
const stored = new Map()
vi.stubGlobal('localStorage', {
  getItem: key => stored.get(String(key)) ?? null,
  setItem: (key, value) => stored.set(String(key), String(value)),
  removeItem: key => stored.delete(String(key)),
  clear: () => stored.clear(),
  key: index => [...stored.keys()][index] ?? null,
  get length() { return stored.size },
})

