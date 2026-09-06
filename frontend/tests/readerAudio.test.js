import test from 'node:test'
import assert from 'node:assert/strict'
import { createReaderAudio } from '../src/playback/readerAudio.js'

const scene = {
  characters: ['ACTOR', 'B', 'C'],
  lines: [
    { character: 'ACTOR', text: 'My first line' },
    { character: 'B', text: 'B one' },
    { character: 'C', text: 'C one' },
    { character: 'ACTOR', text: 'My second line' },
    { character: 'B', text: 'B two' },
    { character: 'C', text: 'C two' },
  ],
}

function harness(actor = 'ACTOR', wait = async () => {}) {
  const calls = []
  const urls = []
  const revoked = []
  const buffer = createReaderAudio(scene, actor, {
    request: (url, options) => new Promise((resolve, reject) => calls.push({
      body: JSON.parse(options.body), signal: options.signal, reject,
      finish: () => resolve({ ok: true, blob: async () => new Blob(['audio']) }),
      disconnectBody: () => resolve({ ok: true, blob: async () => { throw new TypeError('Connection lost') } }),
      fail: (status = 502, retryable = 'true') => resolve({
        ok: false, status, headers: { get: () => retryable }, json: async () => ({ detail: 'Speech failed' }),
      }),
    })),
    createUrl: () => { const url = `blob:${urls.length}`; urls.push(url); return url },
    revokeUrl: (url) => revoked.push(url),
    makeAudio: () => ({ pause() { this.stopped = true }, removeAttribute() {}, load() {} }),
    wait,
  })
  return { buffer, calls, urls, revoked }
}

// These tests use Node's built-in runner and fake audio/network boundaries.
// No React/browser test framework or real OpenAI requests are needed.
test('actor lines never generate speech, including lookahead across actor turns', async () => {
  const { buffer, calls } = harness()
  assert.equal(buffer.ensure(0), null)
  assert.equal(buffer.ensure(3), null)
  buffer.prefetchAfter(0)
  assert.deepEqual(calls.map((call) => call.body.text), ['B one', 'C one'])
  calls.forEach((call) => call.finish())
  await Promise.all([buffer.ensure(1).promise, buffer.ensure(2).promise])
  buffer.prefetchAfter(2)
  assert.deepEqual(calls.map((call) => call.body.text), ['B one', 'C one', 'B two', 'C two'])
  buffer.clear()
})

test('prefetch and foreground share pending work and replay reuses the same audio', async () => {
  const { buffer, calls } = harness()
  buffer.prefetchAfter(0)
  const prefetched = buffer.ensure(1)
  const foreground = buffer.ensure(1)
  assert.equal(prefetched, foreground)
  assert.equal(calls.length, 2)
  calls[0].finish()
  const audio = await foreground.promise
  assert.equal(buffer.ensure(1).audio, audio)
  assert.equal(buffer.ensure(1), prefetched)
  assert.equal(calls.length, 2)
  buffer.clear()
})

test('line request on cache miss shares a single request', async () => {
  const { buffer, calls } = harness()
  const entry = buffer.ensure(4)
  assert.equal(buffer.ensure(4).promise, entry.promise)
  assert.equal(calls.length, 1)
  calls[0].finish()
  await entry.promise
  buffer.clear()
})

test('character index remains stable across lines and actor changes', () => {
  const first = harness()
  first.buffer.ensure(1)
  first.buffer.ensure(4)
  first.buffer.ensure(2)
  assert.deepEqual(first.calls.map((call) => call.body.voice_index), [1, 1, 2])
  const second = harness('C')
  second.buffer.ensure(1)
  assert.equal(second.calls[0].body.voice_index, 1)
  assert.equal(second.buffer.ensure(2), null)
  first.buffer.clear()
  second.buffer.clear()
})

test('lookahead is bounded and advancing evicts older audio but preserves upcoming audio', async () => {
  const { buffer, calls, revoked } = harness()
  const current = buffer.ensure(1)
  buffer.prefetchAfter(1)
  assert.deepEqual(calls.map((call) => call.body.text), ['B one', 'C one', 'B two'])
  calls.forEach((call) => call.finish())
  await Promise.all([current.promise, buffer.ensure(2).promise, buffer.ensure(4).promise])
  const upcoming = buffer.ensure(2).audio
  buffer.prefetchAfter(2)
  assert.equal(current.audio.stopped, true)
  assert.equal(revoked.length, 1)
  assert.equal(buffer.ensure(2).audio, upcoming)
  buffer.prefetchAfter(3)
  assert.equal(calls.length, 4)
  buffer.clear()
})

test('restart/unmount aborts pending work and ignores late responses without leaking URLs', async () => {
  const { buffer, calls, urls, revoked } = harness()
  const ready = buffer.ensure(1)
  calls[0].finish()
  await ready.promise
  const pending = buffer.ensure(2)
  buffer.clear()
  assert.ok(calls.every((call) => call.signal.aborted))
  assert.deepEqual(revoked, urls)
  calls[1].finish()
  await assert.rejects(pending.promise, { name: 'AbortError' })
  assert.equal(urls.length, 1)
  assert.equal(ready.audio.stopped, true)
})

