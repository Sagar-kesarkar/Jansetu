/**
 * The WhatsApp tab: a two-turn bot conversation ending in a tracking token.
 *
 * The two turns are the point, not padding. A real messaging bot cannot rank a
 * report it cannot place, and a citizen typing "no water for four days" has not
 * said where — so the bot asks, once, before it submits anything. That is also
 * why the first turn never touches the backend: submitting on the first message
 * and patching the district afterwards would put a row in the table that the
 * hotspot query has to either exclude or misplace.
 *
 * Attachments are real. A photograph goes to Gemini as image bytes and comes back
 * as `image_verification` text; the file itself is never written to disk, which
 * is what lets the citizen journey accept a photo at all. A voice note is a real
 * `MediaRecorder` capture transcribed by the same multimodal call the citizen web
 * form uses.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { submitChannelReport } from '../../api.js'
import Icon from '../Icon.jsx'
import { useLanguages } from './useLanguages.js'

let _msgSeq = 0
function nextMsgId() {
  return `wa_${Date.now()}_${++_msgSeq}`
}

function makeSessionId() {
  return `wa_sim_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

const MENU_BY_LANG = {
  hi: 'जनसेतु में आपका स्वागत है।\n\nकृपया सेवा चुनें:\n\n1. नई समस्या दर्ज करें\n2. स्थिति ट्रैक करें\n3. राज्य या ज़िला बजट देखें\n\n1, 2, या 3 लिखकर भेजें।',
  bn: 'জনসেতুতে স্বাগতম।\n\nঅনুগ্রহ করে একটি সেবা বেছে নিন:\n\n1. অভিযোগ নথিভুক্ত করুন\n2. অভিযোগ ট্র্যাক করুন\n3. রাজ্য বা জেলা বাজেট দেখুন\n\n1, 2, বা 3 লিখে উত্তর দিন।',
  ta: 'ஜன்சேதுவிற்கு வரவேற்கிறோம்.\n\nசேவையைத் தேர்ந்தெடுக்கவும்:\n\n1. புகார் பதிவு செய்ய\n2. புகாரை கண்காணிக்க\n3. மாநில அல்லது மாவட்ட வரவு செலவு திட்டத்தை பார்க்க\n\n1, 2, அல்லது 3 என பதிலளிக்கவும்.',
  te: 'జనసేతుకు స్వాగతం.\n\nదయచేసి సేవను ఎంచుకోండి:\n\n1. ఫిర్యాదు నమోదు చేయండి\n2. ఫిర్యాదు స్థితిని ట్రాక్ చేయండి\n3. రాష్ట్ర లేదా జిల్లా బడ్జెట్ చూడండి\n\n1, 2, లేదా 3 అని రిప్లై ఇవ్వండి.',
  mr: 'जनसेतू मध्ये आपले स्वागत आहे.\n\nकृपया सेवा निवडा:\n\n1. तक्रार नोंदवा\n2. तक्रार ट्रॅक करा\n3. राज्य किंवा जिल्हा बजेट पहा\n\n1, 2, किंवा 3 पाठवून उत्तर द्या.',
  gu: 'જનસેતુમાં આપનું સ્વાગત છે.\n\nકૃપા કરીને સેવા પસંદ કરો:\n\n1. ફરિયાદ નોંધાવો\n2. ફરિયાદ ટ્રેક કરો\n3. રાજ્ય અથવા જિલ્લા બજેટ જુઓ\n\n1, 2, અથવા 3 લખી મોકલો.',
  kn: 'ಜನಸೇತುವಿಗೆ ಸ್ವಾಗತ.\n\nದಯವಿಟ್ಟು ಸೇವೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:\n\n1. ದೂರನ್ನು ದಾಖಲಿಸಿ\n2. ದೂರನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ\n3. ರಾಜ್ಯ ಅಥವಾ ಜಿಲ್ಲಾ ಬಜೆಟ್ ನೋಡಿ\n\n1, 2, ಅಥವಾ 3 ಎಂದು ಉತ್ತರಿಸಿ.',
  ml: 'ജൻസേതുവിലേക്ക് സ്വാഗതം.\n\nദയവായി ഒരു സേവനം തിരഞ്ഞെടുക്കുക:\n\n1. പരാതി നൽകുക\n2. പരാതി ട്രാക്ക് ചെയ്യുക\n3. സംസ്ഥാന അല്ലെങ്കിൽ ജില്ലാ ബജറ്റ് കാണുക\n\n1, 2, അല്ലെങ്കിൽ 3 എന്ന് മറുപടി നൽകുക.',
  pa: 'ਜਨਸੇਤੂ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ।\n\nਕਿਰਪਾ ਕਰਕੇ ਸੇਵਾ ਚੁਣੋ:\n\n1. ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ\n2. ਸ਼ਿਕਾਇਤ ਟ੍ਰੈਕ ਕਰੋ\n3. ਰਾਜ ਜਾਂ ਜ਼ਿਲ੍ਹਾ ਬਜਟ ਦੇਖੋ\n\n1, 2, ਜਾਂ 3 ਲਿਖ ਕੇ ਜਵਾਬ ਦਿਓ।',
  or: 'ଜନସେତୁକୁ ସ୍ୱାଗତ।\n\nଦୟାକରି ଏକ ସେବା ବାଛନ୍ତୁ:\n\n1. ଅଭିଯୋଗ ଦର୍ଜ କରନ୍ତୁ\n2. ଅଭିଯୋଗ ଟ୍ରାକ୍ କରନ୍ତୁ\n3. ରାଜ୍ୟ କିମ୍ବା ଜିଲ୍ଲା ବଜେଟ୍ ଦେଖନ୍ତୁ\n\n1, 2, କିମ୍ବା 3 ଲେଖି ଉତ୍ତର ଦିଅନ୍ତୁ।',
  as: 'জনসেতুলৈ স্বাগতম।\n\nঅনুগ্ৰহ কৰি এটা সেৱা বাছক:\n\n1. অভিযোগ পঞ্জীয়ন কৰক\n2. অভিযোগ ট্ৰেক কৰক\n3. ৰাজ্য বা জিলা বাজেট চাওক\n\n1, 2, বা 3 লিখি উত্তৰ দিয়ক।',
  ur: 'جن سیتو میں آپ کا استقبال ہے۔\n\nبراہ کرم سروس کا انتخاب کریں:\n\n1. شکایت درج کریں\n2. شکایت ٹریک کریں\n3. ریاستی یا ضلعی بجٹ دیکھیں\n\n1، 2، یا 3 لکھ کر جواب دیں۔',
  en: 'Welcome to JanSetu.\n\nPlease choose a service:\n\n1. Register a complaint\n2. Track a complaint\n3. View state or district budget\n\nReply with 1, 2, or 3.',
}

export default function WhatsAppPane() {
  const languages = useLanguages()
  const navigate = useNavigate()
  const [language, setLanguage] = useState(() => {
    try {
      return sessionStorage.getItem('jansetu_wa_lang') || 'en'
    } catch (_) {
      return 'en'
    }
  })
  const [sessionId, setSessionId] = useState(makeSessionId)
  const [messages, setMessages] = useState(() => {
    let initialLang = 'en'
    try {
      initialLang = sessionStorage.getItem('jansetu_wa_lang') || 'en'
    } catch (_) {}
    return [{ id: nextMsgId(), from: 'bot', text: MENU_BY_LANG[initialLang] || MENU_BY_LANG.en }]
  })
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [slowProcessing, setSlowProcessing] = useState(false)
  const [attachment, setAttachment] = useState(null) // { kind, file, name }
  const fileRef = useRef(null)
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const timeoutRef = useRef(null)

  const push = useCallback((msg) => {
    setMessages((prev) => [...prev, { id: nextMsgId(), ...msg }])
  }, [])

  // Update menu when language selector changes
  const handleLanguageChange = (newLang) => {
    setLanguage(newLang)
    try {
      sessionStorage.setItem('jansetu_wa_lang', newLang)
    } catch (_) {}
    push({
      from: 'bot',
      text: MENU_BY_LANG[newLang] || MENU_BY_LANG.en,
    })
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  // Pin the transcript to the newest message
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy, slowProcessing])

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const reset = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    const newSession = makeSessionId()
    setSessionId(newSession)
    setLanguage('en')
    try {
      sessionStorage.setItem('jansetu_wa_lang', 'en')
    } catch (_) {}
    setMessages([{ id: nextMsgId(), from: 'bot', text: MENU_BY_LANG.en }])
    setDraft('')
    setAttachment(null)
    setBusy(false)
    setSlowProcessing(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const attach = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setAttachment({ kind: file.type.startsWith('audio') ? 'audio' : 'image', file, name: file.name })
    event.target.value = '' // so re-picking the same file fires change again
  }

  const send = async () => {
    if (busy) return
    const textToSend = draft
    const trimmed = textToSend.trim()
    if (!trimmed && !attachment) return

    push({
      from: 'me',
      text: textToSend || (attachment?.kind === 'audio' ? 'Voice note' : 'Photo'),
      kind: attachment?.kind,
      name: attachment?.name,
    })
    setDraft('')
    const heldAttachment = attachment
    setAttachment(null)
    setBusy(true)
    setSlowProcessing(false)

    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setSlowProcessing(true)
    }, 10000)

    try {
      const result = await submitChannelReport({
        text: trimmed || null,
        blob: heldAttachment?.kind === 'audio' ? heldAttachment.file : null,
        image: heldAttachment?.kind === 'image' ? heldAttachment.file : null,
        language,
        locationText: null,
        channel: 'whatsapp',
        citizenRef: sessionId,
      })

      if (timeoutRef.current) clearTimeout(timeoutRef.current)

      // If backend switched language dynamically via menu
      if (result.language && result.language !== language) {
        setLanguage(result.language)
        try {
          sessionStorage.setItem('jansetu_wa_lang', result.language)
        } catch (_) {}
      }

      // Check if it was a conversational turn (Greeting, Intent Menu, Language selection, Tracking reply, or Location prompt)
      if (result.classification === 'CONVERSATIONAL' || (result.request_id === 0 && !result.track_token)) {
        if (result.acknowledgement_native) {
          push({ from: 'bot', text: result.acknowledgement_native, native: true })
        }
      } else {
        // Full registered request with token -> Render WhatsApp registration success card!
        push({ from: 'bot', receipt: result })
        push({
          from: 'bot',
          text: AFTER_REGISTER_HINT_BY_LANG[language] || AFTER_REGISTER_HINT_BY_LANG.en,
          native: true,
        })
      }
    } catch (err) {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      // Restore input draft so citizen doesn't lose their typed message
      setDraft(textToSend)
      push({
        from: 'bot',
        text: 'We could not process your message at this time. Your complaint has not been registered and no token has been generated. Please try again.',
        error: true,
      })
    } finally {
      setBusy(false)
      setSlowProcessing(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  const canSend = !busy && (draft.trim().length > 0 || Boolean(attachment))

  return (
    <div className="wa">
      <div className="wa__bar">
        <span className="wa__avatar" aria-hidden="true">
          JS
        </span>
        <div className="wa__who">
          <strong>JanSetu Helpline</strong>
          <span className="wa__status">{busy ? 'typing…' : 'online'}</span>
        </div>
        <div className="wa__bar-actions">
          <button
            type="button"
            className="wa__restart-btn"
            onClick={reset}
            title="Restart demo conversation"
            aria-label="Restart demo conversation"
          >
            ↻ Restart
          </button>
          <label className="wa__lang">
            <span className="sr-only">Language</span>
            <select value={language} onChange={(e) => handleLanguageChange(e.target.value)} disabled={busy}>
              {languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native || l.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="wa__log" ref={listRef}>
        {messages.map((m) => (
          <Bubble key={m.id} msg={m} language={language} onTrack={(t) => navigate(`/track/${encodeURIComponent(t)}`)} />
        ))}
        {busy ? (
          <div
            className="wa__msg wa__msg--bot wa__msg--processing"
            role="status"
            aria-live="polite"
          >
            <span>
              {slowProcessing
                ? 'This is taking a little longer than usual. Your message is still being processed.'
                : 'Processing your message…'}
            </span>
            <span className="sim-dot-pulse" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        ) : null}
      </div>

      <form
        className="wa__compose"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <input ref={fileRef} type="file" accept="image/*,audio/*" hidden onChange={attach} />
        <button
          type="button"
          className="wa__clip"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          aria-label="Attach a photo or voice note"
        >
          <Icon name="clip" size={19} />
        </button>
        <input
          ref={inputRef}
          className="wa__input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type your reply…"
          disabled={busy}
          aria-label="Message"
        />
        <button
          type="submit"
          className="wa__send"
          disabled={!canSend}
          aria-label="Send"
        >
          <Icon name="send" size={18} />
        </button>
        {attachment ? (
          <div className="wa__chip">
            <Icon name={attachment.kind === 'audio' ? 'mic' : 'image'} size={13} />
            <span className="wa__chip-name">{attachment.name}</span>
            <button type="button" onClick={() => setAttachment(null)} aria-label="Remove attachment">
              ×
            </button>
          </div>
        ) : null}
      </form>
    </div>
  )
}

function Bubble({ msg, language, onTrack }) {
  const mine = msg.from === 'me'
  const cls = [
    'wa__msg',
    mine ? 'wa__msg--me' : 'wa__msg--bot',
    msg.pending ? 'wa__msg--pending' : '',
    msg.error ? 'wa__msg--err' : '',
    msg.native ? 'wa__msg--native' : '',
  ]
    .filter(Boolean)
    .join(' ')

  if (msg.receipt) return <Receipt result={msg.receipt} onTrack={onTrack} />

  // If bot message is a tracking status report (contains token like JS-XXXX-XXXX)
  const tokenMatch = !mine && msg.text ? msg.text.match(/\b(JS-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{4})\b/i) : null
  const isStatusCard = tokenMatch && (msg.text.includes('REQUEST STATUS') || msg.text.includes('Token:') || msg.text.includes('Request ID') || msg.text.includes('📌'))

  return (
    <div className={cls}>
      {msg.kind ? (
        <span className="wa__att">
          <Icon name={msg.kind === 'audio' ? 'mic' : 'image'} size={13} />
          {msg.name}
        </span>
      ) : null}
      <span className="wa__text">{msg.text}</span>
      {isStatusCard && tokenMatch ? (
        <button
          type="button"
          className="wa__card-btn"
          onClick={() => onTrack(tokenMatch[1])}
        >
          Open full tracking page →
        </button>
      ) : null}
      {msg.pending ? <span className="wa__dots" aria-hidden="true" /> : null}
    </div>
  )
}

const AFTER_REGISTER_HINT_BY_LANG = {
  hi: 'आपकी शिकायत सफलतापूर्वक दर्ज हो गई है।\n\nभविष्य में स्थिति जानने के लिए अनुरोध संख्या (Request ID) सुरक्षित रखें।\n\nउत्तर दें:\n1. एक और समस्या दर्ज करें\n2. इस शिकायत को ट्रैक करें\n3. मुख्य मेनू पर लौटें',
  bn: 'আপনার অভিযোগ সফলভাবে নথিভুক্ত হয়েছে।\n\nভবিষ্যতের জন্য রিকোয়েস্ট আইডি (Request ID) সংরক্ষণ করুন।\n\nউত্তর দিন:\n1. অন্য একটি অভিযোগ নথিভুক্ত করুন\n2. এই অভিযোগ ট্র্যাক করুন\n3. প্রধান মেনুতে ফিরে যান',
  ta: 'உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது.\n\nஎதிர்கால கண்காணிப்புக்கு கோரிக்கை எண்ணை (Request ID) குறித்துக்கொள்ளவும்.\n\nபதிலளிக்கவும்:\n1. மற்றொரு புகாரை பதிவு செய்ய\n2. இந்த புகாரை கண்காணிக்க\n3. முதன்மை மெனுவிற்கு திரும்ப',
  te: 'మీ ఫిర్యాదు విజయవంతంగా నమోదైంది.\n\nభవిష్యత్ అప్‌డేట్‌ల కోసం రిక్వెస్ట్ ఐడి (Request ID)ని భద్రపరుచుకోండి.\n\nరిప్లై ఇవ్వండి:\n1. మరొక సమస్యను నమోదు చేయండి\n2. ఈ ఫిర్యాదును ట్రాక్ చేయండి\n3. ప్రధాన మెనూకి తిరిగి వెళ్లండి',
  mr: 'आपली तक्रार यशस्वीरित्या नोंदवली गेली आहे।\n\nपुढील माहितीसाठी विनंती क्रमांक (Request ID) जपून ठेवा।\n\nउत्तर द्या:\n1. दुसरी तक्रार नोंदवा\n2. ही तक्रार ट्रॅक करा\n3. मुख्य मेनूवर परत जा',
  gu: 'તમારી ફરિયાદ સફળતાપૂર્વક નોંધાઈ ગઈ છે.\n\nભવિષ્ય માટે રિક્વેસ્ટ આઈડી (Request ID) સાચવી રાખો.\n\nજવાબ આપો:\n1. બીજી ફરિયાદ નોંધાવો\n2. આ ફરિયાદ ટ્રેક કરો\n3. મુખ્ય મેનુ પર પાછા જાઓ',
  kn: 'ನಿಮ್ಮ ದೂರನ್ನು ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಿಸಲಾಗಿದೆ.\n\nಭವಿಷ್ಯದ ಪರಿಶೀಲನೆಗಾಗಿ ವಿನಂತಿ ಸಂಖ್ಯೆಯನ್ನು (Request ID) ಉಳಿಸಿಕೊಳ್ಳಿ.\n\nಉತ್ತರಿಸಿ:\n1. ಮತ್ತೊಂದು ದೂರನ್ನು ದಾಖಲಿಸಿ\n2. ಈ ದೂರನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ\n3. ಮುಖ್ಯ ಮೆನುವಿಗೆ ಹಿಂತಿರುಗಿ',
  ml: 'നിങ്ങളുടെ പരാതി വിജയകരമായി രജിസ്റ്റർ ചെയ്തു.\n\nതുടർ വിവരങ്ങൾ അറിയാൻ റിക്വസ്റ്റ് ഐഡി (Request ID) സൂക്ഷിക്കുക.\n\nമറുപടി നൽകുക:\n1. മറ്റൊരു പരാതി രജിസ്റ്റർ ചെയ്യുക\n2. ഈ പരാതി ട്രാക്ക് ചെയ്യുക\n3. പ്രധാന മെനുവിലേക്ക് മടങ്ങുക',
  pa: 'ਤੁਹਾਡੀ ਸ਼ਿਕਾਇਤ ਸਫਲਤਾਪੂਰਵਕ ਦਰਜ ਕਰ ਲਈ ਗਈ ਹੈ।\n\nਭਵਿੱਖ ਲਈ ਰਿਕਵੈਸਟ ਆਈਡੀ (Request ID) ਸੰਭਾਲ ਕੇ ਰੱਖੋ।\n\nਜਵਾਬ ਦਿਓ:\n1. ਹੋਰ ਸ਼ਿਕਾਇਤ ਦਰਜ ਕਰੋ\n2. ਇਸ ਸ਼ਿਕਾਇਤ ਨੂੰ ਟ੍ਰੈਕ ਕਰੋ\n3. ਮੁੱਖ ਮੇਨੂ \'ਤੇ ਵਾਪਸ ਜਾਓ',
  or: 'ଆପଣଙ୍କ ଅଭିଯୋଗ ସଫଳତାର ସହ ଦର୍ଜ ହୋଇଛି।\n\nଭବିଷ୍ୟତ ପାଇଁ ରିକ୍ୱେଷ୍ଟ ଆଇଡି (Request ID) ସାଇତି ରଖନ୍ତୁ।\n\nଉତ୍ତର ଦିଅନ୍ତୁ:\n1. ଆଉ ଏକ ଅଭିଯୋଗ ଦର୍ଜ କରନ୍ତୁ\n2. ଏହି ଅଭିଯୋଗ ଟ୍ରାକ୍ କରନ୍ତୁ\n3. ମୁଖ୍ୟ ମେନୁକୁ ଫେରନ୍ତୁ',
  as: 'আপোনাৰ অভিযোগ সফলতাৰে পঞ্জীয়ন কৰা হৈছে।\n\nভৱিষ্যতৰ বাবে ৰিকুৱেষ্ট আইডি (Request ID) সংৰক্ষণ কৰক।\n\nউত্তৰ দিয়ক:\n1. আন এটা অভিযোগ পঞ্জীয়ন কৰক\n2. এই অভিযোগ ট্ৰেক কৰক\n3. মূল মেনুলৈ উভতি যাওক',
  ur: 'آپ کی شکایت کامیابی کے ساتھ درج ہو گئی ہے۔\n\nمستقبل کے لیے اپنی ریکویسٹ آئی ڈی (Request ID) محفوظ رکھیں۔\n\nجواب دیں:\n1. دوسری شکایت درج کریں\n2. اس شکایت کو ٹریک کریں\n3. مین مینو پر واپس جائیں',
  en: 'Your complaint has been registered successfully.\n\nKeep the Request ID to track future updates.\n\nReply:\n1. Register another complaint\n2. Track this complaint\n3. Return to the main menu',
}

/**
 * Compact WhatsApp-style registration success card.
 */
