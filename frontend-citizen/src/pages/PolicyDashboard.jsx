/**
 * `/dashboard` — where the demand data becomes a national picture.
 *
 * Map and table side by side, driven by one query and one selection. Two panels
 * over the same rows rather than two screens: the map answers "where is the
 * pressure", the table answers "how much, and against what coverage", and a
 * planner needs both in the same glance to believe either.
 */
import { useMemo, useState } from 'react'

import { getHotspots } from '../api.js'
import Filters from '../components/Filters.jsx'
import HotspotTable from '../components/HotspotTable.jsx'
import IndiaMap from '../components/IndiaMap.jsx'
import { Async } from '../components/States.jsx'
import { useApi } from '../hooks/useApi.js'
import { useCapabilities } from '../hooks/useCapabilities.jsx'
import { useStates } from '../hooks/useStates.js'
import { num, pct, sectorLabel } from '../lib/format.js'

export default function PolicyDashboard() {
  const caps = useCapabilities()
  const states = useStates()
  const [filters, setFilters] = useState({ state: '', category: '' })
  const [selected, setSelected] = useState(null)

  const query = useApi(
    () => getHotspots({ state: filters.state, category: filters.category, limit: 200 }),
    [filters.state, filters.category],
  )

  // Changing a filter can remove the selected cell from the result set. Deriving
  // the active selection instead of storing it keeps the map from flying to a
  // marker that is no longer drawn, without a state update during render.
  const rows = query.data ?? []
  const activeSelection = rows.some((r) => `${r.district_code}:${r.category}` === selected) ? selected : null

  const summary = useMemo(() => {
    if (!rows.length) return null
    const critical = rows.filter((r) => r.unmet_need_score >= 70).length
    const reports = rows.reduce((sum, r) => sum + r.request_count, 0)
    const worstCoverage = rows.reduce((min, r) => (r.coverage_pct < min.coverage_pct ? r : min), rows[0])
    return { critical, reports, districts: new Set(rows.map((r) => r.district_code)).size, worstCoverage }
  }, [rows])

  return (
    <>
      <div className="page-head">
        <div className="page-head__eyebrow">Government · Analysis</div>
        <h1>Where need is going unmet</h1>
        <p className="page-head__sub">
          Every district–sector pair, ranked by an unmet-need index that combines what citizens report with census
          demographics, infrastructure coverage and money already allocated. Adjusted so that quiet districts are not
          read as satisfied ones.
        </p>
      </div>

      <Filters
        states={states}
        categories={caps.data?.categories ?? []}
        value={filters}
        onChange={setFilters}
        resultCount={query.data?.length}
      />

      {summary ? (
        <div className="caps">
          <span className="pill pill--warn">
            {summary.critical} {summary.critical === 1 ? 'cell' : 'cells'} scoring 70+
          </span>
          <span className="pill">{summary.districts} districts</span>
          <span className="pill">{num(summary.reports)} citizen reports in view</span>
          <span className="pill">
            Lowest coverage: {summary.worstCoverage.district} · {sectorLabel(summary.worstCoverage.category)} ·{' '}
            {pct(summary.worstCoverage.coverage_pct)}
          </span>
        </div>
      ) : null}

      <Async
        {...query}
        loadingLabel="Scoring every district–sector pair…"
        isEmpty={(d) => d.length === 0}
        emptyTitle="No district–sector pairs match"
        emptyBody={
          filters.category
            ? `No citizen requests have been filed for ${sectorLabel(filters.category)}${
                filters.state ? ` in ${filters.state}` : ''
              } yet. The sector exists in the taxonomy but has no demand data behind it.`
            : 'The database has no scored cells. Run the seed script in backend/ to load the reference data.'
        }
      >
        {(data) => (
          <div className="dash">
            <div className="panel">
              <div className="panel__head">
                <div className="panel__title">National view</div>
                <div className="panel__note">OpenStreetMap · click a district</div>
              </div>
              <IndiaMap rows={data} selected={activeSelection} onSelect={setSelected} />
            </div>

            <div className="panel">
              <div className="panel__head">
                <div className="panel__title">Ranked cells</div>
                <div className="panel__note">Click a row to locate it</div>
              </div>
              <HotspotTable rows={data} selected={activeSelection} onSelect={setSelected} />
            </div>
          </div>
        )}
      </Async>
    </>
  )
}
