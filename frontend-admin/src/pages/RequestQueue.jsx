/**
 * The queue. What an officer has open all day.
 *
 * Two defaults are opinions, not conveniences.
 *
 * **Unanswered first.** The console opens filtered to cases nobody has replied to,
 * newest first. A console that opens on everything shows 600 rows of which 500 are
 * closed, and the backlog — the only thing an officer is answerable for — is
 * invisible. The filter is visible and one click from off, so it is a default and
 * not a restriction.
 *
 * **Filters live in the URL.** `?state=Odisha&unanswered=true` is shareable, and
 * more importantly navigating into a case and back returns to the same queue
 * rather than resetting to the top. Local state would lose the officer's place on
 * every reply, which on a screen whose job is working through a list is the
 * difference between usable and not.
 *
 * **The signed-in post supplies the opening jurisdiction.** A BDO in Nabarangpur
 * should land on Odisha, not on 600 cases from nineteen states. It is a default in
 * exactly the sense the other two are: absent-from-URL means not yet chosen, and
 * one click on Clear escapes it. It is emphatically *not* access control — the API
 * will serve any state to anyone, which the sign-in screen says plainly.
 *
 * **Three feeds, one table.** Active, cleared, and the cases triage flagged as not
 * being requests at all. The third is a tab rather than a status in the dropdown
 * on purpose: a dropdown option is something an officer has to know to look for,
 * and a hidden pile of possibly-real complaints that nobody visits is worse than
 * no triage at all.
 */
import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { getRequests, getStats, restoreRequest } from '../api.js'
import { QueueFilters } from '../components/QueueFilters.jsx'
import { StatsBar } from '../components/StatsBar.jsx'
import { Async } from '../components/States.jsx'
import { ChannelTag, ConfidenceTag, PhotoTag, StatusTag, UrgencyTag } from '../components/Tags.jsx'
import { useApi } from '../hooks/useApi.js'
import { useReference } from '../hooks/useReference.js'
import { ago, dateTime, num, sectorLabel } from '../lib/format.js'

const PAGE = 40

/**
 * The three feeds, as tabs rather than status-dropdown presets.
 *
 * `status: null` on the first one means "send no status filter", which the API
 * reads as the working queue and which already excludes triaged-invalid cases —
 * see `routers/requests.py::list_requests`. The exclusion lives there rather than
 * here so the officials' console and this one cannot drift apart.
 *
 * Cleared asks for RESOLVED **or** REJECTED in one request, which is why the
 * `status` query param is a repeatable list on the API and an array here.
 */
const VIEWS = {
  active: {
    label: 'Active requests',
    status: null,
    empty: 'No cases match these filters',
  },
  cleared: {
    label: 'Cleared / resolved',
    status: ['RESOLVED', 'REJECTED'],
    title: 'Closed cases',
    empty: 'Nothing has been closed yet',
    emptyBody: 'Cases appear here once an officer marks them resolved or rejected.',
  },
  invalid: {
    label: 'Invalid requests',
    status: ['INVALID'],
    title: 'Flagged as not a request',
    empty: 'Nothing has been flagged',
    emptyBody:
      'Triage has not set any message aside. With no Gemini API key configured nothing is ever flagged, so this queue stays empty by design.',
  },
}

/** URL params are strings; the API wants absent-or-typed. */
function readFilters(params, session) {
  const view = params.get('view')
  return {
    // Not a filter among the others: it decides which of the three feeds is being
    // worked, and an unknown value falls back to the working queue rather than
    // showing an empty table for a typo in the URL.
    view: VIEWS[view] ? view : 'active',
    // `has` rather than truthiness, so an officer who cleared the state filter
    // keeps it cleared instead of being snapped back to their own jurisdiction.
    state: params.has('state') ? params.get('state') : session?.state || '',
    category: params.get('category') || '',
    channel: params.get('channel') || '',
    language: params.get('language') || '',
    status: params.get('status') || '',
    minUrgency: params.get('min_urgency') || '',
    q: params.get('q') || '',
    // Absent means "not yet chosen", which is the first load — so it opens on the
    // backlog. An explicit `unanswered=false` is the officer having turned it off
    // and must survive a reload.
    unanswered: params.has('unanswered') ? params.get('unanswered') === 'true' : true,
    offset: Number(params.get('offset') || 0),
  }
}

