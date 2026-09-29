const KEY = 'jansetu.cookie-choice.v1'
let choice
let inMemoryOnly = false
try { choice = localStorage.getItem(KEY) } catch { /* optional storage */ }
if (!['accepted', 'declined'].includes(choice)) choice = null

export function cookieChoice() {
  try {
    const saved = localStorage.getItem(KEY)
    if (!inMemoryOnly) choice = ['accepted', 'declined'].includes(saved) ? saved : null
  } catch { /* retain the in-memory choice */ }
  return choice
}
export function chooseCookies(value) {
  choice = value
  try { localStorage.setItem(KEY, value); inMemoryOnly = false } catch { inMemoryOnly = true }
  window.dispatchEvent(new Event('jansetu-cookie-choice'))
}
