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
# Reference + synthetic data ships in the image so a fresh deploy has data on
# first boot with no separate database provisioning step.
COPY data ./data

# Seed at build time: SQLite file is baked in, so cold starts are instant and
# the free-tier container needs no writable volume.
RUN python -m app.db.seed

EXPOSE 8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
