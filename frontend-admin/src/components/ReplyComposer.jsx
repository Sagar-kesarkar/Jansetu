/**
 * The reply composer — "option to give response to the request giver".
 *
 * Three decisions worth stating.
 *
 * **The desk, not the officer.** `responder_desk` is required and defaults to the
 * desk of the signed-in post: "Water Resources Desk, Nabarangpur". An individual's
 * name in an outbound message is PII about the official, and it also invites a
 * citizen to chase a person who will be transferred rather than an office that
 * will still exist. The API caps it at 128 characters; the field stays a plain
 * text input rather than becoming read-only because one officer routinely answers
 * for a neighbouring desk, and desk names are local and cannot be enumerated
 * centrally.
 *
 * **Translation is on by default and honestly reported.** A reply written in
 * English and delivered in English to someone who filed in Odia is a receipt, not
 * an answer. Gemini translates on the way out, mirroring what it does on the way
 * in — and with no API key `translate` returns the text unchanged, the backend
 * stores NULL rather than claiming a translation happened, and the thread says so.
 *
 * **The reply is queued, not sent.** Outbound WhatsApp and IVR need a paid Meta
 * Business app and a telephony account, which constraint 1 forbids. The button
 * says "Record reply" and the confirmation says queued. A UI that said "Sent"
 * would be the one lie in this project a judge could catch in ten seconds.
 */
import { useState } from 'react'

import { postResponse } from '../api.js'
import { channelLabel, statusLabel } from '../lib/format.js'
import { languageName } from '../hooks/useReference.js'

const NEXT_STATUS = ['ACKNOWLEDGED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED']

const MIN_BODY = 5
const MIN_DESK = 2

/**
 * Keyed by post, so signing in as a different desk does not inherit the last
 * one's name. That was the bug the unkeyed version would have shipped: a
 * demonstration that signs out of Nabarangpur and into Sitamarhi would still have
 * sent replies stamped Nabarangpur.
 */
const deskKey = (session) => `jansetu.desk.${session?.id || 'anon'}`

export function ReplyComposer({ request, languages, session, onPosted }) {
  const [body, setBody] = useState('')
  const [desk, setDesk] = useState(
    () => localStorage.getItem(deskKey(session)) || session?.desk || '',
  )
  const [status, setStatus] = useState('')
  const [translate, setTranslate] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)

  const native = request.language && request.language !== 'en'
  const ready = body.trim().length >= MIN_BODY && desk.trim().length >= MIN_DESK

  async function submit(e) {
    e.preventDefault()
    if (!ready || busy) return
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const reply = await postResponse(request.id, {
        bodyEn: body.trim(),
        responderDesk: desk.trim(),
        newStatus: status || null,
        translate,
      })
      // The desk is the same for every reply this officer writes in a sitting.
      // Remembering it is a genuine convenience and carries nothing personal —
      // it is a role, which is exactly why the field asks for one.
      localStorage.setItem(deskKey(session), desk.trim())
      setBody('')
      setStatus('')
      setDone(reply)
      onPosted?.(reply)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <span className="panel__title">Reply to the reporter</span>
        <span className="panel__note">
          Addressed to <span className="ref">{request.citizen_ref || 'no reference'}</span>
        </span>
      </div>
      <div className="panel__body">
        <form className="composer" onSubmit={submit}>
          <label className="field">
            <span className="field__label">Your reply, in English</span>
            <textarea
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="What has been done, what happens next, and by when."
              required
              minLength={MIN_BODY}
            />
          </label>

          <div className="composer__grid">
            <label className="field">
              <span className="field__label">Issuing desk or role</span>
              <input
                type="text"
                value={desk}
                onChange={(e) => setDesk(e.target.value)}
                placeholder="e.g. Water Resources Desk, Nabarangpur"
                maxLength={128}
                required
                minLength={MIN_DESK}
              />
            </label>

            <label className="field">
              <span className="field__label">Move the case to</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">
                  {request.status === 'NEW' ? 'Acknowledged (automatic)' : `Leave as ${statusLabel(request.status)}`}
                </option>
                {NEXT_STATUS.map((s) => (
                  <option key={s} value={s}>
                    {statusLabel(s)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {native ? (
            <label className="check">
              <input
                type="checkbox"
                checked={translate}
                onChange={(e) => setTranslate(e.target.checked)}
              />
              Translate into {languageName(languages, request.language)} before delivery
            </label>
          ) : (
            <p className="composer__hint">
              This request was filed in English, so no translation is needed.
            </p>
          )}

          <div className="btn-row">
            <button type="submit" className="btn" disabled={!ready || busy}>
              {busy ? 'Recording…' : 'Record reply'}
            </button>
            <span className="composer__hint">
              Queued for delivery over {channelLabel(request.channel)}.
            </span>
          </div>

          {error ? (
            <div className="notice notice--bad" role="alert">
              The reply was not recorded: {error.message}
            </div>
          ) : null}

          {done ? (
            <div className="notice notice--ok" role="status">
              Reply recorded and queued for delivery over {channelLabel(done.delivery_channel)}.{' '}
              {done.body_native
                ? `Translated into ${languageName(languages, done.language)}.`
                : native
                  ? 'It could not be translated — it will go out in English.'
                  : ''}
            </div>
          ) : null}
        </form>
      </div>
    </div>
  )
}
