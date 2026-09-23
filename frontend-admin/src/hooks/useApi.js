/**
 * One hook for every read from the API.
 *
 * Four states have to be distinguishable on screen, because they call for
 * different words and different chrome:
 *
 *   loading      first fetch, nothing to show yet          → spinner
 *   loaded-empty succeeded, zero rows                      → "no cases match"
 *   failed       could not reach or parse                  → the actual reason
 *   refreshing   we have data and are re-reading it        → keep the page
 *
 * The last one is the reason this hook is more than a `useEffect`. After an
 * officer records a reply the record is refetched, and blanking the page to a
 * spinner in that moment unmounts the composer — which throws away the
 * confirmation the officer needs to read, including the "this could not be
 * translated" warning. A refresh must leave the screen standing.
 *
 * A *dependency* change is the opposite case and must blank: navigating from
 * docket 500 to 501 while 501 loads would otherwise show 500's words under 501's
 * URL, which on this screen means an officer replying to a case they are not
 * looking at. Hence two entry points — the effect blanks, `reload` does not.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [inFlight, setInFlight] = useState(true)

  // Filters change faster than the network answers. Without this guard a slow
  // response for "Odisha" can land after a fast one for "Bihar" and repaint the
  // queue with the wrong state's cases.
  const generation = useRef(0)

  const run = useCallback((keep = false) => {
    const mine = ++generation.current
    setError(null)
    setInFlight(true)
    if (!keep) setData(null)
    fetcher()
      .then((result) => {
        if (mine === generation.current) setData(result)
      })
      .catch((err) => {
        if (mine !== generation.current) return
        setError(err)
        if (!keep) setData(null)
      })
      .finally(() => {
        if (mine === generation.current) setInFlight(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => run(false), [run])

  const reload = useCallback(() => run(true), [run])

  return {
    data,
    error,
    loading: inFlight && data === null,
    refreshing: inFlight && data !== null,
    reload,
  }
}
