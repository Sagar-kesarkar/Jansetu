/**
 * The filter vocabulary, fetched from the backend once and shared.
 *
 * Nothing here is a constant in the frontend. States come from
 * `data/reference/districts.csv`, languages from `app/i18n/languages.py`, sectors
 * from `app/models/taxonomy.py` — and constraint 4 says extending coverage means
 * adding rows to those files, never editing logic. A hardcoded dropdown here
 * would silently offer states the deployment has no data for and omit the ones
 * someone adds tomorrow.
 *
 * Cached at module scope so navigating between the queue and a case does not
 * re-fetch the vocabulary, and degrading to empty lists is deliberate: a console
 * with no filters still shows the backlog, so a failure here must not take the
 * page down.
 */
import { useEffect, useState } from 'react'

import { getCapabilities, getStates } from '../api.js'

const EMPTY = { states: [], languages: [], categories: [] }

let cached = null

function load() {
  if (!cached) {
    cached = Promise.all([
      getStates().catch(() => []),
      getCapabilities().catch(() => ({})),
    ])
      .then(([states, caps]) => ({
        states: Array.isArray(states) ? states : [],
        languages: caps.languages || [],
        categories: caps.categories || [],
      }))
      .catch(() => {
        cached = null
        return EMPTY
      })
  }
  return cached
}

export function useReference() {
  const [ref, setRef] = useState(EMPTY)
  useEffect(() => {
    let alive = true
    load().then((r) => alive && setRef(r))
    return () => {
      alive = false
    }
  }, [])
  return ref
}

/** Language code to its English and native names, for labelling original text. */
export function languageName(languages, code) {
  const hit = languages.find((l) => l.code === code)
  if (!hit) return code || '—'
  return hit.native ? `${hit.name} (${hit.native})` : hit.name
}
