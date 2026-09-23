/**
 * The demo sign-in for the officials' console.
 *
 * **This is a gate, not authentication, and the sign-in screen says so.** The
 * credentials below live in the shipped JavaScript; the check runs in the browser;
 * and the API behind this console is unauthenticated in the hackathon build, so
 * anyone who can reach it can read the queue with `curl` regardless of what this
 * screen does. Pretending otherwise would be the same class of lie as a button
 * that said "Sent" when nothing had been sent.
 *
 * What it is for: showing *where* an identity check belongs in the architecture,
 * and giving each demo account a jurisdiction and a desk so the console opens on
 * one officer's backlog instead of all of India. In a real deployment this screen
 * is replaced by the state's existing SSO — the seam is `signIn()` returning a
 * session, and nothing else in the app knows how that session was obtained.
 *
 * A real deployment also needs the API to enforce the jurisdiction. Today the
 * state filter here is a convenience, not a boundary: the officer can clear it.
 *
 * No PII, consistent with constraint 5. An account is a *post* — "Block
 * Development Officer, Nabarangpur" — never a person. Posts outlast the people who
 * hold them, which is also why the reply composer asks for a desk.
 */

const SESSION_KEY = 'jansetu.session'

/** Shared across the demo accounts on purpose: one thing to type on stage. */
export const DEMO_PASSWORD = 'jansetu@2026'

export const DEMO_ACCOUNTS = [
  {
    id: 'bdo.nabarangpur',
    post: 'Block Development Officer',
    desk: 'Block Development Office, Nabarangpur',
    state: 'Odisha',
    note: 'Sees Odisha. The district JanSetu ranks first for unmet water need.',
  },
  {
    id: 'phed.sitamarhi',
    post: 'Public Health Officer',
    desk: 'Public Health Engineering Desk, Sitamarhi',
    state: 'Bihar',
    note: 'Sees Bihar. Mostly WhatsApp and IVR reports, mostly in Hindi.',
  },
  {
    id: 'state.cell',
    post: 'State coordination cell',
    desk: 'State Coordination Cell',
    state: '',
    note: 'Sees every state — the view a national dashboard owner would have.',
  },
]

export function findAccount(id) {
  const wanted = (id || '').trim().toLowerCase()
  return DEMO_ACCOUNTS.find((a) => a.id === wanted) || null
}

class SignInError extends Error {}

/**
 * Deliberately says which half was wrong. Real sign-in screens are vague about it
 * to slow down credential stuffing; a demo whose password is printed on the screen
 * has nothing to protect and everything to gain from telling a nervous presenter
 * that they mistyped the account, not the password.
 */
export function signIn(id, password) {
  const account = findAccount(id)
  if (!account) throw new SignInError('No such account. Pick one of the three listed below.')
  if (password !== DEMO_PASSWORD) throw new SignInError('Wrong password for this account.')

  const session = {
    id: account.id,
    post: account.post,
    desk: account.desk,
    state: account.state,
    since: new Date().toISOString(),
  }
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    /* private browsing with storage denied — the session still works in memory */
  }
  return session
}

/**
 * `sessionStorage`, not `localStorage`: closing the tab signs the officer out. On
 * a shared district-office machine that is the correct default, and it also means
 * a fresh tab always opens on the sign-in screen — which is what the demo needs.
 */
export function currentSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && findAccount(parsed.id) ? parsed : null
  } catch {
    return null
  }
}

export function signOut() {
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {
    /* nothing to clear */
  }
}
