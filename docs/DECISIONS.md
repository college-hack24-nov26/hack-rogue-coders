# Reversible implementation decisions

- Local development uses SQLite and development-only password/JWT authentication so the complaint workflow is testable without a hosted account. Production authentication fails closed unless Neon JWKS/issuer/audience are configured. User claims never grant an application role. Operator provisioning is required for staff.
- Neon currently documents managed Better Auth and a JWT plugin. Its phone plugin supports linked existing users and requires an external SMS delivery webhook; phone-first registration is not available in that documented flow. Upstream Better Auth's Expo plugin requires server plugin support, so compatibility with the selected managed Neon project must be tested rather than inferred. Native secure token entry is an integration seam, not verified production onboarding.
- Official publication requires a reviewer-supplied sanitized description. Original report and reporter/channel metadata are excluded from officials' detail/list responses. Timeline exposed there contains demonstration service events only.
- Only a system administrator can access incomplete WhatsApp submissions without a known jurisdiction. Ordinary reviewers cannot access an unknown geographic scope.
- WhatsApp village resolution accepts explicit `LGD:<id>` matching an imported directory record. Location pins and ambiguous names remain incomplete for human review; they never silently establish village identity or land ownership.
- External message delivery defaults off. Durable reply jobs become visibly blocked when delivery is disabled or the service window expires. The Cloud API is at-least-once: a process crash after a provider sends but before recording its receipt can duplicate a reply. Ticket deduplication is transactional and independent of this provider limitation.
- Uploads require checksum/type/size verification, decoder inspection and metadata-stripping re-encoding. Raw uploads remain private; officials also require individual reviewer approval. The local private pipeline is tested; Neon storage is configuration-blocked.
- Forecast jobs publish unavailable snapshots until real released models and source mappings are wired in. No daily retraining, groundwater-to-litres conversion, or seven-to-fifteen-day extrapolation exists.
- Numeric evidence stays in canonical response cards. Gemini explanations containing digits are rejected rather than permitting numerical invention. This conservative rule can reject legitimate text; retrieval/citation coverage and human Marathi review are still needed.
- Application timestamps use UTC; display targets Asia/Kolkata. A production aggregation cutoff and data retention policy still require operator agreement.
- Application flows include farm edits, economics, staff invitations/revocation, reviewed supply, notices, crosswalks, quality diagnostics and job retries. Earlier failed research experiments remain preserved. The revised multi-year, persistence-anchored candidate passes the existing numerical gates but stays unapproved pending source semantics/availability, reviewed mappings and prospective/human review. Test-period exposure and the calibration revision are disclosed.
- Directory imports use the documented HTTPS API after search-endpoint timeouts. Each district's unique IDs are reconciled against the official catalogue. Successful snapshots and per-district commits survive retries; existing jurisdiction conflicts require a reviewed migration. All 44,929 source villages are imported. No village coordinates or station mappings are inferred from that coverage.
- Provider diagnostics disclose variable names/status only. Read-only database/JWKS/model/bucket/phone-access probes are separate from generation, signup/recovery, upload and delivery verification. Actual provider secrets are still absent. Local startup is available through run-local.ps1; no public deployment is implied.

Documentation checked during implementation:
- https://neon.com/docs/auth/overview
- https://neon.com/docs/auth/authentication-flow
- https://neon.com/docs/auth/guides/plugins/jwt
- https://neon.com/docs/auth/guides/plugins/phone-number
- https://neon.com/docs/storage/overview
- https://better-auth.com/docs/integrations/expo
