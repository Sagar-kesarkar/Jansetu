# JanSetu — Officials' Console: frontend Redesign Blueprint

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

> **Purpose.** A complete, reconstruction-grade handoff of the **admin frontend only**
> (`frontend-admin/`, the "Officials' Console"). An AI with **no access to this
> codebase** should be able to rebuild the current interface — structure, styling,
> data contracts and interactions — from this document alone.
>
> **Strict scope.** This covers only the officials' side: the sign-in gate, the
> request queue / dashboard, and the single case-detail view. It **excludes** the
> separate citizen-facing app (`frontend-citizen/`, on port 5173: public grievance
> submission, tracking, policy dashboard, hotspot map, recommendations). Those live
> in a different Vite app and share **zero** code with this one — the CSS, the API
> client and the components are all deliberately duplicated so the two sites deploy
> independently.
>
> **Three scope corrections up front** (the brief's template assumed a more
> conventional admin panel; here is what actually exists):
> 1. **There is no sidebar.** The shell is a top bar + main + footer. Navigation is
>    two routes only; you move by clicking table rows and a "back" link.
> 2. **RBAC is a filter, not a boundary.** Every signed-in account can perform every
>    action. The account only sets an *opening* state filter (clearable) and a
>    default reply-desk. The API is unauthenticated in this build; the sign-in
>    screen says so explicitly. There are no per-action permissions to reproduce.
> 3. **There is no "Route to Department" control.** "Routing" is expressed as a
>    free-text *issuing desk* on a reply plus a status change — not an assignment
>    dropdown.

---

## 1. Tech Stack & Environment (Admin Context)

### 1.1 Framework & language
- **React 19.2.8** + **react-dom 19.2.8**. Function components and hooks only; no
  class components. `<StrictMode>` is enabled.
- **Plain JSX / JavaScript — no TypeScript.** Files are `.jsx` (components/pages)
  and `.js` (api, auth, hooks, lib). No type annotations anywhere.
- **Vite 8.2.2** with **@vitejs/plugin-react 6.1.0** as the only build tooling.
- Entry chain: `index.html` → `/src/main.jsx` → `<App/>`.

### 1.2 Routing
- **react-router-dom 7.18.2**, `BrowserRouter` mounted in `main.jsx`:
  ```jsx
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  )
  ```
- **Exactly three routes**, declared in `App.jsx` inside the shell's `<main>`:
  | Path | Element | Purpose |
  |------|---------|---------|
  | `/` | `<RequestQueue/>` | Dashboard + queue table |
  | `/requests/:id` | `<RequestDetail/>` | Single case view |
  | `*` | `<NotFound/>` | Fallback |
- **Protected admin routes are implemented as a client-side gate, not a route
  guard.** `App.jsx` holds session state; if there is no session it returns
  `<SignIn/>` *instead of* the router. So an unauthenticated deep link renders the
  sign-in screen, and after sign-in the same URL resolves. There is no
  `<PrivateRoute>` wrapper and no redirect — the entire router is simply not
  mounted until a session exists.
  ```jsx
  export default function App() {
    const [session, setSession] = useState(currentSession)
    if (!session) return <SignIn onSignedIn={setSession} />
    return (/* shell with <Routes> */)
  }
  ```
- **Filter state lives in the URL** via `useSearchParams`, not React state. Example:
  `/?state=Odisha&unanswered=true&view=active`. This makes the queue shareable and,
  critically, preserves an officer's place when they open a case and navigate back.

### 1.3 Styling engine
- **A single hand-written CSS file: `src/styles/console.css`** (~1,490 lines),
  imported once at the top of `App.jsx`. That import is the whole styling system.
- **No Tailwind, no CSS Modules, no CSS-in-JS, no component library.** There is no
  `tailwind.config`, no PostCSS pipeline beyond Vite defaults, no Sass.
- **Design tokens are CSS custom properties** declared in `:root` (see §2.2).
- **Class naming is BEM-flavoured**: `block`, `block__element`, `block--modifier`
  (e.g. `panel`, `panel__head`, `btn--ghost`, `queue-tab--on`).
- **Inline `style={{…}}` is used sparingly** for one-off spacing nudges only
  (e.g. `style={{ marginTop: 6 }}`), never for the design language.

### 1.4 State / data fetching
- **Plain `fetch`** wrapped in `src/api.js`. **No axios, no React Query, no SWR, no
  Redux.** No global store — state is local component state + URL params + one
  module-scope cache for reference vocabulary.
- **`API_BASE`** = `import.meta.env.VITE_API_BASE || 'http://localhost:8080'`, with
  any trailing slash stripped. All calls are `` `${API_BASE}${path}` ``.
