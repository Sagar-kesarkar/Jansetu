/**
 * The tracking token, on the screen where the citizen first receives it.
 *
 * This is the only moment the token is ever shown to them unprompted. There is no
 * account to log back into and no email going out, so if they leave this page
 * without keeping it, the case becomes unreachable — they can still be *helped*,
 * but they can never again ask what happened. That asymmetry is why the token is
 * a strip of its own at display size rather than a cell in the detail grid
 * between the sector and the urgency.
 *
 * Monospaced and letter-spaced for a specific reason: the alphabet excludes
 * I, L, O, U, 0 and 1 so nothing in it *can* be misread, but that only helps if
 * the glyphs are wide enough to tell apart when someone copies it onto paper or
 * reads it down a phone line.
 *
 * The instruction sits behind an ⓘ rather than under the strip. It is four lines
 * of text that only matter once, and printed inline it pushes the sector and
 * district — the part that shows whether the platform understood them — below the
 * fold on a phone.
 *
 * The copy button falls back rather than failing. `navigator.clipboard` needs a
 * secure context, and the demo runs over plain http on a LAN address often
 * enough that a dead button would be a visible defect in the video. It is also
 * *raced against a timeout*, because in an unfocused document Chrome resolves
 * `writeText` neither way — the promise simply hangs, and an awaited hang means
 * the citizen clicks Copy and gets no confirmation, no warning and no fallback.
 * An unfocused window is the normal case while a screen recorder has focus, so
 * that is a demo failure, not a hypothetical.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import Icon from './Icon.jsx'

/** Long enough for a real permission prompt, short enough not to read as dead. */
const CLIPBOARD_TIMEOUT_MS = 1200

export default function TokenReceipt({ token }) {
  const [state, setState] = useState('idle') // idle | copied | failed
  const [helpOpen, setHelpOpen] = useState(false)
  const timer = useRef(null)
  const fallbackRef = useRef(null)
  const wrapRef = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  // Click-away and Escape. Without these the popover is a trap on touch, where
  // there is no second click target to move focus to.
  useEffect(() => {
    if (!helpOpen) return
    const onDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setHelpOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setHelpOpen(false)
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [helpOpen])

  const copy = useCallback(async () => {
    clearTimeout(timer.current)
    let ok = false

    try {
      if (navigator.clipboard?.writeText) {
        await Promise.race([
          navigator.clipboard.writeText(token),
          new Promise((_, reject) => setTimeout(() => reject(new Error('clipboard timeout')), CLIPBOARD_TIMEOUT_MS)),
        ])
        ok = true
      }
    } catch {
      /* insecure context, denied, or hung — fall through to execCommand */
    }

    if (!ok) {
      // The pre-permissions path. Still works everywhere, including the http
      // origin the demo is served from.
      const node = fallbackRef.current
      if (node) {
        node.hidden = false
        node.select()
        node.setSelectionRange(0, token.length)
        try {
          ok = document.execCommand('copy')
        } catch {
          ok = false
        }
        node.hidden = true
      }
    }

    setState(ok ? 'copied' : 'failed')
    timer.current = setTimeout(() => setState('idle'), ok ? 2400 : 6000)
  }, [token])

  if (!token) return null

  return (
    <div className="token" ref={wrapRef}>
      <div className="token__strip">
        <span className="token__label">Tracking token</span>

        {/* A <code> rather than an input: it is not editable, and a text field
            invites the reader to think they are meant to type something. */}
        <code className="token__value" translate="no">
          {token}
        </code>

        <button
          type="button"
          className={`token__act${state === 'copied' ? ' token__act--done' : ''}`}
          onClick={copy}
          aria-label={`Copy tracking token ${token}`}
        >
          <Icon name={state === 'copied' ? 'check' : 'copy'} />
          <span>{state === 'copied' ? 'Copied' : 'Copy'}</span>
        </button>

        <button
          type="button"
          className="token__info"
          onClick={() => setHelpOpen((v) => !v)}
          aria-expanded={helpOpen}
          aria-label="How to track your request"
        >
          <Icon name="info" />
        </button>

        {helpOpen ? (
          <div className="token__pop" role="tooltip">
            <strong>How to track your request</strong>
            <p>
              Save this token, open <b>Track Status</b>, and enter it to see the latest status. No login is
              required.
            </p>
          </div>
        ) : null}
      </div>

      {state === 'failed' ? (
        <p className="token__warn" role="status">
          This browser blocked the clipboard. Select the token above and copy it by hand.
        </p>
      ) : null}

      {/* Announced separately so a screen reader hears the outcome without the
          button's own label changing under the user's focus. */}
      <span className="sr-only" role="status" aria-live="polite">
        {state === 'copied' ? 'Token copied to clipboard' : ''}
      </span>

      <textarea
        ref={fallbackRef}
        hidden
        readOnly
        tabIndex={-1}
        aria-hidden="true"
        defaultValue={token}
        className="token__shadow"
      />
    </div>
  )
}
