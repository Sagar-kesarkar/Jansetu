/**
 * Other cases filed by the same opaque reference.
 *
 * The only cross-request link the privacy model permits, and the reason
 * `citizen_ref` exists at all. An officer can see that this handle has reported
 * the same failure three times — which is the difference between a complaint and a
 * pattern — without learning anything about who it is.
 *
 * It also protects the ranking's honesty in the other direction: three reports
 * from one reference is a weaker demand signal than three from three, and an
 * officer who can see the repetition will not treat it as three households.
 */
import { Link } from 'react-router-dom'

import { StatusTag } from './Tags.jsx'
import { ago, dateOnly, sectorLabel } from '../lib/format.js'

export function ReporterHistory({ siblings, citizenRef }) {
  if (!siblings?.length) {
    return (
      <p className="composer__hint" style={{ margin: 0 }}>
        This is the only report from <span className="ref">{citizenRef || 'this reference'}</span>.
      </p>
    )
  }

  return (
    <div className="sibs">
      {siblings.map((s) => (
        <Link className="sib" to={`/requests/${s.id}`} key={s.id}>
          <span className="sib__text">
            <strong>{sectorLabel(s.category)}</strong> — {s.summary_en}
          </span>
          <span className="sib__meta">
            <StatusTag status={s.status} /> {dateOnly(s.created_at)} · {ago(s.created_at)}
          </span>
        </Link>
      ))}
    </div>
  )
}
