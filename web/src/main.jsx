import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import Admin from './Admin'
import Chat from './Chat'
import './styles.css'

function Root() {
  const [route, setRoute] = useState(window.location.hash)
  useEffect(() => {
    const on = () => setRoute(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route.startsWith('#/admin') ? <Admin /> : <Chat />
}

createRoot(document.getElementById('root')).render(<StrictMode><Root /></StrictMode>)
