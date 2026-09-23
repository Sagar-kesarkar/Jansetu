# Contributing to JanSetu (जनसेतु)

Thank you for your interest in contributing to **JanSetu — AI for Digital Public Infrastructure and Governance**!

---

## 🛠 Local Development Setup

1. **Prerequisites**:
   - Python 3.12+
   - Node.js 20+ and npm
   - Optional: Google AI Studio API key for live Gemini structuring.

2. **Backend Setup**:
   ```bash
   python -m venv .venv
   # Windows (PowerShell): .venv\Scripts\Activate.ps1
   # Linux/macOS: source .venv/bin/activate
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --port 8080 --reload
   ```

3. **Citizen Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Officials Console Setup**:
   ```bash
   cd frontend-admin
   npm install
   npm run dev
   ```

---

## 🧪 Testing & Validation

Before submitting changes, ensure all tests and builds pass:

```bash
# Run backend test suite (280 tests)
cd backend
pytest -v

# Run frontend builds
cd ../frontend && npm run build
cd ../frontend-admin && npm run build
```

---

## 📜 Code Style & Principles

- **Zero PII**: Never commit raw citizen contacts, phone numbers, or private keys.
- **Multilingual Support**: Ensure new features support all 13 Indian languages.
- **Explainable Analytics**: Keep scoring algorithms deterministic and auditable.
