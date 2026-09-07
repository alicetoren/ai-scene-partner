import { readFile } from 'node:fs/promises'
const root = new URL('../', import.meta.url)
const scene = JSON.parse(await readFile(new URL('src/demo/sample.json', root), 'utf8'))
const missing = []
for (const line of scene.lines) {
  const name = `public/demo/audio/line-${line.id}.wav`
  try {
    const bytes = await readFile(new URL(name, root))
    if (bytes.length <= 44 || bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WAVE') throw new Error('Invalid WAV')
  } catch { missing.push(name) }
}
if (missing.length) {
  console.error(`Demo audio is missing or invalid (${missing.length} files):\n${missing.join('\n')}\nGenerate and listen to all sample audio before publishing.`)
  process.exitCode = 1
} else console.log(`All ${scene.lines.length} sample WAV files are present. Listen to both roles before publishing.`)
