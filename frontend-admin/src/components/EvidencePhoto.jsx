/**
 * The citizen's photograph, on the officer's desk.
 *
 * This panel exists because the alternative was asking an officer to dispatch a
 * crew on the strength of a sentence they could not check. Gemini's description is
 * good, and it is still a paraphrase produced by a model — the same reason the
 * transcript sits beside the summary elsewhere on this page. A photograph is the
 * one part of a citizen report that is hard to fabricate, so it is the one part an
 * officer should be able to look at.
 *
 * Three states, all of them real:
 *
 * **On file.** Shown inline, clickable to full size, with a download named after
 * the case's tracking token — the same reference the citizen is holding, so a file
 * saved to a desktop can be matched back to a docket without a lookup.
 *
 * **Attached but not retained.** True of every report filed before retention
 * existed, and of any where the write failed. Said plainly rather than hidden,
 * because "no photograph" and "photograph we no longer have" are different facts
 * and an officer chasing the second one deserves to know which they are looking at.
 *
 * **Broken link.** `onError` swaps in the same message. A dead `<img>` in a case
 * file reads as the console being broken, which is worse than the truth.
 */
import { useState } from 'react'

import { photoUrl } from '../api.js'

export function EvidencePhoto({ request }) {
  const r = request
  const [failed, setFailed] = useState(false)

  if (!r.has_photo) return null

  const available = r.photo_stored && !failed
  const reference = r.track_token || `docket-${r.id}`

  return (
    <div className="panel">
      <div className="panel__head">
        <span className="panel__title">Photograph submitted</span>
        <span className="panel__note">
          {available ? <span className="ref">{reference}</span> : 'Not on file'}
        </span>
      </div>
      <div className="panel__body">
        {available ? (
          <>
            {/* An anchor around the image rather than a lightbox. A new tab gives
                the officer the browser's own zoom, rotate and save, which is more
                than a modal would provide and nothing to maintain. */}
            <a
              className="evidence__frame"
              href={photoUrl(r.id)}
              target="_blank"
              rel="noreferrer"
              title="Open the full-size photograph in a new tab"
            >
              <img
                className="evidence__img"
                src={photoUrl(r.id)}
                alt={r.image_verification || 'The photograph submitted with this report'}
                onError={() => setFailed(true)}
                loading="lazy"
              />
            </a>

            <div className="evidence__actions">
              {/* No `download` attribute: it is ignored cross-origin, and the API
                  is on a different port. The filename comes from the server's
                  Content-Disposition, which is why this is `?download=1` and not
                  a client-side rename. */}
              <a className="btn btn--sm" href={photoUrl(r.id, { download: true })}>
                Download as {reference}
              </a>
              <a
                className="btn btn--ghost btn--sm"
                href={photoUrl(r.id)}
                target="_blank"
                rel="noreferrer"
              >
                Open full size
              </a>
            </div>

            <p className="composer__hint" style={{ marginTop: 10, marginBottom: 0 }}>
              Retained as case evidence and reachable only through this console.
              It is not published, not indexed and not part of the district
              statistics — only Gemini's description of it travels beyond this page.
            </p>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            {failed
              ? 'The photograph is recorded on this case but could not be loaded. The file may have been removed from the server.'
              : 'A photograph was submitted, but the file was not retained — this report predates photo retention. Gemini’s description is in the provenance panel and is the only evidence available.'}
          </p>
        )}
      </div>
    </div>
  )
}
