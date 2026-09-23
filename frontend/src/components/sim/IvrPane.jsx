/**
 * The IVR tab: Interactive Multilingual Telephone Helpline Handset.
 *
 * Fully integrated with the server-side state machine (`/ivr/simulate` & `/ivr/sessions`),
 * supporting live voice recording (MediaRecorder), Web Speech synthesis, DTMF keypad,
 * typed assisted fallback, scripted demonstration, and offline fallback mode.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ivrStep } from '../../api.js'
import Icon from '../Icon.jsx'
import { HANDSET, nextId } from './useLanguages.js'

const HELPLINE_TITLE = 'JanSetu IVR Helpline'
const MAX_RECORD_MS = 60_000
const MAX_UTTERANCE_CHARS = 300

// Sample texts for Assisted / Scripted demonstration
const SCRIPTED_COMPLAINTS = [
  { text: 'There has been no clean water supply in our village for three days.', lang: 'en', label: 'Water supply failure (EN)' },
  { text: 'हमारे गाँव में तीन दिनों से पीने के पानी की आपूर्ति बंद है।', lang: 'hi', label: 'पानी की समस्या (HI)' },
  { text: 'எங்கள் கிராமத்தில் மூன்று நாட்களாக குடிநீர் விநியோகம் இல்லை.', lang: 'ta', label: 'குடிநீர் பிரச்சனை (TA)' },
  { text: 'మా గ్రామంలో మూడు రోజులుగా తాగునీటి సరఫరా లేదు.', lang: 'te', label: 'తాగునీటి సమస్య (TE)' },
  { text: 'आमच्या गावात तीन दिवसांपासून पिण्याच्या पाण्याची समस्या आहे.', lang: 'mr', label: 'पिण्याचे पाणी (MR)' },
]

const SCRIPTED_LOCATIONS = [
  'Ward 4, Nabarangpur, Odisha',
  'Pune City, Pune, Maharashtra',
  'Kosagumuda, Nabarangpur, Odisha',
  'Barpeta Town, Barpeta, Assam',
  'Madurai North, Madurai, Tamil Nadu',
]

/** Keypad labels mapped dynamically to the server's conversation state */
function getPadLayout(state) {
  switch (state) {
    case 'LANGUAGE_MENU':
    case 'SELECT_LANGUAGE':
      return [
        { digit: '1', label: 'हिन्दी' },
        { digit: '2', label: 'தமிழ்' },
        { digit: '3', label: 'తెలుగు' },
        { digit: '4', label: 'English' },
        { digit: '5', label: 'मराठी' },
        { digit: '6', label: 'More...' },
        { digit: '0', label: 'Repeat' },
      ]
    case 'MORE_LANGUAGES_MENU':
      return [
        { digit: '1', label: 'বাংলা' },
        { digit: '2', label: 'ગુજરાતી' },
        { digit: '3', label: 'ಕನ್ನಡ' },
        { digit: '4', label: 'മലയാളം' },
        { digit: '5', label: 'ଓଡ଼ିଆ' },
        { digit: '6', label: 'ਪੰਜਾਬੀ' },
        { digit: '7', label: 'অসমীয়া' },
        { digit: '8', label: 'اردو' },
        { digit: '9', label: 'Back' },
        { digit: '0', label: 'Repeat' },
      ]
    case 'MAIN_MENU':
      return [
        { digit: '1', label: 'Register' },
        { digit: '2', label: 'Track' },
        { digit: '3', label: 'Budget SMS' },
        { digit: '8', label: 'Language' },
        { digit: '0', label: 'Repeat' },
        { digit: '9', label: 'End Call' },
      ]
    case 'REVIEW_REQUEST':
      return [
        { digit: '1', label: 'Confirm' },
        { digit: '2', label: 'Redo Problem' },
        { digit: '3', label: 'Redo Loc' },
        { digit: '0', label: 'Repeat' },
        { digit: '9', label: 'Cancel' },
      ]
    case 'REGISTRATION_SUCCESS':
    case 'TOKEN_MENU':
    case 'CONFIRMING':
      return [
        { digit: '1', label: 'Hear Token' },
        { digit: '2', label: 'SMS Token' },
        { digit: '0', label: 'Repeat All' },
        { digit: '9', label: 'End Call' },
      ]
    case 'TRACK_TOKEN_CONFIRMATION':
      return [
        { digit: '1', label: 'Correct' },
        { digit: '2', label: 'Re-enter' },
        { digit: '0', label: 'Repeat' },
        { digit: '9', label: 'Main Menu' },
      ]
    case 'TRACK_RESULT':
      return [
        { digit: '1', label: 'Hear Again' },
        { digit: '2', label: 'SMS Link' },
        { digit: '9', label: 'Main Menu' },
      ]
    case 'FUNDS_INTRO':
    case 'FUNDS_SMS_CONFIRMATION':
      return [
        { digit: '1', label: 'Send SMS' },
        { digit: '2', label: 'Main Menu' },
        { digit: '0', label: 'Repeat' },
      ]
    case 'FUNDS_SMS_RESULT':
      return [
        { digit: '9', label: 'Main Menu' },
        { digit: '0', label: 'Repeat' },
      ]
    default:
      return [
        { digit: '1', label: '' },
        { digit: '2', label: '' },
        { digit: '3', label: '' },
        { digit: '4', label: '' },
        { digit: '5', label: '' },
        { digit: '6', label: '' },
        { digit: '7', label: '' },
        { digit: '8', label: '' },
        { digit: '9', label: '' },
        { digit: '*', label: '' },
        { digit: '0', label: 'Repeat' },
        { digit: '#', label: 'Finish' },
      ]
  }
}

