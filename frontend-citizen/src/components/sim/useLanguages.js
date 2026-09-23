/**
 * The language list, and the demo's stand-in handset numbers.
 *
 * The languages come from `GET /capabilities` rather than a constant here. The
 * backend owns the taxonomy — `i18n/languages.py` — and a hardcoded list in the
 * widget means the fourteenth language gets added in two places and ships out of
 * sync with the pipeline that has to transcribe it.
 */
import { useEffect, useState } from 'react'

import { getCapabilities } from '../../api.js'

/**
 * Enough to render a selector before the fetch lands, so the simulator is usable
 * on the first click rather than showing an empty dropdown for a beat. Replaced
 * wholesale by the API's answer — this is a placeholder, not a source of truth,
 * and the app must never end up reading the count from it.
 */
const FALLBACK = [{ code: 'hi', name: 'Hindi', native: 'हिन्दी' }]

export function useLanguages() {
  const [languages, setLanguages] = useState(FALLBACK)

  useEffect(() => {
    let live = true
    getCapabilities()
      .then((caps) => {
        if (live && caps?.languages?.length) setLanguages(caps.languages)
      })
      .catch(() => {
        /* The simulator still works on the fallback; a dead dropdown is not
           worth an error banner inside a demo widget. */
      })
    return () => {
      live = false
    }
  }, [])

  return languages
}

/**
 * The simulated handsets. Real-looking numbers in the reserved-for-fiction
 * 9987xxxxxx range, and it does not matter that they are fake: `ingest` HMACs
 * whatever it is given into `citizen_ref` and never stores the input, so the
 * number exists only to make consecutive demo submissions group as one sender
 * the way a real handset would.
 */
export const HANDSET = {
  whatsapp: '919987001234',
  sms: '919987005678',
  ivr: '919987009012',
}

/** A stable id for chat bubbles without reaching for a uuid dependency. */
let seq = 0
export const nextId = () => `m${++seq}`
