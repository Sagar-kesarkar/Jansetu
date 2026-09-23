/**
 * RequestProgressTimeline — The shared 6-stage citizen progress tracker.
 *
 * Sequence:
 * 1. Submitted → 2. Acknowledged → 3. Under Review → 4. Assigned to Dept → 5. In Progress → 6. Resolved
 *
 * All step labels below the tick mark icons are strictly and always in English.
 */
import React from 'react'
import { formatShortDate } from '../lib/format.js'

export const CANONICAL_STAGES = [
  { key: 'SUBMITTED', id: 0, label: 'Submitted', defaultLabel: 'Submitted' },
  { key: 'ACKNOWLEDGED', id: 1, label: 'Acknowledged', defaultLabel: 'Acknowledged' },
  { key: 'UNDER_REVIEW', id: 2, label: 'Under Review', defaultLabel: 'Under Review' },
  { key: 'ASSIGNED', id: 3, label: 'Assigned to Dept', defaultLabel: 'Assigned to Dept' },
  { key: 'IN_PROGRESS', id: 4, label: 'In Progress', defaultLabel: 'In Progress' },
  { key: 'RESOLVED', id: 5, label: 'Resolved', defaultLabel: 'Resolved' },
]

const STATUS_TEXT_BY_LANG = {
  CURRENT_STATUS: {
    en: 'Current status',
    hi: 'वर्तमान स्थिति',
    mr: 'सद्यस्थिती',
    ta: 'தற்போதைய நிலை',
    te: 'ప్రస్తుత స్థితి',
    bn: 'বর্তমান অবস্থা',
    gu: 'વર્તમાન સ્થિતિ',
    kn: 'ಪ್ರಸ್ತುತ ಸ್ಥಿತಿ',
    ml: 'നിലവിലെ അവസ്ഥ',
    pa: 'ਮੌਜੂਦਾ ਸਥਿਤੀ',
    or: 'ବର୍ତ୍ତମାନର ସ୍ଥିତି',
    as: 'বৰ্তমান স্থিতি',
    ur: 'موجودہ صورتحال',
  },
  NEEDS_LOCATION_MSG: {
    en: 'Location information is required before this request can be assigned.',
    hi: 'इस अनुरोध को विभाग को सौंपने से पहले स्थान की जानकारी आवश्यक है।',
    mr: 'हा विनंती विभागाकडे सोपवण्यापूर्वी ठिकाणाची माहिती आवश्यक आहे.',
    ta: 'இந்தக் கோரிக்கையை ஒதுக்குவதற்கு முன் இருப்பிடத் தகவல் தேவை.',
    te: 'ఈ అభ్యర్థనను కేటాయించే ముందు స్థాన సమాచారం అవసరం.',
  },
}

export default function RequestProgressTimeline({
  steps = [],
  current = 0,
  currentStatus,
  statusLabel,
  closed = false,
  needsLocation = false,
  language = 'en',
  compact = false,
  filedAt,
  updatedAt,
}) {
  const langKey = language?.toLowerCase() || 'en'
  const offLadder = current == null
  const ended = closed && offLadder

  // Build 6 unified steps — step labels below icons are strictly always English
  const stepList = CANONICAL_STAGES.map((canonical, idx) => {
    const passedStep = steps.find((s) => s.key === canonical.key) || steps[idx]
    const reached = passedStep ? passedStep.reached : (idx === 0 || (!offLadder && idx <= current))
    const timestamp = passedStep?.at || (idx === 0 ? filedAt : null)
    const label = canonical.label

    return {
      key: canonical.key,
      label,
      reached,
      at: timestamp,
    }
  })

  const currentStatusHeading = STATUS_TEXT_BY_LANG.CURRENT_STATUS[langKey] || 'Current status'

  return (
    <div
      className={`stepper${ended ? ' stepper--ended' : ''}${compact ? ' stepper--compact' : ''}`}
      role="group"
      aria-label={`Status: ${statusLabel ?? 'unknown'}`}
      style={compact ? { padding: '12px 16px 4px' } : undefined}
    >
      <ol
        className="stepper__rail"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${stepList.length}, 1fr)`,
          listStyle: 'none',
          margin: '0 0 16px',
          padding: 0,
        }}
      >
        {stepList.map((step, i) => {
          const isCurrent = !offLadder && i === current
          const tone = !step.reached ? 'todo' : ended ? 'refused' : 'done'

          return (
            <li
              key={step.key}
              className={`stepper__step stepper__step--${tone}${isCurrent ? ' stepper__step--now' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="stepper__dot" aria-hidden="true">
                {tone === 'refused' ? '×' : step.reached ? '✓' : i + 1}
              </span>
              <span className="stepper__label" style={{ fontSize: compact ? '11px' : undefined }}>
                {step.label}
              </span>
              <span className="stepper__when">
                {step.at ? formatShortDate(step.at) : ''}
              </span>
            </li>
          )
        })}
      </ol>

      {needsLocation ? (
        <div
          style={{
            margin: '0 0 12px 0',
            padding: '8px 12px',
            background: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '6px',
            color: '#92400e',
            fontSize: '0.85rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
          role="alert"
        >
          <span>⚠️</span>
          <span>
            {STATUS_TEXT_BY_LANG.NEEDS_LOCATION_MSG[langKey] ||
              STATUS_TEXT_BY_LANG.NEEDS_LOCATION_MSG.en}
          </span>
        </div>
      ) : null}

      <div className={`stepper__now${ended ? ' stepper__now--refused' : ''}`}>
        <span className="stepper__now-key">{currentStatusHeading}</span>
        <strong className="stepper__now-val">
          {statusLabel || (ended ? 'Closed without action' : 'Submitted')}
        </strong>
      </div>
    </div>
  )
}
