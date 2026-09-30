import { useEffect, useRef, useState } from 'react'
import { cookieChoice, chooseCookies } from '../sitePreference.js'
import { revokeSubmissionSession } from '../api.js'
import { forgetReceipts } from '../submissionMemory.js'

export default function PrivacyPrompt() {
  const [open, setOpen] = useState(() => !cookieChoice())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const panel = useRef(null)
  const settingsButton = useRef(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement
    panel.current?.querySelector('button')?.focus({ preventScroll: true })
    return () => previous?.focus?.({ preventScroll: true })
  }, [open])
  async function select(value) {
    setBusy(true)
    setError(null)
    chooseCookies(value)
    setOpen(false)
    settingsButton.current?.focus()
    if (value === 'declined') {
      // Stop further identity requests immediately, even if the API is offline.
      forgetReceipts()
      try { await revokeSubmissionSession() } catch {
        setError('Your preference is saved. The server could not clear its previous cookie yet; you can also clear site cookies in your browser.')
      }
    }
    setBusy(false)
  }
  return <>
    <button ref={settingsButton} type="button" className="preference-settings" onClick={() => { setError(null); setOpen(true) }}>Cookie settings</button>
    {!open && error ? <p className="field__hint" role="status">{error}</p> : null}
    {open ? <section ref={panel} className="preference-panel" role="dialog" aria-labelledby="preference-panel-title" aria-describedby="preference-panel-description">
        <p className="preference-panel__eyebrow">Your privacy</p>
        <h2 id="preference-panel-title">Allow required cookies?</h2>
        <p id="preference-panel-description">JanSetu uses a private browser cookie to remember your daily submission limit and prevent identical open complaints. Tracking receipts are saved on this browser for up to 90 days.</p>
        <p className="field__hint">No advertising or analytics cookies. You can decline and still browse or track a complaint. Submitting needs this cookie. We remember your choice on this browser.</p>
        {error ? <p role="alert">{error}</p> : null}
        <div className="preference-panel__actions">
          <button type="button" className="btn" disabled={busy} onClick={() => select('accepted')}>Accept required cookies</button>
          <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => select('declined')}>Not now</button>
          {error ? <button type="button" className="btn btn--ghost" onClick={() => setOpen(false)}>Close</button> : null}
        </div>
      </section> : null}
  </>
}
