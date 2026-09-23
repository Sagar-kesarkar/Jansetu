/**
 * "Track Status" — the return half of the citizen loop.
 *
 * The loop is the point. A platform that collects grievances and never reports
 * back trains people to stop filing, which is exactly the silence this project
 * claims to correct: the districts that report least are the ones that need most,
 * and nothing produces that silence faster than a form that swallows what you
 * said. So this page exists to make the first half credible.
 *
 * Three decisions worth knowing about.
 *
 * **The token goes in the URL.** `/track/JS-7K4M-92QX` is bookmarkable and
 * shareable with the one person a citizen might ask for help — a relative, an ASHA
 * worker, a panchayat clerk. Keeping it in component state would have been simpler
 * and would have made the result unreachable a second time.
 *
 * **Errors are shown exactly as the API worded them.** The backend returns one
 * identical message for "not a token" and "not one of ours", because telling those
 * apart hands an enumerator the only signal they need. Rewording it here — adding
 * a helpful "that isn't a valid format" — would leak the distinction the backend
 * spent effort refusing to make.
 *
 * **A network failure and a bad token look different.** Not for security: for
 * usability. Someone told "invalid token" when the API is simply down will retype
 * a token that was correct.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { getTracking, supplyLocation } from '../api.js'
import RequestProgressTimeline from '../components/RequestProgressTimeline.jsx'
import AuditHistoryModal from '../components/AuditHistoryModal.jsx'
import { DASH, sectorLabel, urgencyLabel, formatFullDateTime } from '../lib/format.js'

const PLACEHOLDER = 'Enter your Query Token (e.g., JS-7K4M-92QX)'

export default function TrackStatus() {
  const { token: routeToken } = useParams()
  const navigate = useNavigate()

  const [input, setInput] = useState(routeToken ?? '')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const inputRef = useRef(null)
  // Guards against a slow first lookup landing after a faster second one and
  // overwriting it — the classic out-of-order response bug on a search box.
  const latest = useRef(0)

  const lookup = useCallback(async (raw, isPoll = false) => {
    const token = raw.trim()
    if (!token) {
      if (!isPoll) {
        setError({ kind: 'empty', message: 'Enter the token you were given when you filed the request.' })
        setResult(null)
      }
      return
    }

    const seq = ++latest.current
    if (!isPoll) setBusy(true)
    setError(null)

    try {
      const data = await getTracking(token)
      if (seq !== latest.current) return
      setResult(data)
    } catch (err) {
      if (seq !== latest.current) return
      if (!isPoll) {
        setResult(null)
        // status 0 is the api.js signal for "never reached the server".
        setError(
          err.status === 0
            ? { kind: 'network', message: err.message }
            : err.status === 404
              ? { kind: 'unknown', message: err.message }
              : { kind: 'server', message: err.message },
        )
      }
    } finally {
      if (seq === latest.current && !isPoll) setBusy(false)
    }
  }, [])

  // Deep links and back-button navigation both arrive as a route change, so the
  // fetch hangs off the URL rather than off the submit handler.
  useEffect(() => {
    if (routeToken) {
      setInput(routeToken)
      lookup(routeToken)
    } else {
      setResult(null)
      setError(null)
      inputRef.current?.focus()
    }
  }, [routeToken, lookup])

  // Automatic background polling every 15s when active and not terminal
  useEffect(() => {
    if (!routeToken || !result || result.is_closed) return

    const poll = () => {
      if (document.visibilityState === 'visible') {
        lookup(routeToken, true)
      }
    }

    const intervalId = setInterval(poll, 15000)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        lookup(routeToken, true)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [routeToken, result, lookup])

  function onSubmit(event) {
    event.preventDefault()
    const token = input.trim()
    if (!token) {
      lookup('')
      return
    }
    // Pushing the route is what triggers the lookup, except when the token is
    // already in the URL — React Router does not re-run the effect for an
    // identical path, so a deliberate retry has to call through directly.
    if (token.toUpperCase() === (routeToken ?? '').toUpperCase()) lookup(token)
    else navigate(`/track/${encodeURIComponent(token)}`)
  }

  return (
    <div className="track">
      <header className="track__head">
        <h1 className="track__title">Track your request</h1>
        <p className="track__lede">
          No account, no login. The token you were given when you filed is the only thing you need.
        </p>
      </header>

      <form className="track__form" onSubmit={onSubmit}>
        <label className="track__label" htmlFor="track-token">
          Query Token
        </label>
        <div className="track__field">
          <input
            id="track-token"
            ref={inputRef}
            className="track__input"
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck="false"
            placeholder={PLACEHOLDER}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-describedby="track-help"
            aria-invalid={error ? 'true' : undefined}
          />
          <button type="submit" className="track__submit" disabled={busy}>
            {busy ? 'Checking…' : 'Check Status'}
          </button>
        </div>
        <p className="track__help" id="track-help">
          Dashes, spaces and lower case are all fine — <code>js7k4m92qx</code> works as well as{' '}
          <code>JS-7K4M-92QX</code>.
        </p>
      </form>

      {error ? (
        <div className={`track__error track__error--${error.kind}`} role="alert">
          <strong>
            {error.kind === 'network'
              ? 'Network error'
              : error.kind === 'unknown'
                ? 'Invalid Token ID'
                : error.kind === 'empty'
                  ? 'No token entered'
                  : 'Something went wrong'}
          </strong>
          {/* Verbatim from the API. See the module docstring. */}
          <span>{error.message}</span>
          {error.kind === 'network' ? (
            <button type="button" className="track__retry" onClick={() => lookup(input)}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {busy && !result ? <div className="track__busy">Looking up your request…</div> : null}

      {result ? (
        <TrackCard
          data={result}
          onRefresh={() => lookup(result.track_token || input)}
          refreshing={busy}
        />
      ) : null}
    </div>
  )
}

