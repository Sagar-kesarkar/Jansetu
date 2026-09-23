import { useState, useEffect } from 'react'
import { num, sectorLabel, urgencyLabel } from '../lib/format.js'
import Icon, { sectorIcon } from './Icon.jsx'
import TokenReceipt from './TokenReceipt.jsx'
import { supplyLocation } from '../api.js'

/** Below this, the extraction is shown as uncertain rather than as fact. */
const LOW_CONFIDENCE = 0.5

export default function IntakeResultCard({ result, languages = [], onReset }) {
  // Handle INVALID_OR_SPAM or unidentifiable submissions
  if (
    result.classification === 'INVALID_OR_SPAM' ||
    (result.request_id === 0 && (!result.requests || result.requests.length === 0))
  ) {
    return (
      <section className="ack" aria-live="polite">
        <header className="ack__bar" style={{ background: '#92400e', borderColor: '#fde68a', color: '#fff' }}>
          <Icon name="alert-triangle" className="ack__bar-icon" />
          <strong className="ack__bar-title">Message Received — Action Pending</strong>
          <span className="ack__bar-rule" aria-hidden="true" />
          <span className="ack__bar-sub">Routed to officials' review queue.</span>
        </header>

        <div style={{ padding: '22px' }}>
          <div style={{ padding: '1.25rem', background: '#fffbeb', borderRadius: '12px', border: '1px solid #fef3c7' }}>
            <div style={{ fontWeight: 700, color: '#92400e', fontSize: '1.05rem', marginBottom: '0.5rem' }}>
              Submitted for Administrative Triage
            </div>
            <p style={{ fontSize: '0.95rem', color: '#78350f', margin: '0 0 1rem 0', lineHeight: 1.5 }}>
              {result.acknowledgement_native ||
                'We could not identify an actionable public infrastructure problem or civic grievance in that message. It has been securely logged to the administration console for official review.'}
            </p>
            {result.triage_reason ? (
              <div style={{ fontSize: '0.85rem', color: '#92400e', background: '#fef3c7', padding: '0.5rem 0.75rem', borderRadius: '6px', marginBottom: '0.75rem' }}>
                <strong>Triage Assessment:</strong> {result.triage_reason}
              </div>
            ) : null}
            <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: 0 }}>
              <em>No tracking token was issued because this submission has not yet been classified as a registered civic grievance.</em>
            </p>
          </div>
        </div>

        {onReset ? (
          <div className="ack__foot">
            <button type="button" className="ack__again" onClick={onReset}>
              Report another need
            </button>
          </div>
        ) : null}
      </section>
    )
  }

  const initialRequests = result.requests && result.requests.length > 1 ? result.requests : [result]
  const [requestsList, setRequestsList] = useState(initialRequests)
  const isMulti = requestsList.length > 1

  // Check how many requests still need location
  const needsLocCount = requestsList.filter((req) => {
    const hasPlace = Boolean(req.district || req.district_label || req.place || req.location_text || req.location_added)
    return !req.location_added && (req.needs_location || req.status === 'NEEDS_LOCATION' || req.location_status === 'MISSING' || !hasPlace)
  }).length

  const handleUpdateItem = (index, updated) => {
    setRequestsList((prev) => {
      const next = [...prev]
      next[index] = {
        ...next[index],
        ...updated,
        location_added: true,
        needs_location: false,
        status: updated.status || 'NEW',
        location_status: updated.location_status || 'RESOLVED',
      }
      return next
    })
  }

  const handleBulkUpdate = (updatedList) => {
    setRequestsList((prev) =>
      prev.map((item, idx) => {
        const updated = updatedList[idx] || updatedList[0] || {}
        return {
          ...item,
          ...updated,
          location_added: true,
          needs_location: false,
          status: updated.status || 'NEW',
          location_status: updated.location_status || 'RESOLVED',
        }
      })
    )
  }

  if (isMulti) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        <div style={{ padding: '0.85rem 1rem', background: '#eff6ff', borderRadius: '10px', border: '1px solid #bfdbfe', color: '#1e40af', fontSize: '0.925rem' }}>
          <strong>Multi-Issue Report:</strong> JanSetu identified {requestsList.length} separate needs in your message. Each is assigned an independent tracking token below.
        </div>

        {needsLocCount > 0 ? (
          <MultiIssueLocationManager
            requests={requestsList}
            onBulkUpdate={handleBulkUpdate}
          />
        ) : null}

        {requestsList.map((req, idx) => (
          <SingleCard
            key={req.track_token || req.request_id || idx}
            item={req}
            index={idx + 1}
            total={requestsList.length}
            languages={languages}
            onReset={onReset}
            onUpdated={(updated) => handleUpdateItem(idx, updated)}
          />
        ))}
      </div>
    )
  }

  return (
    <SingleCard
      item={requestsList[0]}
      index={1}
      total={1}
      languages={languages}
      onReset={onReset}
      onUpdated={(updated) => handleUpdateItem(0, updated)}
    />
  )
}

