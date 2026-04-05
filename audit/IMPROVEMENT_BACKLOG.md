# Improvement Backlog — n7.nz Ecosystem

**Date:** 2026-04-05
**Total tickets:** 20
**Organized by:** Priority then effort

---

## P0 — Security (Fix Before Showing to Evaluators)

### IMP-001: Add SSRF Protection to SecondBrain URL Ingestion
- **Problem:** `ingest.py:112-119` fetches arbitrary URLs without scheme, hostname, or IP validation. Attacker with API access can probe internal services or cloud metadata.
- **Change:** Add `_validate_url()` function: whitelist http/https, block private/reserved IPs (RFC1918, link-local, loopback), resolve DNS and check result IP. Apply to `fetch_url_text()`, `ingest_url()`, and all job queue URL endpoints.
- **Acceptance criteria:**
  - `file://`, `ftp://`, `gopher://` schemes rejected with 400
  - `http://127.0.0.1`, `http://10.x.x.x`, `http://169.254.169.254` rejected with 400
  - `http://localhost` rejected with 400
  - Legitimate URLs (http/https to public IPs) continue to work
  - Unit tests for each rejection case
- **Priority:** P0 | **Effort:** 2h | **Owner:** Backend | **Dependencies:** None

### IMP-002: Rotate Anthropic API Key
- **Problem:** Real API key in local `.env` file, possibly in git history.
- **Change:** 1) Rotate on Anthropic dashboard. 2) Run `git log --all --full-history -- .env`. 3) If committed, purge with `git filter-repo`. 4) Update Railway deployment env var.
- **Acceptance criteria:**
  - Old key returns 401 on Anthropic API
  - New key works in deployed SecondBrain
  - `git log -- .env` shows zero commits
- **Priority:** P0 | **Effort:** 1h | **Owner:** Security | **Dependencies:** None

### IMP-003: Add CSP Headers to All Frontends
- **Problem:** No Content-Security-Policy on any of 4 Next.js apps.
- **Change:** Add CSP header to `next.config.js` headers array. Test each app for console CSP violations.
- **Acceptance criteria:**
  - CSP header present on all page responses
  - No CSP violations on normal page load (test with browser devtools)
  - Inline scripts blocked (verify with test injection)
- **Priority:** P0 | **Effort:** 3h | **Owner:** Frontend | **Dependencies:** None

### IMP-004: Sanitize BriefsClient Markdown Rendering
- **Problem:** `dangerouslySetInnerHTML` renders GitHub markdown as raw HTML without sanitization.
- **Change:** Install `dompurify`. Wrap `markdownToHtml()` output with `DOMPurify.sanitize()`.
- **Acceptance criteria:**
  - `<script>` tags in markdown source are stripped
  - Normal markdown (headings, lists, links, code blocks) renders correctly
  - No visual regression
- **Priority:** P0 | **Effort:** 30min | **Owner:** Frontend | **Dependencies:** None

---

## P1 — Quality & Usability

### IMP-005: Add SecondBrain API Endpoint Tests
- **Problem:** Zero test coverage on `api.py` routes (21 endpoints), auth middleware, and rate limiting.
- **Change:** Add `tests/test_api.py` using httpx TestClient. Cover: health check, auth rejection (no key), auth acceptance (valid key), rate limit enforcement, ask endpoint, ingest text, ingest URL, sources list, source delete, jobs list, workspaces.
- **Acceptance criteria:**
  - 80%+ line coverage on api.py
  - Auth bypass attempt correctly returns 401
  - Rate limit correctly returns 429
  - All endpoint response schemas match expected shape
- **Priority:** P1 | **Effort:** 1d | **Owner:** Backend | **Dependencies:** None

### IMP-006: Fix Market Dashboard Empty States
- **Problem:** "n/a" and "FRESHNESS: UNAVAILABLE" appear without context, looking broken.
- **Change:** Replace "n/a" with contextual empty state component: "Offline" badge + last-known value + timestamp + tooltip explaining data source status. Replace "FRESHNESS: UNAVAILABLE" with "Last updated: unknown" or "Awaiting first data collection."
- **Acceptance criteria:**
  - No raw "n/a" text visible anywhere on dashboard
  - Offline metrics show last-known value with staleness indicator
  - Tooltip on each unavailable metric explains the data source
