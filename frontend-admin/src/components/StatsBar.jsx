/**
 * The header counters. Computed server-side over the whole filtered set.
 *
 * Deliberately not derived from the rows on screen: the queue is a page of at
 * most a few dozen, and a backlog figure taken from a truncated page understates
 * it exactly when it matters most. `GET /requests/stats` does the counting in SQL.
 *
 * The two counters that lead are the ones an officer is answerable for — cases
 * with no reply at all, and how long the oldest open case has been waiting.
 * Everything else is context.
 *
 * The first is labelled "Action required" rather than "Awaiting first reply"
 * because the second describes the platform's state and the first describes the
 * officer's obligation, and only one of those gets a queue cleared.
 */
import { num } from '../lib/format.js'

export function StatsBar({ stats }) {
  if (!stats) return null

  const oldest = stats.oldest_open_days
  const oldestText =
    oldest === null || oldest === undefined
      ? 'nothing open'
      : oldest >= 1
        ? `${Math.round(oldest)} days`
        : 'under a day'

  return (
    <div className="stats">
      <div className={stats.awaiting_first_reply > 0 ? 'stat stat--flag' : 'stat'}>
        <div className="stat__label">Action required</div>
        <div className="stat__value">{num(stats.awaiting_first_reply)}</div>
        <div className="stat__hint">nobody has responded yet</div>
      </div>

      <div className={oldest && oldest > 30 ? 'stat stat--flag' : 'stat'}>
        <div className="stat__label">Oldest open case</div>
        <div className="stat__value">{oldestText}</div>
        <div className="stat__hint">since it was filed</div>
      </div>

      <div className="stat">
        <div className="stat__label">Open</div>
        <div className="stat__value">{num(stats.open)}</div>
        <div className="stat__hint">new, acknowledged or in progress</div>
      </div>

      <div className="stat">
        <div className="stat__label">Filed this week</div>
        <div className="stat__value">{num(stats.filed_last_7_days)}</div>
        <div className="stat__hint">last 7 days</div>
      </div>

      <div className="stat">
        <div className="stat__label">Total on record</div>
        <div className="stat__value">{num(stats.total)}</div>
        <div className="stat__hint">all statuses</div>
      </div>
    </div>
  )
}
