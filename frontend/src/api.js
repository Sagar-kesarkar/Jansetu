/**
 * Every call to the backend goes through here.
 *
 * One module rather than fetches scattered through components, because the demo
 * runs against three different hosts (localhost, a Hugging Face Space, whatever
 * a judge points it at) and the base URL must be changeable in exactly one place.
 */

// Trailing slash stripped so `${BASE}/hotspots` can never become a double slash,
// which some hosts 301 and browsers then re-request without the CORS preflight.
export const API_BASE = (
  import.meta.env.VITE_API_BASE || 'http://localhost:8080'
).replace(/\/+$/, '')

/** Gemini calls are slow; plain reads should not wait as long before failing. */
const READ_TIMEOUT_MS = 20_000
const GEMINI_TIMEOUT_MS = 90_000

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * A judge on a conference network will hit timeouts. Surfacing *which* failure
 * happened — unreachable vs. 500 vs. slow — is the difference between "the demo
 * is broken" and "the wifi is bad", so the messages stay specific.
 */
async function request(path, { timeout = READ_TIMEOUT_MS, ...init } = {}) {
  let resp
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeout),
    })
  } catch (err) {
    if (err.name === 'TimeoutError') {
      throw new ApiError(`The API did not respond within ${timeout / 1000}s.`, 0)
    }
    throw new ApiError(`Cannot reach the API at ${API_BASE}. Is it running?`, 0)
  }

  if (!resp.ok) {
    // FastAPI puts validation errors in `detail`, which is far more useful than
    // the bare status code — pull it out when it is there.
    let detail = ''
    try {
      const body = await resp.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body; the status alone will have to do */
    }
    throw new ApiError(detail || `Request failed (HTTP ${resp.status}).`, resp.status)
  }

  return resp.json()
}

/** Drops empty filters so `?state=` never reaches the API as a literal filter. */
function query(params) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') qs.set(key, value)
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

/**
 * Languages and sectors come from here rather than a constant in the frontend.
 * The backend owns the taxonomy — hardcoding 13 languages in the UI means adding
 * the 14th in two places and shipping with them out of sync.
 */
export const getCapabilities = () => request('/capabilities')

export const getHotspots = ({ state, category, limit = 60 } = {}) =>
  request(`/hotspots${query({ state, category, limit })}`)

export const getRecommendations = ({ state, category, limit = 10 } = {}) =>
  request(`/recommendations${query({ state, category, limit, with_brief: false })}`)

/**
 * One brief, one Gemini call. Passing the caller's filters through is not
 * optional: scores are normalised across the queried set, so omitting them
 * returns a row whose score disagrees with the card it was requested from.
 */
export const getBrief = ({ districtCode, sector, state, category }) =>
  request(
    `/recommendations/brief${query({ district_code: districtCode, sector, state, category })}`,
    { timeout: GEMINI_TIMEOUT_MS },
  )

export const submitText = ({ text, language, locationText }) =>
  request('/intake/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // `channel` is the API's enum, which has no "web" member — a web form is a
    // text submission as far as the pipeline is concerned.
    body: JSON.stringify({
      text,
      language,
      location_text: locationText || null,
      channel: 'text',
    }),
    timeout: GEMINI_TIMEOUT_MS,
  })

export const submitVoice = ({ blob, language, locationText }) => {
  const form = new FormData()
  form.append('audio', blob, 'note.webm')
  form.append('language', language)
  if (locationText) form.append('location_text', locationText)
  // No Content-Type header: the browser must set the multipart boundary itself.
  return request('/intake/voice', { method: 'POST', body: form, timeout: GEMINI_TIMEOUT_MS })
}

export const getRequests = ({ limit = 20 } = {}) => request(`/requests${query({ limit })}`)

/**
 * Look up one case by its tracking token. No auth, by design — see
 * `backend/app/routers/track.py`: requiring an account would exclude the users
 * this platform exists for.
 *
 * `encodeURIComponent` because a person will paste whatever is on their
 * clipboard, spaces and all, and the backend normalises rather than rejects.
 *
 * A 404 here is an expected outcome, not a fault: the backend returns the same
 * message for "not a token" and "not one of ours" on purpose, so the caller
 * shows `err.message` verbatim rather than inventing a distinction the API
 * deliberately refuses to make.
 */
export const getTracking = (token) => request(`/track/${encodeURIComponent(token.trim())}`)

/**
 * Citizen providing location for a request waiting for one.
 * Calls PATCH /track/{token}/location.
 */
export const supplyLocation = ({ token, locationText }) =>
  request(`/track/${encodeURIComponent(token.trim())}/location`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ location_text: locationText }),
  })

export const getBudgetAllocations = ({ state, category } = {}) =>
  request(`/budget/allocations${query({ state, category })}`)

/**
 * The demo simulator's channels: a report arriving as if from WhatsApp or SMS.
 *
 * `/intake/report` rather than `/intake/whatsapp` or `/intake/sms/exotel`, and
 * the reason is that those two are *provider webhooks*. They answer their
 * provider, not their caller: the WhatsApp handler returns `{status:"received"}`
 * and finishes the Gemini pipeline in a background task, because Meta expects a
 * fast 2xx and retries on timeout. Neither can hand a tracking token back inside
 * the request, and the simulator's entire point is showing the citizen receive
 * one. They also try to *send* the reply through Meta and Exotel, which needs
 * credentials this project deliberately does not have.
 *
 * So the simulator posts to the channel-agnostic intake and sets `channel`
 * itself. The row lands attributed to WhatsApp or SMS exactly as the webhook
 * would have written it, which is what the officials' console reads — the
 * difference is only in who transports the bytes.
 */