function writeFilters(f) {
  const out = {}
  // Written even when empty — see readFilters. An empty value is dropped again by
  // `api.js::query`, so the API never receives a literal `?state=`.
  out.state = f.state
  if (f.view && f.view !== 'active') out.view = f.view
  if (f.category) out.category = f.category
  if (f.channel) out.channel = f.channel
  if (f.language) out.language = f.language
  if (f.status) out.status = f.status
  if (f.minUrgency) out.min_urgency = f.minUrgency
  if (f.q) out.q = f.q
  out.unanswered = f.unanswered ? 'true' : 'false'
  if (f.offset) out.offset = String(f.offset)
  return out
}

export function RequestQueue({ session }) {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const reference = useReference()

  const f = useMemo(() => readFilters(params, session), [params, session])
  const view = VIEWS[f.view]

  // Which case is being rescued, and why the last rescue failed. Kept per-row
  // rather than as one flag so a failure on docket 640 cannot grey out the button
  // on 641.
  const [rescuing, setRescuing] = useState(null)
  const [rescueError, setRescueError] = useState(null)

  const setFilters = useCallback(
    (next) => setParams(writeFilters(next), { replace: false }),
    [setParams],
  )

  // A tab is not a filter change: it resets the page and drops the status and
  // unanswered narrowing, both of which belong to the working queue and would
  // silently empty the other two feeds.
  const setView = useCallback(
    (next) => setFilters({ ...f, view: next, status: '', unanswered: false, offset: 0 }),
    [f, setFilters],
  )

  // The tabs own `status` and `unanswered` outside the active view: a "cleared"
  // feed narrowed to NEW, or an invalid feed narrowed to unanswered-only, are
  // states the UI can reach and nobody wants.
  const status = f.view === 'active' ? f.status : view.status
  const unanswered = f.view === 'active' ? f.unanswered : false

  const key = JSON.stringify({ ...f, status, unanswered })

  const queue = useApi(
    () =>
      getRequests({
        state: f.state,
        category: f.category,
        channel: f.channel,
        language: f.language,
        status,
        minUrgency: f.minUrgency,
        q: f.q.length >= 2 ? f.q : '',
        unanswered,
        limit: PAGE,
        offset: f.offset,
      }),
    [key],
  )

  // Counters follow the geography and sector filters only. Narrowing to
  // "unanswered" and then reading "awaiting first reply" off the same filtered
  // set would make the number tautological.
  const stats = useApi(() => getStats({ state: f.state, category: f.category }), [f.state, f.category])

  const byStatus = stats.data?.by_status || {}
  const counts = {
    active: null, // the working queue's size is already the "Open" counter above
    input_needed: byStatus.NEEDS_LOCATION || 0,
    cleared: (byStatus.RESOLVED || 0) + (byStatus.REJECTED || 0),
    invalid: byStatus.INVALID || 0,
  }

  const rescue = useCallback(
    async (id) => {
      setRescuing(id)
      setRescueError(null)
      try {
        await restoreRequest(id)
        // Both feeds move: the row leaves this list and joins the working queue,
        // and the tab count beside it has to stop claiming otherwise.
        queue.reload()
        stats.reload()
      } catch (err) {
        setRescueError({ id, message: err.message })
      } finally {
        setRescuing(null)
      }
    },
    [queue, stats],
  )

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Request queue</h1>
          <p className="page-head__lede">
            Every citizen report, in the words it was filed in, with where and how
            it arrived. Open one to reply in the reporter's own language.
          </p>
        </div>
      </div>

      <StatsBar stats={stats.data} />

      <div className="queue-tabs" role="tablist" aria-label="Which cases to show">
        {Object.entries(VIEWS).map(([id, v]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={f.view === id}
            className={f.view === id ? 'queue-tab queue-tab--on' : 'queue-tab'}
            onClick={() => setView(id)}
          >
            {v.label}
            {counts[id] ? <span className="queue-tab__count">{num(counts[id])}</span> : null}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel__body">
          <QueueFilters value={f} onChange={setFilters} reference={reference} view={f.view} />
        </div>
      </div>

      {f.view === 'invalid' ? (
        <p className="triage-note">
          Gemini judged these messages not to be development requests — test
          messages, adverts, wrong numbers. Nothing here counts towards a
          district's unmet-need score and nothing here has been shown to a
          reporting citizen as refused. Triage is sometimes wrong: read the
          original text against the stated reason, and mark it valid to put it
          back in the working queue.
        </p>
      ) : null}

      <div className="panel">
        <div className="panel__head">
          <span className="panel__title">
            {view.title || (f.unanswered ? 'Action required' : 'All cases')}
            {f.state ? ` — ${f.state}` : ''}
          </span>
          <span className="panel__note">
            {queue.data ? `${num(queue.data.length)} shown, newest first` : 'Newest first'}
          </span>
        </div>

        <div className="panel__body--tight">
          <Async
            {...queue}
            isEmpty={(rows) => rows.length === 0}
            loadingLabel="Loading the queue…"
            emptyTitle={
              f.view === 'active' && f.unanswered
                ? 'Nothing is waiting for a reply'
                : view.empty
            }
            emptyBody={
              f.view === 'active'
                ? f.unanswered
                  ? 'Every case matching these filters has had at least one official response. Untick "Action required only" to see the rest.'
                  : 'Widen the filters, or clear them to see the whole queue.'
                : view.emptyBody
            }
          >
            {(rows) => (
              <>
                <div className="queue-wrap">
                  <table className="queue">
                    <thead>
                      <tr>
                        <th>Docket</th>
                        <th>Filed</th>
                        <th>What was reported</th>
                        <th>Place</th>
                        <th>Arrived by</th>
                        <th>{f.view === 'invalid' ? 'Overrule' : 'Status'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr
                          key={r.id}
                          onClick={() => navigate(`/requests/${r.id}`)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') navigate(`/requests/${r.id}`)
                          }}
                          tabIndex={0}
                          role="link"
                          aria-label={`Open docket ${r.id}`}
                        >
                          <td className="queue__id">#{r.id}</td>

                          <td className="queue__when">
                            <strong>{ago(r.created_at)}</strong>
                            <span>{dateTime(r.created_at)}</span>
                          </td>

                          <td>
                            {/* English leads *in the queue only*. An officer
                                scanning forty rows is triaging, and forty blocks of
                                Odia, Bodo and Manipuri script are unreadable to
                                most desks in most states — a queue you cannot scan
                                is a queue nobody works. The citizen's own words are
                                one line below, in their own script, and on the case
                                page they lead again: that is where the reading
                                happens, and there the paraphrase must not go first. */}
                            <div className="queue__lead">
                              {r.summary_en || r.raw_text}
                            </div>
                            {r.raw_text && r.raw_text !== r.summary_en ? (
                              <div className="queue__original" lang={r.language}>
                                {r.raw_text}
                              </div>
                            ) : null}
                            <div className="tag-row" style={{ marginTop: 6 }}>
                              <span className="tag tag--plain">{sectorLabel(r.category)}</span>
                              <UrgencyTag level={r.urgency} />
                              <PhotoTag hasPhoto={r.has_photo} description={r.image_verification} />
                              <ConfidenceTag value={r.confidence} />
                            </div>
                            {r.triage_reason ? (
                              <div className="triage-reason">
                                <span className="triage-reason__label">
                                  Why this was flagged
                                </span>
                                {r.triage_reason}
                              </div>
                            ) : null}
                          </td>

                          <td className="queue__place">
                            {r.place || <span className="dash">not stated</span>}
                            {r.district ? (
                              <span>
                                {r.district}, {r.state}
                              </span>
                            ) : (
                              <span className="queue__nomatch">no district match</span>
                            )}
                          </td>

                          <td>
                            <ChannelTag channel={r.channel} />
                          </td>

                          {/* In the invalid feed the status column becomes the
                              action column. The status is not news — every row here
                              is INVALID — and the one thing an officer does on this
                              screen is disagree with the machine. */}
                          {f.view === 'invalid' ? (
                            <td>
                              <button
                                type="button"
                                className="btn btn--rescue btn--sm"
                                disabled={rescuing === r.id}
                                onClick={(e) => {
                                  // The whole row is a link to the case page.
                                  e.stopPropagation()
                                  rescue(r.id)
                                }}
                              >
                                {rescuing === r.id ? 'Restoring…' : '✓ Mark as valid'}
                              </button>
                              {rescueError?.id === r.id ? (
                                <div
                                  className="queue__nomatch"
                                  style={{ marginTop: 5, maxWidth: 180 }}
                                >
                                  {rescueError.message}
                                </div>
                              ) : null}
                            </td>
                          ) : (
                            <td>
                              <StatusTag status={r.status} />
                              {r.response_count > 0 ? (
                                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                                  {r.response_count} {r.response_count === 1 ? 'reply' : 'replies'}
                                </div>
                              ) : null}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="pager">
                  <span>
                    Showing {f.offset + 1}–{f.offset + rows.length}
                  </span>
                  <span className="btn-row">
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={f.offset === 0}
                      onClick={() => setFilters({ ...f, offset: Math.max(0, f.offset - PAGE) })}
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={rows.length < PAGE}
                      onClick={() => setFilters({ ...f, offset: f.offset + PAGE })}
                    >
                      Next
                    </button>
                  </span>
                </div>
              </>
            )}
          </Async>
        </div>
      </div>
    </>
  )
}
