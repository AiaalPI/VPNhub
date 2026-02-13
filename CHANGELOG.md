# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Add initial documentation: README, docs/*, CHANGELOG
- Fix trial period button routing: remove duplicate `ConnectMenu` callback handler and route `prob_period` to real trial activation flow with server selection.
- Harden runtime stability: add service readiness wait script, migration retries, polling reconnect/backoff, graceful shutdown, and compose healthchecks/restart policies.
