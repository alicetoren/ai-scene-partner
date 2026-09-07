import { useEffect, useRef, useState } from 'react'
import { createReaderAudio } from '../playback/readerAudio.js'
import { handlePlayerSpace } from '../playback/keyboard.js'

const initialState = { phase: 'idle', index: -1, error: '' }
const canContinue = (phase) => phase === 'actor' || phase === 'reader-ready'

export function useScenePlayback(scene, actor, voiceAssignments, loadAudio) {
  const [state, setState] = useState(initialState)
  // Synchronous guards prevent rapid clicks racing React's next render.
  const current = useRef(initialState)
  const resources = useRef({ generation: 0, audio: null })
  const buffer = useRef(null)
  const playerRef = useRef(null)
  if (!buffer.current) buffer.current = createReaderAudio(scene, actor, { voiceAssignments, loadAudio })

  function transition(next) {
    current.current = next
    setState(next)
  }

  function stop() {
    const r = resources.current
    r.generation += 1
    if (r.audio) {
      r.audio.onended = null
      r.audio.onerror = null
      r.audio.pause()
      r.audio = null
    }
  }

  function release() {
    stop()
    buffer.current.clear()
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

  function playReader(index) {
    const entry = buffer.current.forPlayback(index)
    if (!entry) return
    const generation = resources.current.generation
    transition({ phase: 'loading', index, error: '' })
    function ready(audio) {
      if (generation !== resources.current.generation) return
      if (audio.error) {
        buffer.current.discard(index)
        transition({ phase: 'speech-error', index, error: 'Audio could not be loaded. Please retry this line.' })
        return
      }
      resources.current.audio = audio
      audio.onended = () => {
        if (generation === resources.current.generation) transition({ phase: 'reader-ready', index, error: '' })
      }
      audio.onerror = () => {
        if (generation !== resources.current.generation) return
        stop()
        buffer.current.discard(index)
        transition({ phase: 'speech-error', index, error: 'Audio could not be played. Please retry this line.' })
      }
      transition({ phase: 'reader-ready', index, error: '' })
      void playAudio()
    }
    // Ready audio plays directly in the click/key gesture; pending work is shared.
    if (entry.audio) ready(entry.audio)
    else entry.promise.then(ready).catch((error) => {
      if (generation !== resources.current.generation) return
      transition({ phase: 'speech-error', index, error: error.message || 'Speech request failed. Please retry this line.' })
    })
  }

  function enterLine(index) {
    stop()
    if (index >= scene.lines.length) {
      buffer.current.clear()
      transition({ phase: 'complete', index: -1, error: '' })
      return
    }
    if (scene.lines[index].character === actor) transition({ phase: 'actor', index, error: '' })
    else playReader(index)
    // Keep current audio for replay and the next two readers, skipping actor lines.
    buffer.current.prefetchAfter(index)
  }

  function advance() {
    if (canContinue(current.current.phase)) enterLine(current.current.index + 1)
  }

  useEffect(() => {
    function onKeyDown(event) {
      handlePlayerSpace(event, playerRef.current, current.current.phase !== 'idle', advance)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  return {
    ...state,
    playerRef,
    canContinue: canContinue(state.phase),
    start: () => { if (actor && current.current.phase === 'idle') enterLine(0) },
    restart: () => { release(); transition(initialState) },
    advance,
    replay: playAudio,
    retry: () => {
      if (current.current.phase !== 'speech-error') return
      buffer.current.discard(current.current.index)
      playReader(current.current.index)
    },
  }
}
