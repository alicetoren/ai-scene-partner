import { useScenePlayback } from '../hooks/useScenePlayback'

export default function ScenePlayback({ scene, actor }) {
  const playback = useScenePlayback(scene, actor)
  const line = scene.lines[playback.index]
  const messages = {
    idle: actor ? 'Ready. Start the scene when you are comfortable.' : 'Select your character to start.',
    actor: 'Your turn — perform your line, then Continue or press Space.',
    loading: 'Preparing the reader’s audio…',
    playing: 'Listen — the reader is speaking.',
    'reader-ready': 'Reader finished. Continue or press Space for the next line, or replay.',
    'audio-blocked': 'Press Play Reader Line to start the audio.',
    'speech-error': 'Audio unavailable. Retry this reader line or restart the scene.',
    complete: 'Scene complete. Well done — you can restart for another run.',
  }

  return (
    <>
      <section className="playback" aria-label="Scene playback">
        <p className="intro">The reader voice is AI-generated. Advance manually after each line.</p>
        <p role="status">{messages[playback.phase]}</p>
        {line && (
          <div className="active-line">
            <strong>Line {playback.index + 1} of {scene.lines.length} · {line.character} · {line.character === actor ? 'You' : 'Reader'}</strong>
            <p>{line.text}</p>
          </div>
        )}
        {playback.error && <p role="alert" className="status--error">{playback.error}</p>}
        <div className="playback-actions">
          {playback.phase === 'idle' && <button disabled={!actor} onClick={playback.start}>Start Scene</button>}
          {playback.canContinue && <button onClick={playback.advance}>Continue</button>}
          {playback.phase === 'reader-ready' && <button onClick={playback.replay}>Replay Reader Line</button>}
          {playback.phase === 'audio-blocked' && <button onClick={playback.replay}>Play Reader Line</button>}
          {playback.phase === 'speech-error' && <button onClick={playback.retry}>Retry Reader Line</button>}
          {playback.phase !== 'idle' && <button onClick={playback.restart}>Restart Scene</button>}
        </div>
      </section>
      <h3>Dialogue</h3>
      <ol className="dialogue">
        {scene.lines.map((dialogue, index) => (
          <li
            className={[dialogue.character === actor ? 'actor-line' : '', index === playback.index ? 'current-line' : ''].join(' ')}
            aria-current={index === playback.index ? 'step' : undefined}
            key={dialogue.id}
          >
            <strong>{dialogue.character}{dialogue.character === actor ? ' · You' : ' · Reader'}{index === playback.index ? ' · Current line' : ''}</strong>
            <span>{dialogue.text}</span>
          </li>
        ))}
      </ol>
    </>
  )
}
