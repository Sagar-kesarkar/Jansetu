# Contributing

Use [RUN.md](RUN.md) for setup and [docs/README.md](docs/README.md) for maintained guides.

## Engineering rules

- Use free/open-source components. Do not add billed Google Cloud services or google-cloud-* dependencies.
- Use google-genai for Gemini with non-Gemini fallbacks.
- Keep ranking arithmetic deterministic and analytics independent of services. Update tests/docs when scoring weights change.
- Use plain CSS, not Tailwind; preserve responsive citizen and officials workflows.
- Keep geographic coverage data-driven; validate identifiers and never invent locations.
- Do not introduce citizen names, phone numbers, household addresses, IP addresses or device identifiers. Never commit credentials, databases or citizen evidence.
- Preserve shared intake, per-request tokens, sender ownership and webhook deduplication.

## Validation and documentation

After a change set, run backend tests with mocked external services and build both frontends using RUN.md. Report actual outcomes; simulator success is not provider delivery. No fixed passing-test count is guaranteed.

Label demo financial data, demo authentication and unverified integrations clearly. Documentation-only revisions must not imply that application limitations were fixed.
