import { useState } from 'react'
import ScenePlayback from './components/ScenePlayback'

function App() {
  const [file, setFile] = useState(null)
  const [scene, setScene] = useState(null)
  const [selectedCharacter, setSelectedCharacter] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null
    setFile(nextFile)
    setError('')
  }

  async function handleAnalyze(event) {
    event.preventDefault()
    if (!file) {
      setError('Choose a .txt script before analyzing.')
      return
    }

    setStatus('loading')
    setError('')
    setScene(null)
    setSelectedCharacter('')

    const formData = new FormData()
    formData.append('script_file', file)

    try {
      const response = await fetch('/api/scenes/parse', { method: 'POST', body: formData })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'The script could not be analyzed.')
      }

      setScene(data)
      setStatus('success')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'The script could not be analyzed.')
      setStatus('error')
    }
  }

  return (
    <main className="page">
      <section className="status-card">
        <p className="eyebrow">AI Scene Partner</p>
        <h1>Turn your script into a practice scene.</h1>
        <p className="intro">Upload a UTF-8 plain-text script to identify characters and dialogue.</p>

        <form className="upload-form" onSubmit={handleAnalyze}>
          <label htmlFor="script-file">Plain-text script (.txt)</label>
          <input id="script-file" type="file" accept=".txt,text/plain" onChange={handleFileChange} />
          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'Analyzing script…' : 'Analyze Script'}
          </button>
        </form>

        {error && <p className="status status--error" role="alert">{error}</p>}

        {scene && (
          <section className="scene" aria-live="polite">
            <h2>{scene.title}</h2>
            <label htmlFor="actor-character">I am playing</label>
            <select
              id="actor-character"
              value={selectedCharacter}
              onChange={(event) => setSelectedCharacter(event.target.value)}
            >
              <option value="">Select a character</option>
              {scene.characters.map((character) => <option key={character} value={character}>{character}</option>)}
            </select>

            <h3>Detected characters</h3>
            <div className="characters">
              {scene.characters.map((character) => <span key={character}>{character}</span>)}
            </div>

            <ScenePlayback key={selectedCharacter} scene={scene} actor={selectedCharacter} />
          </section>
        )}
      </section>
    </main>
  )
}

export default App
