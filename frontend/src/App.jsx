import { useEffect, useState } from 'react'

function App() {
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('Connecting to the backend…')

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch('/api/health')

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`)
        }

        const data = await response.json()
        setMessage(data.message)
        setStatus('success')
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Unable to reach the backend.')
        setStatus('error')
      }
    }

    checkBackend()
  }, [])

  return (
    <main className="page">
      <section className="status-card" aria-live="polite">
        <p className="eyebrow">AI Scene Partner</p>
        <h1>Frontend ↔ backend connection</h1>
        <p className={`status status--${status}`}>
          {status === 'loading' && 'Loading: '}
          {status === 'error' && 'Connection error: '}
          {message}
        </p>
      </section>
    </main>
  )
}

export default App