export default function IvrPane() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState('idle') // idle | dialling | live | recording | ended
  const [mode, setMode] = useState('live') // live | assisted | scripted-demo | offline-demo
  const [state, setState] = useState(null)
  const [currentLang, setCurrentLang] = useState('hi')
  const [lines, setLines] = useState([])
  const [busy, setBusy] = useState(false)
  const [token, setToken] = useState(null)
  const [tokensList, setTokensList] = useState([])
  const [complaintPreview, setComplaintPreview] = useState(null)
  const [locationPreview, setLocationPreview] = useState(null)
  const [smsResult, setSmsResult] = useState(null)
  const [canRecord, setCanRecord] = useState(false)
  const [canPress, setCanPress] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [showTypedInput, setShowTypedInput] = useState(false)
  const [typedText, setTypedText] = useState('')
  const [speakerOn, setSpeakerOn] = useState(true)
  const [muted, setMuted] = useState(false)

  const recorder = useRef(null)
  const chunks = useRef([])
  const stopTimer = useRef(null)
  const tick = useRef(null)
  const logRef = useRef(null)

  const push = useCallback((line) => setLines((prev) => [...prev, { id: nextId(), ...line }]), [])

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines, busy])

  // Cleanup timers & audio on unmount
  useEffect(() => {
    return () => {
      clearTimeout(stopTimer.current)
      clearInterval(tick.current)
      try {
        recorder.current?.stream?.getTracks?.().forEach((t) => t.stop())
        if (recorder.current?.state === 'recording') recorder.current.stop()
      } catch {
        /* cleaned up */
      }
      window.speechSynthesis?.cancel()
    }
  }, [])

  // Browser speech playback
  const say = useCallback((text, langCode) => {
    if (!speakerOn) return
    const synth = window.speechSynthesis
    if (!synth || !text || typeof synth.speak !== 'function') return
    try {
      if (!(synth.getVoices() || []).length) return
      synth.cancel()
      const utter = new SpeechSynthesisUtterance(text.slice(0, MAX_UTTERANCE_CHARS))
      utter.lang = langCode ? `${langCode}-IN` : 'hi-IN'
      utter.rate = 0.92
      utter.onerror = () => {}
      synth.speak(utter)
    } catch {
      /* Gracefully degrades to on-screen text */
    }
  }, [speakerOn])

  // Prime browser speech voices
  useEffect(() => {
    const synth = window.speechSynthesis
    if (!synth) return undefined
    const prime = () => synth.getVoices()
    prime()
    synth.addEventListener?.('voiceschanged', prime)
    return () => synth.removeEventListener?.('voiceschanged', prime)
  }, [])

  // Apply server response to UI
  const apply = useCallback(
    (res) => {
      if (!res) return
      setState(res.state ?? null)
      if (res.language) setCurrentLang(res.language)

      const prompts = (res.prompts ?? []).map((p) => (typeof p === 'string' ? p : p?.text)).filter(Boolean)
      prompts.forEach((text) => push({ who: 'line', text }))
      if (prompts.length && speakerOn) say(prompts.join(' '), res.language)

      if (res.digits_spoken?.length) {
        push({ who: 'line', text: res.digits_spoken.join(' · '), spelled: true })
        if (speakerOn) say(res.digits_spoken.join(', '), res.language)
      }

      if (res.docket_ref) setToken(res.docket_ref)
      if (res.registered_tokens?.length) setTokensList(res.registered_tokens)
      if (res.complaint_preview) setComplaintPreview(res.complaint_preview)
      if (res.location_preview) setLocationPreview(res.location_preview)
      if (res.sms_result) setSmsResult(res.sms_result)

      setCanPress(Boolean(res.gather_dtmf))
      setCanRecord(Boolean(res.record_audio))

      if (res.hangup) {
        setPhase('ended')
        setCanPress(false)
        setCanRecord(false)
      }
    },
    [push, say, speakerOn],
  )

  // Step interaction
  const step = useCallback(
    async (payload) => {
      setBusy(true)
      try {
        if (mode === 'offline-demo') {
          // Local deterministic offline walkthrough
          await new Promise((r) => setTimeout(r, 600))
          const offlineRes = handleOfflineStep(payload, state, currentLang)
          apply(offlineRes)
          return offlineRes
        }

        const res = await ivrStep({ callerPhone: HANDSET.ivr, mode, ...payload })
        apply(res)
        return res
      } catch (err) {
        push({ who: 'error', text: `Call notice: ${err.message}` })
        if (mode !== 'offline-demo') {
          // Offer graceful retry / offline demo switch
          push({ who: 'error', text: 'Backend unavailable. You can switch to Offline Demo mode.' })
        }
        setPhase('ended')
        return null
      } finally {
        setBusy(false)
      }
    },
    [apply, mode, push, state, currentLang],
  )

  const dial = async () => {
    setPhase('dialling')
    setLines([])
    setToken(null)
    setTokensList([])
    setComplaintPreview(null)
    setLocationPreview(null)
    setSmsResult(null)
    setElapsed(0)
    clearInterval(tick.current)
    tick.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    setPhase('live')
    await step({ action: 'start' })
  }

  const press = async (digit) => {
    if (!canPress || busy) return
    push({ who: 'me', text: `Pressed [ ${digit} ]` })
    window.speechSynthesis?.cancel()
    await step({ action: 'dtmf', digits: String(digit) })
  }

  // Keyboard navigation for DTMF keys
  useEffect(() => {
    if (phase !== 'live' && phase !== 'recording') return
    const onKey = (e) => {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return
      if ('0123456789*#'.includes(e.key)) {
        e.preventDefault()
        press(e.key)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase, canPress, busy])

  const startRecording = async () => {
    if (!canRecord || busy) return
    window.speechSynthesis?.cancel()
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      // Microphone unavailable -> enter typed assisted mode
      setMode('assisted')
      setShowTypedInput(true)
      push({ who: 'error', text: 'Microphone unavailable — accessible typed input activated.' })
      return
    }

    chunks.current = []
    const rec = new MediaRecorder(stream)
    recorder.current = rec
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' })
      setPhase('live')
      push({ who: 'me', text: `Spoke for ${Math.max(1, Math.round(blob.size / 8000))}s` })
      const b64 = await toBase64(blob)
      await step({ action: 'audio', audioBase64: b64, audioMime: blob.type || 'audio/webm' })
    }
    rec.start()
    setPhase('recording')
    stopTimer.current = setTimeout(() => {
      if (recorder.current?.state === 'recording') recorder.current.stop()
    }, MAX_RECORD_MS)
  }

  const stopRecording = () => {
    clearTimeout(stopTimer.current)
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }

  const submitTyped = async () => {
    if (!typedText.trim() || busy) return
    const textToSend = typedText.trim()
    setTypedText('')
    push({ who: 'me', text: textToSend })
    window.speechSynthesis?.cancel()
    await step({ action: 'audio', textSimulation: textToSend })
  }

  const hangUp = async () => {
    clearInterval(tick.current)
    clearTimeout(stopTimer.current)
    window.speechSynthesis?.cancel()
    try {
      if (recorder.current?.state === 'recording') recorder.current.stop()
    } catch {
      /* stopped */
    }
    setPhase('ended')
    setCanPress(false)
    setCanRecord(false)
    await step({ action: 'hangup' })
  }

  const padLayout = getPadLayout(state)

  return (
    <div className={`ivr ivr--${phase}`}>
      {/* Mode Badge & Banner */}
      <div className="ivr__topbar">
        <div className="ivr__mode-wrap">
          <span className={`ivr__mode-badge ivr__mode-badge--${mode}`}>
            {mode.toUpperCase()} MODE
          </span>
          <select
            className="ivr__mode-select"
            value={mode}
            onChange={(e) => {
              setMode(e.target.value)
              if (e.target.value === 'assisted') setShowTypedInput(true)
            }}
            aria-label="Select IVR operating mode"
          >
            <option value="live">Live (Voice + AI)</option>
            <option value="assisted">Assisted (Typed)</option>
            <option value="scripted-demo">Scripted Demo</option>
            <option value="offline-demo">Offline Demo</option>
          </select>
        </div>

        {mode === 'offline-demo' ? (
          <div className="ivr__offline-banner" role="alert">
            <strong>OFFLINE DEMONSTRATION — NOT REGISTERED</strong>
            <button type="button" onClick={() => setMode('live')}>
              Retry live connection
            </button>
          </div>
        ) : null}
      </div>

      {/* Handset Header */}
      <div className="ivr__head">
        <div className="ivr__head-info">
          <span className="ivr__num">{HELPLINE_TITLE}</span>
          <span className="ivr__timer">{clock(elapsed)}</span>
        </div>
        <div className="ivr__head-actions">
          <button
            type="button"
            className={`ivr__icon-btn ${!speakerOn ? 'ivr__icon-btn--off' : ''}`}
            onClick={() => setSpeakerOn((s) => !s)}
            title={speakerOn ? 'Speaker On' : 'Speaker Off'}
            aria-label="Toggle speaker"
          >
            <Icon name={speakerOn ? 'volume-2' : 'volume-x'} size={16} />
          </button>
          <span className="ivr__lang-tag">{currentLang.toUpperCase()}</span>
          {state ? <span className="ivr__state">{state}</span> : null}
        </div>
      </div>

      {/* Transcript Log */}
      <div className="ivr__log" ref={logRef} aria-live="polite">
        {lines.map((l) => (
          <div
            key={l.id}
            className={`ivr__line ivr__line--${l.who}${l.spelled ? ' ivr__line--spelled' : ''}`}
          >
            {l.who === 'line' ? <strong className="ivr__line-tag">Helpline:</strong> : null}
            {l.who === 'me' ? <strong className="ivr__line-tag">You:</strong> : null}
            <span>{l.text}</span>
          </div>
        ))}
        {busy ? <div className="ivr__line ivr__line--wait">Processing response…</div> : null}
      </div>

      {/* Structured Preview Cards */}
      {(complaintPreview || locationPreview) && (
        <div className="ivr__cards-row">
          {complaintPreview ? (
            <div className="ivr__card">
              <span className="ivr__card-label">Issue Summary</span>
              <p className="ivr__card-val">{complaintPreview}</p>
            </div>
          ) : null}
          {locationPreview ? (
            <div className="ivr__card">
              <span className="ivr__card-label">Location</span>
              <p className="ivr__card-val">{locationPreview}</p>
            </div>
          ) : null}
        </div>
      )}

      {/* Token Receipt Card */}
      {token ? (
        <div className="ivr__token">
          <div className="ivr__token-head">
            <span className="ivr__token-key">Official Tracking Token</span>
            <code>{token}</code>
          </div>
          {mode !== 'offline-demo' ? (
            <button
              type="button"
              className="ivr__token-btn"
              onClick={() => navigate(`/track/${token}`)}
            >
              Track on Web →
            </button>
          ) : (
            <span className="ivr__demo-token-notice">Demo token (Not in live database)</span>
          )}
        </div>
      ) : null}

      {/* Public Funds SMS Card */}
      {smsResult ? (
        <div className="ivr__sms-card">
          <Icon name="check-circle" size={16} />
          <div className="ivr__sms-content">
            <span>{smsResult.type === 'public_funds_link' ? 'Public funds portal SMS sent' : 'Tracking SMS sent'}</span>
            {smsResult.simulated ? (
              <small className="ivr__simulated-notice">Simulated SMS — not delivered to a real handset</small>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Interactive Keypad */}
      {phase !== 'idle' && phase !== 'ended' && canPress ? (
        <div className="ivr__pad-section">
          <span className="ivr__pad-title">Telephone Keypad</span>
          <div className="ivr__pad">
            {padLayout.map((k) => (
              <button
                key={k.digit}
                type="button"
                className="ivr__key"
                onClick={() => press(k.digit)}
                disabled={busy}
                aria-label={`Key ${k.digit} ${k.label}`}
              >
                <strong className="ivr__key-digit">{k.digit}</strong>
                {k.label ? <span className="ivr__key-label">{k.label}</span> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {/* Voice Recording / Microphone Section */}
      {canRecord && phase !== 'ended' ? (
        <div className="ivr__mic-section">
          {phase === 'recording' ? (
            <div className="ivr__recording-box">
              <span className="ivr__pulse" aria-hidden="true" />
              <span className="ivr__rec-label">Listening… speak your response</span>
              <button type="button" className="ivr__stop-btn" onClick={stopRecording}>
                Press # or Tap to Finish
              </button>
            </div>
          ) : (
            <div className="ivr__rec-actions">
              <button
                type="button"
                className="ivr__rec-btn"
                onClick={startRecording}
                disabled={busy}
              >
                <Icon name="mic" size={20} />
                <span>Speak problem or location</span>
              </button>
              <button
                type="button"
                className="ivr__toggle-typed"
                onClick={() => setShowTypedInput((v) => !v)}
              >
                {showTypedInput ? 'Hide typed input' : 'Use typed input instead'}
              </button>
            </div>
          )}
        </div>
      ) : null}

      {/* Accessible Typed Input & Scripted Selectors */}
      {(showTypedInput || mode === 'assisted' || mode === 'scripted-demo') && phase !== 'ended' && phase !== 'idle' ? (
        <div className="ivr__typed-box">
          {mode === 'scripted-demo' && state === 'COMPLAINT_LISTENING' ? (
            <div className="ivr__scripted-helpers">
              <span className="ivr__helper-title">Sample Complaints:</span>
              <div className="ivr__helper-chips">
                {SCRIPTED_COMPLAINTS.map((sc, i) => (
                  <button
                    key={i}
                    type="button"
                    className="ivr__chip"
                    onClick={() => {
                      setTypedText(sc.text)
                      setCurrentLang(sc.lang)
                    }}
                  >
                    {sc.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {mode === 'scripted-demo' && state === 'LOCATION_LISTENING' ? (
            <div className="ivr__scripted-helpers">
              <span className="ivr__helper-title">Sample Locations:</span>
              <div className="ivr__helper-chips">
                {SCRIPTED_LOCATIONS.map((sl, i) => (
                  <button
                    key={i}
                    type="button"
                    className="ivr__chip"
                    onClick={() => setTypedText(sl)}
                  >
                    {sl}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="ivr__typed-row">
            <input
              type="text"
              className="ivr__typed-field"
              placeholder="Type your response here..."
              value={typedText}
              onChange={(e) => setTypedText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitTyped()}
              disabled={busy}
            />
            <button
              type="button"
              className="ivr__typed-send"
              onClick={submitTyped}
              disabled={busy || !typedText.trim()}
            >
              Send
            </button>
          </div>
        </div>
      ) : null}

      {/* Handset Footer */}
      <div className="ivr__foot">
        {phase === 'idle' ? (
          <div className="ivr__idle-panel">
            <p className="ivr__blurb">
              Toll-free helpline in 13 Indian languages. No smartphone or reading required.
            </p>
            <button type="button" className="ivr__dial-btn" onClick={dial}>
              <Icon name="phone" size={20} />
              <span>Start Call</span>
            </button>
          </div>
        ) : phase === 'ended' ? (
          <div className="ivr__ended-panel">
            <button type="button" className="ivr__dial-btn" onClick={dial}>
              <Icon name="phone" size={18} />
              <span>Call Again</span>
            </button>
          </div>
        ) : (
          <div className="ivr__live-controls">
            <button
              type="button"
              className="ivr__ctrl-btn"
              onClick={() => step({ action: 'dtmf', digits: '0' })}
              title="Repeat current menu (0)"
              disabled={busy}
            >
              <Icon name="rotate-ccw" size={16} />
              <span>Repeat (0)</span>
            </button>
            <button type="button" className="ivr__hangup-btn" onClick={hangUp}>
              <Icon name="phone-off" size={18} />
              <span>End Call</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function clock(total) {
  const m = String(Math.floor(total / 60)).padStart(2, '0')
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}`
}

function toBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the audio recording'))
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.readAsDataURL(blob)
  })
}

/** Local deterministic offline simulator helper */
function handleOfflineStep(payload, currentState, currentLang) {
  const action = payload.action || 'start'
  const digits = payload.digits

  if (action === 'start' || !currentState) {
    return {
      status: 'success',
      state: 'LANGUAGE_MENU',
      language: 'en',
      prompts: [{ text: 'OFFLINE DEMO: Welcome to JanSetu. Press 1 for Hindi, 4 for English. Press 0 to repeat.' }],
      gather_dtmf: { valid_digits: ['1', '2', '3', '4', '5', '6', '0'] },
    }
  }

  if (currentState === 'LANGUAGE_MENU') {
    return {
      status: 'success',
      state: 'MAIN_MENU',
      language: digits === '1' ? 'hi' : 'en',
      prompts: [{ text: 'OFFLINE DEMO: Press 1 to register a civic request, 2 to track. Press 9 to end.' }],
      gather_dtmf: { valid_digits: ['1', '2', '3', '8', '0', '9'] },
    }
  }

  if (currentState === 'MAIN_MENU' && digits === '1') {
    return {
      status: 'success',
      state: 'COMPLAINT_LISTENING',
      language: currentLang,
      prompts: [{ text: 'OFFLINE DEMO: Describe the local issue you are facing.' }],
      record_audio: { max_duration_sec: 45 },
    }
  }

  if (currentState === 'COMPLAINT_LISTENING') {
    return {
      status: 'success',
      state: 'LOCATION_LISTENING',
      language: currentLang,
      complaint_preview: payload.textSimulation || 'Local drinking water supply breakdown',
      prompts: [{ text: 'OFFLINE DEMO: Please state where this problem is located.' }],
      record_audio: { max_duration_sec: 45 },
    }
  }

  if (currentState === 'LOCATION_LISTENING') {
    return {
      status: 'success',
      state: 'REVIEW_REQUEST',
      language: currentLang,
      complaint_preview: 'Local drinking water supply breakdown',
      location_preview: payload.textSimulation || 'Ward 4, Nabarangpur, Odisha',
      prompts: [{ text: 'OFFLINE DEMO: Please confirm. Problem: Water supply. Location: Nabarangpur. Press 1 to register.' }],
      gather_dtmf: { valid_digits: ['1', '2', '3', '0', '9'] },
    }
  }

  if (currentState === 'REVIEW_REQUEST' && digits === '1') {
    return {
      status: 'success',
      state: 'REGISTRATION_SUCCESS',
      language: currentLang,
      docket_ref: 'DEMO-JS-0001',
      registered_tokens: ['DEMO-JS-0001'],
      prompts: [{ text: 'OFFLINE DEMONSTRATION — NOT REGISTERED IN DATABASE. Demo Token:' }],
      digits_spoken: ['D', 'E', 'M', 'O', '-', 'J', 'S', '-', '0', '0', '0', '1'],
      gather_dtmf: { valid_digits: ['1', '2', '0', '9'] },
    }
  }

  return {
    status: 'success',
    state: 'ENDED',
    language: currentLang,
    prompts: [{ text: 'OFFLINE DEMO: Call completed. Thank you.' }],
    hangup: true,
  }
}