- **Priority:** P1 | **Effort:** 4h | **Owner:** Frontend | **Dependencies:** None

### IMP-007: Remove Internal Jargon from Public Dashboard
- **Problem:** "1 LAUNCH BLOCKERS" visible in header. "Deterministic only" toggle unclear.
- **Change:** 1) Hide launch blocker count from public mode header. 2) Rename "Deterministic only" to "AI-free mode" or remove from default view. 3) Add tooltips to remaining mode toggles.
- **Acceptance criteria:**
  - Public visitors see clean header without internal status indicators
  - All toggle labels are self-explanatory or have tooltips
- **Priority:** P1 | **Effort:** 1h | **Owner:** Frontend | **Dependencies:** None

### IMP-008: Fix IntegrationAtlas Double-Path Routing
- **Problem:** /atlas redirects to /atlas/atlas. Possible BASE_PATH configuration doubling between Vercel rewrite and Next.js config.
- **Change:** Debug the interaction between `n7-portfolio/next.config.js` rewrite rule for `/atlas/*` and IntegrationAtlas's own `BASE_PATH` setting. Ensure only one applies.
- **Acceptance criteria:**
  - `https://n7.nz/atlas` loads IntegrationAtlas correctly
  - No URL path doubling
  - Internal navigation within Atlas works
- **Priority:** P1 | **Effort:** 2h | **Owner:** Frontend/DevOps | **Dependencies:** None

### IMP-009: Add Dependency Scanning to CI
- **Problem:** No SAST or dependency audit in any pipeline.
- **Change:** Add `pip-audit` step to all Python CI workflows (nz-intel, SecondBrain, SpecCheck, n7-event-hub). Add `npm audit --audit-level=high` to all Node CI workflows.
- **Acceptance criteria:**
  - CI fails on high-severity dependency vulnerabilities
  - Current dependencies pass (fix any existing issues first)
- **Priority:** P1 | **Effort:** 2h | **Owner:** DevOps | **Dependencies:** None

### IMP-010: Add Market Dashboard Onboarding
- **Problem:** First-time visitors face information overload with no guidance.
- **Change:** Add a dismissible "Welcome to n7/market" overlay or guided callout that explains: 1) What the dashboard shows. 2) What freshness/lineage/trust mean. 3) Where to start (suggest Jobs or Tenders). 4) "Dismiss permanently" with localStorage flag.
- **Acceptance criteria:**
  - First visit shows onboarding overlay
  - Overlay can be dismissed permanently
  - Returning visitors do not see overlay
  - Overlay is accessible (keyboard dismissable, focus trapped)
- **Priority:** P1 | **Effort:** 4h | **Owner:** Frontend | **Dependencies:** None

---

## P2 — Maintainability & Operations

### IMP-011: Add Integration Tests for Proxy Flows
- **Problem:** No tests verify portfolio-to-backend proxy chains work correctly.
- **Change:** Add test suite (can run in CI or locally) that calls: `https://n7.nz/brain/health`, `https://n7.nz/api/v1/health`, `https://n7.nz/speccheck`, `https://n7.nz/events/recent`. Verify response status codes and shapes.
- **Acceptance criteria:**
  - Tests pass against live endpoints
  - API key injection verified (SecondBrain health accessible via proxy)
  - Can run as scheduled CI check (weekly)
- **Priority:** P2 | **Effort:** 4h | **Owner:** Fullstack | **Dependencies:** None

### IMP-012: Decompose SecondBrain app.py
- **Problem:** 2,209-line monolithic Streamlit file handling all tabs and UI logic.
- **Change:** Extract each tab into a separate module: `ui/ingest_tab.py`, `ui/ask_tab.py`, `ui/sources_tab.py`, `ui/history_tab.py`, `ui/discover_tab.py`, `ui/rss_tab.py`, `ui/analytics_tab.py`, `ui/eval_tab.py`. Keep app.py as thin orchestrator.
- **Acceptance criteria:**
  - app.py under 300 lines
  - All tabs function identically
  - No test regressions
- **Priority:** P2 | **Effort:** 1d | **Owner:** Backend | **Dependencies:** None

### IMP-013: Add Structured JSON Logging
- **Problem:** Text-based logging across all Python services, not machine-parseable.
- **Change:** Configure Python logging with `python-json-logger` or similar. Include: timestamp, level, module, message, request_id (if available).
- **Acceptance criteria:**
  - Log output is valid JSON
  - Existing log messages preserved
  - Machine-parseable by Grafana Loki or equivalent
