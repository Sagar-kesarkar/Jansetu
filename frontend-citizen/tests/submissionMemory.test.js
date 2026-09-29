import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { retryIdentity, finishRetry, rememberReceipt, savedReceipts, forgetReceipts } from '../src/submissionMemory.js'

beforeEach(() => {
  const values = new Map()
  globalThis.localStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
  globalThis.window = new EventTarget()
})

test('uncertain retry keeps its identity; confirmed result allows a new submission', async () => {
  const body = JSON.stringify({ text: 'road potholes' })
  const first = await retryIdentity(body)
  assert.deepEqual(await retryIdentity(body), first)
  finishRetry(first)
  assert.notEqual((await retryIdentity(body)).key, first.key)
})

test('attachment content matters, filename does not', async () => {
  const form = (text, filename) => {
    const value = new FormData()
    value.append('text', 'road')
    value.append('image', new Blob([text], { type: 'image/jpeg' }), filename)
    return value
  }
  const first = await retryIdentity(form('same bytes', 'one.jpg'))
  assert.equal((await retryIdentity(form('same bytes', 'two.jpg'))).key, first.key)
  assert.notEqual((await retryIdentity(form('different bytes', 'one.jpg'))).key, first.key)
})

test('receipt stores only fingerprint, date and tokens; forgetting it does not affect retries', async () => {
  const pending = await retryIdentity('unfinished message')
  rememberReceipt({ fingerprint: 'opaque', text: 'private content', requests: [{ track_token: 'JS-ABCD-EFGH', summary_en: 'private content' }] })
  const receipts = savedReceipts()
  assert.equal(receipts.length, 1)
  assert.equal(JSON.stringify(receipts).includes('private content'), false)
  forgetReceipts()
  assert.deepEqual(savedReceipts(), [])
  assert.equal((await retryIdentity('unfinished message')).key, pending.key)
})

test('broken and unavailable storage does not prevent safe in-page retries', async () => {
  localStorage.setItem('jansetu.receipts.v1', '{broken')
  assert.deepEqual(savedReceipts(), [])
  globalThis.localStorage = { getItem() { throw Error('blocked') }, setItem() { throw Error('full') } }
  const first = await retryIdentity('blocked storage report')
  assert.equal((await retryIdentity('blocked storage report')).key, first.key)
  assert.doesNotThrow(() => rememberReceipt({fingerprint: 'x', requests: [{track_token: 'JS-ABCD-EFGH'}]}))
})

test('expired receipts are hidden and retained receipt count is bounded', () => {
  localStorage.setItem('jansetu.receipts.v1', JSON.stringify([{ fingerprint: 'old', at: 0, tokens: ['JS-ABCD-EFGH'] }]))
  assert.equal(savedReceipts().length, 0)
  for (let i = 0; i < 60; i++) rememberReceipt({ fingerprint: `receipt${i}`, requests: [{track_token:`JS-ABCD-${String(i).padStart(4, '0')}`}] })
  assert.equal(savedReceipts().length, 50)
})

test('a new complaint after closure retains both old and new tracking receipts', () => {
  rememberReceipt({ fingerprint: 'same-content', requests: [{ track_token: 'JS-ABCD-EFGH' }] })
  rememberReceipt({ fingerprint: 'same-content', requests: [{ track_token: 'JS-IJKL-MNOP' }] })
  assert.equal(savedReceipts().length, 2)
  rememberReceipt({ fingerprint: 'same-content', requests: [{ track_token: 'JS-IJKL-MNOP' }] })
  assert.equal(savedReceipts().length, 2)
})
