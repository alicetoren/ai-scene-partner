import test from 'node:test'
import assert from 'node:assert/strict'
import { assignCharacterVoices, voicePlaybackKey } from '../src/playback/voiceSettings.js'

test('names never imply a voice category', () => {
  assert.deepEqual(assignCharacterVoices(['ALICE', 'JOHN', 'A']), {
    ALICE: { voice_category: 'any', voice_index: 0 },
    JOHN: { voice_category: 'any', voice_index: 1 },
    A: { voice_category: 'any', voice_index: 2 },
  })
})

test('characters receive consecutive slots within each selected category', () => {
  const categories = { A: 'feminine', B: 'masculine', C: 'feminine', D: 'masculine' }
  const result = assignCharacterVoices(['A', 'B', 'C', 'D', 'E'], categories)
  assert.deepEqual(Object.values(result), [
    { voice_category: 'feminine', voice_index: 0 },
    { voice_category: 'masculine', voice_index: 0 },
    { voice_category: 'feminine', voice_index: 1 },
    { voice_category: 'masculine', voice_index: 1 },
    { voice_category: 'any', voice_index: 0 },
  ])
  assert.deepEqual(assignCharacterVoices(['A', 'B', 'C', 'D', 'E'], categories), result)
})

test('changing a role resets playback without altering saved voice assignments', () => {
  const categories = { A: 'feminine', B: 'feminine', C: 'masculine' }
  const assignments = assignCharacterVoices(['A', 'B', 'C'], categories)
  assert.notEqual(voicePlaybackKey('A', assignments), voicePlaybackKey('B', assignments))
  assert.deepEqual(assignments.B, { voice_category: 'feminine', voice_index: 1 })
  assert.deepEqual(assignCharacterVoices(['A', 'B', 'C'], categories), assignments)
})

test('prototype-shaped character names do not interfere with category lookup', () => {
  const result = assignCharacterVoices(['constructor', '__proto__'])
  assert.equal(result.constructor.voice_category, 'any')
  assert.equal(result.__proto__.voice_index, 1)
})
