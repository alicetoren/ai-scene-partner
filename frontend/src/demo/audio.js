// Only bundled assets are eligible. There is deliberately no generation fallback.
export function createDemoAudioLoader(scene, { baseUrl = '/', request = fetch } = {}) {
  const lines = new Map(scene.lines.map((line) => [line.id, line]))
  return async (line, signal) => {
    try {
      const prepared = lines.get(line.id)
      if (!prepared || prepared.text !== line.text || prepared.character !== line.character) throw new Error('Unknown sample line')
      const response = await request(`${baseUrl}demo/audio/line-${line.id}.wav`, {
        signal, credentials: 'omit', redirect: 'error',
      })
      if (!response.ok) throw new Error('Missing sample audio')
      const blob = await response.blob()
      // Static hosts can return index.html with HTTP 200 for a missing file.
      const header = new TextDecoder().decode(await blob.slice(0, 12).arrayBuffer())
      if (blob.size <= 44 || !header.startsWith('RIFF') || header.slice(8, 12) !== 'WAVE') throw new Error('Invalid sample audio')
      return blob
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw Object.assign(new Error('Prepared sample audio is unavailable. Retry to reload the bundled file. This demo cannot generate replacement audio.'), { retryable: false })
    }
  }
}
