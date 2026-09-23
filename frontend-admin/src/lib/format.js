/**
 * Formatting for the console. Dates matter more here than numbers do.
 *
 * The one non-obvious function is `parseUtc`. `app/db/models._now` writes UTC and
 * SQLite hands it back with no timezone designator — `2026-08-22T10:06:28.683835`.
 * The ECMAScript rule for a date-time string without an offset is *local time*,
 * so `new Date(created_at)` in Mumbai reads that as 10:06 IST and every age on
 * this screen is wrong by five and a half hours. A case filed forty minutes ago
 * then shows as "in 5 hours". Appending `Z` when no offset is present is the fix.
 */

const IN = new Intl.NumberFormat('en-IN')

export const DASH = '—'

export const isMissing = (v) => v === null || v === undefined || Number.isNaN(v)

export function num(value) {
  if (isMissing(value)) return DASH
  return IN.format(value)
}

/** See the module docstring: a naive timestamp from SQLite is UTC, not local. */
export function parseUtc(value) {
  if (!value) return null
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasZone ? value : `${value}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

const DATE_TIME = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})

const DATE_ONLY = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** "22 Aug 2026, 3:36 pm" in the reader's own timezone. */
export function dateTime(value) {
  const d = parseUtc(value)
  return d ? DATE_TIME.format(d) : DASH
}

export function dateOnly(value) {
  const d = parseUtc(value)
  return d ? DATE_ONLY.format(d) : DASH
}

/**
 * "3 days ago". Shown alongside the absolute timestamp, never instead of it:
 * relative age is what an officer triages on, and the exact date is what they
 * quote in a file. Both, or the screen is useless for one of the two jobs.
 */
export function ago(value) {
  const d = parseUtc(value)
  if (!d) return DASH
  const seconds = (Date.now() - d.getTime()) / 1000
  if (seconds < 0) return 'just now'
  if (seconds < 60) return 'just now'
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  if (days < 31) return `${days} day${days === 1 ? '' : 's'} ago`
  const months = Math.floor(days / 30.44)
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`
  const years = (days / 365.25).toFixed(1)
  return `${years} yr ago`
}

/** Sector codes are WATER_SUPPLY on the wire; humans read "Water supply". */
export function sectorLabel(code) {
  if (!code) return DASH
  const words = code.replace(/_/g, ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function statusLabel(code) {
  if (!code) return DASH
  const words = code.replace(/_/g, ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const URGENCY_WORDS = {
  1: 'Routine',
  2: 'Low',
  3: 'Affects daily life',
  4: 'Serious',
  5: 'Immediate risk',
}

export const urgencyLabel = (level) => URGENCY_WORDS[level] || `Level ${level}`

/**
 * How the request reached us. Spelled out rather than shown as a raw enum,
 * because the channel is evidence about the reporter: an IVR call means a feature
 * phone, which is the population the whole platform exists to reach.
 */
const CHANNEL_WORDS = {
  voice: 'Voice note',
  text: 'Web form',
  whatsapp: 'WhatsApp',
  sms: 'SMS',
  ivr: 'IVR call',
}

export const channelLabel = (code) => CHANNEL_WORDS[code] || code || DASH

const CHANNEL_NOTES = {
  voice: 'Recorded and transcribed by Gemini.',
  text: 'Typed into the citizen web form.',
  whatsapp: 'Sent as a WhatsApp message.',
  sms: 'Sent as an SMS.',
  ivr: 'Spoken on a phone call from a feature phone.',
}

export const channelNote = (code) => CHANNEL_NOTES[code] || ''
