.PHONY: help install seed dev api web admin ivr test build deploy deploy-gcp-billed

help:
	@echo "install          - backend + frontend-citizen + admin deps"
	@echo "seed             - build reference data and synthetic multilingual requests"
	@echo "api              - run FastAPI on :8080"
	@echo "web              - run Citizen Web App on :5173"
	@echo "admin            - run Officials Console on :5174"
	@echo "ivr              - run interactive IVR Telephony Simulator CLI"
	@echo "test             - run backend tests"
	@echo "build            - production build of citizen and admin frontends"
	@echo "deploy           - deployment pending; see docs/deployment/DEPLOYMENT.md"
	@echo "deploy-gcp-billed- Cloud Run + Firebase. Needs a GCP billing account; NOT the"
	@echo "                   documented route, kept only as an upgrade path."

install:
	cd backend && pip install -r requirements.txt
	cd frontend-citizen && npm install
	cd frontend-admin && npm install

seed:
	cd backend && python -m app.db.seed

api:
	cd backend && uvicorn app.main:app --reload --port 8080

web:
	cd frontend-citizen && npm run dev

admin:
	cd frontend-admin && npm run dev

ivr:
	cd backend && python -m app.channels.simulator

test:
	cd backend && pytest -v

build:
	cd frontend-citizen && npm run build
	cd frontend-admin && npm run build

# The recommended route is deliberately not a one-shot script: both Hugging Face
# Spaces and Netlify want an interactive login the first time, and a Makefile
# target that half-works is worse than instructions that are read.
deploy:
	@echo "Deployment is deferred; see docs/deployment/DEPLOYMENT.md."
	@echo "Backend hosting has not been selected."
	@echo "frontend-citizen hosting on Netlify is planned for later."
	@echo "Do not run legacy billed deployment scripts."

# Retained for completeness. Cloud Run's free tier still requires a billing
# account on file, which is why it is not the default target.
deploy-gcp-billed:
	bash infra/deploy_backend.sh
	bash infra/deploy_frontend.sh
