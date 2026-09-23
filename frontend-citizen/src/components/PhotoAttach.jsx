/**
 * Attach a photograph to a report.
 *
 * Sits on the label row of the message field rather than in a section of its own,
 * because a photo is an *attachment to* the complaint, not a second thing being
 * reported. A separate "Photographs" block below the form reads as another form to
 * fill in, and this screen is already the longest thing a citizen has to get
 * through on a phone.
 *
 * Three decisions worth stating.
 *
 * **`capture="environment"`.** On a phone this opens the rear camera straight
 * away rather than the gallery. The person filing is usually standing in front of
 * the broken thing, so the shortest path is camera-first — and on a desktop the
 * attribute is ignored and the file picker opens as normal, so it costs nothing.
 *
 * **A real preview, made with `createObjectURL`.** Not a filename and a tick. The
 * commonest way to attach the wrong photo is to attach the previous one, and the
 * only thing that catches it is seeing it. The URL is revoked on replace and on
 * unmount, because a few unrevoked blob URLs of phone photographs is tens of
 * megabytes held for the life of the tab.
 *
 * **Client-side size and type checks that mirror the server's.** `routers/intake.py`
 * rejects over 8 MB and anything outside the formats Gemini reads inline. Letting
 * a 12 MB HEIC upload for twenty seconds before the server refuses it is the worst
 * version of that conversation, especially on the 2G connections this platform
 * exists to serve. The server still checks — this is courtesy, not security.
 */
import { useEffect, useRef, useState } from 'react'

import Icon from './Icon.jsx'

/** Mirrors `MAX_IMAGE_BYTES` in `backend/app/routers/intake.py`. */
const MAX_BYTES = 8 * 1024 * 1024
/** Mirrors `ALLOWED_IMAGE_TYPES`. HEIC is here because every recent iPhone shoots it. */
const ACCEPT = 'image/jpeg,image/png,image/webp,image/heic,image/heif'

export default function PhotoAttach({ file, onChange, disabled }) {
  const input = useRef(null)
  const [preview, setPreview] = useState(null)
  const [problem, setProblem] = useState(null)

  // One effect owns the object URL for the whole life of the file, so there is
  // exactly one place that creates and one that revokes it. Doing this in the
  // change handler instead is how a leak gets introduced by a later edit.
  useEffect(() => {
    if (!file) {
      setPreview(null)
      return undefined
    }
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  function pick(event) {
    const chosen = event.target.files?.[0]
    // Reset the input straight away: without this, choosing the same file twice in
    // a row fires no change event and the citizen thinks the button is broken.
    event.target.value = ''
    if (!chosen) return

    if (chosen.size > MAX_BYTES) {
      setProblem(
        `That photo is ${(chosen.size / 1024 / 1024).toFixed(1)} MB. Please send one under 8 MB.`,
      )
      return
    }
    if (chosen.type && !ACCEPT.includes(chosen.type)) {
      setProblem('Send a JPEG, PNG, WebP or HEIC photo.')
      return
    }
    setProblem(null)
    onChange(chosen)
  }

  function clear() {
    setProblem(null)
    onChange(null)
  }

  return (
    <>
      <button
        type="button"
        className="photo__add"
        onClick={() => input.current?.click()}
        disabled={disabled}
      >
        <Icon name="image" size={15} />
        <span>{file ? 'Change photo' : 'Add photo'}</span>
      </button>

      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        capture="environment"
        onChange={pick}
        disabled={disabled}
        className="photo__input"
        tabIndex={-1}
        aria-hidden="true"
      />

      {problem ? (
        <p className="photo__problem" role="alert">
          {problem}
        </p>
      ) : null}

      {file && preview ? (
        <div className="photo__picked">
          <img className="photo__thumb" src={preview} alt="The photograph you attached" />
          <div className="photo__meta">
            <strong>Photo attached</strong>
            <span>{(file.size / 1024).toFixed(0)} KB</span>
            <p className="photo__note">
              Gemini will describe the damage it can see. The photo is sent to the
              officer handling your case.
            </p>
          </div>
          <button type="button" className="photo__drop" onClick={clear} disabled={disabled}>
            <Icon name="close" size={14} />
            <span className="sr-only">Remove the photo</span>
          </button>
        </div>
      ) : null}
    </>
  )
}
