// A scene-local sliding window, not a persistent audio cache.
const LOOKAHEAD_READERS = 2

function rethrowNetworkFailure(error) {
  // fetch and response body reads report network failures as TypeError.
  if (error instanceof TypeError) error.retryable = true
  throw error
}

function waitForRetry(signal) {
  return new Promise((resolve, reject) => {
    const cancel = () => {
      clearTimeout(timer)
      reject(new DOMException('Canceled recovery', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', cancel)
      resolve()
    }, 500)
    if (signal.aborted) cancel()
    else signal.addEventListener('abort', cancel, { once: true })
  })
}

export function createReaderAudio(scene, actor, {
  request = fetch,
  makeAudio = (url) => new Audio(url),
  createUrl = (blob) => URL.createObjectURL(blob),
  revokeUrl = (url) => URL.revokeObjectURL(url),
  wait = waitForRetry,
} = {}) {
  const entries = new Map()

  function discard(index) {
    const entry = entries.get(index)
    if (!entry) return
    entries.delete(index)
    entry.controller.abort()
    if (entry.audio) {
      entry.audio.onended = null
      entry.audio.onerror = null
      entry.audio.pause()
      entry.audio.removeAttribute('src')
      entry.audio.load()
    }
    if (entry.url) revokeUrl(entry.url)
  }

  function ensure(index) {
    const line = scene.lines[index]
    if (!actor || !line || line.character === actor) return null
    if (entries.has(index)) return entries.get(index)
    const entry = { controller: new AbortController(), audio: null, url: null }
    entries.set(index, entry)
    entry.promise = (async () => {
      const response = await request('/api/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: line.text, voice_index: scene.characters.indexOf(line.character) }),
        signal: entry.controller.signal,
      }).catch(rethrowNetworkFailure)
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const error = new Error(typeof data?.detail === 'string' ? data.detail : 'Speech generation failed. Please retry this line.')
        const hint = response.headers?.get('X-Speech-Retryable')
        error.retryable = hint === 'true' || (!hint && [408, 429, 500, 502, 503, 504].includes(response.status))
        throw error
      }
      const blob = await response.blob().catch(rethrowNetworkFailure)
      if (entries.get(index) !== entry) throw new DOMException('Obsolete audio', 'AbortError')
      if (!blob.size) throw Object.assign(new Error('No audio was returned. Please retry this line.'), { retryable: true })
      entry.url = createUrl(blob)
      entry.audio = makeAudio(entry.url)
      entry.audio.preload = 'auto'
      return entry.audio
    })()
    // Background failures do not retry speculatively. Playback owns bounded recovery.
    entry.promise.catch(() => {})
    return entry
  }

  function forPlayback(index) {
    const entry = ensure(index)
    if (!entry) return null
    if (!entry.playbackPromise) {
      entry.playbackPromise = entry.promise.then((audio) => {
        if (audio.error) throw Object.assign(new Error('Prefetched audio could not be loaded.'), { retryable: true })
        return audio
      }).catch(async (error) => {
        if (!error.retryable || entries.get(index) !== entry) throw error
        await wait(entry.controller.signal)
        if (entries.get(index) !== entry) throw new DOMException('Obsolete recovery', 'AbortError')
        discard(index)
        const replacement = ensure(index)
        // Exactly one replacement. Concurrent consumers share it, even if it fails.
        replacement.playbackPromise = replacement.promise
        return replacement.promise
      })
      entry.playbackPromise.catch(() => {})
    }
    return { audio: entry.audio?.error ? null : entry.audio, promise: entry.playbackPromise }
  }

  function prefetchAfter(index) {
    for (const previous of entries.keys()) if (previous < index) discard(previous)
    let remaining = LOOKAHEAD_READERS
    for (let next = index + 1; next < scene.lines.length && remaining > 0; next += 1) {
      if (scene.lines[next].character === actor) continue
      ensure(next)
      remaining -= 1
    }
  }

  return {
    ensure,
    forPlayback,
    prefetchAfter,
    discard,
    clear: () => { for (const index of entries.keys()) discard(index) },
  }
}