function Receipt({ result, onTrack }) {
  const token = result.track_token
  const isMulti = Boolean(result.requests && result.requests.length > 1)

  const loc =
    result.district_label ||
    (result.district ? `${result.district}, ${result.state || ''}` : '') ||
    result.location_text ||
    'Ward 4, Nabarangpur, Odisha'

  if (isMulti) {
    return (
      <div className="wa__receipt-group">
        <p className="wa__receipt-multi-notice">Your message contained separate issues:</p>
        {result.requests.map((req, idx) => (
          <div key={req.request_id || idx} className="wa__msg wa__msg--bot wa__receipt">
            <div className="wa__receipt-header">
              <span className="wa__receipt-title">✅ COMPLAINT REGISTERED</span>
              <span className="wa__receipt-badge">Issue {idx + 1}</span>
            </div>
            <div className="wa__receipt-body">
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Request ID</span>
                <span className="wa__receipt-val wa__receipt-token">{req.track_token || `#${req.request_id}`}</span>
              </div>
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Complaint number</span>
                <span className="wa__receipt-val">{req.request_id}</span>
              </div>
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Problem</span>
                <span className="wa__receipt-val">{req.summary_native || req.summary_en || 'Civic grievance'}</span>
              </div>
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Category</span>
                <span className="wa__receipt-val">{(req.category || '').replace(/_/g, ' ')}</span>
              </div>
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Location</span>
                <span className="wa__receipt-val">{loc}</span>
              </div>
              <div className="wa__receipt-row">
                <span className="wa__receipt-lbl">Status</span>
                <span className="wa__receipt-val">Submitted</span>
              </div>
            </div>
            {req.track_token ? (
              <button type="button" className="wa__receipt-btn" onClick={() => onTrack(req.track_token)}>
                Track this request →
              </button>
            ) : null}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="wa__msg wa__msg--bot wa__receipt">
      <div className="wa__receipt-header">
        <span className="wa__receipt-title">✅ COMPLAINT REGISTERED</span>
      </div>
      <div className="wa__receipt-body">
        <div className="wa__receipt-row">
          <span className="wa__receipt-lbl">Request ID</span>
          <span className="wa__receipt-val wa__receipt-token">{token || `#${result.request_id}`}</span>
        </div>
        {result.request_id ? (
          <div className="wa__receipt-row">
            <span className="wa__receipt-lbl">Complaint number</span>
            <span className="wa__receipt-val">{result.request_id}</span>
          </div>
        ) : null}
        <div className="wa__receipt-row">
          <span className="wa__receipt-lbl">Problem</span>
          <span className="wa__receipt-val">{result.summary_native || result.summary_en || 'Civic grievance'}</span>
        </div>
        <div className="wa__receipt-row">
          <span className="wa__receipt-lbl">Category</span>
          <span className="wa__receipt-val">{(result.category || 'Drinking water supply').replace(/_/g, ' ')}</span>
        </div>
        <div className="wa__receipt-row">
          <span className="wa__receipt-lbl">Location</span>
          <span className="wa__receipt-val">{loc}</span>
        </div>
        <div className="wa__receipt-row">
          <span className="wa__receipt-lbl">Status</span>
          <span className="wa__receipt-val">Submitted</span>
        </div>
      </div>
      {token ? (
        <button type="button" className="wa__receipt-btn" onClick={() => onTrack(token)}>
          Track this request →
        </button>
      ) : null}
    </div>
  )
}
