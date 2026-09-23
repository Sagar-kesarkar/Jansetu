/**
 * The reply thread on one case.
 *
 * Both versions of every reply are shown — what the officer wrote in English, and
 * what the citizen will actually receive. Showing only the English would hide the
 * one thing worth auditing: whether the translation is any good. Showing only the
 * translated version would stop an English-reading officer from checking their own
 * words.
 *
 * When `body_native` is NULL the reply went out untranslated, and that is stated
 * rather than left as an absence. The backend deliberately stores NULL instead of
 * a copy of the English when Gemini is unavailable, precisely so this screen can
 * tell the difference.
 */
import { dateTime, statusLabel } from '../lib/format.js'
import { languageName } from '../hooks/useReference.js'
import { Empty } from './States.jsx'

export function ResponseThread({ responses, language, languages }) {
  if (!responses?.length) {
    return (
      <Empty
        title="No reply yet"
        body="Nobody has responded to this citizen. A report that is never answered teaches the reporter that filing achieves nothing."
      />
    )
  }

  const native = language && language !== 'en'

  return (
    <div>
      {responses.map((r) => (
        <div className="reply" key={r.id}>
          <div className="reply__head">
            <span className="reply__desk">{r.responder_desk}</span>
            <span className="reply__when">{dateTime(r.created_at)}</span>
          </div>

          <p className="reply__body">{r.body_en}</p>

          {r.body_native ? (
            <div className="reply__native">
              <div className="reply__native-label">
                Delivered in {languageName(languages, r.language)}
              </div>
              <p style={{ margin: 0 }}>{r.body_native}</p>
            </div>
          ) : native ? (
            <div className="reply__untranslated">
              Sent untranslated — this citizen filed in{' '}
              {languageName(languages, r.language)} and will receive English.
            </div>
          ) : null}

          <div className="reply__delivery">
            {r.status_before !== r.status_after ? (
              <>
                Moved {statusLabel(r.status_before)} → {statusLabel(r.status_after)}.{' '}
              </>
            ) : null}
            {r.delivery_state === 'queued'
              ? `Queued for delivery over ${r.delivery_channel}.`
              : `Delivery: ${r.delivery_state} (${r.delivery_channel}).`}
          </div>
        </div>
      ))}
    </div>
  )
}
