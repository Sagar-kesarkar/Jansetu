# Build from the REPOSITORY ROOT, not from backend/:
#   docker build -f backend/Dockerfile -t jansetu-api .
# The data/ directory has to be inside the build context, and Docker cannot
# COPY from a parent path.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# Only application reference/demo assets belong in the image. Never copy uploads.
COPY data/reference ./data/reference
COPY data/synthetic ./data/synthetic
COPY data/ivr_prompts ./data/ivr_prompts

# Include migration tooling for controlled upgrades after storage is configured.
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
# Do not bake a disposable SQLite database into a deployment image or connect to
# the live database during builds. Provision storage and seed once at release time.

EXPOSE 8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
