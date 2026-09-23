/**
 * The small labels that carry most of the queue's meaning.
 *
 * Every one of these is a word rather than a code. `IN_PROGRESS`, `4` and `ivr`
 * are what the API returns; "In progress", "Serious" and "IVR call" are what an
 * officer reads without translating in their head. Colour is used sparingly and
 * only where it maps to action: red for a case nobody has touched, red for
 * urgency 4–5, and nothing for the rest.
 */
import { channelLabel, statusLabel, urgencyLabel } from '../lib/format.js'

export function StatusTag({ status }) {
  return <span className={`tag tag--status-${status}`}>{statusLabel(status)}</span>
}

export function UrgencyTag({ level }) {
  return (
    <span className={`tag tag--u${level}`} title={`Urgency ${level} of 5`}>
      {urgencyLabel(level)}
    </span>
  )
}

export function ChannelTag({ channel }) {
  return <span className="tag tag--plain">{channelLabel(channel)}</span>
}

/**
 * Shown only when a photograph was actually attached, and it says which of the
 * two photo states applies. "Attached, not read" is a different fact from
 * "attached and described" — the first means the vision call failed or ran with
 * no API key, and an officer must not read the absence of a description as the
 * absence of a photograph.
 */
export function PhotoTag({ hasPhoto, description }) {
  if (!hasPhoto) return null
  return (
    <span
      className="tag tag--photo"
      title={
        description
          ? 'A photograph was submitted and read by Gemini. The image itself is not stored.'
          : 'A photograph was submitted but could not be read. The image itself is not stored.'
      }
    >
      {description ? 'Photo read' : 'Photo, not read'}
    </span>
  )
}

/**
 * Extraction confidence, surfaced only when it is low.
 *
 * 0.1 is the fallback path's fixed value and means "no model touched this" — the
 * category came from keyword matching. An officer needs to know that the sector
 * on a row may be wrong, and hiding it would be the more comfortable choice and
 * the less honest one.
 */
export function ConfidenceTag({ value }) {
  if (value === null || value === undefined || value >= 0.5) return null
  const unprocessed = value <= 0.15
  return (
    <span
      className="tag tag--u3"
      title={
        unprocessed
          ? 'Classified by keyword matching, not by Gemini. The sector may be wrong — read the original text.'
          : 'Gemini was unsure of the sector. Read the original text before acting.'
      }
    >
      {unprocessed ? 'Unverified sector' : `Low confidence ${value.toFixed(2)}`}
    </span>
  )
}

export function SectorTag({ category }) {
  return <span className="tag tag--plain">{category || 'OTHER'}</span>
}

