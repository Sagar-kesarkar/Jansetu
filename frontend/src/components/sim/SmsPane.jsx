/**
 * The SMS tab: the channel that decides whether the platform reaches anyone.
 *
 * This is the least impressive-looking pane and the most important one. A
 * feature-phone SMS has no attachments, no read receipts and no session — one
 * 160-character body, and whatever the reply says has to be readable on a
 * two-line screen. If JanSetu works here, "no app, no smartphone, no literacy
 * assumption" is a fact rather than a slogan.
 *
 * Three things are modelled rather than styled.
 *
 * **Attachments are absent, not disabled-looking.** There is no clip button to
 * grey out, because the point is that this channel never had one.
 *
 * **The 160-character limit is enforced and counted.** A real gateway silently
 * splits a longer body into segments that arrive out of order, so a report that
 * overflows is a report that arrives scrambled. The counter turns red before the
 * limit rather than after.
 *
 * **Delivery is slow on purpose.** `SEND_DELAY_MS` stands in for a store-and-
 * forward hop over 2G. A demo where SMS feels as instant as WhatsApp quietly
 * misrepresents the thing being demonstrated, and the wait is where the
 * "Processing…" state earns its place.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { submitChannelReport } from '../../api.js'
import { HANDSET, nextId, useLanguages } from './useLanguages.js'

const SMS_LIMIT = 160
const SEND_DELAY_MS = 800
const SHORTCODE = '51969'

const MENU_BY_LANG = {
  hi: 'जनसेतु में आपका स्वागत है।\n\nविकल्प चुनें:\n1. नई समस्या दर्ज करें\n2. स्थिति ट्रैक करें\n3. राज्य या ज़िला बजट देखें\n\n1, 2, या 3 लिखकर भेजें।',
  bn: 'জনসেতুতে স্বাগতম।\n\nবিকল্প বাছুন:\n1. অভিযোগ নথিভুক্ত করুন\n2. ট্র্যাক করুন\n3. বাজেট দেখুন\n\n1, 2, বা 3 লিখে উত্তর দিন।',
  ta: 'ஜன்சேதுவிற்கு வரவேற்கிறோம்.\n\nதேர்வு:\n1. புகார் பதிவு செய்ய\n2. கண்காணிக்க\n3. பட்ஜெட் பார்க்க\n\n1, 2, அல்லது 3 என அனுப்பவும்.',
  te: 'జనసేతుకు స్వాగతం.\n\nఎంపిక:\n1. ఫిర్యాదు నమోదు చేయండి\n2. ట్రాక్ చేయండి\n3. బడ్జెట్ చూడండి\n\n1, 2, లేదా 3 అని పంపండి.',
  mr: 'जनसेतू मध्ये आपले स्वागत आहे.\n\nपर्याय निवडा:\n1. तक्रार नोंदवा\n2. ट्रॅक करा\n3. बजेट पहा\n\n1, 2, किंवा 3 पाठवा.',
  gu: 'જનસેતુમાં આપનું સ્વાગત છે.\n\nવિકલ્પ:\n1. ફરિયાદ નોંધાવો\n2. ટ્રેક કરો\n3. બજેટ જુઓ\n\n1, 2, અથવા 3 મોકલો.',
  kn: 'ಜನಸೇತುವಿಗೆ ಸ್ವಾಗತ.\n\nಆಯ್ಕೆ:\n1. ದೂರನ್ನು ದಾಖಲಿಸಿ\n2. ಟ್ರ್ಯಾಕ್ ಮಾಡಿ\n3. ಬಜೆಟ್ ನೋಡಿ\n\n1, 2, ಅಥವಾ 3 ಕಳುಹಿಸಿ.',
  ml: 'ജൻസേതുവിലേക്ക് സ്വാഗതം.\n\nഓപ്ഷൻ:\n1. പരാതി നൽകുക\n2. ട്രാക്ക് ചെയ്യുക\n3. ബജറ്റ് കാണുക\n\n1, 2, അല്ലെങ്കിൽ 3 അയക്കുക.',
  pa: 'ਜਨਸੇਤੂ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ।\n\nਚੋਣ:\n1. ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ\n2. ਟ੍ਰੈਕ ਕਰੋ\n3. ਬਜਟ ਦੇਖੋ\n\n1, 2, ਜਾਂ 3 ਭੇਜੋ।',
  or: 'ଜନସେତୁକୁ ସ୍ୱାਗତ।\n\nବିକଳ୍ପ:\n1. ଅଭିଯୋଗ ଦର୍ଜ କରନ୍ତୁ\n2. ଟ୍ରାକ୍ କରନ୍ତୁ\n3. ବଜେଟ୍ ଦେଖନ୍ତୁ\n\n1, 2, କିମ୍ବା 3 ପଠାନ୍ତୁ.',
  as: 'জনসেতুলৈ স্বাগতম।\n\nবিকল্প:\n1. অভিযোগ পঞ্জীয়ন কৰক\n2. ট্ৰেক কৰক\n3. বাজেট চাওক\n\n1, 2, বা 3 পঠিয়াওক।',
  ur: 'جن سیتو میں خوش آمدید۔\n\nانتخاب:\n1. شکایت درج کریں\n2. ٹریک کریں\n3. بجٹ دیکھیں\n\n1، 2، یا 3 بھیجیں۔',
  en: 'Welcome to JanSetu.\n\nPlease choose:\n1. Register a complaint\n2. Track a complaint\n3. View state or district budget\n\nReply 1, 2, or 3.',
}

export default function SmsPane() {
  const languages = useLanguages()
  const navigate = useNavigate()
  const [language, setLanguage] = useState('en')
  const [draft, setDraft] = useState('')
  const [thread, setThread] = useState([
    { id: nextId(), from: 'them', text: MENU_BY_LANG.en },
  ])
  const [busy, setBusy] = useState(false)
  const [slowProcessing, setSlowProcessing] = useState(false)
  const [phase, setPhase] = useState('') // sending | delivered | processing
  const listRef = useRef(null)
  const timers = useRef([])
  const timeoutRef = useRef(null)

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [thread, phase, busy, slowProcessing])

  const push = useCallback((msg) => setThread((prev) => [...prev, { id: nextId(), ...msg }]), [])
  const wait = (ms) => new Promise((resolve) => timers.current.push(setTimeout(resolve, ms)))

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang)
    push({
      from: 'them',
      text: MENU_BY_LANG[newLang] || MENU_BY_LANG.en,
    })
  }

  const over = draft.length > SMS_LIMIT

  const send = async () => {
    const body = draft.trim()
    if (!body || over) return

    push({ from: 'me', text: body })
    setDraft('')
    setBusy(true)
    setSlowProcessing(false)

    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setSlowProcessing(true)
    }, 10000)

    try {
      setPhase('sending')
      await wait(SEND_DELAY_MS)
      setPhase('processing')

      const result = await submitChannelReport({
        text: body,
        language,
        locationText: null,
        channel: 'sms',
        citizenRef: HANDSET.sms,
      })

      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      setPhase('')

      // If backend switched language dynamically
      if (result.language && result.language !== language) {
        setLanguage(result.language)
      }

      if (result.classification === 'CONVERSATIONAL' || (result.request_id === 0 && !result.track_token)) {
        push({
          from: 'them',
          text: result.acknowledgement_native || result.summary_en || 'JANSETU: Option processed.',
        })
      } else {
        push({
          from: 'them',
          text: result.acknowledgement_native || `JANSETU: Request registered. Ref ${result.track_token || `#${result.request_id}`}. District: ${
            result.district || 'pending'
          }. Reply STATUS <ref> to check.`,
          token: result.track_token,
        })
      }
    } catch (err) {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      setPhase('')
      push({
        from: 'them',
        text: 'JANSETU: We could not process your message at this time. Your complaint has not been registered and no token has been generated. Please try again.',
        error: true,
      })
    } finally {
      setBusy(false)
      setSlowProcessing(false)
    }
  }

  return (
    <div className="sms">
      <div className="sms__bar">
        <span className="sms__to">To: {SHORTCODE}</span>
        <label className="sms__lang">
          <span className="sr-only">Language</span>
          <select value={language} onChange={(e) => handleLanguageChange(e.target.value)} disabled={busy}>
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.code.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="sms__log" ref={listRef}>
        {thread.map((m) => (
          <div
            key={m.id}
            className={`sms__msg sms__msg--${m.from === 'me' ? 'me' : 'them'}${m.error ? ' sms__msg--err' : ''}`}
          >
            <span className="sms__msg-from">{m.from === 'me' ? `${HANDSET.sms} ▸` : `◂ ${SHORTCODE}`}</span>
            <span className="sms__msg-text">{m.text}</span>
            {m.token ? (
              <button
                type="button"
                className="sms__track"
                onClick={() => navigate(`/track/${m.token}`)}
              >
                Track {m.token} →
              </button>
            ) : null}
          </div>
        ))}
        {busy ? (
          <div className="sms__msg sms__msg--them sms__msg--processing" role="status" aria-live="polite">
            <span>
              {slowProcessing
                ? 'This is taking a little longer than usual. Your message is still being processed.'
                : 'Processing your message'}
            </span>
            <span className="sim-dot-pulse" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        ) : null}
      </div>

      <div className="sms__compose">
        <textarea
          className="sms__input"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          placeholder="Type your reply…"
          disabled={busy}
          aria-label="SMS text"
          aria-invalid={over}
        />
        <div className="sms__foot">
          <span className={`sms__count${over ? ' sms__count--over' : ''}`}>
            {draft.length}/{SMS_LIMIT}
          </span>
          <button
            type="button"
            className="sms__send"
            onClick={send}
            disabled={busy || !draft.trim() || over}
          >
            SEND
          </button>
        </div>
      </div>
    </div>
  )
}
