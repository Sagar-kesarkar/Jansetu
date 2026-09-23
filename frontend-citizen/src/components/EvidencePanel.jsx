/**
 * The evidence panel — the most important component in this application.
 *
 * Everything else here could be rebuilt in a weekend. This is the part that makes
 * the difference between a ranking a government could act on and a number on a
 * slide: it shows every input, the weight applied to each, and the arithmetic that
 * produced the total, so a planner can disagree with the *weighting* rather than
 * having to disbelieve the *system*.
 *
 * Three things it deliberately does that a JSON dump would not:
 *
 * 1. Shows the four contributions summing visibly to the score. The bar is a
 *    proportion of 100, so a 76 reads as "high but not maximal", which is the
 *    honest reading.
 * 2. Names demand as 35% of the total, next to the other 65%. That is the answer
 *    to "could a district brigade its way to the top", and it should be on screen
 *    before anyone has to ask.
 * 3. Gives the participation adjustment its inputs. "1.483x" alone is an
 *    unexplained multiplier; "1.483x, because literacy is 46% and internet
 *    penetration is 12%" is an argument.
 */
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import { DASH, inr, isMissing, num, pct, people } from '../lib/format.js'
import { COMPONENTS, contribution } from '../lib/score.js'

export default function EvidencePanel({ rec }) {
  const e = rec.evidence
  const weights = e.weights || {}

  const rows = COMPONENTS.map((c) => {
    const raw = e.component_scores?.[c.key] ?? 0
    const weight = weights[c.key] ?? 0
    return { ...c, raw, weight, points: contribution(raw, weight) }
  })

  const totalPoints = rows.reduce((sum, r) => sum + r.points, 0)
  const demandShare = (weights.demand ?? 0) * 100

  // recharts wants one object per bar group; this is a single stacked bar, so one
  // row with a key per segment plus the headroom left to 100.
  const chartData = [
    {
      name: 'score',
      ...Object.fromEntries(rows.map((r) => [r.key, Number(r.points.toFixed(2))])),
      headroom: Math.max(0, 100 - totalPoints),
    },
  ]

  return (
    <div className="ev">
      <p className="ev__lead">
        Every figure below is computed by deterministic Python from citizen reports, census demographics, the
        infrastructure coverage index and published allocations. No language model produces any number on this panel —
        Gemini only structures the incoming reports and, if asked, narrates what is already here.
      </p>

      {/* ---- composition ---- */}
      <section className="ev__section">
        <h4 className="ev__h">How the score of {num(rec.unmet_need_score, 2)} is composed</h4>

        <div style={{ width: '100%', height: 62 }}>
          <ResponsiveContainer>
            <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 4, bottom: 0, left: 4 }}>
              <XAxis
                type="number"
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tick={{ fontSize: 11, fill: '#6f7684' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis type="category" dataKey="name" hide />
              {rows.map((r, i) => (
                <Bar
                  key={r.key}
                  dataKey={r.key}
                  stackId="s"
                  fill={r.color}
                  radius={i === 0 ? [4, 0, 0, 4] : 0}
                  isAnimationActive={false}
                />
              ))}
              {/* The unfilled remainder to 100. Without it the bar always looks
                  full and every district looks like a maximum-need district. */}
              <Bar dataKey="headroom" stackId="s" fill="#ece8e0" radius={[0, 4, 4, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="comp" style={{ marginTop: 14 }}>
          {rows.map((r) => (
            <div className="comp__row" key={r.key}>
              <div className="comp__name">
                <span style={{ color: r.color, fontWeight: 700 }}>■</span> {r.label}
                <div className="comp__weight">weight {num(r.weight * 100, 0)}%</div>
              </div>
              <div className="comp__track" title={r.what}>
                <div className="comp__fill" style={{ width: `${Math.min(100, r.raw * 100)}%`, background: r.color }} />
              </div>
              <div className="comp__nums">
                {num(r.raw, 3)} × {num(r.weight, 2)} = <span className="comp__contrib">{num(r.points, 2)}</span>
              </div>
            </div>
          ))}

          <div className="comp__total">
            <span>Sum of weighted components</span>
            <span className="comp__total-v">{num(totalPoints, 2)}</span>
          </div>
        </div>

        {/* The gaming answer, stated before it is asked. */}
        <p className="ev__formula" style={{ whiteSpace: 'normal' }}>
          Citizen demand is {num(demandShare, 0)}% of the score. The remaining {num(100 - demandShare, 0)}% comes from
          official coverage, deprivation and allocation data, which a co-ordinated complaint drive cannot move — so
          volume alone cannot buy a district a top ranking.
        </p>

        <details>
          <summary style={{ fontSize: 12.5, color: 'var(--ink-3)', cursor: 'pointer', marginTop: 10 }}>
            What each component measures
          </summary>
          <dl style={{ margin: '10px 0 0', fontSize: 12.5, color: 'var(--ink-2)' }}>
            {rows.map((r) => (
              <div key={r.key} style={{ marginBottom: 8 }}>
                <dt style={{ fontWeight: 600, color: r.color }}>{r.label}</dt>
                <dd style={{ margin: 0, lineHeight: 1.55 }}>{r.what}</dd>
              </div>
            ))}
          </dl>
        </details>
      </section>

      {/* ---- participation adjustment ---- */}
      <section className="ev__section">
        <h4 className="ev__h">Reporting-bias correction</h4>
        <div className="ev__participation">
          <div className="ev__participation-x">{num(e.participation_adjustment, 3)}×</div>
          <div className="ev__participation-say">{participationSentence(e)}</div>
        </div>
        <div className="ev__formula">
          adjustment = mean(0.5·literacy + 0.5·internet) ÷ max(0.5·literacy + 0.5·internet, 0.15), capped at 2.5×
        </div>
        <div className="ev__metrics" style={{ marginTop: 12 }}>
          <Metric k="Literacy" v={pct(e.literacy_pct)} sub="Census, district level" />
          <Metric k="Internet penetration" v={pct(e.internet_pct)} sub="Share of households" />
        </div>
      </section>

      {/* ---- citizen signal ---- */}
      <section className="ev__section">
        <h4 className="ev__h">What citizens reported</h4>
        <div className="ev__metrics">
          <Metric k="Reports filed" v={num(e.citizen_requests)} sub="In this sector, this district" />
          <Metric
            k="Urgency-weighted demand"
            v={num(e.weighted_demand, 1)}
            sub="Routine 0.5× → immediate risk 2.5×"
          />
          <Metric
            k="Per 100,000 people"
            v={
              isMissing(e.population) || !e.population
                ? DASH
                : num((e.weighted_demand / e.population) * 100_000, 2)
            }
            sub="Before the correction above"
          />
        </div>
      </section>

      {/* ---- official data ---- */}
      <section className="ev__section">
        <h4 className="ev__h">What the official data shows</h4>
        <div className="ev__metrics">
          <Metric k="Coverage" v={pct(e.coverage_pct)} sub="Infrastructure index" />
          <Metric k="Still unserved" v={pct(e.coverage_gap_pct)} sub="Drives the coverage-gap component" />
          <Metric
            k="Allocated per person"
            v={isMissing(e.allocation_per_capita) ? DASH : `${inr(e.allocation_per_capita, 2)}`}
            sub="Existing sanctioned plans"
          />
          <Metric
            k="Deprivation index"
            v={num(e.deprivation_index, 2)}
            sub="0 best · 1 worst"
          />
          <Metric k="Population" v={num(e.population)} sub={people(e.population) + ' people'} />
          <Metric
            k="People a project would reach"
            v={people(rec.est_beneficiaries)}
            sub="Population × coverage gap"
          />
        </div>
      </section>

      {/* ---- provenance ---- */}
      <section className="ev__section">
        <h4 className="ev__h">Scheme alignment</h4>
        <div className="ev__metrics">
          <Metric k="Central scheme" v={rec.linked_scheme} sub="Where this project would be funded from" />
          <Metric k="District code" v={rec.district_code} sub="LGD directory key" />
        </div>
      </section>
    </div>
  )
}

function Metric({ k, v, sub }) {
  return (
    <div className="ev__metric">
      <div className="ev__metric-k">{k}</div>
      <div className="ev__metric-v">{v}</div>
      {sub ? <div className="ev__metric-sub">{sub}</div> : null}
    </div>
  )
}

/**
 * The sentence that carries the whole pitch, built from this district's own
 * figures rather than a stock phrase — and worded honestly in all three
 * directions, because a correction that only ever scales up is not a correction.
 */
function participationSentence(e) {
  const adj = e.participation_adjustment
  const reports = e.citizen_requests
  const net = isMissing(e.internet_pct) ? null : pct(e.internet_pct, 0)
  const lit = isMissing(e.literacy_pct) ? null : pct(e.literacy_pct, 0)

  if (adj > 1.05) {
    return (
      <>
        Reported demand was scaled <strong>up</strong>. {net ? `At ${net} internet penetration` : 'With low connectivity'}
        {lit ? ` and ${lit} literacy` : ''}, these {num(reports)} report{reports === 1 ? '' : 's'} represent far more
        unmet need than {num(reports)} from a well-connected district — the people who cannot file are not the people
        who do not need.
      </>
    )
  }
  if (adj < 0.95) {
    return (
      <>
        Reported demand was scaled <strong>down</strong>.{' '}
        {net ? `With ${net} internet penetration${lit ? ` and ${lit} literacy` : ''}, this` : 'This'} district reports
        more easily than the average one in view, so raw volume here overstates need relative to its peers.
      </>
    )
  }
  return (
    <>
      No correction applied. {lit && net ? `Literacy (${lit}) and internet penetration (${net})` : 'This district'} sit
      close to the average across the districts in view, so the reports are taken at face value.
    </>
  )
}
