/**
 * `/` — the citizen journey.
 *
 * Deliberately one column and short: this is the screen that has to work on a
 * ₹6,000 phone held at arm's length in daylight. Two ways in — speak or type —
 * because the population this is built for splits almost evenly on whether they
 * can comfortably do the second one.
 */
import { useEffect, useState } from 'react'

import { submitReport } from '../api.js'
import IntakeResultCard from '../components/IntakeResultCard.jsx'
import LanguagePicker from '../components/LanguagePicker.jsx'
import PhotoAttach from '../components/PhotoAttach.jsx'
import { ErrorState, Loading } from '../components/States.jsx'
import VoiceRecorder from '../components/VoiceRecorder.jsx'
import { useCapabilities } from '../hooks/useCapabilities.jsx'

/**
 * Pre-filled so the demo, and a judge clicking around, submits something the
 * pipeline can actually resolve to a district. It is a placeholder, not a
 * default — the field is free text and geocoding is fuzzy on purpose.
 */
const EXAMPLE_PLACE = 'Nabarangpur, Odisha'

export default function CitizenIntake() {
  const caps = useCapabilities()
  const [mode, setMode] = useState('text')
  const [language, setLanguage] = useState('hi')
  const [text, setText] = useState('')
  const [place, setPlace] = useState('')
  const [blob, setBlob] = useState(null)
  const [photo, setPhoto] = useState(null)

  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Default to the first language the backend advertises rather than to a
  // hardcoded 'hi', so the picker and the request always agree.
  useEffect(() => {
    const first = caps.data?.languages?.[0]?.code
    if (first) setLanguage((cur) => (cur === 'hi' ? first : cur))
  }, [caps.data])

  const geminiOn = caps.data?.google_ai?.enabled

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      // One endpoint for both modes now, rather than `/intake/text` and
      // `/intake/voice` chosen by a ternary. `/intake/report` is the multipart
      // route that carries text, audio and a photograph in any combination, and a
      // photo can accompany either mode — a citizen who records a voice note is
      // more likely to attach a picture, not less. The two narrow endpoints stay
      // in the API for callers that only ever send one thing.
      const res = await submitReport({
        text: mode === 'voice' ? null : text.trim(),
        blob: mode === 'voice' ? blob : null,
        image: photo,
        language,
        locationText: place.trim() || null,
      })
      setResult(res)
      // Clearing the message but keeping language and place: the next report from
      // the same person is usually about the same village. The photo goes too —
      // it belongs to the problem just reported, and carrying it into the next one
      // would attach the wrong evidence to a different case.
      setText('')
      setBlob(null)
      setPhoto(null)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = !submitting && (mode === 'voice' ? !!blob : text.trim().length >= 4)

  return (
    <>
      <div className="page-head">
        <div className="page-head__eyebrow">Citizen</div>
        <h1>Tell us what your area needs</h1>
        <p className="page-head__sub">
          Speak or write in your own language. No name, no phone number, no login — we keep only which district the
          request came from.
        </p>
      </div>

      {result ? (
        // "Report another need" lives inside the card rather than under it: the
        // card is the whole screen at this point, and a button floating below a
        // finished panel reads as belonging to the page, not to the receipt.
        <IntakeResultCard
          result={result}
          languages={caps.data?.languages ?? []}
          onReset={() => setResult(null)}
        />
      ) : (
        <form className="card card__pad" onSubmit={onSubmit}>
          <div className="intake__mode" role="group" aria-label="How would you like to report?">
            <button type="button" aria-pressed={mode === 'text'} onClick={() => setMode('text')}>
              ✍ Write it
            </button>
            <button type="button" aria-pressed={mode === 'voice'} onClick={() => setMode('voice')}>
              🎙 Speak it
            </button>
          </div>

          {caps.loading ? <Loading label="Checking which languages are available…" /> : null}
          {caps.error ? <ErrorState error={caps.error} onRetry={caps.reload} /> : null}

          {caps.data ? (
            <>
              <LanguagePicker
                languages={caps.data.languages}
                value={language}
                onChange={setLanguage}
                disabled={submitting}
              />

              {mode === 'text' ? (
                <div className="field">
                  <div className="field__head">
                    <span className="field__label">What is the problem?</span>
                    <PhotoAttach file={photo} onChange={setPhoto} disabled={submitting} />
                  </div>
                  <textarea
                    className="textarea"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="हमारे गाँव में तीन महीने से नल का पानी नहीं आ रहा है…"
                    disabled={submitting}
                    lang={language}
                    aria-label="What is the problem?"
                  />
                  <span className="field__hint">
                    Write it the way you would say it. Spelling, transliteration and mixed languages are all fine.
                  </span>
                </div>
              ) : (
                <div className="field">
                  <div className="field__head">
                    <span className="field__label">Record your message</span>
                    <PhotoAttach file={photo} onChange={setPhoto} disabled={submitting} />
                  </div>
                  <VoiceRecorder onRecorded={setBlob} disabled={submitting} />
                </div>
              )}

              <label className="field">
                <span className="field__label">
                  Village, block or district <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>(optional)</span>
                </span>
                <input
                  className="input"
                  value={place}
                  onChange={(e) => setPlace(e.target.value)}
                  placeholder={EXAMPLE_PLACE}
                  disabled={submitting}
                />
                <span className="field__hint">
                  If you name a place in your message we will use that instead. This is what lets the request reach the
                  right district plan.
                </span>
              </label>

              <button type="submit" className="btn btn--block" disabled={!canSubmit}>
                {submitting ? 'Sending…' : 'Submit request'}
              </button>

              {submitting ? (
                <p className="field__hint" style={{ textAlign: 'center', marginTop: 12 }}>
                  {mode === 'voice'
                    ? 'Transcribing and understanding your recording — this takes a few seconds.'
                    : 'Understanding your message — this takes a few seconds.'}
                </p>
              ) : null}

              {error ? <ErrorState error={error} /> : null}

              <hr className="rule" />
              <p className="field__hint">
                {geminiOn
                  ? `Understood by Google ${caps.data.google_ai.model} — transcription, translation and structuring in one call. Nothing is charged; this runs on the free AI Studio tier.`
                  : 'No Gemini key is configured, so messages are classified by keyword matching only. Sector accuracy will be lower and the confidence shown will say so.'}
              </p>
            </>
          ) : null}
        </form>
      )}
    </>
  )
}
