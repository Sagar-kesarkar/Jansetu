/**
 * The national view. Leaflet with OpenStreetMap tiles — free, attributed, and
 * requiring no key or billing account, which is the whole reason the Google Maps
 * JS API is absent from this project.
 *
 * Circle markers at district centroids rather than a choropleth. Two reasons: a
 * district-boundary GeoJSON for India is a 20 MB asset that would dominate the
 * bundle and the load time, and the unit of analysis here is (district × sector),
 * so a district can legitimately appear twice with different scores. A polygon
 * cannot express that; a marker can, and radius encodes magnitude for free.
 */
import { useEffect } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'

import { inr, num, pct, sectorLabel } from '../lib/format.js'
import { BANDS, scoreColor, scoreLabel, scoreRadius } from '../lib/score.js'

/** Roughly the geographic centre of India at a zoom that fits Kashmir to Kanyakumari. */
const CENTRE = [22.5, 79]
const ZOOM = 5

/**
 * Selecting a row in the table moves the map to it.
 *
 * Without this the two panels are two lists that happen to share a colour scale.
 * With it, clicking "Nabarangpur" in the table answers "where is that?" — which is
 * the question a planner who has never been to Odisha actually has.
 */
function FlyTo({ position }) {
  const map = useMap()
  useEffect(() => {
    if (position) map.flyTo(position, Math.max(map.getZoom(), 6), { duration: 0.6 })
  }, [position?.[0], position?.[1]]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export default function IndiaMap({ rows, selected, onSelect }) {
  const focus = rows.find((r) => `${r.district_code}:${r.category}` === selected)

  return (
    <>
      <div className="map">
        <MapContainer center={CENTRE} zoom={ZOOM} scrollWheelZoom minZoom={4} maxZoom={9}>
          <FlyTo position={focus ? [focus.latitude, focus.longitude] : null} />
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            // Attribution is a licence condition of the ODbL tiles, not a nicety.
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />

          {rows.map((row) => {
            const key = `${row.district_code}:${row.category}`
            const isSelected = selected === key
            return (
              <CircleMarker
                key={key}
                center={[row.latitude, row.longitude]}
                radius={scoreRadius(row.unmet_need_score)}
                pathOptions={{
                  color: isSelected ? '#16181d' : '#ffffff',
                  weight: isSelected ? 2.5 : 1,
                  fillColor: scoreColor(row.unmet_need_score),
                  fillOpacity: 0.85,
                }}
                eventHandlers={{ click: () => onSelect?.(key) }}
              >
                {/* Hover gives the name without a click, so scanning the map for a
                    district does not require opening 24 popups. */}
                <Tooltip direction="top" offset={[0, -4]}>
                  {row.district} · {num(row.unmet_need_score, 1)}
                </Tooltip>

                <Popup>
                  <div className="mappop__name">{row.district}</div>
                  <div className="mappop__state">
                    {row.state} · {sectorLabel(row.category)}
                  </div>
                  <dl style={{ margin: 0 }}>
                    <Row k="Unmet need" v={`${num(row.unmet_need_score, 1)} · ${scoreLabel(row.unmet_need_score)}`} />
                    <Row k="Citizen reports" v={num(row.request_count)} />
                    <Row k="Coverage" v={pct(row.coverage_pct)} />
                    <Row k="Allocated" v={`${inr(row.allocation_per_capita, 2)}/person`} />
                    <Row k="Population" v={num(row.population)} />
                  </dl>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>

      <div className="legend">
        {BANDS.map((b) => (
          <span className="legend__item" key={b.label}>
            <span className="legend__swatch" style={{ background: b.color }} />
            {b.label}
            {b.min > -Infinity ? ` ${b.min}+` : ''}
          </span>
        ))}
        <span className="legend__item" style={{ marginLeft: 'auto', color: 'var(--ink-3)' }}>
          Size and colour both encode unmet need
        </span>
      </div>
    </>
  )
}

function Row({ k, v }) {
  return (
    <div className="mappop__row">
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  )
}
