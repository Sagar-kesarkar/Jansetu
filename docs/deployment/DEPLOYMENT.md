# JanSetu (जनसेतु) — Deployment & Production Setup Guide

This guide covers deployment strategies for JanSetu on containerized infrastructure (Docker / Kubernetes) and cloud platforms.

---

## 🐳 Docker Container Deployment

The backend contains a production-ready multi-stage Dockerfile (`backend/Dockerfile`).

### Build & Run Backend Container:
```bash
cd backend
docker build -t jansetu-backend:latest .
docker run -d -p 8080:8080 \
  -e GEMINI_API_KEY="your_ai_studio_key" \
  -e DATABASE_URL="sqlite:///./jansetu.db" \
  -e CORS_ORIGINS="https://citizen.jansetu.gov.in,https://admin.jansetu.gov.in" \
  --name jansetu-api jansetu-backend:latest
```

---

## 🌐 Production Architecture & Database Migration

For enterprise deployments:
1. **Database**: Switch from SQLite to Managed PostgreSQL:
   ```ini
   DATABASE_URL=postgresql://user:password@pg-host:5432/jansetu
   ```
2. **Migrations**: Apply Alembic migrations on startup:
   ```bash
   alembic upgrade head
   ```
3. **CORS & Domain Security**: Set explicit allowed origins in `.env`:
   ```ini
   CORS_ORIGINS=https://citizen.example.org,https://admin.example.org
   ```
4. **HTTPS & Reverse Proxy**: Deploy behind NGINX, Cloudflare, or AWS ALB with TLS termination.

---

## 📞 Channel Webhook Configuration

### Meta WhatsApp Cloud API:
1. Configure webhook URL: `https://api.yourdomain.com/channels/whatsapp/webhook`
2. Set verify token in `.env`: `WHATSAPP_VERIFY_TOKEN=your_secure_random_token`
3. Subscribe to `messages` event.

### Exotel IVR & SMS:
1. Point inbound IVR Applet to: `https://api.yourdomain.com/channels/ivr/event`
2. Configure SMS incoming callback: `https://api.yourdomain.com/sms/incoming`
3. Provide DLT Entity and Template IDs in `.env` for Indian regulatory compliance.
