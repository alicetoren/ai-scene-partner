import { useState } from 'react'
import ScenePlayback from './components/ScenePlayback'
import { validateScriptFile } from './upload'
import { assignCharacterVoices, voicePlaybackKey } from './playback/voiceSettings'

function App() {
  const [file, setFile] = useState(null)
  const [scene, setScene] = useState(null)
  const [selectedCharacter, setSelectedCharacter] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [voiceCategories, setVoiceCategories] = useState({})
  const voiceAssignments = assignCharacterVoices(scene?.characters ?? [], voiceCategories)

  function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null
    setFile(nextFile)
    setError(nextFile ? validateScriptFile(nextFile) : '')
  }

  async function handleAnalyze(event) {
    event.preventDefault()
    const validationError = validateScriptFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setStatus('loading')
    setError('')
    setScene(null)
    setSelectedCharacter('')
    setVoiceCategories({})

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
        <p className="intro">Upload a TXT or text-based PDF script to identify characters and dialogue.</p>

        <form className="upload-form" onSubmit={handleAnalyze}>
          <label htmlFor="script-file">Script (.txt or .pdf)</label>
          <input id="script-file" type="file" accept=".txt,.pdf,text/plain,application/pdf" onChange={handleFileChange} disabled={status === 'loading'} aria-describedby="upload-help" />
          <p id="upload-help" className="intro">Up to 10 MiB. TXT files must use UTF-8. Image-only/scanned PDFs are not supported yet.</p>
          {file && <p>Selected file: <strong>{file.name}</strong></p>}
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

            <ScenePlayback
              key={voicePlaybackKey(selectedCharacter, voiceAssignments)}
              scene={scene}
              actor={selectedCharacter}
              voiceAssignments={voiceAssignments}
              onCategoryChange={(character, category) => setVoiceCategories((previous) => ({ ...previous, [character]: category }))}
            />
          </section>
        )}
      </section>
    </main>
  )
}

export default App
