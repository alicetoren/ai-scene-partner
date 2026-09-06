import { useEffect, useRef, useState } from 'react'

const initialState = { phase: 'idle', index: -1, error: '' }
const canContinue = (phase) => phase === 'actor' || phase === 'reader-ready'

export function useScenePlayback(scene, actor) {
  const [state, setState] = useState(initialState)
  // The ref is updated synchronously so rapid clicks cannot race React's render.
  const current = useRef(initialState)
  const resources = useRef({ generation: 0, controller: null, audio: null, url: null })

  function transition(next) {
    current.current = next
    setState(next)
  }

  function release() {
    const r = resources.current
    r.generation += 1
    r.controller?.abort()
    r.controller = null
    if (r.audio) {
      r.audio.onended = null
      r.audio.onerror = null
      r.audio.pause()
      r.audio.removeAttribute('src')
      r.audio.load()
      r.audio = null
    }
    if (r.url) URL.revokeObjectURL(r.url)
    r.url = null
  }

  useEffect(() => () => release(), [])

  async function playAudio() {
    const r = resources.current
    const audio = r.audio
    if (!audio || ['loading', 'playing'].includes(current.current.phase)) return
    const generation = r.generation
    const index = current.current.index
    transition({ phase: 'playing', index, error: '' })
    audio.currentTime = 0
    try {
      await audio.play()
    } catch {
      if (generation === r.generation) {
        transition({ phase: 'audio-blocked', index, error: 'Playback could not start. Press Play Reader Line to try again.' })
      }
    }
  }

  async function generate(index) {
    const line = scene.lines[index]
    // This guard is also enforced at entry: actor text never reaches the API.
    if (!line || line.character === actor) return
    release()
    const r = resources.current
    const generation = r.generation
    const controller = new AbortController()
    r.controller = controller
    transition({ phase: 'loading', index, error: '' })
    try {
      const response = await fetch('/api/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: line.text }),
        signal: controller.signal,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'Speech generation failed. Please retry this line.')
      }
      const blob = await response.blob()
      if (generation !== r.generation) return
      if (!blob.size) throw new Error('No audio was returned. Please retry this line.')
      r.url = URL.createObjectURL(blob)
      r.audio = new Audio(r.url)
      r.audio.onended = () => {
        if (generation === r.generation) transition({ phase: 'reader-ready', index, error: '' })
      }
      r.audio.onerror = () => {
        if (generation !== r.generation) return
        release()
        transition({ phase: 'speech-error', index, error: 'Audio could not be played. Please retry this line.' })
      }
      transition({ phase: 'reader-ready', index, error: '' })
      await playAudio()
    } catch (error) {
      if (generation !== r.generation) return
      transition({ phase: 'speech-error', index, error: error.message || 'Speech request failed. Please retry this line.' })
    }
  }

  function enterLine(index) {
    release()
    if (index >= scene.lines.length) {
      transition({ phase: 'complete', index: -1, error: '' })
    } else if (scene.lines[index].character === actor) {
      transition({ phase: 'actor', index, error: '' })
    } else {
      void generate(index)
    }
  }

  function advance() {
    if (canContinue(current.current.phase)) enterLine(current.current.index + 1)
  }

  useEffect(() => {
    function onKeyDown(event) {
      if (event.code !== 'Space' || event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      if (event.target instanceof Element && event.target.closest('button, input, select, textarea, a, [contenteditable]')) return
      if (!canContinue(current.current.phase)) return
      event.preventDefault()
      advance()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  return {
    ...state,
    canContinue: canContinue(state.phase),
    start: () => { if (current.current.phase === 'idle') enterLine(0) },
    restart: () => { release(); transition(initialState) },
    advance,
    replay: playAudio,
    retry: () => { if (current.current.phase === 'speech-error') void generate(current.current.index) },
  }
}
