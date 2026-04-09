# Release Notes — Smart Payments v1.0
**Release Date:** Day 4 of monitoring window  
**Feature Owner:** Payments Team  
**Rollout Strategy:** Gradual — 100% of new signups, 40% of existing users

---

## What Changed

Smart Payments is a redesigned payment flow for PurpleMerit that introduces:

- **One-tap checkout** — saved payment methods with biometric confirmation
- **Real-time payment status** — live transaction tracking via new `/api/v2/payments/status` endpoint
- **Smart retry logic** — automatic retry on transient failures (up to 2 retries)
- **Unified payment ledger** — consolidated transaction history across all payment methods

The feature replaces the legacy `/api/v1/checkout` endpoint entirely for users in the rollout cohort.

---

## Dependencies Introduced

- New third-party payment processor: **StripeConnect v3** (replacing internal processor)
- Redis cache layer for session tokens (new infrastructure, not battle-tested at scale)
- `/api/v2/payments/status` — new endpoint, not load tested beyond 5,000 concurrent users

---

## Known Risks at Launch

1. **Redis session cache** — under high concurrency, session token expiry may cause silent payment failures. Workaround not yet implemented. *Severity: High*

2. **StripeConnect webhook latency** — in staging, webhooks confirming payment success showed occasional 3–8 second delays. Under load this may cause the app to show "pending" indefinitely. *Severity: Medium*

3. **Android crash on biometric fallback** — on Android 11 devices, falling back from biometric to PIN authentication causes an unhandled exception in the payment flow. Fix is in QA. *Severity: High*

4. **Retry logic double-charge risk** — the smart retry mechanism does not check idempotency keys correctly if the first attempt times out (vs fails). This can result in duplicate charges in edge cases. *Severity: Critical — patch pending*

5. **API gateway not horizontally scaled** — the `/api/v2/payments/status` endpoint runs on a single instance. No autoscaling configured. Expected to degrade above 8,000 concurrent requests. *Severity: High*

---

## Rollback Plan

- Feature flag `smart_payments_enabled` can be toggled off in the admin dashboard
- Rollback routes all users back to `/api/v1/checkout`
- Estimated rollback time: ~15 minutes
- Data migration: not required (ledger entries are additive)

---

## Success Criteria (defined by PM)

| Metric | Target |
|---|---|
| Payment success rate | ≥ 95% |
| Crash rate | ≤ 1.5% |
| API p95 latency | ≤ 800ms |
| D1 Retention | ≥ 35% |
| Support ticket volume | ≤ 150/day |
| Funnel completion | ≥ 60% |