/**
 * `/capabilities` is fetched once and shared.
 *
 * The languages and sector codes live in the backend taxonomy. Every page that
 * needs them reads from here, so adding a 14th language means editing
 * `app/i18n/languages.py` and nothing in this directory.
 */
import { createContext, useContext } from 'react'

import { getCapabilities } from '../api.js'
import { useApi } from './useApi.js'

const CapabilitiesContext = createContext({ data: null, error: null, loading: true })

export function CapabilitiesProvider({ children }) {
  const state = useApi(getCapabilities, [])
  return <CapabilitiesContext.Provider value={state}>{children}</CapabilitiesContext.Provider>
}

export const useCapabilities = () => useContext(CapabilitiesContext)
