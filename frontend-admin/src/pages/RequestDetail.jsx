/**
 * One case, open on an officer's desk.
 *
 * The layout answers the four questions in the order they get asked: what was
 * reported (the citizen's own words, first and largest), where and when it came
 * from and from whom (provenance, alongside), what has already been said
 * (thread), and then the reply box.
 *
 * Two things are deliberately *not* collapsed together.
 *
 * **The transcript and the summary are different documents.** For a voice or IVR
 * call, `transcript` is what Gemini heard and `summary_en` is what Gemini
 * concluded. An officer acting on a report needs to be able to see that the
 * summary says "borewell dry for three weeks" while the transcript says
 * "borewell dry since Holi" — the paraphrase is where meaning goes missing, and
 * hiding one behind the other removes the only check available.
 *
 * **A reply and a status change are separate actions.** Most replies should move
 * the case, and the composer offers that in one step. But an officer sometimes
 * needs to mark something rejected or resolved with no message — a duplicate, or
 * a case closed by a different department — and forcing a fake citizen-facing
 * message to record that would put fiction in the outbound thread. Hence the bare
 * status control below the composer.
 */
import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getRequest, patchStatus, restoreRequest } from '../api.js'
import { EvidencePhoto } from '../components/EvidencePhoto.jsx'
import { ProvenancePanel } from '../components/ProvenancePanel.jsx'
import { ReplyComposer } from '../components/ReplyComposer.jsx'
import { ReporterHistory } from '../components/ReporterHistory.jsx'
import { ResponseThread } from '../components/ResponseThread.jsx'
import { Async } from '../components/States.jsx'
import { ConfidenceTag, StatusTag, UrgencyTag } from '../components/Tags.jsx'
import { useApi } from '../hooks/useApi.js'
import { useReference } from '../hooks/useReference.js'
import { sectorLabel, statusLabel } from '../lib/format.js'

const ALL_STATUS = ['NEW', 'ACKNOWLEDGED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED']

/**
 * A case triage flagged as not being a request at all.
 *
 * Replaces the composer and the status control rather than joining them. Every
 * other action on this page assumes a real grievance: replying to a suspected
 * advert sends a citizen a message about a case they never filed, and marking one
 * "Resolved" records casework that never happened. There is exactly one decision
 * to make here, so there is exactly one control.
 */
