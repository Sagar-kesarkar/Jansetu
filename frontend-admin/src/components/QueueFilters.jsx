/**
 * Queue filters.
 *
 * Every dropdown is populated from the backend — states from
 * `data/reference/districts.csv`, languages from `app/i18n/languages.py`, sectors
 * from `app/models/taxonomy.py`. Constraint 4 says coverage grows by adding rows
 * to those files, so a hardcoded list here would go stale the first time someone
 * did that.
 *
 * The search box searches the citizen's original text, our English summary and
 * the scrubbed place levels. It does **not** search the citizen's raw location
 * line, even though that column exists and is indexed: substring search over a
 * hidden field discloses it a character at a time. The placeholder says what is
 * searched so nobody assumes otherwise — see `routers/requests.py::list_requests`.
 */
import { useEffect, useState } from 'react'

import { languageName } from '../hooks/useReference.js'
import { channelLabel, sectorLabel, statusLabel } from '../lib/format.js'

const CHANNELS = ['whatsapp', 'ivr', 'voice', 'text', 'sms']
const STATUSES = ['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED']

export function QueueFilters({ value, onChange, reference, view = 'active' }) {
  // The status dropdown and the unanswered toggle belong to the working queue
  // only. Both are owned by the tab outside it — a "cleared" feed narrowed to NEW
  // returns nothing, and there is no such thing as replying to a test message —
  // so showing controls that cannot do anything is worse than hiding them.
  const working = view === 'active'

  // The search box is debounced locally so typing does not fire a request per
  // keystroke. Everything else applies immediately — a dropdown change is a
  // deliberate act and waiting 400ms for it feels broken.
  const [draft, setDraft] = useState(value.q || '')

  useEffect(() => {
    setDraft(value.q || '')
  }, [value.q])

  useEffect(() => {
    if ((draft || '') === (value.q || '')) return
    const t = setTimeout(() => onChange({ ...value, q: draft || '', offset: 0 }), 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  const set = (patch) => onChange({ ...value, ...patch, offset: 0 })

  return (
    <div className="filters">
      <label className="field">
        <span className="field__label">State</span>
        <select value={value.state || ''} onChange={(e) => set({ state: e.target.value })}>
          <option value="">All states</option>
          {reference.states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Sector</span>
        <select value={value.category || ''} onChange={(e) => set({ category: e.target.value })}>
          <option value="">All sectors</option>
          {reference.categories.map((c) => (
            <option key={c} value={c}>
              {sectorLabel(c)}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Arrived by</span>
        <select value={value.channel || ''} onChange={(e) => set({ channel: e.target.value })}>
          <option value="">All channels</option>
          {CHANNELS.map((c) => (
            <option key={c} value={c}>
              {channelLabel(c)}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Language</span>
        <select value={value.language || ''} onChange={(e) => set({ language: e.target.value })}>
          <option value="">All languages</option>
          {reference.languages.map((l) => (
            <option key={l.code} value={l.code}>
              {languageName(reference.languages, l.code)}
            </option>
          ))}
        </select>
      </label>

      {working ? (
        <label className="field">
          <span className="field__label">Status</span>
          <select value={value.status || ''} onChange={(e) => set({ status: e.target.value })}>
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {statusLabel(s)}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="field">
        <span className="field__label">Urgency</span>
        <select
          value={value.minUrgency || ''}
          onChange={(e) => set({ minUrgency: e.target.value })}
        >
          <option value="">Any urgency</option>
          <option value="3">3 and above</option>
          <option value="4">4 and above</option>
          <option value="5">5 — immediate risk</option>
        </select>
      </label>

      <label className="field">
        <span className="field__label">Search</span>
        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Original text, summary or place"
          aria-label="Search the original text, the English summary or the place"
        />
      </label>

      {working ? (
        <label className="check">
          <input
            type="checkbox"
            checked={!!value.unanswered}
            onChange={(e) => set({ unanswered: e.target.checked })}
          />
          Action required only
        </label>
      ) : null}

      <button
        type="button"
        className="btn btn--ghost btn--sm"
        style={{ marginBottom: 7 }}
        onClick={() =>
          onChange({
            // The tab survives Clear. It is which feed is being worked, not a
            // filter narrowing it — clearing filters and being thrown back to the
            // working queue would lose an officer's place mid-review.
            view: value.view,
            state: '',
            category: '',
            channel: '',
            language: '',
            status: '',
            minUrgency: '',
            q: '',
            unanswered: false,
            offset: 0,
          })
        }
      >
        Clear
      </button>
    </div>
  )
}
