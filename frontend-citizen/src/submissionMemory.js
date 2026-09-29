// Optional, bounded receipts: no complaint text or media is stored here.
const RECEIPTS = 'jansetu.receipts.v1'
const RETRIES = 'jansetu.retries.v1'
const MAX_AGE = 90 * 86400 * 1000
const read = (key) => {
  try {
    const rows = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(rows) ? rows.filter(r => r && typeof r.at === 'number' && Date.now() - r.at < MAX_AGE).slice(-50) : []
  } catch { return [] }
}
const write = (key, rows) => {
  try { localStorage.setItem(key, JSON.stringify(rows.slice(-50))) } catch { /* optional storage */ }
}
const pending = new Map()

export async function retryIdentity(body) {
  const parts = []
  if (body instanceof FormData) {
    for (const [key, value] of body.entries()) {
      if (key === 'citizen_ref' || key === 'channel') continue
      if (value instanceof Blob) {
        const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', await value.arrayBuffer()))
        parts.push([key, value.type, Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')])
      } else parts.push([key, value])
    }
  } else parts.push(['json', body || ''])
  parts.sort((a, b) => a[0].localeCompare(b[0]))
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(parts))))
  const fingerprint = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
  const existing = pending.get(fingerprint) || read(RETRIES).find(r => r.fingerprint === fingerprint)?.key
  const key = existing || crypto.randomUUID()
  pending.set(fingerprint, key)
  write(RETRIES, [...read(RETRIES).filter(r => r.fingerprint !== fingerprint), { fingerprint, key, at: Date.now() }])
  return { fingerprint, key }
}

export function finishRetry(identity) {
  if (!identity) return
  pending.delete(identity.fingerprint)
  write(RETRIES, read(RETRIES).filter(r => r.fingerprint !== identity.fingerprint))
}

export function rememberReceipt(result) {
  const tokens = (result.requests || []).map(r => r.track_token).filter(t => /^JS-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(t || ''))
  if (!result.fingerprint || !tokens.length) return
  write(RECEIPTS, [...read(RECEIPTS).filter(r => JSON.stringify(r.tokens) !== JSON.stringify(tokens)),
    { fingerprint: result.fingerprint, tokens, at: Date.now() }])
  window.dispatchEvent(new Event('jansetu-receipts'))
}

export const savedReceipts = () => read(RECEIPTS).filter(r => Array.isArray(r.tokens)).reverse()
export function forgetReceipts() {
  write(RECEIPTS, [])
  window.dispatchEvent(new Event('jansetu-receipts'))
}