export const submitChannelReport = ({ text, blob, image, language, locationText, channel, citizenRef }) => {
  const form = new FormData()
  if (text) form.append('text', text)
  if (blob) form.append('audio', blob, 'note.webm')
  if (image) form.append('image', image, image.name || 'photo.jpg')
  form.append('language', language)
  form.append('channel', channel)
  if (locationText) form.append('location_text', locationText)
  // The simulated handset's number. `ingest` HMACs it into `citizen_ref` — the
  // raw value is never stored, which is what lets the simulator use a plausible
  // number instead of a placeholder.
  if (citizenRef) form.append('citizen_ref', citizenRef)
  return request('/intake/report', { method: 'POST', body: form, timeout: GEMINI_TIMEOUT_MS })
}

/**
 * One step of a simulated IVR call, driven by the backend's real state machine.
 *
 * Unlike WhatsApp and SMS, this *is* the production path: `/ivr/simulate` walks
 * the same `transition()` the Exotel webhooks walk, so the greeting, the
 * language menu, the record prompt and the digit-by-digit token readback are all
 * the ones a real caller would hear, in the language they chose. The widget only
 * supplies the handset — DTMF presses, the microphone, and a voice to speak the
 * prompts the state machine returns.
 */
export const ivrStep = ({
  action,
  callerPhone,
  digits,
  audioBase64,
  audioMime,
  languageDigit,
  textSimulation,
  mode = 'live',
}) =>
  request('/ivr/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      caller_phone: callerPhone,
      action,
      digits: digits ?? null,
      audio_base64: audioBase64 ?? null,
      audio_mime: audioMime || 'audio/webm',
      language_digit: languageDigit || '1',
      text_simulation: textSimulation ?? null,
      mode,
    }),
    timeout: GEMINI_TIMEOUT_MS,
  })

export const createIvrSession = ({ callerPhone, initialLanguage, mode = 'live' }) =>
  request('/ivr/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      caller_phone: callerPhone,
      initial_language: initialLanguage ?? null,
      mode,
    }),
  })

export const getIvrSession = (sessionId) => request(`/ivr/sessions/${sessionId}`)

export const sendIvrDtmf = (sessionId, digits) =>
  request(`/ivr/sessions/${sessionId}/dtmf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ digits }),
  })

export const sendIvrInput = (sessionId, text) =>
  request(`/ivr/sessions/${sessionId}/input`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    timeout: GEMINI_TIMEOUT_MS,
  })

export const sendIvrAudio = (sessionId, audioInput, audioMime = 'audio/webm') => {
  if (audioInput instanceof Blob || (typeof File !== 'undefined' && audioInput instanceof File)) {
    const form = new FormData()
    form.append('file', audioInput, 'recording.webm')
    return request(`/ivr/sessions/${sessionId}/audio`, {
      method: 'POST',
      body: form,
      timeout: GEMINI_TIMEOUT_MS,
    })
  }
  return request(`/ivr/sessions/${sessionId}/audio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_base64: audioInput, audio_mime: audioMime }),
    timeout: GEMINI_TIMEOUT_MS,
  })
}

export const repeatIvrPrompt = (sessionId) =>
  request(`/ivr/sessions/${sessionId}/repeat`, { method: 'POST' })

export const endIvrSession = (sessionId) =>
  request(`/ivr/sessions/${sessionId}/end`, { method: 'POST' })

/**
 * The citizen web form's submission — text or a voice note, either optionally
 * carrying a photograph.
 *
 * Delegates to the same multipart route the simulator uses, because a web report
 * with a photo needs exactly what a WhatsApp report with a photo needs. `/intake/text`
 * takes JSON and so cannot carry a file at all; `/intake/voice` requires audio. This
 * is the route that accepts any combination, which is why it exists.
 */
export const submitReport = ({ text, blob, image, language, locationText }) =>
  submitChannelReport({
    text,
    blob,
    image,
    language,
    locationText,
    // The API's enum has no "web" member. A typed report is `text`; a recorded one
    // is `voice`, which is what the console's "Arrived by" column reads.
    channel: blob ? 'voice' : 'text',
  })

// ---- Public Funds & State/District Budget ----

export const getFundsOverview = ({ scope = 'state', state = 'Maharashtra', district, fiscalYear = '2026-27', category } = {}) =>
  request(
    `/api/v1/funds/overview${query({
      scope,
      state,
      district,
      fiscal_year: fiscalYear,
      category,
    })}`,
  )

export const getFundsDistricts = ({ state = 'Maharashtra', fiscalYear = '2026-27', category } = {}) =>
  request(
    `/api/v1/funds/districts${query({
      state,
      fiscal_year: fiscalYear,
      category,
    })}`,
  )

export const getFundsSectors = ({ scope = 'state', state = 'Maharashtra', district, fiscalYear = '2026-27' } = {}) =>
  request(
    `/api/v1/funds/sectors${query({
      scope,
      state,
      district,
      fiscal_year: fiscalYear,
    })}`,
  )

export const getFundsSources = () => request('/api/v1/funds/sources')

export const getFundsCoverage = () => request('/api/v1/funds/coverage')

export const getStates = () => request('/states')

export const getDistricts = ({ state } = {}) => request(`/districts${query({ state })}`)



