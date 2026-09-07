import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createDemoAudioLoader } from '../src/demo/audio.js'
import { createReaderAudio } from '../src/playback/readerAudio.js'

const scene = JSON.parse(readFileSync(new URL('../src/demo/sample.json', import.meta.url)))
const wav = new Uint8Array(46)
wav.set(new TextEncoder().encode('RIFF'), 0)
wav.set(new TextEncoder().encode('WAVE'), 8)
const audioBlob = new Blob([wav])
function harness(actor, request) {
  let liveCalls = 0
  const revoked = []
  const buffer = createReaderAudio(scene, actor, {
    loadAudio: createDemoAudioLoader(scene, { baseUrl: '/portfolio/', request }),
    request: () => { liveCalls++; throw new Error('Live API must never be called') },
    makeAudio: () => ({ pause() {}, removeAttribute() {}, load() {} }),
    createUrl: () => 'blob:demo', revokeUrl: url => revoked.push(url), wait: async () => {},
  })
  return { buffer, revoked, liveCalls: () => liveCalls }
}

test('sample is eight ordered original turns with audio slots for both roles', () => {
  assert.equal(scene.characters.length, 2)
  assert.deepEqual(scene.lines.map(line => line.id), [1,2,3,4,5,6,7,8])
  for (const character of scene.characters) assert.equal(scene.lines.filter(line => line.character === character).length, 4)
})

test('both roles stay silent on their own turns; prefetch/replay use only static assets', async () => {
  for (const actor of scene.characters) {
    const calls = []
    const h = harness(actor, async (url, options) => { calls.push({url, options}); return { ok:true, blob:async()=>audioBlob } })
    const reader = scene.lines.findIndex(line => line.character !== actor)
    const actorLine = scene.lines.findIndex(line => line.character === actor)
    assert.equal(h.buffer.ensure(actorLine), null)
    h.buffer.prefetchAfter(-1)
    const entry = h.buffer.forPlayback(reader)
    const audio = await entry.promise
    const count = calls.length
    assert.equal(h.buffer.forPlayback(reader).audio, audio)
    assert.equal(calls.length, count)
    assert(calls.every(call => call.url.startsWith('/portfolio/demo/audio/line-') && call.options.redirect === 'error'))
    h.buffer.clear()
    assert(calls.every(call => call.options.signal.aborted))
    assert(h.revoked.length > 0)
    assert.equal(h.liveCalls(), 0)
  }
})

for (const failure of ['404', 'html', 'empty', 'network']) {
  test(`missing/invalid asset (${failure}) fails closed, including manual retry`, async () => {
    let assetCalls = 0
    const h = harness('NORA', async () => {
      assetCalls++
      if (failure === 'network') throw new TypeError('Offline')
      return { ok: failure !== '404', blob: async () => new Blob([failure === 'html' ? '<html>Fallback</html>' : '']) }
    })
    await assert.rejects(h.buffer.forPlayback(1).promise, /Prepared sample audio is unavailable/)
    assert.equal(assetCalls, 1) // No background recovery loop.
    h.buffer.discard(1)
    await assert.rejects(h.buffer.forPlayback(1).promise, /cannot generate replacement audio/)
    assert.equal(assetCalls, 2)
    assert.equal(h.liveCalls(), 0)
    h.buffer.clear()
  })
}

test('restart aborts static work and stale audio cannot populate the buffer', async () => {
  let finish
  const h = harness('NORA', () => new Promise(resolve => { finish = resolve }))
  const entry = h.buffer.forPlayback(1)
  h.buffer.clear()
  finish({ok:true, blob:async()=>audioBlob})
  await assert.rejects(entry.promise, {name:'AbortError'})
  assert.equal(h.liveCalls(), 0)
})

test('unknown lines cannot form asset paths or initiate a request', async () => {
  let calls = 0
  const loader = createDemoAudioLoader(scene, {request:()=>{calls++}})
  await assert.rejects(loader({id:'../../api/speech', text:'x', character:'NORA'}), /unavailable/)
  assert.equal(calls, 0)
})
