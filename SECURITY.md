# Security Policy & Privacy Architecture

JanSetu is designed as Digital Public Infrastructure (DPI) with strict privacy and security principles.

---

## 🔒 Zero-PII Guarantees

1. **No Raw Phone Numbers or Personal Contacts**:
   - Inbound telephony and messaging identifiers (WhatsApp numbers, SMS caller IDs, IVR CLIs) are hashed immediately upon ingress using HMAC-SHA256 with a private server-side salt.
   - Database tables store only opaque identifiers (e.g., `anon_8697ac2b65bd707b...`).
2. **Accountless High-Entropy Tracking**:
   - Tracking tokens (`JS-XXXX-XXXX`) use a 30-character unambiguous alphabet ($30^8 \approx 6.56 \times 10^{11}$ combinations) and cannot be enumerated or guessed sequentially.
3. **Protected Officials Desk**:
   - Casework views display only scrubbed locality/ward names, extracted urgency, and sector classifications to prevent resident profiling.

---

## 🛡 Reporting a Vulnerability

If you discover a security vulnerability or potential data leak:
- **Do NOT** open a public issue on GitHub.
- Please email the core maintainers with a detailed description and reproduction steps.
- We commit to acknowledging receipt within 48 hours and deploying a remediation patch promptly.
