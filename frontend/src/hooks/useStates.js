/**
 * The list of states in the filter, derived from the data rather than declared.
 *
 * There is no `/states` endpoint and there should not be one: coverage is defined
 * by the rows in `data/reference/districts.csv`, so the states worth offering are
 * exactly the states present in the scored set. Hardcoding twenty-eight names
 * here would mean the filter offers states the deployment has no data for, and
 * silently omits the ones someone adds tomorrow.
 *
 * Fetched unfiltered and once, at the API's maximum limit — a state must not
 * disappear from the dropdown just because its districts rank below a page
 * boundary. The promise is cached at module scope so the two policy pages share
 * one request across navigations.
 */
import { useEffect, useState } from 'react'

import { getHotspots } from '../api.js'

let cached = null

function loadStates() {
  if (!cached) {
    cached = getHotspots({ limit: 500 })
      .then((rows) => [...new Set(rows.map((r) => r.state).filter(Boolean))].sort())
      .catch(() => {
        // A failure here degrades the filter to "All India", which is a usable
        // dashboard. It must not take the page down with it.
        cached = null
        return []
      })
  }
  return cached
}

export function useStates() {
  const [states, setStates] = useState([])
  useEffect(() => {
    let alive = true
    loadStates().then((s) => alive && setStates(s))
    return () => {
      alive = false
    }
  }, [])
  return states
}
