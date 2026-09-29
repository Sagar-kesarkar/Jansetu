import { test } from 'node:test'
import assert from 'node:assert/strict'

async function fixture() {
  const values = new Map()
  globalThis.localStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
  globalThis.window = new EventTarget()
  const preference = await import(`../src/sitePreference.js?test=${crypto.randomUUID()}`)
  return { ...preference, values }
}

test('new visitor has no consent until they choose; accept and decline persist', async () => {
  const state = await fixture()
  assert.equal(state.cookieChoice(), null)
  let events = 0
  window.addEventListener('jansetu-cookie-choice', () => events++)
  state.chooseCookies('accepted')
  assert.equal(state.cookieChoice(), 'accepted')
  state.chooseCookies('declined')
  assert.equal(state.cookieChoice(), 'declined')
  assert.equal(events, 2)
})

test('another tab changing or clearing preference is respected', async () => {
  const state = await fixture()
  state.chooseCookies('accepted')
  state.values.set('jansetu.cookie-choice.v1', 'declined')
  assert.equal(state.cookieChoice(), 'declined')
  state.values.clear()
  assert.equal(state.cookieChoice(), null)
})

test('denial wins when writing storage fails even if old acceptance remains', async () => {
  const state = await fixture()
  state.chooseCookies('accepted')
  localStorage.setItem = () => { throw new Error('storage full') }
  state.chooseCookies('declined')
  assert.equal(state.cookieChoice(), 'declined')
})
