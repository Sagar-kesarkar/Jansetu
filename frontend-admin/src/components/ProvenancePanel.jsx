/**
 * Where the request came from, when, and from whom — the officer's four questions.
 *
 * This panel is the direct answer to what the console was asked for, and three of
 * its rows need explaining.
 *
 * **Where (geography).** Two different things are shown and must not be conflated.
 * `place` is what the citizen said, scrubbed to ward level. `district` is what the
 * platform matched it to — an LGD code, which is what makes the row joinable
 * against any other government dataset. When the match failed, that is shown
 * loudly: an unresolved request never reaches a hotspot or a recommendation, so a
 * silent NULL is a request that quietly falls out of the national picture.
 *
 * **Who.** An opaque reference, and an explicit sentence saying that is all there
 * is. A blank "Reporter: —" reads as missing data and invites someone to go
 * looking for the real identity in a database that does not contain one. Saying
 * *why* it is opaque is the difference between a gap and a design.
 *
 * **The photograph.** Its description is here; the image itself has its own panel
 * in the left column, because a description an officer cannot check is
 * corroboration on trust. What stays true is that only the description travels — the
 * file is reachable through this console and nowhere else.
 */
import { ChannelTag } from './Tags.jsx'
import { languageName } from '../hooks/useReference.js'
import { ago, channelNote, dateTime, num, sectorLabel } from '../lib/format.js'

function Row({ k, children }) {
  return (
    <div className="row">
      <div className="row__k">{k}</div>
      <div className="row__v">{children}</div>
    </div>
  )
}

export function ProvenancePanel({ request, languages }) {
  const r = request
  const loc = r.location || {}
  const levels = [
    ['Ward / sector', loc.sector_or_ward],
    ['Locality', loc.locality],
    ['City / district', loc.district_or_city],
    ['State', loc.state],
    ['PIN', loc.pin_code],
  ].filter(([, v]) => v)

  return (
    <div className="panel">
      <div className="panel__head">
        <span className="panel__title">Provenance</span>
        <span className="panel__note">
          Docket <span className="ref">#{r.id}</span>
        </span>
      </div>
      <div className="panel__body">
        <div className="rows">
          <Row k="Filed">
            {dateTime(r.created_at)}
            <small>{ago(r.created_at)}</small>
          </Row>

          <Row k="Arrived by">
            <ChannelTag channel={r.channel} />{' '}
            <small>{channelNote(r.channel)}</small>
          </Row>

          <Row k="Filed in">
            {languageName(languages, r.language)}
            <small>
              {r.language === 'en'
                ? 'No translation was needed.'
                : 'Translated to English by Gemini for this screen.'}
            </small>
          </Row>

          <Row k="Sector">{sectorLabel(r.category)}</Row>

          {r.affected_estimate ? (
            <Row k="People affected">
              {num(r.affected_estimate)}
              <small>as stated in the request, not an estimate of ours</small>
            </Row>
          ) : null}

          <Row k="Reported place">
            {r.place || <span className="dash">No place was stated</span>}
            {levels.length ? (
              <small>
                {levels.map(([label, v]) => `${label}: ${v}`).join(' · ')}
              </small>
            ) : null}
          </Row>

          <Row k="Matched to">
            {r.district ? (
              <>
                {r.district}, {r.state}
                <small>
                  LGD district code <span className="ref">{r.district_code}</span>
                </small>
              </>
            ) : (
              <>
                <span className="queue__nomatch">Not matched to a district</span>
                <small>
                  This request is counted nowhere in the national ranking.
                </small>
              </>
            )}
          </Row>

          <Row k="Reporter">
            <span className="ref">{r.citizen_ref || 'none recorded'}</span>
          </Row>
        </div>

        {r.has_photo ? (
          <div className="derived">
            <div className="derived__label">
              {r.image_verification ? 'Photograph, as read by Gemini' : 'Photograph attached'}
            </div>
            <p>
              {r.image_verification || (
                <span className="muted">
                  A photograph was submitted but could not be read — no description
                  was produced. Treat the written complaint as the only evidence.
                </span>
              )}
            </p>
            <p className="composer__hint" style={{ marginTop: 8, marginBottom: 0 }}>
              {r.photo_stored
                ? 'This is what Gemini concluded; the photograph itself is in the panel on the left, so you can check it.'
                : 'The file was not retained for this report. This description is all that remains of it.'}
            </p>
          </div>
        ) : null}

        <div className="privacy">
          <strong>What this console cannot tell you</strong>
          The reporter reference above is a one-way HMAC. There is no name, phone
          number, address or device on this record — not withheld from this screen,
          not present in the database. The place is held to ward level and never
          finer, and your reply is routed to that reference by the channel adapter
          without anyone here learning who it belongs to.
        </div>
      </div>
    </div>
  )
}
