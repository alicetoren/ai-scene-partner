import { useState } from 'react'
import ScenePlayback from './components/ScenePlayback'
import { validateScriptFile } from './upload'
import { assignCharacterVoices, voicePlaybackKey } from './playback/voiceSettings'

function App() {
  const [file, setFile] = useState(null)
  const [scene, setScene] = useState(null)
  const [sceneFilename, setSceneFilename] = useState('')
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

      setSceneFilename(file.name)
      setScene(data)
      setStatus('success')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'The script could not be analyzed.')
      setStatus('error')
    }
  }

  const uploadForm = (
    <form className="upload-form" onSubmit={handleAnalyze} aria-busy={status === 'loading'}>
      <label className="upload-label" htmlFor="script-file">Upload your script</label>
      <div className="file-picker">
        <p className="file-types">TXT or PDF <span aria-hidden="true">·</span> Up to 10 MiB</p>
        <input id="script-file" type="file" accept=".txt,.pdf,text/plain,application/pdf" onChange={handleFileChange} disabled={status === 'loading'} aria-describedby="upload-help" />
        {file && <p className="selected-file">Selected: <strong>{file.name}</strong></p>}
        <p id="upload-help" className="muted">TXT files must use UTF-8. Text-based PDFs only; image-only/scanned PDFs are not supported.</p>
      </div>
      <button type="submit" disabled={status === 'loading'}>
        {status === 'loading' ? 'Preparing your scene…' : 'Prepare scene'}
        {status !== 'loading' && <span aria-hidden="true"> →</span>}
      </button>
      <p className="muted">AI-generated reader voices. Your lines stay silent.</p>
    </form>
  )

  return (
    <div className="app-shell">
      <header className="product-bar">
        <div className="brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 10v4m4-8v12m4-15v18m4-15v12m4-8v4" /></svg></span>AI Scene Partner</div>
        <p>A little support. More time in the scene.</p>
      </header>
      <main className="page">
        <section className={scene ? 'scene-heading' : 'onboarding'} aria-label={scene ? 'Prepared scene' : 'Prepare your scene'}>
          {scene ? (
            <div><p className="eyebrow">Your scene</p><h1>{scene.title}</h1><p className="scene-meta">{sceneFilename} · {scene.characters.length} characters · {scene.lines.length} lines</p></div>
          ) : (
            <div className="welcome">
              <p className="eyebrow">Meet your new line reader</p>
              <h1>Ready to{' '}<br />run lines?</h1>
              <p className="intro">Choose your character. Your AI scene partner reads the other parts.</p>
              <ol className="workflow"><li><span>01 / Upload</span>Bring your script</li><li><span>02 / Choose</span>Pick your part</li><li><span>03 / Play</span>Start your scene</li></ol>
            </div>
          )}
          <details className={scene ? 'replace-script' : 'upload-panel'} open={scene ? undefined : true}>
            <summary hidden={!scene}>Upload another script</summary>
            {uploadForm}
          </details>
        </section>
        <p className={status === 'success' ? 'sr-only' : 'analysis-status'} role="status">{status === 'loading' ? 'Preparing your scene… Characters and dialogue will appear when ready.' : status === 'success' ? 'Scene prepared. Choose your character below.' : ''}</p>
        {error && <p className="status--error upload-error" role="alert">{error}</p>}
        {scene && (
          <div className="scene-workspace">
            <section className="character-panel" aria-label="Your character">
              <h2 className="eyebrow">Your cast</h2>
              <div className="character-control">
                <label htmlFor="actor-character">Who are you playing?</label>
                <select id="actor-character" value={selectedCharacter} onChange={(event) => setSelectedCharacter(event.target.value)}>
                  <option value="">Select a character</option>
                  {scene.characters.map((character) => <option key={character} value={character}>{character}</option>)}
                </select>
                <p className="muted">Your lines stay silent.</p>
              </div>
            </section>
            <ScenePlayback
              key={voicePlaybackKey(selectedCharacter, voiceAssignments)}
              scene={scene}
              actor={selectedCharacter}
              voiceAssignments={voiceAssignments}
              onCategoryChange={(character, category) => setVoiceCategories((previous) => ({ ...previous, [character]: category }))}
            />
          </div>
        )}
      </main>
      <footer className="product-footer"><span>Made for the work between auditions.</span><span>AI voices · Manual line progression</span></footer>
    </div>
  )
}

export default App
