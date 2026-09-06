import test from 'node:test'
import assert from 'node:assert/strict'
import { MAX_UPLOAD_BYTES, validateScriptFile } from '../src/upload.js'

test('TXT and PDF extensions are accepted case-insensitively', () => {
  for (const name of ['scene.txt', 'scene.pdf', 'SCENE.TXT', 'SCENE.PDF']) {
    assert.equal(validateScriptFile({ name, size: 100 }), '')
  }
})

test('missing, empty, unsupported, and oversized files receive useful feedback', () => {
  assert.match(validateScriptFile(null), /Choose a TXT or PDF/)
  assert.match(validateScriptFile({ name: 'scene.pdf', size: 0 }), /empty/)
  assert.match(validateScriptFile({ name: 'scene.pdf.exe', size: 100 }), /Choose a TXT/)
  assert.match(validateScriptFile({ name: 'scene.pdf', size: MAX_UPLOAD_BYTES + 1 }), /10 MiB/)
  assert.equal(validateScriptFile({ name: 'scene.txt', size: MAX_UPLOAD_BYTES }), '')
})
