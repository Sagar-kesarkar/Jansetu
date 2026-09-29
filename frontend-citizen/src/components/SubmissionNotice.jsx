import { Link } from 'react-router-dom'

const labels = {
  NEW: 'Submitted', ACKNOWLEDGED: 'Acknowledged', UNDER_REVIEW: 'Under review',
  ASSIGNED: 'Assigned', IN_PROGRESS: 'In progress', NEEDS_LOCATION: 'Needs location',
  INVALID: 'Flagged for review', RESOLVED: 'Resolved', REJECTED: 'Closed without action',
}

export default function SubmissionNotice({ quota, error, onDismiss, filed }) {
  const detail = error?.detail
  return <section className="submission-notice" aria-label="Submission update">
    <button type="button" className="submission-notice__dismiss" onClick={onDismiss} aria-label="Dismiss submission update">×</button>
    <div role="status" aria-live="polite" aria-atomic="true">
      <p className="submission-notice__title">{error
        ? detail?.code === 'duplicate' ? 'Already submitted' : detail?.code === 'daily_limit' ? 'Daily limit reached' : 'Submission update'
        : filed ? 'Request submitted' : 'Message received'}</p>
      {quota ? <p className="field__hint">{quota.used} of {quota.limit} used today · {quota.remaining} remaining.
        {detail?.code === 'daily_limit' ? ' Resets at midnight IST.' : ''}</p> : null}
    </div>
    {error ? <div className="submission-notice__message" role="alert">
      <p>{error.message}</p>
      {detail?.complaints?.map((case_, index) => <p key={case_.token || index}>
        <strong>{labels[case_.status] || case_.status}</strong>
        {case_.token ? <> · <Link to={`/track/${encodeURIComponent(case_.token)}`}>Track {case_.token}</Link></> : null}
        {case_.reason ? <span className="submission-notice__reason">{case_.reason}</span> : null}
      </p>)}
    </div> : null}
  </section>
}
