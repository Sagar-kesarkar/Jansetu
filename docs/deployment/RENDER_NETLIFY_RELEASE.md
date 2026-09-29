# Render and Netlify release preparation

Started 29 September 2026. Commit, push and deployment have now been explicitly
authorised after validation. No hosting service has been created yet.
This is a release worksheet, not a claim that
the app is deployment-ready.

## Proposed topology and open choices

Render Free runs FastAPI. Netlify runs the citizen site and, if wanted, a separate
officials demo site. Store complaints, quota identities and duplicate fingerprints
in external PostgreSQL; retain photographs in durable object storage. Existing
SQLite and file evidence remain suitable for local development only.

The free Render web filesystem is ephemeral, including on spin-down. Free Render
Postgres expires after 30 days. Confirm the competition date before considering
that database; an external free PostgreSQL service is another option. A keep-alive
job does not solve persistence. A disabled-by-default GitHub Actions health check
is now prepared; see [cron setup and activation](CRON_HEALTH_CHECK.md).

The user has confirmed that Render and Netlify accounts are ready and that no
custom domain is available. Use a solution compatible with provider domains;
competition deadline and live service URLs are still pending.

Requested Netlify project names: `jansetuu` for the citizen website and
`jansetuadmin` for the officials console. Intended URLs are
`https://jansetuu.netlify.app` and `https://jansetuadmin.netlify.app`, subject to
Netlify name availability. Neither name has been reserved or verified yet.
Use Brave, as explicitly confirmed by the user, for dashboard work; the current
automation connection cannot control Brave. Do not use the in-app browser instead.

The funds coverage model mismatch has now been repaired locally. Four regression
cases plus the existing funds API tests passed (11 total). This does not constitute
verification of the hosted release.

Prefer HTTPS sibling custom domains for the website and API: this avoids relying
on third-party cookies and permits direct long-running AI requests. With only
netlify.app/onrender.com domains, cross-site cookies may be blocked. A Netlify
same-origin proxy fixes that cookie relationship but has a 26-second timeout;
the current client permits 90-second AI requests. That path requires an asynchronous
submission/status flow or another verified transport before release. Do not silently
route the current synchronous submission through a proxy and claim it is reliable.

## Concrete work before provisioning

1. Confirm existing hosting accounts, competition date and domain availability.
2. Choose database and photo storage. Add the PostgreSQL driver and storage adapter,
   then test actual PostgreSQL migrations, concurrent daily limits and photo recovery.
   The current requirements do not include a PostgreSQL driver.
3. Complete the domain/cookie transport above. Require HTTPS cookie security, stable
   SUBMISSION_SECRET and CITIZEN_REF_SALT, exact CORS origins and backend-only keys.
4. Smoke-test the competition's
   main screens with reference data. Use only synthetic demo cases: officials API
   access is not authenticated by the current browser-only demo sign-in.
5. Build and run the deployment image locally. The Dockerfile now excludes uploaded
   evidence explicitly, includes migrations and no longer seeds SQLite during build.
   The root .dockerignore excludes credentials, local databases and preview data.
6. Prepare a final local diff and ask for explicit commit/push approval. The previous
   baseline remains aa99ea7d841eca7871cf4b55215d20e3f501f217. Do not overwrite it.

## Render settings once the release is ready

| Setting | Value |
| --- | --- |
| Service | Web service, Free instance |
| Runtime | Docker |
| Dockerfile | backend/Dockerfile |
| Build context | Repository root |
| Health path | /health |
| Auto deploy | Off during competition preparation |
| Port | Supplied by Render; existing Docker command uses PORT |
| DATABASE_URL | External PostgreSQL URL using the installed SQLAlchemy driver |
| SUBMISSION_SECRET | Stable private random value of at least 32 characters |
| CITIZEN_REF_SALT | Separate stable private random value |
| SUBMISSION_COOKIE_SECURE | true |
| SUBMISSION_COOKIE_SAMESITE | lax for verified same-site domain arrangement |
| DAILY_SUBMISSION_LIMIT | 6 |
| CORS_ORIGINS | Exact citizen and officials HTTPS origins |
| PUBLIC_BASE_URL | Actual API HTTPS origin |
| OFFICIALS_CONSOLE_ORIGIN | Actual officials site HTTPS origin |

Set Gemini credentials only in backend settings if using live AI. Do not paste
secrets into chat, Git, Docker build arguments or VITE_* variables. Domain names
and provider resource names remain unset until accounts and routing are confirmed.

## Netlify and live acceptance

Preparation checks: `git diff --check` passed, migration/config copy sources exist,
and nothing is staged. Docker is not available on this shell's PATH, so the changed
image has not been built or run locally. The earlier 311 backend and 9 frontend
test results cover the feature code, not a hosted release or this container image.

Use the existing citizen root netlify.toml and separate officials configuration.
Set VITE_API_BASE to the chosen HTTPS API URL at build time. Freeze the selected
release commit and disable automatic publication while reviewing release candidates.

After provisioning, seed approved reference/synthetic data once, then verify:
cookie accept/decline; text and photo submission; six-used limit; exact duplicates;
closure and resubmission; tracking; admin demo workflow; restart persistence for
both cases and photos; a first request after Render sleeps; and slow AI responses.
Take a database backup before schema upgrades. Keep the local baseline available.

## Sources checked

- [Render free service behaviour and database expiry](https://render.com/docs/free)
- [Render deployment lifecycle](https://render.com/docs/deploys)
- [Netlify proxy timeout](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/)
- [Render service configuration](https://render.com/docs/blueprint-spec)