- **Timeouts via `AbortSignal.timeout`**: reads **20 s**, writes (reply, which may
  trigger a Gemini translation) **90 s**. A dedicated `ApiError` carries a
  `.status`, and failures are surfaced specifically ("Cannot reach the API…",
  "…did not respond within 20s", or the server's `detail`).
- **Query builder** drops empty values (so `?state=` never hits the API) and
  **appends arrays** as repeated params (`status=RESOLVED&status=REJECTED`).
- **`useApi(fetcher, deps)`** (`src/hooks/useApi.js`) is the read primitive. It
  distinguishes four states the UI renders differently:
  - `loading` (first fetch, no data yet) → spinner
  - `refreshing` (has data, re-reading) → keep the page standing (used after a
    reply so the confirmation isn't unmounted)
  - `error` → the actual reason + API base
  - loaded-empty → an empty-state message
  It uses a `generation` ref to ignore out-of-order responses (a slow "Odisha"
  landing after a fast "Bihar"). `reload()` re-fetches **without** blanking; a deps
  change **does** blank.
- **`useReference()`** (`src/hooks/useReference.js`) fetches `/states` +
  `/capabilities` **once**, cached at module scope, degrading to empty lists on
  failure so a vocabulary outage never takes the page down.

### 1.5 The API surface this console uses (all of `api.js`)
| Function | Method & path | Used by |
|---|---|---|
| `getCapabilities()` | `GET /capabilities` | reference vocab (languages, categories) |
| `getStates()` | `GET /states` | reference vocab (state list) |
| `getStats({state,category})` | `GET /requests/stats?…` | KPI cards + tab counts |
| `getRequests({…filters})` | `GET /requests?…` | queue table |
| `getRequest(id)` | `GET /requests/{id}` | case detail |
| `photoUrl(id,{download})` | `GET /requests/{id}/photo[?download=1]` | evidence `<img>`/download (URL, not fetch) |
| `postResponse(id,{…})` | `POST /requests/{id}/responses` | reply composer (write) |
| `patchStatus(id,status)` | `PATCH /requests/{id}/status` | "move without replying" |
| `restoreRequest(id)` | `PATCH /requests/{id}/restore` | overrule triage / "mark as valid" |

This console **never** calls `/hotspots` or `/recommendations` (those are the
citizen-side policy dashboard).

### 1.6 Dev/build config
- `vite.config.js`: `server.port = 5174` (runs alongside the citizen app on 5173),
  `plugins: [react()]`, `build: { outDir: 'dist', sourcemap: false }`.
- `index.html`: title "JanSetu Console — citizen requests and official replies";
  **no webfont `<link>`** — system fonts only, for offline Indic-script coverage
  (see §2.3). Root node `<div id="root">`.

---

## 2. Admin Layout Shell & Theming

### 2.1 The shell (`App.jsx` + `.shell`/`.topbar`/`.main`/`.foot`)
The whole app is a **single vertical flex column** the height of the viewport:

```
.shell  { min-height:100%; display:flex; flex-direction:column }
  ├─ header.topbar     ← fixed-height dark bar (does not scroll away; it's normal flow, not position:fixed)
  ├─ main.main         ← flex:1, holds the routed page
  └─ footer.foot       ← privacy statement
```

**Top bar** (`.topbar`, background `--slate` #2a3442, bottom border #1b232d).
Inner wrapper `.topbar__in` is the content-width row:
```
.topbar__in { max-width:1400px; margin:0 auto; padding:12px 20px;
              display:flex; align-items:center; gap:18px; flex-wrap:wrap }
```
Children, left → right:
1. `.brand` (a `<Link to="/">`, `display:flex; align-items:baseline; gap:9px`):
   `.brand__mark` "JanSetu" (serif, 20px, weight 600) + `.brand__sub` "Officials'
   console" (11px, uppercase, letter-spacing 0.12em, muted blue `#9fb0c4`).
2. `.topbar__spacer` (`flex:1`) — pushes the rest to the right.
3. `.topbar__note` (12.5px, muted, max-width 340px): a one-line reminder that
   nothing here changes the policy rankings.
4. `.who` (the signed-in **post**, right-aligned, `flex-direction:column`, with a
   `border-left:1px solid #3b4757` and `padding-left:16px` acting as a divider):
   `.who__post` (post title, white, 13.5px, weight 600) + `.who__where`
   ("{state or 'All states'} · {account id}", 11.5px muted; the id wrapped in a
   `.ref` chip recoloured for the dark bar).
5. **Sign-out** button: `.btn.btn--ghost.btn--sm`, restyled on the slate bar
   (transparent, border `#4a5766`, text `#cfd9e4`; hover fills `#354152`).

**Main** (`.main`): `flex:1; max-width:1400px; width:100%; margin:0 auto;
padding:22px 20px 56px`. Everything routed renders here.

**Footer** (`.foot`): top border `--rule`, white bg, 12.5px `--ink-3`; inner
`.foot__in` same 1400px/`0 auto`/`16px 20px` container. Carries the standing
privacy statement (no name/phone/address/IP/device stored).

> **No sidebar, no nav menu, no breadcrumb.** With only two destinations, wayfinding
> is: the brand returns to the queue; table rows open cases; a "← Back to the queue"
> link returns. Reproduce this — do **not** add a nav rail.

### 2.2 Colour palette (all tokens from `:root`)
This app is deliberately a **third visual identity** — "a desk": neutral paper,
slate chrome, one accent blue, and colour used *only* where it maps to an action.

**Neutrals / ink (text):**
| Token | Hex | Use |
|---|---|---|
| `--ink` | `#14171c` | primary text |
| `--ink-2` | `#414855` | secondary text, ghost-button text |
| `--ink-3` | `#6b7382` | muted labels, hints, table headers |
| `--ink-4` | `#939aa6` | faint / dashes |

**Rules & surfaces:**
| Token | Hex | Use |
|---|---|---|
| `--rule` | `#d8dce3` | borders, table header underline, stat-grid gap colour |
| `--rule-soft` | `#e9ecf1` | inner/row dividers |
| `--paper` | `#f4f6f8` | **body background** |
| `--surface` | `#ffffff` | panels, cards, inputs |
| `--surface-2` | `#fafbfc` | table header bg, quiet fills, hovers |

**Chrome & accent:**
| Token | Hex | Use |
|---|---|---|
| `--slate` | `#2a3442` | top bar + sign-in left panel |
| `--slate-ink` | `#ffffff` | text on slate |
| `--accent` | `#1f4e79` | primary buttons, links, focus ring, row hover text context |
| `--accent-soft` | `#eaf1f8` | row hover bg, active-tab badge, primary-status tag |

**Semantic status colours** (each is a fill + a text/`600` colour, most with a
matching border tint on tags):
| Meaning | Token(s) | Fill | Text | Where |
|---|---|---|---|---|
| Alarm / act now | `--alarm` / `--alarm-soft` | `#fbedee` | `#a8202f` | NEW status, "Action required" KPI, urgency 4–5, "no district match" |
| Warning / attention | `--warn` / `--warn-soft` | `#fdf3e3` | `#8a5406` | ACKNOWLEDGED, urgency 3, low-confidence, untranslated-reply note |
| OK / done | `--ok` / `--ok-soft` | `#e8f4ef` | `#14684a` | RESOLVED, **rescue button**, success notices |
| In progress | `--accent` / `--accent-soft` | `#eaf1f8` | `#1f4e79` | IN_PROGRESS status |
| Rejected / neutral | — | `#eef0f3` | `#414855` | REJECTED, plain/channel tags, `.ref` chips |
| Invalid / spam | (literal) | `#f0ecf8` | `#543f83` | **INVALID status + photo tag — purple, deliberately NOT red** |
| Triage reason | (literal) | `#f7f5fb` | `#4a3d6b` | Gemini's flag reason block (left border `#a08fc4`) |

> Design rule to preserve: **red = "act now" only.** A suspected advert (INVALID) is
> purple because it is the *opposite* of urgent — set aside and reviewable.

### 2.3 Typography
Three font stacks, **system fonts only** (no webfont request; Nirmala UI / Noto
supply Indic script so a citizen's original Odia/Bodo/Hindi text renders offline):
- `--serif`: `Georgia, 'Times New Roman', 'Nirmala UI', serif` — **all headings
  (`h1–h3`), the brand mark, panel titles, state-message titles, sign-in claim.**
  Weight 600, `letter-spacing:-0.01em`.
- `--sans`: `system-ui, -apple-system, 'Segoe UI', Roboto, 'Nirmala UI',
  sans-serif` — **body default**, `15px / line-height 1.5`, colour `--ink`.
- `--mono`: `ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, monospace` — **docket
  refs, tracking tokens, tabular counts, `.ref` chips**, so a token can be read back
  digit-by-digit over a phone line.

Key sizes (px): body 15 · h1 page-head **26** · case-detail h1 uses mono
`.docket__ref` · panel title **16** (serif) · stat value **24** (`tabular-nums`) ·
table body **14** · table header **11** (uppercase, `letter-spacing 0.08em`) ·
`.quote` (citizen's words on detail) **17** · micro-labels (field/stat/row keys)
**11**, uppercase, `letter-spacing ≈0.08–0.09em`, colour `--ink-3`.

### 2.4 Spacing, radii, elevation, borders (for dense data)
- **Radii:** `--r-sm 4px` (buttons, inputs, tags-ish, chips), `--r 8px` (panels,
  stat grid), `--r-lg 12px` (rare).
- **Shadows:** `--shadow-1` = `0 1px 2px rgba(20,23,28,.06), 0 1px 3px
  rgba(20,23,28,.04)` (panels); `--shadow-2` = `0 4px 6px -2px …, 0 12px 24px -8px …`
  (elevated, seldom used).
- **Container width:** `--wide 1400px` for top bar, main, footer.
- **Table density:** header cells `padding:9px 12px`; body cells `padding:11px 12px`,
  `vertical-align:top`; header underline `1px --rule`; row dividers `1px
  --rule-soft`; last row divider removed. Rows are `cursor:pointer`, hover
  `background:--accent-soft`.
- **Panels:** `.panel` = white, `1px --rule` border, radius 8px, `--shadow-1`.
  `.panel__head` = `padding:13px 16px`, bottom border `--rule-soft`, `display:flex;
  justify-content:space-between; align-items:baseline; gap:14px; flex-wrap:wrap`
  (title left, note right). `.panel__body` = `padding:16px`; `.panel__body--tight`
  = `padding:0` (used to let a table span edge-to-edge). Consecutive panels get
  `margin-top:16px` via `.panel + .panel`.
- **Focus:** global `:focus-visible { outline:2px solid --accent; outline-offset:2px }`.
- **Buttons** (`.btn`): filled accent, white text, `padding:8px 14px`, radius 4px,
  14px/500, hover `filter:brightness(1.12)`. Variants: `--ghost` (white bg, ink
  text, `--rule` border), `--sm` (`padding:5px 10px`, 13px), `--rescue` (green
  `--ok` fill — the only green button, reserved for restoring a triaged case).
  `.btn-row` = `flex; gap:9px; flex-wrap:wrap; align-items:center`.

---

## 3. Deep-Dive: The "Request Queue" & Dashboard (`pages/RequestQueue.jsx`)

Vertical order of the page inside `.main`:
1. `.page-head` — `<h1>Request queue</h1>` + `.page-head__lede` (one explanatory
   sentence). `.page-head` is `display:flex; justify-content:space-between;
   align-items:flex-end; flex-wrap:wrap; margin-bottom:18px`.
2. **`<StatsBar/>`** — the KPI row.
3. **`.queue-tabs`** — the three feeds.
4. A `.panel` wrapping **`<QueueFilters/>`**.
5. (invalid feed only) a `.triage-note` paragraph explaining the flagged queue.
6. A `.panel` with `.panel__head` (result title + "N shown, newest first") and a
   `.panel__body--tight` holding the table + pager, all inside `<Async>`.

### 3.1 KPI metrics row (`components/StatsBar.jsx` + `.stats`/`.stat`)
Fed by `GET /requests/stats` (counted in SQL over the *whole* filtered set, never
from the visible page). Rendered only when `stats` is present.

**Layout — a hairline-divided cell grid:**
```
.stats { display:grid;
         grid-template-columns:repeat(auto-fit, minmax(150px,1fr));
         gap:1px;                       /* the 1px gap is the divider   */
         background:var(--rule);        /* gap shows through as #d8dce3 */
         border:1px solid var(--rule);
         border-radius:8px; overflow:hidden; margin-bottom:18px }
.stat  { background:var(--surface); padding:12px 14px }   /* white cells */
```
So the cards auto-fit (min 150px each, growing to fill), separated by clean 1px
rules with no visible gutter. Each cell: `.stat__label` (11px uppercase muted) →
`.stat__value` (24px, weight 600, `tabular-nums`) → `.stat__hint` (12px muted).

**The five cards, in exact order:**
| # | Label | Value source | Hint | Red-flag rule |
|---|---|---|---|---|
| 1 | **Action required** | `awaiting_first_reply` | "nobody has responded yet" | `.stat--flag` (alarm-soft bg, red value) when `> 0` |
| 2 | **Oldest open case** | `oldest_open_days` → `"N days"` / `"under a day"` / `"nothing open"` | "since it was filed" | `.stat--flag` when `> 30` |
| 3 | **Open** | `open` | "new, acknowledged or in progress" | never |
| 4 | **Filed this week** | `filed_last_7_days` | "last 7 days" | never |
| 5 | **Total on record** | `total` | "all statuses" | never |

`.stat--flag` = `background:var(--alarm-soft)` and `.stat--flag .stat__value {
color:var(--alarm) }`.

> **Mapping to the brief's expected KPIs:** "Action Required" = card 1. "Oldest Open
> Case" = card 2. "Total on Record" = card 5. **"AI Triaged Spam" is *not* a KPI
> card** — the INVALID count surfaces instead as the numeric badge on the "Invalid
> requests" tab (§3.2). If the redesign wants it as a card, add a sixth `.stat`
> reading `by_status.INVALID`.

Counters follow only the **State** and **Sector** filters (not the queue's
status/unanswered narrowing) so "action required" can't become tautological.

### 3.2 Sub-navigation tabs (`.queue-tabs` / `.queue-tab`)
Three **feeds** (not filter presets) rendered as folder-style tabs:
```
.queue-tabs { display:flex; gap:4px; border-bottom:1px solid var(--rule);
              margin-bottom:18px; overflow-x:auto }
.queue-tab  { border:1px solid transparent; border-bottom:none; background:none;
              color:var(--ink-3); font:500 14px sans; padding:9px 15px;
              border-radius:4px 4px 0 0; margin-bottom:-1px }   /* sits on the rule */
.queue-tab--on { background:var(--surface); border-color:var(--rule);
                 color:var(--ink); font-weight:600 }            /* attached tab look */
```
| Tab | `view` key | Status filter sent | Count badge |
|---|---|---|---|
| **Active requests** | `active` | none → working queue (API excludes INVALID + NEEDS_LOCATION) | none (its size is the "Open" KPI) |
| **Cleared / resolved** | `cleared` | `['RESOLVED','REJECTED']` | `RESOLVED + REJECTED` |
| **Invalid requests** | `invalid` | `['INVALID']` | `INVALID` |

Count badges: `.queue-tab__count` = mono, 11.5px, bg `#eef0f3`, `border-radius:9px`,
`padding:1px 7px`; on the active tab it flips to `--accent-soft` bg / `--accent`
text. Tabs use `role="tab"` + `aria-selected`. Switching a tab resets `offset`,
clears the status dropdown and turns off "unanswered".

### 3.3 Filters row (`components/QueueFilters.jsx` / `.filters`)
Sits in a white `.panel > .panel__body`. Layout:
```
.filters { display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end }
.field   { display:flex; flex-direction:column; gap:4px }   /* label stacked over control */
.field__label { font:11px uppercase; letter-spacing:.08em; color:var(--ink-3) }
select / input { border:1px solid var(--rule); border-radius:4px; padding:7px 9px;
                 min-width:130px }        /* search input min-width:220px */
```
Controls, left → right (every dropdown is **populated from the backend**, never
hardcoded):
1. **State** — `<select>`; "All states" + `reference.states` (from `/states`).
2. **Sector** — `<select>`; "All sectors" + `reference.categories` (from
   `/capabilities`), labelled via `sectorLabel()` (`WATER_SUPPLY`→"Water supply").
3. **Arrived by** (channel) — `<select>`; options `whatsapp, ivr, voice, text, sms`
   labelled "WhatsApp / IVR call / Voice note / Web form / SMS".
4. **Language** — `<select>`; "All languages" + `reference.languages`, labelled
   `name (native)`.
5. **Status** — `<select>`; **shown only in the Active feed**. Options `NEW,
   ACKNOWLEDGED, IN_PROGRESS, RESOLVED, REJECTED`.
6. **Urgency** — `<select>`; "Any urgency" / "3 and above" / "4 and above" /
   "5 — immediate risk".
7. **Search** — `<input type="search">`; placeholder "Original text, summary or
   place"; **debounced 400 ms** locally (all other filters apply immediately).
   Searches original text + English summary + scrubbed place levels; **min 2 chars**.
8. **Action required only** — a `.check` checkbox; **shown only in the Active feed**;
   default **on** at first load.
9. **Clear** — `.btn.btn--ghost.btn--sm`; resets all filters but keeps the current
   tab.

`.check` = `inline-flex; align-items:center; gap:7px; font-size:13.5px` with a
15×15 checkbox using `accent-color:var(--accent)`.

**Default opening state** (opinionated): Active feed, **unanswered-only on**,
newest first, **scoped to the signed-in account's state** (a BDO in Nabarangpur
lands on Odisha). All three are visible and one click from off; none is enforced.

---

## 4. Deep-Dive: The Data Table & Routing Actions

### 4.1 Table structure (`.queue` in `RequestQueue.jsx`)
Wrapped in `.queue-wrap { overflow-x:auto }` inside `.panel__body--tight`
(padding 0, so the table meets the panel edges). `.panel__head` above it shows the
result title (`view.title` or, in the active feed, "Action required" when
unanswered-only else "All cases", with ` — {state}` appended) and a note
`"{n} shown, newest first"`.

```
table.queue { width:100%; border-collapse:collapse; font-size:14px }
th { text-align:left; font:600 11px sans; text-transform:uppercase;
     letter-spacing:.08em; color:var(--ink-3); padding:9px 12px;
     border-bottom:1px solid var(--rule); background:var(--surface-2); white-space:nowrap }
td { padding:11px 12px; border-bottom:1px solid var(--rule-soft); vertical-align:top }
tbody tr { cursor:pointer }               /* whole row navigates to the case */
tbody tr:hover { background:var(--accent-soft) }
```
Each `<tr>` is a **row-as-link**: `onClick`→`navigate('/requests/{id}')`,
`onKeyDown` Enter, `tabIndex={0}`, `role="link"`, `aria-label="Open docket {id}"`.

**Six columns:**
| # | Header | Cell content & classes |
|---|---|---|
| 1 | **Docket** | `.queue__id` (mono, muted) → `#{id}` — the internal DB id in the list. |
| 2 | **Filed** | `.queue__when` → `<strong>{ago}</strong>` (relative, e.g. "3 days ago") over `<span>{dateTime}</span>` (absolute "22 Aug 2026, 3:36 pm"). |
| 3 | **What was reported** | `.queue__lead` (14.5px) = `summary_en \|\| raw_text` (**English leads in the queue** for scannability). Below it `.queue__original` (13px muted, `lang={r.language}`) = `raw_text` **only when it differs** from the summary (the citizen's own script). Then a `.tag-row`: sector `.tag--plain`, `<UrgencyTag>`, `<PhotoTag>`, `<ConfidenceTag>`. In the invalid feed, a `.triage-reason` block is appended with Gemini's reason. |
| 4 | **Place** | `.queue__place` → `r.place` (or muted "not stated"), then a `<span>` "{district}, {state}" **or** `.queue__nomatch` (red) "no district match". |
| 5 | **Arrived by** | `<ChannelTag>` (plain grey tag: WhatsApp / IVR call / Voice note / Web form / SMS). |
| 6 | **Status** *(header becomes **"Overrule"** in the invalid feed)* | Active/Cleared: `<StatusTag>` + optional muted "{n} replies". Invalid: a green `.btn--rescue.btn--sm` "✓ Mark as valid" (stops row-click propagation; shows "Restoring…"; per-row error under it). |

**Pager** (`.pager`, below the table): `display:flex; justify-content:space-between;
align-items:center; padding:12px 16px; border-top:1px solid var(--rule-soft)`. Left:
"Showing {offset+1}–{offset+rows}". Right: Previous / Next ghost buttons (page size
**40**; Next disabled when fewer than 40 rows returned).

**Tag components (`components/Tags.jsx`) — reproduce exactly:**
- `StatusTag`: `<span class="tag tag--status-{STATUS}">{Label}</span>`. CSS exists
  for `NEW`(red) `ACKNOWLEDGED`(amber) `IN_PROGRESS`(accent blue) `RESOLVED`(green)
  `REJECTED`(grey) `INVALID`(purple). *(Backend can also emit `UNDER_REVIEW`,
  `ASSIGNED`, `NEEDS_LOCATION`, which currently have no tag CSS → they'd render as
  the bare `.tag` base. A redesign should add styles for these.)*
- `UrgencyTag`: `tag tag--u{level}`; u1/u2 grey, u3 amber, u4/u5 red; words
  1 Routine / 2 Low / 3 Affects daily life / 4 Serious / 5 Immediate risk;
  `title="Urgency N of 5"`.
- `ChannelTag`: `tag tag--plain` with `channelLabel()`.
- `PhotoTag`: only if `has_photo`; `tag tag--photo` (purple); text "Photo read"
  (has description) vs "Photo, not read"; tooltip notes the image itself isn't
  stored.
- `ConfidenceTag`: only when `confidence < 0.5`; `tag tag--u3` (amber); "Unverified
  sector" when `≤0.15` (keyword fallback, no model) else "Low confidence 0.NN".

Base tag: `.tag { display:inline-block; font:500 11.5px; letter-spacing:.02em;
padding:2px 7px; border-radius:3px; border:1px solid transparent; white-space:nowrap }`.
`.ref` chip (tokens/ids): mono 12.5px, bg `#eef0f3`, `1px --rule` border, radius 3px,
`padding:1px 5px`.

### 4.2 Complaint detail view (`pages/RequestDetail.jsx`)
Route `/requests/:id`; data via `getRequest(id)` through `<Async>`.

- **"← Back to the queue"** link (`.back`, 13.5px).
- **`.page-head`**: `<h1>` leads with the **citizen's `track_token`** in mono
  `.docket__ref` (e.g. `JS-GDDV-TAXX`) — falling back to `Docket #{id}` — then
  ` — {sector}`. The lede shows `Internal ref #{id}` (`.docket__internal`,
  tabular-nums) · district,state · place. A `.tag-row` on the right carries Status,
  Urgency, Confidence.
- **`.case` — the two-column work area:**
  ```
  .case { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);
          gap:16px; align-items:start }
  @media (max-width:1080px){ .case { grid-template-columns:1fr } }   /* stacks */
  ```

**LEFT column (`.case__col`, the wider 1.55fr) — top to bottom:**
1. **"What the citizen reported"** panel. `panel__note` = "Spoken, transcribed by
   Gemini" for `voice`/`ivr`, else "As typed". Body: `.quote__label` "In their own
   words" then `.quote` (**17px, left border `3px --accent`, `lang={r.language}`**)
   = `raw_text \|\| transcript`. **This is the native-language primary view** — on
   the detail page the citizen's own words lead, the opposite of the queue.
   - Optional `.derived` block "Transcript" — shown only if `transcript` differs
     from `raw_text` (what Gemini *heard* vs the stored text).
   - Optional `.derived` block **"Summary in English — ours, not theirs"** — shown
     only if `summary_en` differs from `raw_text`. (`.derived` = `--surface-2` fill,
     `1px --rule-soft` border, radius 4px, `padding:12px 14px`, uppercase
     `.derived__label`.) This is the native-vs-English provenance the brief asks
     for: original and machine-summary are **separate documents, never merged.**
2. **`<EvidencePhoto>`** panel (only if `has_photo`). If `photo_stored`: an
   `<a class="evidence__frame">` wrapping `<img class="evidence__img">`
   (`max-height:320px; object-fit:contain` — evidence must not be cropped),
   opening full-size in a new tab; plus `.evidence__actions` with "Download as
   {token}" (filled) and "Open full size" (ghost). The download filename comes from
   the server's `Content-Disposition` (via `?download=1`), named after the tracking
   token. If not stored: a muted "attached, not retained / could not be loaded"
   message. Privacy note: only Gemini's *description* travels; the file is reachable
   solely through this console.
3. **Either `<TriagePanel>` (if `status === 'INVALID'`) or `<ReplyComposer>`** — see
   §4.3.
4. **"Replies sent"** panel → `<ResponseThread>` (§4.3).
5. **`<StatusControl>` "Move without replying"** panel — **hidden when INVALID.**

**RIGHT column (`.case__col`, the 1fr rail):**
1. **`<ProvenancePanel>`** — the source/channel dossier (§4.4).
2. **"Same reporter"** panel → `<ReporterHistory>`: other cases sharing the opaque
   `citizen_ref`, each a `.sib` row (`flex; justify-content:space-between`) linking
   to that case with its status tag + date. "First report" when none.

### 4.3 Interactive admin actions (the write surface)
> **RBAC reality:** every signed-in post can do all of the below. The session only
> supplies the default *issuing desk* and the opening state filter. There is no
> permission gating in the client, and the API is unauthenticated in this build
> (stated on the sign-in screen). Model the *seam* — `auth.js::signIn` returns a
> session; a real deployment swaps in the state's SSO — rather than inventing roles.

**(a) Reply — `<ReplyComposer>` → `POST /requests/{id}/responses`.** The primary
action; replaces the triage panel on valid cases. A `.composer` form:
- **"Your reply, in English"** — `<textarea rows=5>`, required, **min 5 chars**.
- **`.composer__grid`** (`grid-template-columns:minmax(0,1.4fr) minmax(0,1fr)`,
  stacks < 640px):
  - **"Issuing desk or role"** — text input, required, **2–128 chars**, defaults to
    `session.desk` (e.g. "Block Development Office, Nabarangpur"), **remembered per
    post** in `localStorage` under `jansetu.desk.{accountId}`. This is a **desk, not
    a person** (avoids officer PII; posts outlast people). *This field is the app's
    closest thing to "route to department".*
  - **"Move the case to"** — `<select>`; blank option = "Acknowledged (automatic)"
    when NEW, else "Leave as {status}"; explicit options `ACKNOWLEDGED, IN_PROGRESS,
    RESOLVED, REJECTED`.
- **Translate toggle** — a `.check`; shown only when the case language ≠ English;
  **on by default**: "Translate into {language} before delivery". English cases show
  a hint instead.
- **Submit** — `.btn` "Record reply" (→ "Recording…" while busy). Disabled until
  body ≥5 and desk ≥2. Copy is honest: replies are **queued, not sent** ("Queued
  for delivery over {channel}") because outbound WhatsApp/IVR need paid accounts.
- **Result notices** — `.notice.notice--ok` (translated / or "could not be
  translated — will go out in English, check GEMINI_API_KEY") or
  `.notice.notice--bad` on failure. A standing hint reminds that replies/status
  **never affect the analytics ranking**.
- On success it clears the body, remembers the desk, and calls `onPosted()` which
  **refetches** the case (so `response_count`, `status`, and the thread stay
  consistent — via `useApi.reload()`, which doesn't blank the screen).

**(b) Move without replying — `<StatusControl>` → `PATCH /requests/{id}/status`.**
A quieter panel below the composer: a `.btn-row` of ghost buttons for every status
**except the current one and NEW** (so: Acknowledged / In progress / Resolved /
Rejected). For duplicates or cases closed by another department; the citizen is
**not** notified. Hidden entirely on INVALID cases.

**(c) Overrule triage / "Mark as valid" — → `PATCH /requests/{id}/restore`.** The
only green (`--rescue`) action. Two entry points: the per-row button in the invalid
queue table, and `<TriagePanel>` on an INVALID case detail (which shows Gemini's
reason + explanation and replaces the composer/status controls). The backend
**refuses anything not INVALID (409)**, so a mis-click can't reopen finished work;
on success the row rejoins the working queue as NEW and both the queue and the tab
counts reload. `triage_reason` is intentionally retained on the row after restore.

There are **no** other write actions — no delete, no assignment/routing workflow,
no priority/urgency editing, no bulk actions. Analytics (hotspots,
recommendations, priority scores) is a **separate, read-only** citizen-side app and
is never reachable or writable from this console.

### 4.4 Provenance panel (`components/ProvenancePanel.jsx`) — the "four questions"
A right-rail `.panel` answering *what / where / when / from whom*. Body is a
definition list (`.rows` → repeated `.row { display:grid;
grid-template-columns:128px minmax(0,1fr); gap:12px; padding:9px 0;
border-bottom:1px solid --rule-soft }`, key `.row__k` uppercase muted, value
`.row__v`, with `.row__v small` for sub-notes). Rows, in order:
- **Filed** — absolute datetime + relative `ago`.
- **Arrived by** — `<ChannelTag>` + a plain-language `channelNote` (e.g. "Spoken on
  a phone call from a feature phone").
- **Filed in** — language name (+ whether it was translated to English for the
  screen).
- **Sector** — `sectorLabel`.
- **People affected** — only if `affected_estimate` present ("as stated…, not an
  estimate of ours").
- **Reported place** — `r.place` + the scrubbed hierarchy levels (Ward/Locality/
  City/State/PIN) that exist, joined by " · ".
- **Matched to** — either "{district}, {state}" + the **LGD district code** in a
  `.ref` chip, **or** a loud `.queue__nomatch` "Not matched to a district" with a
  note that the row is counted nowhere in the national ranking.
- **Reporter** — the opaque `citizen_ref` in a `.ref` chip (or "none recorded").

If a photo exists, a `.derived` block repeats Gemini's image description. A closing
`.privacy` box (accent-soft, `1px #cfe0ef`) states plainly what the console
**cannot** show: the reporter ref is a one-way HMAC; no name/phone/address/device
exists on the record; place is held to ward level; replies route by ref via the
channel adapter without anyone here learning the identity.

### 4.5 Loading / empty / error (`components/States.jsx`)
`<Async>` renders one of: `<Loading>` (a `.spinner` — 22px accent-topped ring,
`@keyframes spin`, slowed under `prefers-reduced-motion`), `<ErrorState>`
(`.state--error`, red title, the actual message **plus the API base URL** so a
down backend is obvious), `<Empty>` (serif title + body), or `children(data)`.
`.state` = centered, `padding:40px 22px`.

---

## 5. Data Models Expected by the Admin UI

All shapes below are the **exact API contract** (FastAPI/Pydantic) the console
consumes. Field names are what the JSX reads.

### 5.1 Complaint — list row (`GET /requests` → `CitizenRequestOut[]`)
```jsonc
{
  "id": 636,                        // internal DB id; shown as "#636" in Docket col
  "district_code": "OD_NABARANGPUR",// LGD-style key (null if unmatched)
  "district": "Nabarangpur",        // authoritative district name (null if unmatched)
  "state": "Odisha",                // (null if unmatched)
  "district_label": "Raigad (Navi Mumbai)", // display string: official + citizen's named place
  "category": "WATER_SUPPLY",       // enum code; UI labels via sectorLabel()
  "urgency": 4,                     // 1..5
  "summary_en": "Borewell dry for three weeks in ward 4.", // machine English summary
  "language": "or",                 // short language code (drives lang= + translation copy)
  "channel": "whatsapp",            // voice | text | whatsapp | sms | ivr
  "created_at": "2026-08-22T10:06:28.683835", // naive UTC (frontend appends 'Z')
  "raw_text": "…",                  // citizen's own words, untranslated (native script)
  "confidence": 0.83,               // 0..1; ConfidenceTag shows when < 0.5
  "place": "Ward 4, Kosagumuda",    // scrubbed, never finer than ward (may be null)
  "location": {                     // structured place; see LocationHierarchy (5.5)
    "state": "Odisha", "district_or_city": "Nabarangpur",
    "locality": "Kosagumuda", "sector_or_ward": "Ward 4", "pin_code": null
  },
  "image_verification": "A hand-pump…", // Gemini's photo description (null if none)
  "has_photo": true,                // a photo was submitted (even if unreadable)
  "photo_stored": true,             // bytes are on file at /requests/{id}/photo
  "track_token": "JS-GDDV-TAXX",    // citizen's bearer tracking ref (null on older rows)
  "citizen_ref": "c1a2…",           // opaque one-way HMAC reporter handle (null-able)
  "status": "NEW",                  // see enum in 5.6
  "triage_reason": null,            // one-sentence reason when status = INVALID
  "response_count": 0,              // number of official replies (list convenience)
  "submission_group_id": null,      // shared when one message split into many issues
  "issue_index": 1,                 // 1-based position within its submission
  "issue_count": 1,                 // >1 → UI could show "Part 1 of 2"
  "title": null,                    // short issue label (optional)
  "location_status": "RESOLVED",    // RESOLVED | UNRESOLVED | MISSING
  "clarification_question": null
}
```
The raw, verbatim citizen location line is **deliberately not in this response**
(privacy boundary at the read model). `q=` search covers `raw_text`, `summary_en`
and the scrubbed place levels only.

### 5.2 Complaint — detail (`GET /requests/{id}` → `RequestDetail`)
Everything in 5.1 **plus**:
```jsonc
{
  "affected_estimate": 300,         // people affected, if the citizen stated it (null-able)
  "transcript": "…",                // what Gemini heard (voice/ivr); may differ from raw_text
  "responses": [ /* ResponseOut, see 5.3 */ ],
  "from_same_reporter": [ /* SiblingRequest, see 5.4 */ ]
}
```

### 5.3 Official reply (`ResponseOut`; array on detail; single on POST)
```jsonc
{
  "id": 12,
  "request_id": 636,
  "body_en": "A repair crew is scheduled for Thursday.",
  "body_native": "…",          // translated delivery text; NULL = went out untranslated
  "language": "or",
  "responder_desk": "Water Resources Desk, Nabarangpur", // a role, never a person
  "status_before": "NEW",
  "status_after": "ACKNOWLEDGED",
  "delivery_channel": "whatsapp",
  "delivery_state": "queued",  // "queued" = stored, ready for adapter (never claims "delivered")
  "created_at": "2026-08-22T11:00:00Z"
}
```
`POST /requests/{id}/responses` body (`ResponseIn`):
`{ body_en (≥5), responder_desk (2..128), new_status?: <RequestStatus>, translate: true }`.

### 5.4 Sibling request (`from_same_reporter[]`, `SiblingRequest`)
```jsonc
{ "id": 640, "category": "WATER_SUPPLY", "urgency": 3, "status": "IN_PROGRESS",
  "summary_en": "…", "created_at": "…" }
```

### 5.5 Location hierarchy (`location`) — max granularity is ward, by design
```jsonc
{ "state": null, "district_or_city": null, "locality": null,
  "sector_or_ward": null, "pin_code": null }   // no field exists below ward
```

### 5.6 Status enum (`status`) & other closed sets
- **`RequestStatus`**: `NEW`, `ACKNOWLEDGED`, `UNDER_REVIEW`, `ASSIGNED`,
  `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `INVALID`, `NEEDS_LOCATION`.
  - *Open* = NEW/ACKNOWLEDGED/UNDER_REVIEW/ASSIGNED/IN_PROGRESS.
  - *Closed* = RESOLVED/REJECTED. *Not actionable / hidden by default* = INVALID,
    NEEDS_LOCATION. The current UI actively renders/handles NEW, ACKNOWLEDGED,
    IN_PROGRESS, RESOLVED, REJECTED, INVALID; UNDER_REVIEW/ASSIGNED/NEEDS_LOCATION
    exist in the contract but have no dedicated tab or tag styling yet.
- **`Channel`**: `voice`, `text`, `whatsapp`, `sms`, `ivr`.
- **`urgency`**: integer 1–5.
- **`location_status`**: `RESOLVED` | `UNRESOLVED` | `MISSING`.
- `PATCH /requests/{id}/status` body: `{ "status": <RequestStatus> }`.
- `PATCH /requests/{id}/restore`: no body; **409** unless the row is INVALID.

### 5.7 Header stats (`GET /requests/stats` → `RequestStats`)
```jsonc
{
  "total": 612,
  "open": 138,
  "awaiting_first_reply": 47,          // card 1 ("Action required")
  "by_status": { "NEW": 47, "ACKNOWLEDGED": 20, "UNDER_REVIEW": 0, "ASSIGNED": 0,
                 "IN_PROGRESS": 71, "RESOLVED": 300, "REJECTED": 120,
                 "INVALID": 40, "NEEDS_LOCATION": 14 }, // every status present, zero-filled
  "by_channel":  { "whatsapp": 260, "voice": 150, "text": 110, "ivr": 61, "sms": 31 },
  "by_language": { "hi": 210, "or": 120, "…": 0 },
  "by_urgency":  { "1": 40, "2": 90, "3": 180, "4": 200, "5": 102 },
  "filed_last_7_days": 33,             // card 4
  "oldest_open_days": 42.0,            // card 2 (null when nothing open)
  "status_order": [ "NEW", "ACKNOWLEDGED", "…" ]   // canonical display order
}
```
Accepts `?state=` and `?category=` only. Tab counts derive from `by_status`.

### 5.8 Reference vocabulary (populate the filter dropdowns)
- **`GET /states`** → `["Odisha", "Bihar", …]` (string array).
- **`GET /capabilities`** → `{ "languages": [ { "code": "or", "name": "Odia",
  "native": "ଓଡ଼ିଆ" }, … ], "categories": ["WATER_SUPPLY", "SANITATION", …] }`.
  `languageName(languages, code)` renders `name (native)`.

### 5.9 `GET /requests` query parameters (filters → API)
`state`, `district_code`, `category`, `language`, `channel`,
`status` (**repeatable**: `?status=RESOLVED&status=REJECTED`), `citizen_ref`,
`min_urgency` (1–5), `unanswered` (bool), `q` (≥2 chars),
`limit` (default 60 in client / 100 server, ≤1000), `offset`. Empty values are
dropped client-side. Results are always **newest first**
(`created_at desc, id desc`). Omitting `status` yields the working queue, which
**excludes INVALID and NEEDS_LOCATION** unless asked for by name.

---

## Appendix A — File inventory (what to reconstruct)
```
frontend-admin/
├─ index.html                      # title, #root, no webfont
├─ vite.config.js                  # port 5174, react plugin, dist/no-sourcemap
├─ package.json                    # React 19.2.8, react-router-dom 7.18.2, Vite 8.2.2
└─ src/
   ├─ main.jsx                     # StrictMode + BrowserRouter + <App/>
   ├─ App.jsx                      # shell (topbar/main/foot) + auth gate + 3 routes
   ├─ api.js                       # every backend call (fetch), timeouts, ApiError
   ├─ auth.js                      # demo gate: 3 accounts, DEMO_PASSWORD, sessionStorage
   ├─ styles/console.css           # the ENTIRE design system (~1,490 lines)
   ├─ pages/
   │  ├─ SignIn.jsx                # two-panel gate (.gate)
   │  ├─ RequestQueue.jsx          # KPIs + tabs + filters + table + pager
   │  └─ RequestDetail.jsx         # 2-col case view; TriagePanel & StatusControl live here
   ├─ components/
   │  ├─ StatsBar.jsx              # 5 KPI cards
   │  ├─ QueueFilters.jsx          # the filter row
   │  ├─ Tags.jsx                  # Status/Urgency/Channel/Photo/Confidence tags
   │  ├─ ProvenancePanel.jsx       # source/where/who dossier + privacy box
   │  ├─ ReplyComposer.jsx         # POST reply (desk, status, translate)
   │  ├─ ResponseThread.jsx        # replies (English + native, delivery state)
   │  ├─ ReporterHistory.jsx       # siblings by citizen_ref
   │  ├─ EvidencePhoto.jsx         # inline photo + download-as-token
   │  ├─ States.jsx                # Loading / Empty / ErrorState / Async
   │  └─ Logo.jsx                  # raster logo.png → inline SVG fallback
   ├─ hooks/
   │  ├─ useApi.js                 # loading/refreshing/error/data + race guard
   │  └─ useReference.js           # cached /states + /capabilities; languageName()
   └─ lib/
      └─ format.js                 # num, dateTime, ago, sectorLabel, statusLabel,
                                    #  urgencyLabel, channelLabel/Note, parseUtc
```

## Appendix B — Sign-in gate (`pages/SignIn.jsx` + `.gate`)
A full-height 2-column grid `grid-template-columns:minmax(0,0.9fr)
minmax(0,1.1fr)`; **below 900px the left panel is dropped entirely** (not stacked)
and only the form shows.
- **Left `.gate__aside`** (slate, CSS-only starfield gradient): the `<Logo>` with
  wordmark; a *claim* (not a testimonial) — "The districts that need the most file
  the fewest complaints…"; a 3-item `.gate__points` list; a track footer.
- **Right `.gate__panel`** (white, centered, max-width 420): wordmark lockup;
  "Sign in to your post" (`.gate__title`, 29px serif); Post ID + Password fields;
  submit; then **`.gate__accounts`** — three clickable `.gate__acct` cards
  (one click fills both fields); then a `.gate__disclaimer` (amber) stating this is
  a demo gate, not authentication.
- **Accounts** (`auth.js`, RBAC-lite): `bdo.nabarangpur` (Odisha),
  `phed.sitamarhi` (Bihar), `state.cell` (all states). Shared password
  `jansetu@2026`. Session = `{id, post, desk, state, since}` in **`sessionStorage`**
  (closing the tab signs out). The state on the session is only the queue's opening
  filter — **not** an access boundary.

## Appendix C — Formatting rules (`lib/format.js`) to preserve
- **`parseUtc`**: SQLite returns naive UTC (`2026-08-22T10:06:28`); the code
  appends `Z` when no offset is present, else ages are off by the local TZ. Any
  reconstruction must do the same.
- `num` → `Intl.NumberFormat('en-IN')`. `dateTime` → "22 Aug 2026, 3:36 pm";
  `dateOnly` → "22 Aug 2026". `ago` → "just now / N min / N hr / N day(s) / N
  month(s) / N.N yr ago".
- `sectorLabel`/`statusLabel`: `SNAKE_CASE` → sentence case. `urgencyLabel`:
  1 Routine…5 Immediate risk. `channelLabel`: voice→Voice note, text→Web form,
  whatsapp→WhatsApp, sms→SMS, ivr→IVR call.

---

### One-paragraph brief for the redesign AI
Rebuild a **three-region flex-column shell** (dark slate top bar, 1400px-centered
white-on-paper main, privacy footer — **no sidebar**) hosting exactly two screens: a
**queue/dashboard** (five hairline-divided KPI cells → three folder tabs
Active/Cleared/Invalid → a wrap-flex filter row → a dense six-column clickable table
with semantic status/urgency/channel tags → prev/next pager) and a **two-column case
view** (left: citizen's own words first + English summary as a separate "derived"
block + evidence photo + reply composer/triage + reply thread + bare status control;
right: provenance dossier + same-reporter list). Use the exact token palette in §2.2
(neutral ink scale, one accent blue `#1f4e79`, red only for "act now", purple for
spam/invalid, green only for the rescue button), system serif for headings and
system mono for tokens, and a plain-`fetch` data layer against the endpoints in
§1.5 returning the shapes in §5. There is no real auth, no per-role permissions, and
no department-routing widget — only reply (with a free-text issuing desk), status
change, and restore-from-invalid.
