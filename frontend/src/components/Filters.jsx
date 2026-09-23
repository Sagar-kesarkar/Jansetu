/**
 * State and sector filters, shared by both policy pages.
 *
 * The note about renormalisation is not decoration. Scores are min-maxed across
 * the queried set, so filtering to one state re-ranks its districts against each
 * other and the numbers legitimately change. A planner who is not told that will
 * read it as a bug — or worse, screenshot two views and think one of them lied.
 */
import { sectorLabel } from '../lib/format.js'

export default function Filters({ states, categories, value, onChange, resultCount }) {
  const set = (patch) => onChange({ ...value, ...patch })

  return (
    <div className="filters">
      <label className="field">
        <span className="field__label">State</span>
        <select className="select" value={value.state} onChange={(e) => set({ state: e.target.value })}>
          <option value="">All India</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Sector</span>
        <select className="select" value={value.category} onChange={(e) => set({ category: e.target.value })}>
          <option value="">All sectors</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {sectorLabel(c)}
            </option>
          ))}
        </select>
      </label>

      {value.state || value.category ? (
        <button type="button" className="btn btn--ghost btn--sm" style={{ marginBottom: 1 }} onClick={() => onChange({ state: '', category: '' })}>
          Clear
        </button>
      ) : null}

      <div className="filters__count">
        {resultCount == null ? null : (
          <>
            <strong>{resultCount}</strong> {resultCount === 1 ? 'cell' : 'cells'}
            {value.state ? ' · ranked within state' : ' · ranked nationally'}
          </>
        )}
      </div>
    </div>
  )
}