function TriagePanel({ request, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function rescue() {
    setBusy(true)
    setError(null)
    try {
      await restoreRequest(request.id)
      onChanged?.()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <span className="panel__title">Flagged as not a request</span>
        <span className="panel__note">No reply has been sent to the citizen</span>
      </div>
      <div className="panel__body">
        {request.triage_reason ? (
          <div className="triage-reason">
            <span className="triage-reason__label">Gemini's reason</span>
            {request.triage_reason}
          </div>
        ) : null}

        <p className="composer__hint" style={{ marginTop: 12 }}>
          This message is not in the working queue and does not count towards this
          district's unmet-need score. The citizen has not been told it was set
          aside. Triage is a machine judgement and it is sometimes wrong — read the
          words above against the reason, and if this is a real report, put it back.
        </p>

        <div className="btn-row" style={{ marginTop: 12 }}>
          <button type="button" className="btn btn--rescue" disabled={busy} onClick={rescue}>
            {busy ? 'Restoring…' : '✓ Mark as valid'}
          </button>
        </div>

        {error ? (
          <div className="notice notice--bad" role="alert" style={{ marginTop: 12 }}>
            {error.message}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/**
 * Status without a message. Sits under the composer, visually quieter, because it
 * is the exception — see the module docstring.
 */
function StatusControl({ request, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function move(status) {
    setBusy(true)
    setError(null)
    try {
      await patchStatus(request.id, status)
      onChanged?.()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <span className="panel__title">Move without replying</span>
        <span className="panel__note">Currently {statusLabel(request.status)}</span>
      </div>
      <div className="panel__body">
        <div className="btn-row">
          {ALL_STATUS.filter((s) => s !== request.status && s !== 'NEW').map((s) => (
            <button
              key={s}
              type="button"
              className="btn btn--ghost btn--sm"
              disabled={busy}
              onClick={() => move(s)}
            >
              {statusLabel(s)}
            </button>
          ))}
        </div>
        <p className="composer__hint">
          For duplicates, or a case closed by another department. The citizen is not
          told — if they should be, write a reply instead.
        </p>
        {error ? (
          <div className="notice notice--bad" role="alert">
            {error.message}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function RequestDetail({ session }) {
  const { id } = useParams()
  const { languages } = useReference()
  const state = useApi(() => getRequest(id), [id])
  const reload = state.reload

  // A posted reply changes response_count, status and the thread at once, so the
  // record is refetched rather than patched locally. One extra GET on a click the
  // officer already waited on beats three pieces of state drifting apart.
  const onPosted = useCallback(() => reload(), [reload])

  return (
    <>
      <Link className="back" to="/">
        ← Back to the queue
      </Link>

      <Async {...state} loadingLabel={`Loading docket #${id}…`}>
        {(r) => (
          <>
            <div className="page-head">
              <div>
                {/* The citizen's own reference leads, not ours.
                    `#636` is the row's primary key — meaningful to this database and
                    to nobody else. The token is what the citizen was given, what they
                    quote on the phone, and what names the photograph an officer
                    downloads. Leading with it means an officer taking a call about
                    "JS-GDDV-TAXX" is reading the same string back. The internal ref
                    stays alongside, because it is what appears in logs and in the
                    console's own URL. */}
                <h1>
                  <span className="docket__ref">{r.track_token || 'Tracking token unavailable'}</span>
                  {' — '}
                  {sectorLabel(r.category)}
                </h1>
                <p className="page-head__lede">
                  <span className="docket__internal">Internal ref #{r.id}</span>
                  {' · '}
                  {r.district ? `${r.district}, ${r.state}` : 'District not matched'}
                  {r.place ? ` · ${r.place}` : ''}
                </p>
              </div>
              <div className="tag-row">
                <StatusTag status={r.status} />
                <UrgencyTag level={r.urgency} />
                <ConfidenceTag value={r.confidence} />
              </div>
            </div>

            <div className="case">
              <div className="case__col">
                <div className="panel">
                  <div className="panel__head">
                    <span className="panel__title">What the citizen reported</span>
                    <span className="panel__note">
                      {r.channel === 'voice' || r.channel === 'ivr'
                        ? 'Spoken, transcribed by Gemini'
                        : 'As typed'}
                    </span>
                  </div>
                  <div className="panel__body">
                    <div className="quote__label">In their own words</div>
                    <p className="quote" lang={r.language}>
                      {r.raw_text || r.transcript || <span className="dash">No text was captured</span>}
                    </p>

                    {r.transcript && r.transcript !== r.raw_text ? (
                      <div className="derived">
                        <div className="derived__label">Transcript</div>
                        <p lang={r.language}>{r.transcript}</p>
                      </div>
                    ) : null}

                    {r.summary_en && r.summary_en !== r.raw_text ? (
                      <div className="derived">
                        <div className="derived__label">Summary in English — ours, not theirs</div>
                        <p>{r.summary_en}</p>
                      </div>
                    ) : null}
                  </div>
                </div>

                <EvidencePhoto request={r} />

                {r.status === 'INVALID' ? (
                  <TriagePanel request={r} onChanged={reload} />
                ) : (
                  <ReplyComposer
                    request={r}
                    languages={languages}
                    session={session}
                    onPosted={onPosted}
                  />
                )}

                <div className="panel">
                  <div className="panel__head">
                    <span className="panel__title">Replies sent</span>
                    <span className="panel__note">
                      {state.refreshing
                        ? 'Updating…'
                        : r.responses?.length
                          ? `${r.responses.length} on record`
                          : 'None yet'}
                    </span>
                  </div>
                  <div className="panel__body">
                    <ResponseThread
                      responses={r.responses}
                      language={r.language}
                      languages={languages}
                    />
                  </div>
                </div>

                {/* Hidden on a flagged case: the only decision available there is
                    whether it is a request at all, and offering "Resolved" would
                    let an officer close a message nobody ever read as casework. */}
                {r.status === 'INVALID' ? null : (
                  <StatusControl request={r} onChanged={reload} />
                )}
              </div>

              <div className="case__col">
                <ProvenancePanel request={r} languages={languages} />

                <div className="panel">
                  <div className="panel__head">
                    <span className="panel__title">Same reporter</span>
                    <span className="panel__note">
                      {r.from_same_reporter?.length
                        ? `${r.from_same_reporter.length} other ${
                            r.from_same_reporter.length === 1 ? 'case' : 'cases'
                          }`
                        : 'First report'}
                    </span>
                  </div>
                  <div className="panel__body">
                    <ReporterHistory
                      siblings={r.from_same_reporter}
                      citizenRef={r.citizen_ref}
                    />
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </Async>
    </>
  )
}
