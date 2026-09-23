# JanSetu (जनसेतु) — GitHub Publishing & Release Guide

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

> [!WARNING]
> **STRICT LOCAL-ONLY AUDIT LOCK NOTICE**  
> This guide contains non-executed manual commands for future repository publication. During the current automated audit task, no remote repository creation, credential authentication, staging, committing, or pushing has been performed. All steps below are for the repository owner to execute manually when authorized.

---

## 📋 Recommended Repository Details

- **Recommended Repository Name**: `jansetu`
- **Acceptable Alternative Name**: `jansetu-digital-public-infrastructure`
- **Default Branch**: `main`
- **Visibility**: `Public` (Recommended for open Digital Public Goods / Hackathon Review) or `Private` (with explicit collaborator access granted to event judges).

---

## 🛡 Pre-Publication Safety & Compliance Checklist

Before running any Git staging or publishing commands, manually verify:

1. [ ] **No Secrets in Staged Diff**: Verify that `.env`, API keys (`GEMINI_API_KEY`, `EXOTEL_API_KEY`), and service account JSONs are absent.
2. [ ] **No Citizen PII**: Verify that `data/evidence/` contains only sample files and no real citizen phone numbers exist in tracked files.
3. [ ] **Database Excluded**: Verify that `*.db` / `jansetu.db` is ignored by `.gitignore`.
4. [ ] **Archive Folder**: Confirm `_archive_unwanted_files/` contains only historical reference material and is documented in `_archive_unwanted_files/ARCHIVE_MANIFEST.md`.
5. [ ] **Builds & Tests Pass**:
   - Backend tests: `pytest -q` (280 passing).
   - Citizen frontend build: `npm run build --prefix frontend-citizen`.
   - Officials console build: `npm run build --prefix frontend-admin`.

---

## 💻 Future Manual Publication Steps (For User Execution)

> [!CAUTION]
> **FUTURE MANUAL STEP — DO NOT RUN AUTOMATICALLY**  
> Execute these commands only when you are ready to publish the repository to your GitHub account.

### Step 1: Review Working Tree Status
```bash
git status
```

### Step 2: Stage Verified Repository Files
```bash
git add .
git status
```

### Step 3: Create Initial Release Commit
```bash
git commit -m "feat: initial release of JanSetu — AI for Digital Public Infrastructure and Governance"
```

### Step 4: Create Remote Repository on GitHub (Using GitHub CLI or Web UI)
Using GitHub CLI (`gh`):
```bash
gh repo create jansetu --public --source=. --remote=origin --description "JanSetu — AI for Digital Public Infrastructure and Governance"
```

*Or manually add your remote:*
```bash
git remote add origin https://github.com/<your-github-username>/jansetu.git
```

### Step 5: Push Main Branch to GitHub
```bash
git push -u origin main
```

---

## 🔒 Security Best Practices
- Never paste API keys into Git commit messages or public issue trackers.
- Always use environment variables in deployment environments.
- Rotate your `GEMINI_API_KEY` if it was ever exposed in any public terminal or environment.
