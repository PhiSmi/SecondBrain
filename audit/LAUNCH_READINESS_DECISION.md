# Launch Readiness Decision — n7.nz Ecosystem

**Date:** 2026-04-05
**Verdict:** LAUNCH ONLY TO FRIENDLY TESTERS / CONTROLLED AUDIENCE

---

## Decision

The n7.nz ecosystem is appropriate for:
- Sharing with hiring managers, recruiters, and technical evaluators as a portfolio
- Sharing with NZ tech colleagues interested in market intelligence
- Demonstrating in interviews and architecture discussions
- Using personally as a market intelligence and knowledge management tool

The ecosystem is NOT appropriate for:
- Public launch as a product with paying customers
- Deployment to untrusted users who may abuse API endpoints
- Any scenario requiring SLA guarantees, data isolation, or support
- Enterprise or government use without accessibility and compliance remediation

---

## Rationale

### What is ready

| Area | Status | Evidence |
|------|--------|----------|
| All endpoints live | READY | 9/10 returning 200 (Event Hub health path minor issue) |
| Security fundamentals | READY | HMAC auth, security headers, non-root containers, dependabot |
| Infrastructure as Code | READY | Terraform managing all infrastructure, CI plan/apply |
| Observability | READY | Prometheus metrics, Grafana dashboards, alert rules |
| CI/CD | READY | 14 workflows, automated testing, scheduled data pipelines |
| Data pipeline | READY | 20 source adapters running on schedule, snapshot architecture |
| Documentation | READY | 10 ADRs, security review, SLO document |

### What needs fixing before wider exposure

| Area | Issue | Blocking Level |
|------|-------|----------------|
| SSRF vulnerability | SecondBrain URL ingestion has no URL validation | Blocks untrusted API access |
| API key exposure | .env with real key may be in git history | Blocks public repo sharing |
| Missing CSP | No Content-Security-Policy on frontends | Low risk but should fix |
| Test gaps | Zero API tests on SecondBrain | Blocks confident deployment |
| UX rough edges | "n/a" values, internal jargon, no onboarding | Blocks non-technical audience |

### What needs fixing before production

| Area | Issue | Effort |
|------|-------|--------|
| User accounts | No authentication on market dashboard | 1 week |
| Staging environment | All deploys go to production | 1 day |
| Backup/restore | No documented recovery procedure | 4 hours |
| Accessibility | Partial, unsystematic | 3 days |
| Integration tests | No cross-service testing | 4 hours |
| Structured logging | Text-based, not machine-parseable | 1 day |

---

## Recommended Action Plan

### This week
1. Rotate Anthropic API key (1h)
2. Add SSRF protection to SecondBrain (2h)
3. Remove "1 LAUNCH BLOCKERS" from public header (15min)
4. Fix "n/a" empty states with contextual messaging (4h)

### Next week
5. Add CSP headers to all frontends (3h)
6. Add SecondBrain API endpoint tests (1d)
7. Fix IntegrationAtlas routing (2h)
8. Add DOMPurify to BriefsClient (30min)

### After that
- Share confidently with hiring managers and technical evaluators
- Consider market dashboard as standalone product with user accounts

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SSRF exploitation via SecondBrain | Medium | High | Fix IMP-001 (2h) |
| API key compromise | Low (if never committed) | High | Fix IMP-002 (1h) |
| XSS via BriefsClient | Low (trusted source) | Medium | Fix IMP-004 (30min) |
| Data loss (no backup) | Low | High | Fix IMP-014 (4h) |
| Scraper breakage (source changes) | Medium | Low | Fixture fallback exists |
| Railway cost spike | Low | Medium | Free tier monitoring |
| Solo dev burnout | Medium | High | Prioritize ruthlessly |

---

## Final Note

This ecosystem is genuinely impressive engineering work that demonstrates real skills. The issues identified are normal for a solo-dev project at this stage and are all fixable. The 4 P0 security items should be addressed before sharing the codebase with security-minded evaluators. The UX improvements should be made before sharing with non-technical audiences. The architecture, observability, and security fundamentals are strong enough to withstand scrutiny from senior engineers and architects.
