/**
 * `/recommendations` — the output the whole pipeline exists to produce.
 *
 * A ranked list of projects, each one traceable to its inputs. This is the last
 * screen in the demo and the one a judge will interrogate, so the ordering is the
 * API's and nothing here re-sorts, re-scales or re-labels it.
 */
import { useState } from 'react'

import { getRecommendations } from '../api.js'
import Filters from '../components/Filters.jsx'
import PriorityCard from '../components/PriorityCard.jsx'
import { Async } from '../components/States.jsx'
import { useApi } from '../hooks/useApi.js'
import { useCapabilities } from '../hooks/useCapabilities.jsx'
import { useStates } from '../hooks/useStates.js'
import { sectorLabel } from '../lib/format.js'

export default function Recommendations() {
  const caps = useCapabilities()
  const states = useStates()
  const [filters, setFilters] = useState({ state: '', category: '' })

  const query = useApi(
    () => getRecommendations({ state: filters.state, category: filters.category, limit: 12 }),
    [filters.state, filters.category],
  )

  const geminiOn = Boolean(caps.data?.google_ai?.enabled)

  return (
    <>
      <div className="page-head">
        <div className="page-head__eyebrow">Government · Recommendations</div>
        <h1>What to fund next</h1>
        <p className="page-head__sub">
          Ranked projects, each mapped to the central scheme that would fund it. Open the evidence on any card to see
          every input, the weight applied to it, and the arithmetic that produced the score.
        </p>
      </div>

      <Filters
        states={states}
        categories={caps.data?.categories ?? []}
        value={filters}
        onChange={setFilters}
        resultCount={query.data?.length}
      />

      <Async
        {...query}
        loadingLabel="Ranking district–sector pairs…"
        isEmpty={(d) => d.length === 0}
        emptyTitle="No recommendations for this filter"
        emptyBody={
          filters.category
            ? `Nothing has been reported for ${sectorLabel(filters.category)}${
                filters.state ? ` in ${filters.state}` : ''
              }, so there is no demand signal to rank. Clear the sector filter to see the national list.`
            : 'No scored cells exist. Run the seed script in backend/ to load reference and demand data.'
        }
      >
        {(data) => (
          <div className="reclist">
            {data.map((rec) => (
              <PriorityCard
                key={`${rec.district_code}:${rec.category}`}
                rec={rec}
                filters={filters}
                geminiOn={geminiOn}
              />
            ))}
          </div>
        )}
      </Async>
    </>
  )
}
