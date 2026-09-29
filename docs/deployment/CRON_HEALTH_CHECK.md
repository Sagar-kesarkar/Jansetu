# Scheduled backend health check

Prepared at the user's request. Publication is now authorised; the job stays
inactive until its deployed URL, expiry and enable flag are configured.
Workflow: `.github/workflows/backend-health.yml`.

The workflow checks the Render API's existing `/health` endpoint every 10 minutes
(minutes 7, 17, 27, 37, 47 and 57 UTC). Actual GitHub execution times remain best effort. It requires HTTP 200 and JSON `status: ok`.
This is a read-only server check, not a database backup or an AI/complaint request.
There is no repository checkout and no GitHub token permission is granted.

## Activate after deployment and explicit Git publication approval

1. Confirm the repository is public. The workflow skips private repositories to
   avoid consuming paid/private Actions minutes.
2. Publish the workflow on the repository's default branch with the approved release.
3. In GitHub Settings > Secrets and variables > Actions > Variables, set:
   - `BACKEND_HEALTH_URL`: actual `https://SERVICE.onrender.com/health` URL.
   - `BACKEND_HEALTH_UNTIL`: competition end as an ISO timestamp with a timezone,
     for example the actual date/time followed by `+05:30` for India time.
   - `BACKEND_HEALTH_ENABLED`: `true`.
4. Use Actions > Backend health check > Run workflow for the first live test.
   Verify a green result and the Render service logs before relying on it.
5. At competition end set enabled to `false` or disable the workflow in Actions.
   The expiry also prevents further HTTP requests, even if the schedule remains.

No Render/Netlify password, database URL, cookie secret or Gemini key is needed.
Failed health checks appear as failed workflow runs; notifications follow the
repository owner's existing GitHub notification preferences.

## Practical limits

Render native Cron Jobs have a $1 minimum monthly service charge, so none was
created. Standard GitHub-hosted Actions runners are free for public repositories.
GitHub schedules are best effort: jobs can be delayed or dropped under load, and
public repository schedules can be disabled after 60 days without activity.
Consequently this can reduce idle gaps but cannot guarantee an always-awake server.

Render running hours count toward the workspace's 750 monthly free hours, shared
across free web services. Do not assume several services can all remain awake for
free. Render filesystem persistence and database expiry are unchanged by this job.
The health route only proves that the HTTP process responds; it does not verify
database storage, photo retention, Gemini or provider delivery.

Sources checked:
- [Render Cron Jobs pricing](https://render.com/docs/cronjobs)
- [Render Free limits](https://render.com/docs/free)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
