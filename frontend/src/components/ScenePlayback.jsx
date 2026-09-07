import { useEffect, useRef } from 'react'
import { useScenePlayback } from '../hooks/useScenePlayback'
import { VOICE_CATEGORIES } from '../playback/voiceSettings'
import { dialogueScrollTop } from '../playback/dialogueScroll'

export default function ScenePlayback({ scene, actor, voiceAssignments, onCategoryChange }) {
  const playback = useScenePlayback(scene, actor, voiceAssignments)
  const scriptRef = useRef(null)
  const currentLineRef = useRef(null)

  // Follow explicit line changes only. Audio phase updates never interrupt browsing
  // or move keyboard focus, and scrolling stays inside the script panel.
  useEffect(() => {
    const script = scriptRef.current
    const line = currentLineRef.current
    if (!script) return
    if (playback.index < 0) {
      script.scrollTop = 0
    } else if (line) {
      const lineTop = line.getBoundingClientRect().top - script.getBoundingClientRect().top + script.scrollTop
      script.scrollTop = dialogueScrollTop(lineTop, script.clientHeight, script.scrollHeight)
    }
  }, [playback.index])

  const messages = {
    idle: actor ? 'Ready when you are.' : 'Choose your character to start.',
    actor: 'Your turn. Take your time.',
    loading: 'Preparing the reader’s audio…',
    playing: 'Listen — the reader is speaking.',
    'reader-ready': 'Reader finished. Your cue to continue.',
    'audio-blocked': 'Press Play Reader Line to start the audio.',
    'speech-error': 'Audio unavailable. Retry this reader line or restart the scene.',
    complete: 'Scene complete. Ready for another run?',
  }

  return (
    <div className="scene-player" ref={playback.playerRef}>
      <aside className="setup-panel" aria-label="Character and reader setup">
        <fieldset className="reader-voices" disabled={playback.phase !== 'idle'}>
          <legend>Reader voices</legend>
          {scene.characters.map((character, index) => (
            <div className="voice-row" key={character}>
              {character === actor ? <p><strong>{character}</strong><span className="role-note">You · No AI speech</span></p> : (
                <>
                  <label htmlFor={`reader-voice-${index}`}><strong>{character}</strong><span className="role-note">AI reader</span></label>
                  <select id={`reader-voice-${index}`} value={voiceAssignments[character].voice_category} onChange={(event) => onCategoryChange(character, event.target.value)}>
                    {VOICE_CATEGORIES.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </>
              )}
            </div>
          ))}
        </fieldset>
        <p className="muted">Voice categories describe approximate sound, not character gender. Neutral / Any uses a mixed palette.</p>
        {playback.phase !== 'idle' && <p className="muted">Restart scene to change reader voices.</p>}
      </aside>
      <section className="script-panel" aria-label="Scene playback">
        <header className="script-heading"><h2>Scene dialogue</h2><span>{playback.index >= 0 ? `Line ${playback.index + 1} of ${scene.lines.length}` : `${scene.lines.length} lines`}</span></header>
        <div className="script-scroll" ref={scriptRef} tabIndex={0} role="region" aria-label="Scene dialogue. Use arrow keys to browse; Space advances during a scene.">
          <ol className="dialogue">
            {scene.lines.map((dialogue, index) => (
              <li
                ref={index === playback.index ? currentLineRef : null}
                className={[dialogue.character === actor ? 'actor-line' : '', index === playback.index ? 'current-line' : ''].join(' ')}
                aria-current={index === playback.index ? 'step' : undefined}
                key={dialogue.id}
              >
                <div className="line-label"><span className="line-number" aria-hidden="true">{index + 1}</span><strong>{dialogue.character} · {dialogue.character === actor ? 'You' : 'Reader'}{index === playback.index ? ' · Current line' : ''}</strong></div>
                <p>{dialogue.text}</p>
              </li>
            ))}
          </ol>
        </div>
        <div className="playback">
          <div className="playback-message">
            <p role="status">{messages[playback.phase]}{playback.index >= 0 && <span className="sr-only"> Line {playback.index + 1} of {scene.lines.length}. {scene.lines[playback.index].character}.</span>}</p>
            <p className="muted">{playback.canContinue ? 'Press Space or Continue when you’re ready.' : playback.phase === 'complete' ? 'Restart scene to return to setup.' : 'AI-generated reader voices. Advance manually after each line.'}</p>
          </div>
          {playback.error && <p role="alert" className="status--error">{playback.error}</p>}
          <div className="playback-actions">
            {playback.phase === 'idle' && <button disabled={!actor} onClick={playback.start}>Start scene <span aria-hidden="true">→</span></button>}
            {playback.canContinue && <button onClick={playback.advance}>Continue <span aria-hidden="true">→</span></button>}
            {playback.phase === 'reader-ready' && <button className="secondary" onClick={playback.replay}>Replay Reader Line</button>}
            {playback.phase === 'audio-blocked' && <button onClick={playback.replay}>Play Reader Line</button>}
            {playback.phase === 'speech-error' && <button onClick={playback.retry}>Retry Reader Line</button>}
            {playback.phase !== 'idle' && <button className="secondary" onClick={playback.restart}>Restart scene</button>}
          </div>
        </div>
      </section>
    </div>
  )
}
