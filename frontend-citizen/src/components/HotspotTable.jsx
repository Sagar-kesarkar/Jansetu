/**
 * The same rows as the map, sortable and readable.
 *
 * The map answers "where"; this answers "by how much, and on what basis". Both
 * are on screen at once because a planner asked to defend a ranking needs the
 * number, not a coloured dot — and the two are the same query, so they cannot
 * disagree.
 *
 * Default sort is the API's own `rank`, which is the unmet-need ordering. Clicking
 * a column re-sorts client-side; it does not re-query, because re-querying would
 * renormalise the scores and change the values the user was just reading.
 */
import { useMemo, useState } from 'react'

import { inr, num, pct, sectorLabel } from '../lib/format.js'
import { scoreColor, scoreLabel, scoreText } from '../lib/score.js'

const COLUMNS = [
  { key: 'rank', label: '#', numeric: true, width: 46 },
  { key: 'district', label: 'District', numeric: false },
  { key: 'category', label: 'Sector', numeric: false },
  { key: 'unmet_need_score', label: 'Unmet need', numeric: true },
  { key: 'request_count', label: 'Reports', numeric: true },
  { key: 'coverage_pct', label: 'Coverage', numeric: true },
  { key: 'allocation_per_capita', label: '₹ / person', numeric: true },
]

export default function HotspotTable({ rows, selected, onSelect }) {
  const [sort, setSort] = useState({ key: 'rank', dir: 'asc' })

  const sorted = useMemo(() => {
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const x = a[sort.key]
      const y = b[sort.key]
      // Nulls sort last in both directions. A district with no allocation data is
      // not the cheapest district in the country, and letting null read as 0 would
      // put it at the top of "₹ / person" ascending and imply exactly that.
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      if (typeof x === 'string') return x.localeCompare(y) * dir
      return (x - y) * dir
    })
  }, [rows, sort])

  function toggle(key) {
    setSort((cur) =>
      cur.key === key
        ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' }
        : // A first click on a measure should show the worst cases, which for every
          // numeric column here except rank means descending.
          { key, dir: key === 'rank' || key === 'district' || key === 'category' ? 'asc' : 'desc' },
    )
  }

  return (
    <div className="tablewrap">
      <table className="dtable">
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={col.numeric ? 'th--num' : undefined}
                style={col.width ? { width: col.width } : undefined}
                aria-sort={sort.key === col.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button type="button" onClick={() => toggle(col.key)}>
                  {col.label}
                  <span className="sortcue" aria-hidden="true">
                    {sort.key === col.key ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = `${row.district_code}:${row.category}`
            return (
              <tr
                key={key}
                aria-selected={selected === key}
                onClick={() => onSelect?.(key)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect?.(key)
                  }
                }}
              >
                <td className="td--num">{row.rank}</td>
                <td>
                  <div className="dtable__district">{row.district}</div>
                  <div className="dtable__state">{row.state}</div>
                </td>
                <td>{sectorLabel(row.category)}</td>
                <td className="td--num">
                  <span
                    className="pill pill--score"
                    style={{
                      background: scoreColor(row.unmet_need_score),
                      color: scoreText(row.unmet_need_score),
                    }}
                    title={scoreLabel(row.unmet_need_score)}
                  >
                    {num(row.unmet_need_score, 1)}
                  </span>
                </td>
                <td className="td--num">{num(row.request_count)}</td>
                <td className="td--num">{pct(row.coverage_pct)}</td>
                <td className="td--num">{inr(row.allocation_per_capita, 2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
