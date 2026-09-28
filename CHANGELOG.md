# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- KYN VPN web storefront and separate email-based account portal: one-time codes,
  existing YooMoney wallet checkout, signed payment notifications, retryable XUI
  provisioning, subscription renewal and private profile downloads. Disabled
  until hosting, SMTP, legal URLs and payment notification routing are configured.
- Initial documentation: README, docs/*, and release/ops scaffolding.

### Changed
- Runtime hardening and self-healing infrastructure (compose healthchecks, restart policies, wait script).

### Fixed
- Trial period UX routing fixes (dead buttons / callback routing).

## [0.1.0] - 2026-02-24

### Added
- Baseline CI workflows and QA scripts.
- Initial growth execution roadmap and issue backlog templates.