- **Priority:** P2 | **Effort:** 1d | **Owner:** Backend | **Dependencies:** None

### IMP-014: Document Backup/Restore Procedure
- **Problem:** No documented procedure for Railway volume backup or disaster recovery.
- **Change:** Write runbook covering: 1) How to backup SQLite + ChromaDB from Railway volumes. 2) How to restore to new Railway instance. 3) Test the procedure end-to-end at least once.
- **Acceptance criteria:**
  - Runbook exists in n7-infra or SecondBrain repo
  - Backup procedure tested manually at least once
  - Estimated data loss window documented (RPO)
- **Priority:** P2 | **Effort:** 4h | **Owner:** DevOps | **Dependencies:** None

### IMP-015: Add Terraform Staging Workspace
- **Problem:** All changes deploy directly to production with no staging environment.
- **Change:** Add staging workspace in Terraform Cloud. Configure CI to plan against staging on feature branches. Apply to production only on merge to main.
- **Acceptance criteria:**
  - `terraform workspace list` shows both `n7-infra-prod` and `n7-infra-staging`
  - Feature branch PRs plan against staging
  - Merge to main applies to production only
- **Priority:** P2 | **Effort:** 1d | **Owner:** DevOps | **Dependencies:** None

---

## P3 — Strategic

### IMP-016: User Accounts on Market Dashboard
- **Problem:** No user accounts means no stickiness, saved views, or personalization.
- **Change:** Integrate Supabase Auth (already available). Add: sign up, sign in, saved filter presets, saved compare views, email alert preferences.
- **Acceptance criteria:**
  - Users can create accounts and sign in
  - Saved views persist across sessions
  - Unauthenticated users retain current public read access
- **Priority:** P3 | **Effort:** 1w | **Owner:** Fullstack | **Dependencies:** None

### IMP-017: Email Alerts for Market Signals
- **Problem:** No way for users to be notified of new tenders, jobs, or demand shifts matching their criteria.
- **Change:** Add alert subscription system: users define filters (keywords, agencies, skills), receive email when matching signals appear. Use existing Resend integration via Event Hub.
- **Acceptance criteria:**
  - Users can create alert subscriptions
  - New matching events trigger email notifications
  - Rate-limited to prevent spam (max 1 email per event type per day)
- **Priority:** P3 | **Effort:** 1w | **Owner:** Fullstack | **Dependencies:** IMP-016

### IMP-018: WCAG 2.1 AA Accessibility Audit
- **Problem:** Accessibility is partial and unsystematic.
- **Change:** Conduct full WCAG 2.1 AA audit of all public-facing pages. Fix identified issues. Add automated accessibility testing to CI.
- **Acceptance criteria:**
  - All pages pass axe-core automated checks
  - Skip navigation link on all pages
  - Focus management in modals/dialogs
  - Color contrast meets AA standards
  - Screen reader testing on key workflows
- **Priority:** P3 | **Effort:** 3d | **Owner:** Frontend | **Dependencies:** None

### IMP-019: Evaluate Monorepo Consolidation
- **Problem:** 11 repos for 1 person creates high maintenance overhead.
- **Change:** Evaluate consolidating related repos into a monorepo with workspace-based deployment. Candidates: all Next.js apps into one repo, all Python services into one repo. Write ADR documenting decision.
- **Acceptance criteria:**
  - ADR written with analysis of trade-offs
  - If proceeding: migration plan documented
  - CI/CD reconfigured for selective builds
- **Priority:** P3 | **Effort:** 2w | **Owner:** Architecture | **Dependencies:** None

### IMP-020: Cross-Service Request Tracing
- **Problem:** No correlation IDs across services. Debugging cross-service issues requires manual log correlation.
- **Change:** Generate request ID in n7-portfolio proxy. Forward as `X-Request-ID` header to all backend services. Include in all log entries and Prometheus labels.
- **Acceptance criteria:**
  - Every request through n7.nz carries a unique request ID
  - ID appears in logs of all services in the request chain
  - Can trace a single request across portfolio → nz-intel or portfolio → SecondBrain
- **Priority:** P3 | **Effort:** 2d | **Owner:** Backend | **Dependencies:** IMP-013
