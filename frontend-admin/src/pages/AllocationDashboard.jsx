/**
 * AllocationDashboard.jsx — Priority & Public Funds Dashboard (Officials Console)
 *
 * Provides government officials and planners with transparent, authoritative fiscal intelligence:
 * - Direct connection to shared domain service (/api/v1/funds/...)
 * - Anti-double-counting stage precedence (BE/RE/RELEASE/ACTUAL)
 * - Real anomaly detection (spent > released warning)
 * - State and district funding overviews & proportional fund flow
 * - Citizen grievance demand vs. government expenditure comparison
 * - Decision-support funding signals & Sector Priority Register
 * - Authenticated data sync & review audit panel
 * - CSV export of filtered data
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

import {
  approveAdminFundsImport,
  getAdminFundsImports,
  getFundsCoverage,
  getFundsDistricts,
  getFundsOverview,
  getFundsSectors,
  getStates,
  rejectAdminFundsImport,
  triggerAdminFundsSync,
} from '../api.js'

export function AllocationDashboard({ session }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  // URL-synchronized filters
  const selectedState = searchParams.get('state') || session?.state || 'Maharashtra'
  const selectedDistrict = searchParams.get('district') || ''
  const selectedYear = searchParams.get('year') || '2026–27'
  const selectedSector = searchParams.get('sector') || 'ALL'
  const scope = searchParams.get('scope') || 'state'

  const [statesList, setStatesList] = useState(['Maharashtra', 'Tamil Nadu'])
  const [coverage, setCoverage] = useState({
    covered_states: [],
    covered_districts: [],
    covered_district_codes: [],
  })

  // Financial Data State
  const [overview, setOverview] = useState(null)
  const [districtsData, setDistrictsData] = useState([])
  const [sectorsData, setSectorsData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshStamp, setRefreshStamp] = useState(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }))

  // Admin Review State
  const [showReviewPanel, setShowReviewPanel] = useState(false)
  const [importRuns, setImportRuns] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState(null)
  const [reviewNotes, setReviewNotes] = useState('')

  // Load vocabulary and verified coverage
  useEffect(() => {
    getStates()
      .then((res) => res && res.length > 0 && setStatesList(res))
      .catch(() => {})

    getFundsCoverage()
      .then((cov) => cov && setCoverage(cov))
      .catch(() => {})
  }, [])

  // Update query params helper
  function updateParams(newParams) {
    const updated = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(newParams)) {
      if (v === null || v === undefined || v === '') {
        updated.delete(k)
      } else {
        updated.set(k, v)
      }
    }
    setSearchParams(updated)
  }

  // Load core financial datasets
  const loadData = () => {
    setLoading(true)
    setError(null)

    const fiscalYearParam = selectedYear.replace('–', '-')

    const pOverview = getFundsOverview({
      scope,
      state: selectedState,
      district: scope === 'district' ? selectedDistrict : undefined,
      fiscalYear: fiscalYearParam,
      category: selectedSector !== 'ALL' ? selectedSector : undefined,
    })

    const pDistricts = getFundsDistricts({
      state: selectedState,
      fiscalYear: fiscalYearParam,
      category: selectedSector !== 'ALL' ? selectedSector : undefined,
    })

    const pSectors = getFundsSectors({
      scope,
      state: selectedState,
      district: scope === 'district' ? selectedDistrict : undefined,
      fiscalYear: fiscalYearParam,
    })

    Promise.all([pOverview, pDistricts, pSectors])
      .then(([ov, dists, secs]) => {
        setOverview(ov)
        setDistrictsData(dists || [])
        setSectorsData(secs || [])
        setLoading(false)
        setRefreshStamp(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }))
      })
      .catch((err) => {
        setError(err.message || 'Failed to load public funds data')
        setLoading(false)
      })
  }

  useEffect(() => {
    loadData()
  }, [selectedState, selectedDistrict, selectedYear, selectedSector, scope])

  // Load admin import history
  const loadImportRuns = () => {
    getAdminFundsImports()
      .then((runs) => setImportRuns(runs || []))
      .catch(() => {})
  }

  useEffect(() => {
    if (showReviewPanel) {
      loadImportRuns()
    }
  }, [showReviewPanel])

  // Sync state budget trigger
  const handleSync = async (adapterKey = 'maharashtra_finance') => {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res = await triggerAdminFundsSync(adapterKey)
      setSyncMsg(`Sync complete! (${res.records_approved || res.records_parsed} records ingested)`)
      loadData()
      loadImportRuns()
    } catch (err) {
      setSyncMsg(`Sync failed: ${err.message}`)
    } finally {
      setSyncing(false)
    }
  }

  // Bulk Approve Import Run
  const handleApproveRun = async (runId) => {
    try {
      await approveAdminFundsImport(runId, reviewNotes || 'Approved by desk officer')
      setSyncMsg(`Import #${runId} approved successfully.`)
      loadData()
      loadImportRuns()
    } catch (err) {
      setSyncMsg(`Approval failed: ${err.message}`)
    }
  }

  // Bulk Reject Import Run
  const handleRejectRun = async (runId) => {
    try {
      await rejectAdminFundsImport(runId, reviewNotes || 'Rejected by desk officer')
      setSyncMsg(`Import #${runId} rejected.`)
      loadData()
      loadImportRuns()
    } catch (err) {
      setSyncMsg(`Rejection failed: ${err.message}`)
    }
  }

  // CSV Export
  const exportCsv = () => {
    if (!sectorsData || sectorsData.length === 0) return
    const headers = ['Sector', 'Active Need Share (%)', 'Active Grievances', 'Allocated (Cr)', 'Released (Cr)', 'Spent (Cr)', 'Utilisation (%)', 'Assessment']
    const rows = sectorsData.map((s) => [
      `"${s.label}"`,
      s.grievance_share_pct,
      s.active_grievances,
      s.allocated,
      s.released,
      s.spent,
      s.utilisation_rate,
      `"${s.assessment}"`,
    ])
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `JanSetu-Fiscal-Summary-${selectedState}-${selectedYear}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  // Derived Decision Support Signals
  const fundingSignals = useMemo(() => {
    if (!sectorsData || sectorsData.length === 0) return []
    const signals = []

    for (const s of sectorsData) {
      if (s.need_gap > 8.0) {
        signals.push({
          kind: 'critical',
          title: `${s.label} appears under-weighted`,
          text: `${s.grievance_share_pct}% of active grievance volume relates to ${s.label.toLowerCase()}, while it receives ${s.allocation_share_pct}% of current budget allocation.`,
        })
      } else if (s.need_gap < -6.0) {
        signals.push({
          kind: 'warning',
          title: `${s.label} spending is moving fastest`,
          text: `${s.utilisation_rate}% of released ${s.label.toLowerCase()} funds are recorded as spent. Verify completion evidence before next release.`,
        })
      } else if (s.allocated > 0 && Math.abs(s.need_gap) <= 5.0) {
        signals.push({
          kind: 'good',
          title: `${s.label} utilisation is on track`,
          text: `${s.utilisation_rate}% of released funds are spent, broadly aligned with recorded citizen grievance demand (${s.grievance_share_pct}%).`,
        })
      }
    }

    if (signals.length === 0) {
      signals.push({
        kind: 'good',
        title: 'Allocations broadly aligned',
        text: 'All civic sectors have balanced allocations against recorded citizen grievances.',
      })
    }
    return signals
  }, [sectorsData])

  // Donut chart datasets
  const grievanceDonutData = useMemo(() => {
    return sectorsData
      .filter((s) => s.active_grievances > 0)
      .map((s) => ({
        name: s.label,
        value: s.active_grievances,
        color: s.color,
      }))
  }, [sectorsData])

  const expenditureDonutData = useMemo(() => {
    return sectorsData
      .filter((s) => s.spent > 0)
      .map((s) => ({
        name: s.label,
        value: s.spent,
        color: s.color,
      }))
  }, [sectorsData])

  const maxDistrictAlloc = useMemo(() => {
    if (!districtsData || districtsData.length === 0) return 1
    return Math.max(...districtsData.map((d) => d.allocated || 1), 1)
  }, [districtsData])

  return (
    <>
      {/* Page Header */}
      <div className="page-head">
        <div>
          <p className="eyebrow">Strategic fund allocation & needs assessment</p>
          <h1>Priority & public funds</h1>
          <p>
            Compare what citizens are reporting with what has been allocated, released and spent—without changing the independent grievance ranking.
          </p>
        </div>

        <div className="page-head__actions">
          <button type="button" className="btn btn--ghost" onClick={loadData} title="Refresh without blanking screen">
            ↻ Refresh
          </button>
          <button type="button" className="btn btn--ghost" onClick={exportCsv} title="Download CSV summary">
            ⬇ Export summary
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => handleSync('maharashtra_finance')}
            disabled={syncing}
          >
            {syncing ? 'Syncing...' : '↻ Sync State Budget'}
          </button>
          <button
            type="button"
            className={`btn ${showReviewPanel ? 'btn--accent' : 'btn--ghost'}`}
            onClick={() => setShowReviewPanel(!showReviewPanel)}
          >
            🛡 Audit & Ingestion ({importRuns.length || '•'})
          </button>
        </div>
      </div>

      {syncMsg ? (
        <div className="notice notice--ok" style={{ marginBottom: '14px' }}>
          {syncMsg}
        </div>
      ) : null}

      {/* Authenticated Admin Review Panel */}
      {showReviewPanel ? (
        <section className="panel" style={{ marginBottom: '18px', borderLeft: '4px solid var(--accent)' }}>
          <div className="panel__head">
            <div>
              <p className="eyebrow">Administrative Data Governance</p>
              <h2>Official Financial Source Ingestion & Review</h2>
            </div>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setShowReviewPanel(false)}>
              Close Panel
            </button>
          </div>
          <div className="panel__body">
            <p style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '14px' }}>
              Financial records ingested from allowlisted government portals (<code>*.gov.in</code>) remain in{' '}
              <code>PENDING_REVIEW</code> until validated and approved by an authorized desk officer.
            </p>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => handleSync('maharashtra_finance')}
                disabled={syncing}
              >
                Sync Maharashtra Finance Dept
              </button>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => handleSync('data_gov_in')}
                disabled={syncing}
              >
                Sync Open Government Data (data.gov.in)
              </button>
              <button
                type="button"
                className="btn btn--sm btn--ghost"
                onClick={() => handleSync('egramswaraj')}
                disabled={syncing}
              >
                Sync eGramSwaraj
              </button>
            </div>

            <div className="table-wrap">
              <table style={{ fontSize: '12.5px' }}>
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Source Publisher</th>
                    <th>Fiscal Year</th>
                    <th>Parsed</th>
                    <th>Approved</th>
                    <th>Status</th>
                    <th>SHA-256 Checksum</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {importRuns.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '16px', color: 'var(--ink-3)' }}>
                        No import runs recorded yet. Click a sync button above to trigger an authoritative ingestion.
                      </td>
                    </tr>
                  ) : (
                    importRuns.map((r) => (
                      <tr key={r.id}>
                        <td><strong>#{r.id}</strong></td>
                        <td>{r.source_name || 'Government Data Portal'}</td>
                        <td>{r.fiscal_year}</td>
                        <td>{r.records_parsed}</td>
                        <td>{r.records_approved}</td>
                        <td>
                          <span
                            className={`tag ${
                              r.status === 'APPROVED' || r.status === 'SUCCESS'
                                ? 'tag--blue'
                                : r.status === 'PENDING_REVIEW'
                                ? 'status--NEW'
                                : 'tag--purple'
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td>
                          <code style={{ fontSize: '11px' }}>
                            {r.checksum_sha256 ? r.checksum_sha256.slice(0, 12) + '…' : '—'}
                          </code>
                        </td>
                        <td>
                          {r.status === 'PENDING_REVIEW' ? (
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button
                                type="button"
                                className="btn btn--rescue btn--sm"
                                onClick={() => handleApproveRun(r.id)}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="btn btn--ghost btn--sm"
                                onClick={() => handleRejectRun(r.id)}
                              >
                                Reject
                              </button>
                            </div>
                          ) : (
                            <span style={{ color: 'var(--ink-3)', fontSize: '12px' }}>Verified</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {/* Filter Bar */}
      <section className="filterbar" aria-label="Dashboard filters">
        <label>
          <span>State</span>
          <select
            value={selectedState}
            onChange={(e) => updateParams({ state: e.target.value, district: '' })}
          >
            {statesList.map((st) => {
              const isCovered = coverage.covered_states.length > 0 && coverage.covered_states.includes(st)
              return (
                <option key={st} value={st}>
                  {isCovered ? `🟢 ${st}` : `🔴 ${st}`}
                </option>
              )
            })}
          </select>
        </label>

        <label>
          <span>Financial year</span>
          <select
            value={selectedYear}
            onChange={(e) => updateParams({ year: e.target.value })}
          >
            <option value="2026–27">2026–27 (Current)</option>
            <option value="2025–26">2025–26</option>
          </select>
        </label>

        <label>
          <span>Sector</span>
          <select
            value={selectedSector}
            onChange={(e) => updateParams({ sector: e.target.value })}
          >
            <option value="ALL">All civic sectors</option>
            <option value="WATER_SUPPLY">Water supply</option>
            <option value="ROADS">Road repair</option>
            <option value="SANITATION">Sanitation & sewage</option>
            <option value="ELECTRICITY">Electricity</option>
            <option value="HEALTH">Health</option>
            <option value="EDUCATION">Education</option>
            <option value="FLOOD_CONTROL">Flood control</option>
            <option value="HOUSING">Housing</option>
          </select>
        </label>

        <div className="fresh">
          <span className="live-dot" />
          Live operational view
          <small>Refreshed {refreshStamp}</small>
        </div>
      </section>

      {loading ? (
        <div className="panel" style={{ padding: '48px', textAlign: 'center', color: 'var(--ink-3)' }}>
          <div className="loading-spinner" style={{ margin: '0 auto 12px' }} />
          <p>Reconciling official state budget publications and citizen demand...</p>
        </div>
      ) : error ? (
        <div className="panel" style={{ padding: '32px', textAlign: 'center' }}>
          <div className="notice notice--bad" style={{ maxWidth: '600px', margin: '0 auto' }}>
            <strong>Unable to load public funds:</strong> {error}
            <div style={{ marginTop: '12px' }}>
              <button type="button" className="btn btn--sm btn--ghost" onClick={loadData}>
                Retry connection
              </button>
            </div>
          </div>
        </div>
      ) : !overview?.is_data_available && overview?.total_allocated === 0 ? (
        <div className="panel" style={{ padding: '48px', textAlign: 'center' }}>
          <h2>Data Unavailable for this Selection</h2>
          <p style={{ color: 'var(--ink-3)', maxWidth: '540px', margin: '8px auto' }}>
            No verified official financial data is currently available for {selectedState}. Release or expenditure
            records have not yet been published by the state finance department.
          </p>
        </div>
      ) : (
        <>
          {/* Anomaly Warning Banner if spent > released */}
          {overview?.has_anomaly ? (
            <div className="notice notice--bad" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>⚠️</span>
              <span>
                <strong>Fiscal Anomaly Detected:</strong> Recorded expenditure exceeds the released amount for this
                selection. This record requires administrative verification.
              </span>
            </div>
          ) : null}

          {/* State Funding Overview Panel */}
          <section className="overview panel">
            <div className="panel__head">
              <div>
                <p className="eyebrow">
                  {selectedState} · FY {selectedYear}
                </p>
                <h2>State funding overview</h2>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span className="panel__note">Amounts shown in ₹ crore</span>
                {overview?.metadata ? (
                  <span style={{ fontSize: '11.5px', color: 'var(--ink-3)' }}>
                    Source: <strong>{overview.metadata.source_name}</strong>
                  </span>
                ) : null}
              </div>
            </div>

            <div className="overview__grid">
              <div className="metric">
                <span>Total civic budget</span>
                <strong>₹{overview.total_allocated.toLocaleString()} Cr</strong>
                <small>approved allocation</small>
              </div>

              <div className="metric">
                <span>Funds released</span>
                <strong>₹{overview.funds_released.toLocaleString()} Cr</strong>
                <small>{overview.release_rate_pct}% of allocation</small>
              </div>

              <div className="metric">
                <span>Recorded expenditure</span>
                <strong>₹{overview.recorded_expenditure.toLocaleString()} Cr</strong>
                <small>{overview.utilisation_rate_pct}% of released funds</small>
              </div>

              <div className="metric metric--accent">
                <span>Available released funds</span>
                <strong style={{ color: overview.available_funds < 0 ? 'var(--alarm)' : undefined }}>
                  ₹{overview.available_funds.toLocaleString()} Cr
                </strong>
                <small>remaining in treasury</small>
              </div>
            </div>

            {/* Proportional Progress Bar */}
            <div className="fund-flow">
              <span
                style={{ width: `${Math.min(overview.release_rate_pct, 100)}%` }}
                title={`Released: ${overview.release_rate_pct}%`}
              />
              <span
                style={{
                  width: `${Math.min((overview.recorded_expenditure / (overview.total_allocated || 1)) * 100, 100)}%`,
                }}
                title={`Spent: ${overview.utilisation_rate_pct}% of released`}
              />
            </div>

            <div className="fund-flow__legend">
              <span>
                <i className="legend-box allocated" />
                Allocated (100%)
              </span>
              <span>
                <i className="legend-box released" />
                Released ({overview.release_rate_pct}%)
              </span>
              <span>
                <i className="legend-box spent" />
                Spent ({overview.utilisation_rate_pct}%)
              </span>
            </div>
          </section>

          {/* 2-Column Wide Grid: District Comparison + Decision Support Signals */}
          <div className="dashboard-grid dashboard-grid--wide">
            {/* District Comparison Horizontal Bars */}
            <section className="panel">
              <div className="panel__head">
                <div>
                  <p className="eyebrow">District comparison</p>
                  <h2>Allocation and utilisation</h2>
                </div>
                <span className="panel__note">Selected districts in {selectedState}</span>
              </div>

              <div className="panel__body">
                <div className="bar-chart" role="img" aria-label="District allocation, release and spending comparison">
                  {districtsData.length === 0 ? (
                    <p style={{ color: 'var(--ink-3)', fontSize: '13px' }}>
                      No district breakdown available for this state.
                    </p>
                  ) : (
                    districtsData.slice(0, 7).map((d) => (
                      <div className="bar-row" key={d.district_code || d.district}>
                        <div className="bar-label">
                          <strong>{d.district}</strong>
                          <small>{d.active_grievances} grievances</small>
                        </div>
                        <div className="bar-track">
                          <span
                            className="bar bar--allocation"
                            style={{ width: `${Math.min((d.allocated / maxDistrictAlloc) * 100, 100)}%` }}
                            title={`Allocated ₹${d.allocated} Cr`}
                          />
                          <span
                            className="bar bar--released"
                            style={{ width: `${Math.min((d.released / maxDistrictAlloc) * 100, 100)}%` }}
                            title={`Released ₹${d.released} Cr`}
                          />
                          <span
                            className="bar bar--spent"
                            style={{ width: `${Math.min((d.spent / maxDistrictAlloc) * 100, 100)}%` }}
                            title={`Spent ₹${d.spent} Cr`}
                          />
                        </div>
                        <strong className="bar-value">₹{d.spent} Cr</strong>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>

            {/* Decision Support Funding Signals */}
            <section className="panel insight-panel">
              <div className="panel__head">
                <div>
                  <p className="eyebrow">Decision support</p>
                  <h2>Funding signals</h2>
                </div>
              </div>

              <div className="panel__body insight-list">
                {fundingSignals.map((sig, idx) => (
                  <article key={idx} className={`insight insight--${sig.kind}`}>
                    <span className="insight__icon">
                      {sig.kind === 'critical' ? '⚠️' : sig.kind === 'warning' ? 'ℹ️' : '✓'}
                    </span>
                    <div>
                      <strong>{sig.title}</strong>
                      <p>{sig.text}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          {/* 2 Donut Visualizations: The Need vs The Spending */}
          <div className="dashboard-grid">
            {/* The Need: Citizen Grievances by Sector */}
            <section className="panel">
              <div className="panel__head">
                <div>
                  <p className="eyebrow">The need</p>
                  <h2>Citizen grievances by sector</h2>
                </div>
                <span className="panel__note">Active grievance share</span>
              </div>

              <div className="panel__body donut-layout">
                <div style={{ position: 'relative', width: '170px', height: '170px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={grievanceDonutData}
                        innerRadius={52}
                        outerRadius={78}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {grievanceDonutData.map((entry, index) => (
                          <Cell key={`cell-g-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val, name) => [`${val} grievances`, name]}
                        contentStyle={{ background: '#0f172a', color: '#fff', borderRadius: '6px', fontSize: '12px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      pointerEvents: 'none',
                    }}
                  >
                    <strong style={{ fontSize: '19px', fontFamily: 'var(--mono)' }}>
                      {overview.total_active_grievances}
                    </strong>
                    <small style={{ fontSize: '10px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>
                      active cases
                    </small>
                  </div>
                </div>

                <div className="legend">
                  {sectorsData.map((s) => (
                    <div key={s.category}>
                      <span>
                        <i style={{ background: s.color }} />
                        {s.label}
                      </span>
                      <strong>{s.grievance_share_pct}%</strong>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* The Spending: Expenditure by Sector */}
            <section className="panel">
              <div className="panel__head">
                <div>
                  <p className="eyebrow">The spending</p>
                  <h2>Expenditure by sector</h2>
                </div>
                <span className="panel__note">Share of ₹{overview.recorded_expenditure} Cr spent</span>
              </div>

              <div className="panel__body donut-layout">
                <div style={{ position: 'relative', width: '170px', height: '170px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={expenditureDonutData}
                        innerRadius={52}
                        outerRadius={78}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {expenditureDonutData.map((entry, index) => (
                          <Cell key={`cell-e-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val, name) => [`₹${val} Cr`, name]}
                        contentStyle={{ background: '#0f172a', color: '#fff', borderRadius: '6px', fontSize: '12px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      pointerEvents: 'none',
                    }}
                  >
                    <strong style={{ fontSize: '18px', fontFamily: 'var(--mono)' }}>
                      ₹{overview.recorded_expenditure}
                    </strong>
                    <small style={{ fontSize: '10px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>
                      crore spent
                    </small>
                  </div>
                </div>

                <div className="legend">
                  {sectorsData.map((s) => {
                    const spendShare = overview.recorded_expenditure > 0
                      ? Math.round((s.spent / overview.recorded_expenditure) * 100)
                      : 0
                    return (
                      <div key={s.category}>
                        <span>
                          <i style={{ background: s.color }} />
                          {s.label}
                        </span>
                        <strong>{spendShare}%</strong>
                      </div>
                    )
                  })}
                </div>
              </div>
            </section>
          </div>

          {/* Sector Priority Register Table */}
          <section className="panel priority-table">
            <div className="panel__head">
              <div>
                <p className="eyebrow">Needs-to-spend reconciliation</p>
                <h2>Sector priority register</h2>
              </div>
              <button
                type="button"
                className="text-btn"
                onClick={() => navigate(`/?state=${encodeURIComponent(selectedState)}`)}
              >
                Open linked grievances →
              </button>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Sector</th>
                    <th>Active need</th>
                    <th>Allocated</th>
                    <th>Released</th>
                    <th>Spent</th>
                    <th>Utilisation</th>
                    <th>Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {sectorsData.map((s) => (
                    <tr key={s.category}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span
                            style={{
                              width: '9px',
                              height: '9px',
                              borderRadius: '2px',
                              background: s.color,
                              display: 'inline-block',
                            }}
                          />
                          <strong>{s.label}</strong>
                        </div>
                      </td>
                      <td>{s.grievance_share_pct}%</td>
                      <td>₹{s.allocated.toLocaleString()} Cr</td>
                      <td>₹{s.released.toLocaleString()} Cr</td>
                      <td>₹{s.spent.toLocaleString()} Cr</td>
                      <td>
                        <div className="mini-progress">
                          <span style={{ width: `${Math.min(s.utilisation_rate, 100)}%` }} />
                        </div>
                        <small>{s.utilisation_rate}% of released</small>
                      </td>
                      <td>
                        <span className={`assessment assessment--${s.assessment_type === 'warn' ? 'critical' : s.assessment_type === 'attention' ? 'watch' : 'balanced'}`}>
                          {s.assessment}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Methodology Notice */}
          <div className="method-note">
            <span style={{ fontSize: '17px', color: 'var(--accent)' }}>🛡</span>
            <p>
              <strong>How to read this dashboard:</strong> grievance volume is an independent need signal, not an
              automatic funding formula. Population, asset condition, disaster risk, committed works and legal
              obligations must also be considered. Dashboard analysis never changes complaint urgency or ranking.
            </p>
          </div>
        </>
      )}
    </>
  )
}
