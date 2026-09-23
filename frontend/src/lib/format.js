/**
 * Number formatting, Indian conventions.
 *
 * `Intl.NumberFormat('en-IN')` groups as 9,01,058 rather than 901,058 — which is
 * the form an Indian official reads without pausing. It ships in every browser,
 * so this costs no dependency.
 */

const IN = new Intl.NumberFormat('en-IN')

/** A missing value renders as an em dash, never as 0 — they mean different
 *  things here. A district with no allocation data is not a district with no
 *  allocation, and showing "₹0" would be a claim we cannot support. */
export const DASH = '—'

export const isMissing = (v) => v === null || v === undefined || Number.isNaN(v)

export function num(value, digits = 0) {
  if (isMissing(value)) return DASH
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function inr(value, digits = 0) {
  if (isMissing(value)) return DASH
  return `₹${num(value, digits)}`
}

export function pct(value, digits = 1) {
  if (isMissing(value)) return DASH
  return `${num(value, digits)}%`
}

/** Lakh/crore, because "9.01 lakh people" lands and "901,058 people" does not. */
export function people(value) {
  if (isMissing(value)) return DASH
  if (value >= 1_00_00_000) return `${(value / 1_00_00_000).toFixed(2)} crore`
  if (value >= 1_00_000) return `${(value / 1_00_000).toFixed(2)} lakh`
  return IN.format(value)
}

/** Sector codes are WATER_SUPPLY on the wire; humans read "Water supply". */
export function sectorLabel(code) {
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
 * Full Indian convention date/time formatting e.g. "24 Aug 2026, 1:25 am"
 */
export function formatFullDateTime(iso) {
  if (!iso) return 'Time not available'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Time not available'
  return d.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

/**
 * Short date format e.g. "24 Aug"
 */
export function formatShortDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

