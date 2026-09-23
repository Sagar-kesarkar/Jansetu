/**
 * The console shell, its sign-in gate, and its two routes.
 *
 * There is no navigation menu because there are only two screens and one is a
 * child of the other. What the topbar carries instead is the signed-in post and
 * the one sentence an officer opening this for the first time needs: this is the
 * receiving end of the citizen platform, and the ranking is somewhere else.
 * Officers who think casework moves the national priority list will manage the
 * list instead of the cases.
 *
 * The gate wraps the router rather than living inside it as a `/login` route. A
 * route would let a deep link to `/requests/500` render the case for an instant
 * before redirecting, and the redirect would then have to remember where it was
 * going. Rendering the sign-in screen *instead of* the router means an
 * unauthenticated deep link shows nothing and, after signing in, the URL is still
 * `/requests/500` and simply resolves.
 */
import { useCallback, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'

import { currentSession, signOut } from './auth.js'
import { Logo } from './components/Logo.jsx'
import { AllocationDashboard } from './pages/AllocationDashboard.jsx'
import { RequestDetail } from './pages/RequestDetail.jsx'
import { RequestQueue } from './pages/RequestQueue.jsx'
import { SignIn } from './pages/SignIn.jsx'
import './styles/console.css'

function NotFound() {
  return (
    <div className="panel">
      <div className="panel__body">
        <div className="state">
          <div className="state__title">No such screen</div>
          <p className="state__body">
            This console has a queue, allocation analytics, and a case view. <Link to="/">Back to the queue</Link>.
          </p>
        </div>
      </div>
    </div>
  )
}

export function App() {
  const [session, setSession] = useState(currentSession)

  const out = useCallback(() => {
    signOut()
    setSession(null)
  }, [])

  if (!session) return <SignIn onSignedIn={setSession} />

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__in">
          <Link className="brand brand--light" to="/">
            <Logo size={36} />
            <span>
              <strong>JanSetu</strong>
              <small>OFFICIALS' CONSOLE</small>
            </span>
          </Link>

          <nav className="mainnav" aria-label="Officials console navigation">
            <NavLink
              to="/"
              end
              className={({ isActive }) => (isActive ? 'on' : '')}
            >
              Grievance Operations
            </NavLink>
            <NavLink
              to="/funds"
              className={({ isActive }) => (isActive ? 'on' : '')}
            >
              Priority & Public Funds
            </NavLink>
          </nav>

          <div className="who">
            <span>{session.post}</span>
            <small>
              {session.state || 'All states'} · <code>{session.id}</code>
            </small>
          </div>

          <button type="button" className="btn btn--ghost btn--sm" onClick={out} style={{ marginLeft: '8px' }}>
            Sign out
          </button>
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<RequestQueue session={session} />} />
          <Route path="/funds" element={<AllocationDashboard session={session} />} />
          <Route path="/allocation" element={<AllocationDashboard session={session} />} />
          <Route path="/requests/:id" element={<RequestDetail session={session} />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <footer className="foot">
        <div className="foot__in">
          JanSetu — reports carry an opaque reference and a district code. No name,
          phone number, address, IP or device is stored anywhere in this system, so
          none can be shown here.
        </div>
      </footer>
    </div>
  )
}
