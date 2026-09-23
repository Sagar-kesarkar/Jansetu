/**
 * One ranked recommendation, collapsed to a headline and expandable to its proof.
 *
 * The card leads with what to build and who it reaches, because that is the unit a
 * planning official works in — not a score. The score is present and large, but
 * the reason it is trustworthy is one click away rather than on the surface.
 *
 * The Gemini brief is a button, never automatic. `with_brief=true` on the list
 * endpoint costs one model call per row, which on the free AI Studio tier would
 * exhaust the quota partway through a demo and leave the last cards blank.
 */
import { useState } from 'react'

import { getBrief } from '../api.js'
import { num, people, sectorLabel } from '../lib/format.js'
import { scoreColor, scoreLabel, scoreText } from '../lib/score.js'
import EvidencePanel from './EvidencePanel.jsx'
import { ErrorState } from './States.jsx'

export default function PriorityCard({ rec, filters, geminiOn }) {
  const [open, setOpen] = useState(false)
  const [brief, setBrief] = useState(rec.brief_md ?? null)
  const [briefing, setBriefing] = useState(false)
  const [briefError, setBriefError] = useState(null)

  async function generateBrief() {
    setBriefing(true)
    setBriefError(null)
    try {
      // Filters are passed through because scores are normalised across the
      // queried set. Fetching without them returns the same district carrying a
      // different score than the card the button sits on, and a number that
      // changes when you ask for an explanation destroys the point of the panel.
      const fresh = await getBrief({
        districtCode: rec.district_code,
        sector: rec.category,
        state: filters.state,
        category: filters.category,
      })
      setBrief(fresh.brief_md || 'Gemini returned an empty brief. The evidence below is unaffected.')
    } catch (err) {
      setBriefError(err)
    } finally {
      setBriefing(false)
    }
  }

  const color = scoreColor(rec.unmet_need_score)

  return (
    <article className={`rec${open ? ' rec--open' : ''}`}>
      <div className="rec__top">
        <div className="rec__rank" style={{ background: color, color: scoreText(rec.unmet_need_score) }}>
          {rec.rank}
        </div>

        <div className="rec__body">
          <h3 className="rec__title">{rec.project_title}</h3>
          <div className="rec__where">
            {rec.district}, {rec.state} · {sectorLabel(rec.category)}
          </div>
          <div className="rec__tags">
            <span className="pill">{rec.linked_scheme}</span>
            <span className="pill">{people(rec.est_beneficiaries)} people reached</span>
            {rec.evidence.participation_adjustment > 1.05 ? (
              <span className="pill pill--warn">
                Under-reported · {num(rec.evidence.participation_adjustment, 2)}× correction
              </span>
            ) : null}
          </div>
        </div>

        <div className="rec__score">
          <div className="rec__score-num" style={{ color }}>
            {num(rec.unmet_need_score, 1)}
          </div>
          <div className="rec__score-lbl">{scoreLabel(rec.unmet_need_score)}</div>
        </div>
      </div>

      {/* Assembled deterministically in analytics/explain.py, so it is present and
          true whether or not a Gemini key exists. */}
      <p className="rec__rationale">{rec.rationale}</p>

      <div className="rec__actions">
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? 'Hide evidence' : 'Show the evidence'}
        </button>

        {geminiOn && !brief ? (
          <button type="button" className="btn btn--sm" onClick={generateBrief} disabled={briefing}>
            {briefing ? 'Writing…' : 'Generate policy brief'}
          </button>
        ) : null}

        {!geminiOn ? (
          <span className="pill" title="Set GEMINI_API_KEY to enable narrated briefs">
            Briefs need a Gemini key
          </span>
        ) : null}
      </div>

      {open ? <EvidencePanel rec={rec} /> : null}

      {briefError ? <ErrorState error={briefError} onRetry={generateBrief} /> : null}

      {brief ? (
        <div className="brief">
          <div className="brief__meta">
            <span>Policy brief</span>
            <span className="pill">Written by Gemini</span>
          </div>
          <div className="brief__body">
            {/* Paragraph splitting rather than a markdown renderer: the prompt asks
                for three plain paragraphs and no headings, so a parser would be a
                dependency earning nothing. */}
            {brief
              .split(/\n{2,}/)
              .map((para) => para.trim())
              .filter(Boolean)
              .map((para, i) => (
                <p key={i}>{para}</p>
              ))}
          </div>
          <p className="brief__caveat">
            Gemini was given only the computed evidence above — no database access and no citizen text. Every figure in
            this brief traces back to a number on this card; the model chose the wording, not the ranking.
          </p>
        </div>
      ) : null}
    </article>
  )
}
