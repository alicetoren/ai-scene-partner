import test from 'node:test'
import assert from 'node:assert/strict'
import { handlePlayerSpace } from '../src/playback/keyboard.js'

function press({ active = true, repeat = false, inside = true, tag = 'P', interactive = false } = {}) {
  let prevented = false
  let advanced = 0
  const event = { code: 'Space', repeat, target: { tagName: tag, closest: () => interactive }, preventDefault: () => { prevented = true } }
  handlePlayerSpace(event, { contains: () => inside }, active, () => { advanced += 1 })
  return { prevented, advanced }
}

test('active player owns Space even when its advance callback cannot advance', () => {
  let prevented = false
  handlePlayerSpace({ code: 'Space', target: { tagName: 'BODY', closest: () => false }, preventDefault: () => { prevented = true } }, null, true, () => {})
  assert.equal(prevented, true)
})

test('Space advances once and key repeats cannot scroll or advance again', () => {
  assert.deepEqual(press(), { prevented: true, advanced: 1 })
  assert.deepEqual(press({ repeat: true }), { prevented: true, advanced: 0 })
})

test('idle player, other page content, and native controls keep normal keyboard behavior', () => {
  for (const options of [{ active: false }, { inside: false }, { interactive: true }]) {
    assert.deepEqual(press(options), { prevented: false, advanced: 0 })
  }
})