function MultiIssueLocationManager({ requests, onBulkUpdate }) {
  const [mode, setMode] = useState('same') // 'same' | 'different'
  const [sharedPlace, setSharedPlace] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [savedSuccess, setSavedSuccess] = useState(false)

  const handleApplySame = async (e) => {
    e.preventDefault()
    const trimmed = sharedPlace.trim()
    if (!trimmed) return
    setSaving(true)
    setError(null)
    try {
      const results = await Promise.all(
        requests.map((req) => supplyLocation({ token: req.track_token, locationText: trimmed }))
      )
      setSavedSuccess(true)
      onBulkUpdate(results)
    } catch (err) {
      setError(err.message || 'Could not update location for all issues')
    } finally {
      setSaving(false)
    }
  }

  if (savedSuccess) {
    return (
      <div style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem', background: '#ecfdf5', borderRadius: '10px', border: '1px solid #a7f3d0', color: '#065f46', fontSize: '0.95rem' }}>
        <strong>✓ Shared Location Applied!</strong> All {requests.length} issues registered for <em>"{sharedPlace.trim()}"</em> and tracking tokens generated below.
      </div>
    )
  }

  return (
    <div style={{ marginBottom: '1.75rem', padding: '1.25rem', background: '#fffbeb', borderRadius: '12px', border: '1px solid #fde68a', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#92400e', fontWeight: 700, fontSize: '1.05rem' }}>
        <Icon name="pin" /> Location Confirmation Needed
      </div>
      <p style={{ fontSize: '0.9rem', color: '#78350f', margin: '0 0 1rem 0', lineHeight: 1.5 }}>
        Your report contains multiple separate issues. Please choose whether all issues are taking place at the same location or different locations:
      </p>

      {/* Choice Buttons / Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => setMode('same')}
          style={{
            padding: '0.55rem 1rem',
            borderRadius: '8px',
            border: mode === 'same' ? '2px solid #2563eb' : '1px solid #d1d5db',
            background: mode === 'same' ? '#eff6ff' : '#ffffff',
            color: mode === 'same' ? '#1d4ed8' : '#374151',
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span>🔘</span> Apply Same Location to All ({requests.length}) Issues
        </button>

        <button
          type="button"
          onClick={() => setMode('different')}
          style={{
            padding: '0.55rem 1rem',
            borderRadius: '8px',
            border: mode === 'different' ? '2px solid #2563eb' : '1px solid #d1d5db',
            background: mode === 'different' ? '#eff6ff' : '#ffffff',
            color: mode === 'different' ? '#1d4ed8' : '#374151',
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span>🔀</span> Enter Different Location for Each Issue
        </button>
      </div>

      {mode === 'same' ? (
        <form onSubmit={handleApplySame} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={sharedPlace}
            onChange={(e) => setSharedPlace(e.target.value)}
            placeholder="Enter city, town, village or district for all issues (e.g. Madurai, Tamil Nadu)"
            disabled={saving}
            style={{
              flex: '1 1 300px',
              padding: '0.65rem 0.85rem',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              fontSize: '0.9rem',
              background: '#ffffff',
            }}
          />
          <button
            type="submit"
            disabled={saving || !sharedPlace.trim()}
            style={{
              padding: '0.65rem 1.25rem',
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '0.9rem',
              cursor: 'pointer',
            }}
          >
            {saving ? 'Applying & Registering…' : `Apply to All (${requests.length}) & Generate Tokens`}
          </button>
        </form>
      ) : (
        <div style={{ padding: '0.75rem 1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', color: '#475569', fontSize: '0.875rem' }}>
          👉 Please enter the specific location for each issue in the separate cards below.
        </div>
      )}

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.5rem' }}>{error}</p> : null}
    </div>
  )
}

function SingleCard({ item, index, total, languages, onReset, onUpdated }) {
  const [itemData, setItemData] = useState(item)

  // Sync with prop updates from bulk action
  useEffect(() => {
    setItemData(item)
  }, [item])

  const {
    request_id,
    track_token,
    title,
    summary_en,
    transcript,
    category,
    urgency,
    district,
    district_label,
    state,
    language,
    confidence,
    status,
    location_status,
    needs_location,
    raw_text,
    acknowledgement_native,
    summary_native,
  } = itemData

  const isMulti = total > 1
  const lowConfidence = (confidence || 0) < LOW_CONFIDENCE
  const languageName = languages.find((l) => l.code === language)?.name || language?.toUpperCase()

  const formatLocation = (loc, st) => {
    if (!loc) return null
    if (!st || String(loc).toLowerCase().includes(String(st).toLowerCase())) return loc
    return `${loc}, ${st}`
  }

  const districtText =
    formatLocation(district_label, state) ||
    formatLocation(district, state) ||
    formatLocation(itemData.place || itemData.location_text, state) ||
    'Location required'

  const hasPlace = Boolean(district || district_label || itemData.place || itemData.location_text || itemData.location_added)
  const needsLoc = !itemData.location_added && (needs_location || status === 'NEEDS_LOCATION' || location_status === 'MISSING' || !hasPlace)

  const handleLocationUpdated = (updated) => {
    setItemData((prev) => ({
      ...prev,
      district: updated.district || prev.district,
      district_label: updated.district_label || updated.place || prev.district_label,
      place: updated.place || prev.place,
      location_text: updated.place || updated.location_text || prev.location_text,
      state: updated.state || prev.state,
      status: updated.status || prev.status || 'NEW',
      location_status: updated.location_status || 'RESOLVED',
      needs_location: false,
      location_added: true,
    }))
    if (onUpdated) onUpdated(updated)
  }

  // The citizen's native statement (displayed below header)
  const nativeText = raw_text || acknowledgement_native || summary_native || (language !== 'en' ? title : null)

  return (
    <section className="ack" aria-live="polite">
      <header
        className="ack__bar"
        style={
          needsLoc
            ? { background: '#92400e', borderColor: '#fde68a', color: '#fff' }
            : undefined
        }
      >
        <Icon name={needsLoc ? 'alert-triangle' : 'check-circle'} className="ack__bar-icon" />
        <strong className="ack__bar-title">
          {needsLoc
            ? 'Action Required: Location Missing'
            : isMulti
              ? `Request ${index} of ${total} registered`
              : 'Request registered'}
        </strong>
        <span className="ack__bar-rule" aria-hidden="true" />
        <span className="ack__bar-sub">
          {needsLoc
            ? 'Complaint not yet registered — location needed to issue tracking token'
            : 'Your request has been securely recorded.'}
        </span>
        {request_id ? <span className="ack__bar-ref">#{request_id}</span> : null}
      </header>

      {nativeText ? (
        <p className="ack__native" lang={language}>
          {nativeText}
        </p>
      ) : null}

      {/* Do NOT show tracking token receipt if location is missing */}
      {needsLoc ? (
        <div style={{ padding: '0 22px' }}>
          <LocationSupplyForm token={track_token} onUpdated={handleLocationUpdated} />
        </div>
      ) : (
        <TokenReceipt token={track_token} />
      )}

      <div className="ack__grid">
        <Field icon={sectorIcon(category)} k="Sector" v={sectorLabel(category)} />
        <Field icon="clock" k="Urgency" v={`${urgency || 1} · ${urgencyLabel(urgency || 1)}`} />
        <Field
          icon="pin"
          k="District"
          v={
            needsLoc ? (
              <span style={{ color: '#b45309', fontWeight: 600 }}>Location required</span>
            ) : (
              districtText
            )
          }
        />
        <Field icon="globe" k="Language" v={languageName} />
      </div>

      {summary_en ? (
        <div className="ack__panel">
          <span className="ack__panel-icon">
            <Icon name="doc" />
          </span>
          <div>
            <div className="ack__panel-key">Planner summary</div>
            <p className="ack__panel-body">{summary_en}</p>
          </div>
        </div>
      ) : null}

      {transcript && transcript !== summary_en && transcript !== nativeText ? (
        <div className="ack__panel">
          <span className="ack__panel-icon">
            <Icon name="doc" />
          </span>
          <div>
            <div className="ack__panel-key">Transcript</div>
            <p className="ack__panel-body" lang={language}>
              {transcript}
            </p>
          </div>
        </div>
      ) : null}

      {lowConfidence ? (
        <p className="ack__note">
          <strong>Low confidence ({num((confidence || 0) * 100)}%).</strong>{' '}
          {(confidence || 0) <= 0.15
            ? 'This was classified by keyword matching, not by Gemini — no API key is configured, so the sector is a best guess from vocabulary alone.'
            : 'The sector above is uncertain. It still counts toward the district total; a reviewer can recategorise it.'}
        </p>
      ) : null}

      {onReset ? (
        <div className="ack__foot">
          <button type="button" className="ack__again" onClick={onReset}>
            Report another need
          </button>
        </div>
      ) : null}
    </section>
  )
}

function LocationSupplyForm({ token, onUpdated }) {
  const [place, setPlace] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)

  if (saved) {
    const locLabel = saved.district_label || saved.district || saved.place || place.trim()
    return (
      <div style={{ padding: '0.85rem 1rem', background: '#ecfdf5', borderRadius: '8px', border: '1px solid #a7f3d0', color: '#065f46', fontSize: '0.95rem', margin: '1rem 0' }}>
        <strong>✓ Location Added & Request Registered!</strong> {locLabel ? `Assigned to ${locLabel}.` : 'Assigned to district.'}
      </div>
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmed = place.trim()
    if (!trimmed || !token) return
    setSaving(true)
    setError(null)
    try {
      const res = await supplyLocation({ token, locationText: trimmed })
      setSaved(res)
      if (onUpdated) onUpdated(res)
    } catch (err) {
      setError(err.message || 'Could not update location')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ margin: '0.5rem 0 1.25rem 0', padding: '1.25rem', background: '#fffbeb', borderRadius: '10px', border: '1px solid #fde68a' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#92400e', fontWeight: 700, fontSize: '1rem' }}>
        <Icon name="pin" /> Location Required — Complaint Not Yet Registered
      </div>
      <p style={{ fontSize: '0.9rem', color: '#78350f', margin: '0 0 0.9rem 0', lineHeight: 1.5 }}>
        <strong>Action Needed:</strong> Your grievance cannot be registered, assigned to officials, or tracked without specifying the location (city, town, village, or district) where this issue is occurring. 
        <strong> A tracking token will only be generated after you provide your location.</strong>
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          value={place}
          onChange={(e) => setPlace(e.target.value)}
          placeholder="Enter city, town, village or district (e.g. Madurai, Tamil Nadu)"
          disabled={saving}
          style={{ flex: '1 1 260px', padding: '0.6rem 0.85rem', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '0.9rem' }}
        />
        <button
          type="submit"
          disabled={saving || !place.trim()}
          style={{ padding: '0.6rem 1.25rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}
        >
          {saving ? 'Registering...' : 'Add Location & Generate Token'}
        </button>
      </form>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.5rem' }}>{error}</p> : null}
    </div>
  )
}

function Field({ icon, k, v }) {
  return (
    <div className="ack__cell">
      <span className="ack__cell-icon">
        <Icon name={icon} />
      </span>
      <div className="ack__cell-text">
        <div className="ack__cell-key">{k}</div>
        <div className="ack__cell-val">{v}</div>
      </div>
    </div>
  )
}
