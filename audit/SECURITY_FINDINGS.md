# Security Findings — n7.nz Ecosystem Audit

**Date:** 2026-04-05
**Scope:** All 11 repositories, 10 live endpoints

---

## Summary

| Severity | Count | Launch Blockers |
|----------|-------|-----------------|
| HIGH | 2 | 2 (conditional) |
| MEDIUM | 4 | 0 |
| LOW | 4 | 0 |
| POSITIVE | 12 | — |

---

## HIGH Severity

### SEC-001: SSRF in SecondBrain URL Ingestion
- **Severity:** HIGH
- **Likelihood:** Medium (requires API key access)
- **Impact:** Internal service probing, cloud metadata access, credential theft
- **Location:** `SecondBrain/ingest.py:112-119`
- **Code:**
  ```python
  def fetch_url_text(url: str) -> tuple[str, bool]:
      resp = requests.get(url, timeout=15, headers={...})
  ```
- **Missing:** URL scheme whitelist, private IP blocking, DNS resolution validation
- **Exploit:** `POST /ingest/url {"url": "http://169.254.169.254/latest/meta-data/"}`
- **Remediation:** Add `_validate_url()` — whitelist http/https, block RFC1918/link-local/loopback ranges, resolve DNS and re-check IP
- **Compare:** SpecCheck already has proper SSRF protection at `speccheck/web/ssrf.py:1-87`
- **Launch blocker:** Yes, if SecondBrain API is exposed to untrusted users

### SEC-002: Potential API Key in Git History
- **Severity:** HIGH
- **Likelihood:** High (file exists locally)
- **Impact:** API key abuse, cost theft
- **Location:** `SecondBrain/.env:1` contains `ANTHROPIC_API_KEY=sk-ant-api03-...`
- **Mitigation:** `.gitignore` includes `.env`
- **Action required:** 1) Rotate key immediately. 2) Run `git log --all --full-history -- .env` to verify never committed. 3) If in history, use `git filter-repo`.
- **Launch blocker:** Yes

---

## MEDIUM Severity

### SEC-003: No Content Security Policy
- **Severity:** MEDIUM
- **Location:** All 4 Next.js apps (`next.config.js` / `next.config.mjs`)
- **Evidence:** Security headers present (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) but no CSP
- **Impact:** Reduced defense-in-depth against XSS
- **Remediation:** Add `Content-Security-Policy` header. Recommended policy:
  ```
  default-src 'self' https:;
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  font-src 'self' data:;
  connect-src 'self' https://n7.nz https://*.supabase.co;
  ```

### SEC-004: Unsanitized HTML Rendering in BriefsClient
- **Severity:** MEDIUM
- **Location:** `n7-portfolio/app/briefs/BriefsClient.js:122`
- **Evidence:** `dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }}` where `markdownToHtml` is regex-based conversion
- **Source:** Content fetched from Phil's own GitHub repo (trusted)
- **Residual risk:** GitHub account compromise → XSS
- **Remediation:** `npm install dompurify` → `DOMPurify.sanitize(markdownToHtml(content))`

### SEC-005: IntegrationAtlas Default AUTH_SECRET
- **Severity:** MEDIUM
- **Location:** `IntegrationAtlas/lib/workbench-auth.js:4-6`
- **Evidence:** Falls back to `"integrationatlas-dev-secret"` in non-production
- **Impact:** Predictable session tokens in dev/staging
- **Remediation:** Require AUTH_SECRET in all environments. Fail-fast startup check.

### SEC-006: Error Messages Leak Implementation Details
- **Severity:** MEDIUM
- **Location:** `SecondBrain/api.py:294`
- **Evidence:** `raise HTTPException(status_code=400, detail=str(e))` — exception message may contain file paths, library names, internal URLs
- **Remediation:** Return generic error for 5xx. Sanitize 4xx error messages. Log full exception server-side.

---

## LOW Severity

### SEC-007: No SAST/Dependency Audit in CI
- **Severity:** LOW
- **Location:** All CI workflows
- **Evidence:** No bandit, safety, pip-audit, or npm audit steps
- **Remediation:** Add `pip-audit` to Python CI, `npm audit --audit-level=high` to Node CI

### SEC-008: In-Memory Rate Limiting
- **Severity:** LOW
- **Location:** All 4 Python services
- **Evidence:** Per-IP rate limiting in Python dict, lost on restart
- **Impact:** Rate limits reset on deploy. Acceptable at current scale.
- **Remediation:** Document as known limitation. Consider Redis if scale increases.

### SEC-009: IntegrationAtlas File-Based Concurrency
- **Severity:** LOW (data loss, not security)
- **Location:** `IntegrationAtlas/lib/workbench-store.js:23-43`
- **Evidence:** Read-modify-write without file locking
- **Remediation:** Implement file locking or migrate to SQLite

### SEC-010: Metrics Endpoint Optionally Unprotected
- **Severity:** LOW
- **Location:** All Python services `/metrics` endpoint
- **Evidence:** Protected by `METRICS_SECRET` bearer token, but if not configured, metrics are public
- **Impact:** Internal operation metrics visible (request counts, latency, error rates)
- **Remediation:** Require METRICS_SECRET in production. Fail-fast if not configured.

---

## Positive Findings (Confirmed)

| # | Finding | Evidence |
|---|---------|----------|
| P1 | HMAC timing-safe auth on all services | `hmac.compare_digest()` in Python, `timingSafeEqual()` in Node |
| P2 | Parameterized SQL queries throughout | All SQLite uses `?` placeholders in db.py |
| P3 | Zero eval/exec/subprocess with user input | Grep confirmed across all repos |
| P4 | No hardcoded secrets in source code | All credentials via environment variables |
| P5 | Non-root Docker containers | All 3 Railway Python services use `appuser` |
| P6 | Server-side API key proxy | SecondBrain key injected in `brain/[...path]/route.js`, never reaches browser |
| P7 | Security headers on all services | X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, Permissions-Policy |
| P8 | Dependabot on all 11 repos | Weekly, minor/patch only |
| P9 | SSRF protection on SpecCheck | Private IP blocking + DNS resolution at `ssrf.py:45-86` |
| P10 | scrypt password hashing on IntegrationAtlas | With proper salt handling |
| P11 | httpOnly + sameSite cookies | IntegrationAtlas sessions with secure flag in production |
| P12 | AI crawler blocking | robots.txt blocks GPTBot, ClaudeBot, CCBot, anthropic-ai |
