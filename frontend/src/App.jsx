/**
 * The shell, and the one place the two journeys are told apart.
 *
 * `data-journey` on the wrapper reassigns the accent and surface tokens in
 * base.css, so navigating from the citizen form to the policy dashboard changes
 * the temperature of the whole page. That is for the demo video: the cut between
 * "a farmer reports a problem" and "a ministry ranks it" has to be legible in one
 * frame, without narration.
 */
import { Suspense, lazy } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { API_BASE } from './api.js'
import DemoSimulator from './components/DemoSimulator.jsx'
import Logo from './components/Logo.jsx'
import { Loading } from './components/States.jsx'
import { CapabilitiesProvider } from './hooks/useCapabilities.jsx'
import CitizenIntake from './pages/CitizenIntake.jsx'
import TrackStatus from './pages/TrackStatus.jsx'

/**
 * The policy pages are loaded on demand; the citizen page is not.
 *
 * Leaflet and recharts are ~70% of this bundle and neither appears on `/`. That
 * page is the one written for a ₹6,000 phone on a 3G connection, so it should not
 * download a charting library to render a textarea. Splitting here takes the
 * citizen entry point from 720 kB to roughly a fifth of that.
 */
const PolicyDashboard = lazy(() => import('./pages/PolicyDashboard.jsx'))
const Recommendations = lazy(() => import('./pages/Recommendations.jsx'))
const PublicFunds = lazy(() => import('./pages/PublicFunds.jsx'))

const POLICY_ROUTES = ['/dashboard', '/recommendations', '/public-funds']

export default function App() {
  const { pathname } = useLocation()
  const journey = POLICY_ROUTES.some((p) => pathname.startsWith(p)) ? 'policy' : 'citizen'

  return (
    <CapabilitiesProvider>
      <div className="shell" data-journey={journey}>
        <header className="masthead">
          <div className="masthead__inner">
            <NavLink to="/" className="wordmark" aria-label="JanSetu — home">
              <Logo size={38} />
              {/* The mark and the type are grouped separately so the two words
                  keep a shared baseline while the mark centres against them.
                  Baseline-aligning an image against text sits it on the
                  descender line and reads as a dropped logo. */}
              <span className="wordmark__text">
                <span className="wordmark__name">JanSetu</span>
                {/* "People's bridge" — the name is the thesis, so it is set in
                    Devanagari next to the roman form rather than explained. */}
                <span className="wordmark__native">जनसेतु</span>
              </span>
            </NavLink>

            <nav className="nav" aria-label="Main">
              <span className="nav__group-label">Citizen</span>
              <NavLink to="/" className={navClass} end>
                Report a need
              </NavLink>
              {/* Second in the citizen group, not tucked in a footer link. The
                  return visit is the one that decides whether a person files
                  again, and it has to be as easy to find as the form was. */}
              <NavLink to="/track" className={navClass}>
                Track Status
              </NavLink>
              <span className="nav__divider" aria-hidden="true" />
              <span className="nav__group-label">Government</span>
              <NavLink to="/dashboard" className={navClass}>
                Hotspots
              </NavLink>
              <NavLink to="/recommendations" className={navClass}>
                Priorities
              </NavLink>
              <NavLink to="/public-funds" className={navClass}>
                Public Funds
              </NavLink>
            </nav>
          </div>
        </header>

        <main className={`main${journey === 'citizen' ? ' main--narrow' : ''}`}>
          <Suspense fallback={<Loading label="Loading the dashboard…" />}>
            <Routes>
              <Route path="/" element={<CitizenIntake />} />
              {/* Two paths, one page. `/track/JS-7K4M-92QX` is what a citizen can
                  bookmark or send to whoever helped them file; `/track` is the
                  empty search box the nav tab points at. */}
              <Route path="/track" element={<TrackStatus />} />
              <Route path="/track/:token" element={<TrackStatus />} />
              <Route path="/dashboard" element={<PolicyDashboard />} />
              <Route path="/recommendations" element={<Recommendations />} />
              <Route path="/public-funds" element={<PublicFunds />} />
              {/* A deep link that 404s in front of a judge is avoidable. */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>

        <footer className="footer">
          Citizen reports, census demographics and public investment data joined at the district level ·
          Scoring is deterministic Python; Gemini structures input and narrates output, and never produces a
          ranked number · API <code>{API_BASE}</code>
        </footer>

        {/* Outside `main`, and on every route by design. The three channels are
            what make the coverage claim true — a citizen with a feature phone and
            no literacy assumption — and a judge reading the dashboard should be
            one click from the WhatsApp thread that produced the row they are
            looking at, not hunting for a separate demo page. */}
        <DemoSimulator />
      </div>
    </CapabilitiesProvider>
  )
}

const navClass = ({ isActive }) => `nav__link${isActive ? ' nav__link--active' : ''}`
