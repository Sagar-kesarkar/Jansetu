# Netlify frontend deployment

Repository: https://github.com/Sagar-kesarkar/Jansetu

Backend hosting has not been selected. Netlify hosts only the two static React
websites; it does not run the FastAPI server or SQLite database.

## Citizen website

Import this repository into Netlify using branch `main`. The root `netlify.toml`
sets base directory `frontend-citizen`, build command `npm run build`, publish directory
`dist` (relative to the base), and Node.js 22. SPA redirects support deep links.

## Officials website

Create a second Netlify site using the same repository and branch. Set its base
directory to `frontend-admin` and use `frontend-admin/netlify.toml`. Its build
command is `npm run build`, and publish directory is `dist` relative to that base.

## Connect the backend later

Set `VITE_API_BASE` on both Netlify sites to the selected backend's public HTTPS
URL, then rebuild both sites. This value is embedded at build time. Without it,
the current clients default to localhost:8080; the static websites can build but
live intake, tracking, casework and dashboards require the backend.

Configure backend CORS to allow the actual origins of both deployed sites.
Keep `GEMINI_API_KEY`, channel credentials, and the HMAC secret exclusively on
the backend. Never put secrets in `VITE_*` variables, which are public.

The officials sign-in is a demo gate, not production authorization. Before
connecting real citizen data, implement backend-enforced access controls.

## Repository contents

Source code, lockfiles, migrations, tests, documentation, reference/demo datasets,
and reusable IVR prompt audio are retained. Local credentials, databases, citizen
evidence, build outputs, dependencies, logs, editor settings, internal handoff
prompts and archive files are excluded. IVR prompt audio is application content,
not a citizen recording.