test('failed prefetch recovers on demand without a manual retry or duplicate generation', async () => {
  const { buffer, calls } = harness()
  const failed = buffer.ensure(1)
  calls[0].reject(new TypeError('offline'))
  await assert.rejects(failed.promise, /offline/)
  buffer.prefetchAfter(0)
  assert.equal(buffer.ensure(1), failed)
  assert.equal(calls.length, 2)
  const playback = buffer.forPlayback(1)
  assert.equal(buffer.forPlayback(1).promise, playback.promise)
  await new Promise(setImmediate)
  assert.equal(calls.length, 3)
  const retry = buffer.forPlayback(1)
  calls[2].finish()
  assert.equal(await playback.promise, await retry.promise)
  assert.equal(buffer.forPlayback(1).audio, await playback.promise)
  assert.equal(calls.length, 3)
  buffer.clear()
})

test('no character selection means no billable requests', () => {
  const { buffer, calls } = harness('')
  buffer.prefetchAfter(-1)
  assert.equal(buffer.ensure(1), null)
  assert.equal(buffer.forPlayback(1), null)
  assert.equal(calls.length, 0)
})

test('a pending prefetch that fails after advancement shares one foreground recovery', async () => {
  const { buffer, calls } = harness()
  buffer.ensure(1)
  const playback = buffer.forPlayback(1)
  calls[0].fail()
  await new Promise(setImmediate)
  assert.equal(calls.length, 2)
  calls[1].finish()
  const audio = await playback.promise
  assert.equal(buffer.forPlayback(1).audio, audio)
  buffer.clear()
})

test('cold on-demand failure gets at most one automatic retry, then a controlled error', async () => {
  const { buffer, calls } = harness()
  const playback = buffer.forPlayback(1)
  calls[0].fail()
  await new Promise(setImmediate)
  const shared = buffer.forPlayback(1)
  calls[1].fail()
  await assert.rejects(playback.promise, /Speech failed/)
  await assert.rejects(shared.promise, /Speech failed/)
  await assert.rejects(buffer.forPlayback(1).promise, /Speech failed/)
  assert.equal(calls.length, 2)
  buffer.clear()
})

test('permanent errors never automatically retry even if the HTTP status is 502', async () => {
  for (const status of [400, 401, 422, 502, 503]) {
    const { buffer, calls } = harness()
    const playback = buffer.forPlayback(1)
    calls[0].fail(status, 'false')
    await assert.rejects(playback.promise, /Speech failed/)
    assert.equal(calls.length, 1)
    buffer.clear()
  }
})

test('restart during recovery backoff prevents a replacement request', async () => {
  let resume
  let signal
  const { buffer, calls } = harness('ACTOR', (value) => {
    signal = value
    return new Promise((resolve) => { resume = resolve })
  })
  const playback = buffer.forPlayback(1)
  calls[0].fail()
  await new Promise(setImmediate)
  buffer.clear()
  assert.equal(signal.aborted, true)
  resume()
  await assert.rejects(playback.promise, { name: 'AbortError' })
  assert.equal(calls.length, 1)
})

test('restart during fallback ignores late audio and revokes no nonexistent URL', async () => {
  const { buffer, calls, urls } = harness()
  const playback = buffer.forPlayback(1)
  calls[0].fail()
  await new Promise(setImmediate)
  buffer.clear()
  assert.ok(calls[1].signal.aborted)
  calls[1].finish()
  await assert.rejects(playback.promise, { name: 'AbortError' })
  assert.equal(urls.length, 0)
})

test('actor playback requests are excluded from fallback too', () => {
  const { buffer, calls } = harness()
  assert.equal(buffer.forPlayback(0), null)
  assert.equal(buffer.forPlayback(3), null)
  assert.equal(calls.length, 0)
})

test('unusable prefetched media is replaced once and its URL released', async () => {
  const { buffer, calls, revoked } = harness()
  const prefetched = buffer.ensure(1)
  calls[0].finish()
  const brokenAudio = await prefetched.promise
  brokenAudio.error = { code: 4 }
  const playback = buffer.forPlayback(1)
  assert.equal(playback.audio, null)
  await new Promise(setImmediate)
  assert.equal(calls.length, 2)
  assert.equal(revoked.length, 1)
  calls[1].finish()
  assert.notEqual(await playback.promise, brokenAudio)
  buffer.clear()
})

test('network failure while downloading audio can recover without duplicate requests', async () => {
  const { buffer, calls } = harness()
  const playback = buffer.forPlayback(1)
  calls[0].disconnectBody()
  await new Promise(setImmediate)
  assert.equal(calls.length, 2)
  calls[1].finish()
  await playback.promise
  buffer.clear()
})
