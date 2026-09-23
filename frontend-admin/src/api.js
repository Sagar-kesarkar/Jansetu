/**
 * Every call the console makes to the backend.
 *
 * A deliberate copy of the citizen app's client rather than an import across
 * `../../frontend/src`. Two Vite apps that reach into each other's source cannot
 * be built or deployed independently — Netlify's `base` is one directory — and
 * the two clients want genuinely different things: this one never touches
 * `/hotspots` or `/recommendations`, and the citizen app must never gain the
 * ability to write a reply.
 *
 * The duplication is about 60 lines and buys two independently deployable sites.
 */

// Trailing slash stripped so `${BASE}/requests` can never become a double slash,
// which some hosts 301 and browsers then re-request without the CORS preflight.
export const API_BASE = (
  import.meta.env.VITE_API_BASE || 'http://localhost:8080'
).replace(/\/+$/, '')

const READ_TIMEOUT_MS = 20_000

/** Posting a reply may trigger a Gemini translation into the citizen's language. */
const WRITE_TIMEOUT_MS = 90_000

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Surfacing *which* failure happened — unreachable vs. 422 vs. slow — matters
 * more here than on a read-only dashboard. An officer whose reply failed needs to
 * know whether to retype it or to wait, and "something went wrong" answers
 * neither question.
 */
async function request(path, { timeout = READ_TIMEOUT_MS, ...init } = {}) {
  let resp
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeout),
    })
  } catch (err) {
    if (err.name === 'TimeoutError') {
      throw new ApiError(`The API did not respond within ${timeout / 1000}s.`, 0)
    }
    throw new ApiError(`Cannot reach the API at ${API_BASE}. Is it running?`, 0)
  }

  if (!resp.ok) {
    let detail = ''
    try {
      const body = await resp.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body; the status alone will have to do */
    }
    throw new ApiError(detail || `Request failed (HTTP ${resp.status}).`, resp.status)
  }

  return resp.json()
}

/**
 * Drops empty filters so `?state=` never reaches the API as a literal filter.
 *
 * Arrays append rather than replace: `status: ['RESOLVED', 'REJECTED']` has to
 * leave as `?status=RESOLVED&status=REJECTED`, which is what FastAPI reads back
 * into a `list[RequestStatus]`. `qs.set` would send the JS-stringified
 * `?status=RESOLVED,REJECTED` and get a 422 for an unknown enum member.
 */
function query(params) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const v of value) if (v !== null && v !== undefined && v !== '') qs.append(key, v)
    } else if (value !== null && value !== undefined && value !== '' && value !== false) {
      qs.set(key, value)
    }
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

/**
 * Languages and sectors come from the backend, never from a constant here. The
 * backend owns the taxonomy; a hardcoded list means adding the fourteenth
 * language in two places and shipping them out of sync.
 */
export const getCapabilities = () => request('/capabilities')

/** Covered states, derived from `data/reference/districts.csv` server-side. */
export const getStates = () => request('/states')

export const getStats = ({ state, category } = {}) =>
  request(`/requests/stats${query({ state, category })}`)

export const getRequests = ({
  state,
  districtCode,
  category,
  language,
  channel,
  status,
  citizenRef,
  minUrgency,
  unanswered,
  q,
  limit = 60,
  offset = 0,
} = {}) =>
  request(
    `/requests${query({
      state,
      district_code: districtCode,
      category,
      language,
      channel,
      status,
      citizen_ref: citizenRef,
      min_urgency: minUrgency,
      unanswered,
      q,
      limit,
      offset,
    })}`,
  )

export const getRequest = (id) => request(`/requests/${id}`)

/**
 * The URL of a case's photograph. A URL, not a fetch, on purpose.
 *
 * For display, an `<img src>` loads a cross-origin image without needing CORS at
 * all, so there is nothing to fetch and no blob to manage.
 *
 * For download, the browser has to *navigate* to this URL rather than XHR it. The
 * `download` attribute on an anchor is silently ignored cross-origin — and the
 * console is served from a different port to the API — so the filename can only
 * come from the server's `Content-Disposition`, which `?download=1` switches to
 * `attachment` with the case's tracking token as the name. Fetching into a blob and
 * calling `URL.createObjectURL` would also work and would put the whole photograph
 * through JS memory to end up with the same file.
 */
export const photoUrl = (id, { download = false } = {}) =>
  `${API_BASE}/requests/${id}/photo${download ? '?download=1' : ''}`

/**
 * `responderDesk` is a desk or role, not a person — the API caps it at 128 chars
 * and the placeholder in the composer says so. An officer's own name in an
 * outbound message is PII about the officer, and it also invites a citizen to
 * chase an individual rather than an office that will still exist next year.
 */
export const postResponse = (id, { bodyEn, responderDesk, newStatus, translate = true }) =>
  request(`/requests/${id}/responses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      body_en: bodyEn,
      responder_desk: responderDesk,
      new_status: newStatus || null,
      translate,
    }),
    timeout: WRITE_TIMEOUT_MS,
  })

export const patchStatus = (id, status) =>
  request(`/requests/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })

/**
 * Overrule triage: return a machine-flagged case to the working queue.
 *
 * Its own route rather than `patchStatus(id, 'NEW')` because the backend refuses
 * anything that is not INVALID — see `routers/requests.py::restore_request`. A
 * mis-click here cannot reopen finished casework.
 */
export const restoreRequest = (id) =>
  request(`/requests/${id}/restore`, { method: 'PATCH' })

export const getBudgetAllocations = ({ state, category } = {}) =>
  request(`/budget/allocations${query({ state, category })}`)

export const getFundsOverview = ({ scope = 'state', state = 'Maharashtra', district, fiscalYear = '2026-27', category } = {}) =>
  request(`/api/v1/funds/overview${query({ scope, state, district, fiscal_year: fiscalYear, category })}`)

export const getFundsSectors = ({ scope = 'state', state = 'Maharashtra', district, fiscalYear = '2026-27' } = {}) =>
  request(`/api/v1/funds/sectors${query({ scope, state, district, fiscal_year: fiscalYear })}`)

export const getFundsDistricts = ({ state = 'Maharashtra', fiscalYear = '2026-27', category } = {}) =>
  request(`/api/v1/funds/districts${query({ state, fiscal_year: fiscalYear, category })}`)

export const getFundsCoverage = () => request('/api/v1/funds/coverage')

export const getFundsSources = () => request('/api/v1/funds/sources')

export const getAdminFundsImports = () => request('/api/v1/admin/funds/imports')

export const triggerAdminFundsSync = (adapterKey = 'maharashtra_finance') =>
  request('/api/v1/admin/funds/imports/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ adapter_key: adapterKey, auto_approve: true }),
  })

export const approveAdminFundsImport = (importId, notes = '') =>
  request(`/api/v1/admin/funds/imports/${importId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  })

export const rejectAdminFundsImport = (importId, notes = '') =>
  request(`/api/v1/admin/funds/imports/${importId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  })


