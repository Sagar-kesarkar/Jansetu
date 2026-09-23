/**
 * Loading, empty and error, as three visibly different things.
 *
 * Every one of these takes a specific message. A generic "Something went wrong"
 * is the same as no message: the point of showing the API base URL on failure is
 * that the most likely cause is a backend that is not running, and that is fixable
 * in ten seconds by whoever is looking at the screen.
 */
import { API_BASE } from '../api.js'

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" />
      <div className="state__body">{label}</div>
    </div>
  )
}

export function Empty({ title = 'Nothing to show', body }) {
  return (
    <div className="state">
      <div className="state__title">{title}</div>
      {body ? <p className="state__body">{body}</p> : null}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__title">Could not load this</div>
      <p className="state__body">
        {error?.message || 'The request failed.'}
        <br />
        <span style={{ color: 'var(--ink-3)', fontSize: '12.5px' }}>
          API base: <code>{API_BASE}</code>
        </span>
      </p>
      {onRetry ? (
        <button type="button" className="btn btn--ghost btn--sm" onClick={onRetry} style={{ marginTop: 14 }}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

/**
 * The three states in one call, so a page reads as
 * `<Async {...q}>{(data) => …}</Async>` instead of a ladder of early returns.
 */
export function Async({ loading, error, data, reload, isEmpty, loadingLabel, emptyTitle, emptyBody, children }) {
  if (loading) return <Loading label={loadingLabel} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!data || (isEmpty ? isEmpty(data) : false)) return <Empty title={emptyTitle} body={emptyBody} />
  return children(data)
}
