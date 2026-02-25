# Release Process (AI Release Train)

## Release Types
- Patch: `X.Y.Z+1` (bugfix, ops hardening, copy)
- Minor: `X.Y+1.0` (new feature, backward compatible)
- Major: `X+1.0.0` (breaking changes)

## Release Inputs
- Merged PRs with milestone `Release vX.Y.Z` or included sprint milestone.
- CI green.
- Smoke checklist ready.

## Release Steps
1. Freeze:
   - Project column: all release scope issues in `Done`.
2. Build:
   - `docker compose build --no-cache vpn_hub_bot` (or CI artifact).
3. Generate notes:
   - Use `scripts/release_train/generate_release_notes.sh`.
4. Tag + changelog:
   - Update `CHANGELOG.md` with a new version section.
   - Create git tag `vX.Y.Z`.
5. Deploy:
   - Through the approved deployment path (Actions / server runbook).
6. Post-release:
   - Run smoke checks and move issues to `Monitoring`.
7. Monitoring window:
   - 30–60 minutes for patch, 24h for minor.

## Release Gates
Block release if:
- Restart loops / unhealthy container state.
- Telegram conflict/unauthorized errors.
- Migration failures.
- Spike in payment failures or webhook errors.

