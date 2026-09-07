import test from 'node:test'
import assert from 'node:assert/strict'
import { dialogueScrollTop } from '../src/playback/dialogueScroll.js'

test('current turn starts in the upper third with room for previous context', () => {
  assert.equal(dialogueScrollTop(800, 600, 2400), 600)
})

test('first turns and scenes shorter than the viewport do not scroll past the start', () => {
  assert.equal(dialogueScrollTop(100, 600, 2400), 0)
  assert.equal(dialogueScrollTop(100, 600, 300), 0)
})

test('last turns stop at the end of the script', () => {
  assert.equal(dialogueScrollTop(2300, 600, 2400), 1800)
})