function TrackCard({ data, onRefresh, refreshing = false }) {
  const [showHistory, setShowHistory] = useState(false)

  const {
    track_token,
    filed_at,
    created_at,
    updated_at,
    category,
    category_label,
    urgency,
    summary_en,
    original_text,
    language,
    channel,
    district_label,
    state,
    place,
    status_label,
    status,
    step_index,
    steps,
    is_closed,
    latest_response,
    response_count,
  } = data

  const filedTimestamp = filed_at || created_at
  const updatedTimestamp = updated_at || filedTimestamp

  return (
    <section className="tcard" aria-live="polite">
      {showHistory ? <AuditHistoryModal data={data} language={language} onClose={() => setShowHistory(false)} /> : null}

      <header className="tcard__head">
        <div>
          <div className="tcard__key">Query Token</div>
          <code className="tcard__token" translate="no">
            {track_token}
          </code>
        </div>
        <div className="tcard__filed" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.35rem' }}>
          <div>
            <span className="tcard__key" style={{ marginRight: '0.4rem' }}>Filed</span>
            <span className="tcard__filed-val">{formatFullDateTime(filedTimestamp)}</span>
          </div>
          {updatedTimestamp && updatedTimestamp !== filedTimestamp ? (
            <div>
              <span className="tcard__key" style={{ marginRight: '0.4rem' }}>Last updated</span>
              <span className="tcard__filed-val">{formatFullDateTime(updatedTimestamp)}</span>
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="tcard__refresh"
              onClick={() => setShowHistory(true)}
              style={{ background: '#f8fafc', color: '#1e293b', borderColor: '#cbd5e1', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
            >
              📜 Audit History ({data.history?.length || 1})
            </button>
            {onRefresh ? (
              <button
                type="button"
                className="tcard__refresh"
                onClick={onRefresh}
                disabled={refreshing}
              >
                {refreshing ? 'Checking…' : '↻ Refresh status'}
              </button>
            ) : null}
          </div>
        </div>
      </header>

      {data.needs_location ? (
        <TrackLocationForm token={track_token} onUpdated={onRefresh} />
      ) : null}

      <RequestProgressTimeline
        steps={steps}
        current={step_index}
        status={status}
        statusLabel={status_label}
        closed={is_closed}
        needsLocation={data.needs_location}
        language={language}
        filedAt={filedTimestamp}
        updatedAt={updatedTimestamp}
      />

      <div className="tcard__grid">
        <Field k="Category" v={category_label || sectorLabel(category)} />
        <Field k="Urgency" v={`${urgency} · ${urgencyLabel(urgency)}`} />
        <Field k="Locality" v={place} />
        <Field k="District" v={district_label ? `${district_label}${state ? `, ${state}` : ''}` : null} />
      </div>

      <div className="tcard__block">
        <div className="tcard__key">What was reported</div>
        <p className="tcard__body">{summary_en}</p>
        {/* Their own sentence back. Someone who filed in Odia and is handed only
            an English summary cannot tell whether they were understood, and
            confirming that is most of why they returned to this page. */}
        {original_text && original_text !== summary_en ? (
          <p className="tcard__native" lang={language}>
            “{original_text}”
          </p>
        ) : null}
        <div className="tcard__meta">
          Filed by {channelLabel(channel)} · {language?.toUpperCase()}
        </div>
      </div>

      <div className="tcard__block tcard__block--reply">
        <div className="tcard__key">
          Official remarks
          {response_count > 1 ? <span className="tcard__count"> · latest of {response_count}</span> : null}
        </div>
        {latest_response ? (
          <>
            <p className="tcard__body">{latest_response.body_en}</p>
            {latest_response.body_native ? (
              <p className="tcard__native">{latest_response.body_native}</p>
            ) : null}
            <div className="tcard__meta">
              {latest_response.responder_desk} · {longDate(latest_response.created_at)}
            </div>
          </>
        ) : (
          <p className="tcard__pending">Pending department review</p>
        )}
      </div>
    </section>
  )
}

function TrackLocationForm({ token, onUpdated }) {
  const [place, setPlace] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmed = place.trim()
    if (!trimmed || !token) return
    setSaving(true)
    setError(null)
    try {
      const res = await supplyLocation({ token, locationText: trimmed })
      setSaved(res || true)
      if (onUpdated) onUpdated(res)
    } catch (err) {
      setError(err.message || 'Failed to update location')
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    const locLabel = typeof saved === 'object' ? (saved.district_label || saved.district || saved.place || place.trim()) : place.trim()
    return (
      <div style={{ margin: '1rem 0', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', border: '1px solid #a7f3d0', color: '#065f46', fontSize: '0.9rem' }}>
        ✓ Location added! {locLabel ? `Assigned to ${locLabel}.` : 'Assigned to district.'}
      </div>
    )
  }

  return (
    <div style={{ margin: '1.25rem 0', padding: '1rem', background: '#fffbeb', borderRadius: '8px', border: '1px solid #fef3c7' }}>
      <div style={{ fontWeight: 600, color: '#92400e', marginBottom: '0.25rem' }}>
        ⚠️ Missing Location Information
      </div>
      <p style={{ fontSize: '0.85rem', color: '#78350f', margin: '0 0 0.75rem 0' }}>
        This request is missing a village, town, or district. Please enter your location so the administration can assign and prioritize it.
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          value={place}
          onChange={(e) => setPlace(e.target.value)}
          placeholder="e.g. Nabarangpur, Odisha"
          disabled={saving}
          style={{ flex: '1 1 200px', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '0.9rem' }}
        />
        <button
          type="submit"
          disabled={saving || !place.trim()}
          style={{ padding: '0.5rem 1rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}
        >
          {saving ? 'Updating…' : 'Submit Location'}
        </button>
      </form>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.5rem' }}>{error}</p> : null}
    </div>
  )
}

function Field({ k, v }) {
  return (
    <div className="tcard__cell">
      <div className="tcard__key">{k}</div>
      <div className="tcard__val">{v || DASH}</div>
    </div>
  )
}

/** The API's lowercase channel enum, as a person would say it. */
function channelLabel(channel) {
  return (
    { text: 'web form', voice: 'voice note', whatsapp: 'WhatsApp', sms: 'SMS', ivr: 'phone call' }[
      channel
    ] ?? channel
  )
}

function longDate(iso) {
  if (!iso) return DASH
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return DASH
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
