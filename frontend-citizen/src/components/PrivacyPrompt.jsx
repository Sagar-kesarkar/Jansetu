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
    panel.current?.querySelector('button')?.focus()
    const trap = event => {
      if (event.key !== 'Tab') return
      const buttons = [...panel.current.querySelectorAll('button:not(:disabled)')]
      const first = buttons[0], last = buttons.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', trap)
    return () => { document.removeEventListener('keydown', trap); previous?.focus?.() }
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
    <button ref={settingsButton} type="button" className="cookie-settings" onClick={() => { setError(null); setOpen(true) }}>Cookie settings</button>
    {!open && error ? <p className="field__hint" role="status">{error}</p> : null}
    {open ? <div className="cookie-choice__backdrop">
      <section ref={panel} className="cookie-choice" role="dialog" aria-modal="true" aria-labelledby="cookie-choice-title" aria-describedby="cookie-choice-description">
        <p className="cookie-choice__eyebrow">Your privacy</p>
        <h2 id="cookie-choice-title">Allow required cookies?</h2>
        <p id="cookie-choice-description">JanSetu uses a private browser cookie to remember your daily submission limit and prevent identical open complaints. Tracking receipts are saved on this browser for up to 90 days.</p>
        <p className="field__hint">No advertising or analytics cookies. You can decline and still browse or track a complaint. Submitting needs this cookie. We remember your choice on this browser.</p>
        {error ? <p role="alert">{error}</p> : null}
        <div className="cookie-choice__actions">
          <button type="button" className="btn" disabled={busy} onClick={() => select('accepted')}>Accept required cookies</button>
          <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => select('declined')}>Not now</button>
          {error ? <button type="button" className="btn btn--ghost" onClick={() => setOpen(false)}>Close</button> : null}
        </div>
      </section>
    </div> : null}
  </>
}
