/**
 * The one place a score becomes a colour or a size.
 *
 * The map, the table and the cards all read from here so a district that looks
 * critical on the map cannot look moderate in the table two inches away.
 */

/**
 * Teal → amber → crimson rather than green → red. Roughly 1 in 12 men has a
 * red-green deficiency, and this is the screen a policymaker makes a funding
 * decision on; the lightness also increases monotonically with need, so the
 * ramp still reads correctly in greyscale or on a projector.
 *
 * Thresholds are absolute on the 0–100 score, not percentiles of the current
 * view. If they were relative, filtering to one state would recolour every
 * district and imply a crisis that the filter itself invented.
 */
export const BANDS = [
  { min: 70, label: 'Critical', color: '#A8202F', text: '#fff' },
  { min: 55, label: 'High', color: '#DD7230', text: '#fff' },
  { min: 40, label: 'Elevated', color: '#E8B84B', text: '#3A2A05' },
  { min: 25, label: 'Moderate', color: '#6FB3A8', text: '#0A2E2B' },
  { min: -Infinity, label: 'Adequate', color: '#2A7F86', text: '#fff' },
]

export function band(score) {
  return BANDS.find((b) => score >= b.min) ?? BANDS[BANDS.length - 1]
}

export const scoreColor = (score) => band(score).color
export const scoreLabel = (score) => band(score).label
export const scoreText = (score) => band(score).text

/**
 * Radius in pixels, not in metres: at zoom 5 a metre-based radius makes
 * Rajasthan's marker swallow four neighbours. The floor of 7px keeps a
 * low-need district clickable rather than a dot nobody can hit on a laptop
 * trackpad.
 */
export function scoreRadius(score) {
  const clamped = Math.max(0, Math.min(100, score))
  return 7 + (clamped / 100) * 17
}

/**
 * The four components of the index, in the order they appear in the formula.
 *
 * `what` is shown in the evidence panel, not tucked in a tooltip. A planner
 * asked to defend "deprivation: 1.00" needs to know it is a normalised rank
 * against the districts currently in view, not an absolute statement that the
 * district is the worst in India — those are very different claims, and the
 * second one is not true.
 *
 * Order and keys match `analytics/priority.py::DEFAULT_WEIGHTS`. Weights are not
 * duplicated here: they arrive in every API response, so the screen shows the
 * weights that were actually applied rather than the ones we expected.
 */
export const COMPONENTS = [
  {
    key: 'demand',
    label: 'Citizen demand',
    color: '#C75B12',
    what: 'Urgency-weighted reports per 100,000 people, scaled by the participation adjustment, then normalised across the districts in view.',
  },
  {
    key: 'coverage_gap',
    label: 'Coverage gap',
    color: '#1B4B5A',
    what: 'The share of the district the official infrastructure index says is still unserved. Not normalised — it is already a percentage.',
  },
  {
    key: 'deprivation',
    label: 'Deprivation',
    color: '#6B4C9A',
    what: 'An SDG-style composite of how badly off the district is overall, normalised across the districts in view.',
  },
  {
    key: 'underfunding',
    label: 'Underfunding',
    color: '#14684A',
    what: 'How little is already allocated here per person, inverted — so a district that has already been funded scores low and does not get funded twice.',
  },
]

/** Points this component contributes to the 0–100 score: weight × component × 100. */
export const contribution = (componentScore, weight) => componentScore * weight * 100
