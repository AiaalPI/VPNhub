This directory contains lightweight release-train scripts.

These scripts intentionally:
- Do not print secrets (basic redaction).
- Use `docker compose` for build/test/smoke actions.
- Use `gh` only when explicitly available and authenticated.

