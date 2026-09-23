# Deploying JanSetu for free

The hackathon requires a live deployed link. All three routes below cost
nothing. Pick one, get the URL into the submission form, then stop touching it.

## Recommended: Hugging Face Spaces (backend) + Netlify (frontend)

Genuinely free, no credit card, no billing account.

**Backend** — Spaces runs a Dockerfile directly:

1. Create a Space at huggingface.co/new-space, SDK = Docker, hardware = free CPU basic.
2. Push this repo to it. Spaces looks for `Dockerfile` at the root, so either
   move `backend/Dockerfile` to the root or add a root Dockerfile that copies it.
3. Add `GEMINI_API_KEY` under Settings → Variables and secrets → *Secrets*.
4. Spaces serves on port 7860 by default — set `PORT=7860` as a variable, or
   leave 8080 and add `app_port: 8080` to the Space README frontmatter.

**Frontend** — `netlify deploy --prod --dir=frontend/dist` after `npm run build`,
or connect the repo in the Netlify UI. Set `VITE_API_BASE` to the Space URL.

## Alternative: Firebase Hosting (frontend) + Cloud Run (backend)

Firebase Hosting's Spark plan is free. Cloud Run has a perpetual free tier
(2M requests/month) but **requires a billing account on file** even though you
will not be charged at demo volume. If you have the $300 new-account credit,
this is the tidiest option and is on-theme for a Google track.

```bash
bash infra/deploy_backend.sh    # Cloud Run
bash infra/deploy_frontend.sh   # Firebase Hosting
```

## Simplest: Render free tier

Connect the repo, choose Docker, add `GEMINI_API_KEY`. Free instances sleep
after 15 minutes of inactivity and take ~50s to wake. Acceptable, but hit the
URL once right before a judge opens it.

## What NOT to use

Cloud Speech-to-Text, Cloud Translation, Google Maps and BigQuery are all
billed. This project deliberately avoids every one of them — Gemini covers the
AI, Leaflet + OpenStreetMap covers the map, SQLite covers storage. The only
credential the app needs is a free AI Studio key.
