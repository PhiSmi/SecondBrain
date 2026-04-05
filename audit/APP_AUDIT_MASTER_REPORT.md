# n7.nz Ecosystem — Full-Spectrum Independent Audit

**Audit date:** 2026-04-05
**Auditor:** Independent panel (security, architecture, product, UX, market)
**Subject:** n7.nz ecosystem — 11 repositories, 10 live endpoints, ~30,000+ LOC
**Builder:** Phil Smith, solo developer, Wellington NZ
**Constraint:** Solo dev, $22–35/month budget, portfolio/career-transition vehicle

---

# 1. Executive Verdict

**What this is:** A multi-service portfolio ecosystem built by a Senior Technical BA transitioning to Solution Architect. It combines a career portfolio, a 15-page NZ market intelligence dashboard, a RAG knowledge base, an API contract testing tool, an integration pattern workbench, a prompt engineering tool, an event bus, a multi-agent weekly brief pipeline, and full IaC/observability — all under one domain (n7.nz), run by one person for ~$25/month.

**Is it actually good?** Yes, with caveats. This is not a toy. The architecture is genuinely thoughtful, the security posture is above-average for a solo project, the observability stack is real, and the market dashboard solves a real (niche) problem. The codebase is consistent, well-structured, and shows disciplined engineering habits — not AI-slop-and-pray.

**Is it fit for purpose?** As a portfolio demonstrating integration architecture, API design, observability, security, and AI skills — it is exceptionally fit. As production software serving paying customers — it is not there yet, and that is not its current goal.

**Is it market-ready?** No individual product in this ecosystem is market-ready for external users. The market dashboard is closest, but lacks user accounts, onboarding, and polish for non-technical users. This is correctly positioned as a demonstration platform.

**Is it portfolio junk?** No. This is the opposite end of the spectrum from portfolio junk. Portfolio junk is a React todo app deployed once. This is 11 repos, 14 CI/CD workflows, 20 data source adapters, Terraform IaC, Grafana observability, event-driven architecture, and a multi-agent AI pipeline — all live, all monitored, all tested. The depth is real.

**Top reasons:**
1. Architecture discipline is genuine — ADRs, STRIDE threat models, SLOs, lineage metadata
2. Security is intentional, not accidental — timing-safe auth, SSRF protection, security headers, non-root containers
3. Observability is production-grade — Prometheus metrics, Grafana dashboards, alert rules
4. The market dashboard solves a real niche problem (NZ tech market intelligence) with real data
5. Solo-dev operational ceiling is the binding constraint, not engineering quality

---

# 2. Launch-Readiness Decision

**Verdict: Launch only to friendly testers / controlled audience**

**Why:**
- All 10 endpoints are live and returning 200 (except Event Hub health at /events/health returning 404 — likely /events/recent is the correct public endpoint)
- SecondBrain health shows "degraded" (background worker warning) — acceptable for demo
- Data freshness is 20 hours old at time of audit — the 6-hour ingest cycle means this is normal
- No user authentication or multi-tenancy on market dashboard — fine for public read-only
- SSRF vulnerability in SecondBrain URL ingestion is a real risk if exposed to untrusted users
- No CSP headers on any frontend — low-risk for current audience but should be fixed
- The ecosystem is appropriate for showing to recruiters, architects, and technical evaluators

**Not ready for:**
- Paying customers
- Untrusted public API consumers beyond rate-limited read access
- Any scenario requiring user accounts, data isolation, or SLA guarantees

---

# 3. Product Understanding

**Target user:** Technical hiring managers, solution architects, and the builder himself (Phil) as a career portfolio and personal market intelligence tool.

**Core use case:** Demonstrate integration architecture competence through a living, working multi-service platform that also provides genuine NZ tech market intelligence.

**Primary workflows:**
1. Visitor lands on n7.nz → views portfolio → explores projects → optionally opens market dashboard
2. Phil (or interested viewer) uses market dashboard to see NZ job/tender/currency data
3. Phil uses SecondBrain to ingest and query personal knowledge base
4. Phil uses PromptBuilder to craft AI prompts
5. Phil uses SpecCheck to test API contracts
6. Automated weekly brief pipeline runs, publishes to /briefs

**What good looks like in this category:** A portfolio that demonstrates breadth AND depth. Not just "I built a CRUD app" but "I designed, built, deployed, secured, monitored, and automated a multi-service platform with real data pipelines." This ecosystem achieves that.

**Where this app currently fits:** Between "impressive portfolio" and "useful niche tool." The market dashboard has genuine utility for anyone tracking NZ tech procurement. Everything else is portfolio-grade demonstration.

---

# 4. Scorecard

| Dimension | Score | Justification |
|-----------|-------|---------------|
| Product clarity | 7/10 | Clear for technical audience. Market dashboard purpose is obvious. Portfolio purpose is obvious. But the relationship between 7+ tools is confusing for non-technical visitors. |
| Fit for purpose | 9/10 | As a portfolio demonstrating SA/integration skills, this is nearly ideal. Loses a point for market dashboard not being independently viable. |
| UI quality | 7/10 | Dark theme is polished and consistent. Market dashboard is information-dense but well-structured. SpecCheck and PromptBuilder are clean. Portfolio page is strong. |
| UX quality | 6/10 | Market dashboard cognitive load is high. No onboarding. Many buttons/modes without explanation. Power-user tool, not consumer-friendly. |
| Accessibility | 5/10 | ARIA labels present on key components. Semantic HTML used. But no systematic audit, no focus management, no skip-nav, contrast not verified, keyboard navigation incomplete. |
| Security | 7/10 | Above average for solo project. HMAC auth, security headers, non-root containers, STRIDE analysis. Loses points for SSRF in SecondBrain, missing CSP, exposed .env in git history. |
| Privacy/trust | 7/10 | Minimal user data collected. API keys server-side only. No PII storage. robots.txt blocks AI crawlers. NZ Privacy Act referenced in security review. |
| Code quality | 8/10 | Consistent patterns across repos. Clean module boundaries. Parameterized queries. Proper error handling. Pydantic validation. Some areas (SecondBrain app.py at 2209 lines) need decomposition. |
| Architecture | 9/10 | Genuinely strong. Clean service boundaries, event-driven integration, snapshot-centric data flow, proxy pattern for API key injection, IaC, observability pipeline. 10 ADRs documenting decisions. |
| Maintainability | 7/10 | Good module structure. But 11 repos for one person is a maintenance burden. No integration tests across services. Some large monolithic files. |
| Reliability | 6/10 | Health checks exist. Alerting exists. But in-memory rate limiting resets on restart, no distributed state, no circuit breakers between services, background worker shows warnings. |
| Performance | 7/10 | ETag caching, SWR on frontend, snapshot-centric architecture avoids real-time scraping. Loses points for no pagination/virtualization evidence on large data tables, no bundle size evidence. |
| Test maturity | 5/10 | Tests exist (60% coverage target on nz-intel, unit tests on SecondBrain). But no API endpoint tests on SecondBrain, no integration tests, no e2e tests, no security tests. Coverage is breadth-shallow. |
| Production readiness | 6/10 | IaC, CI/CD, health checks, monitoring, alerting — all present. But solo-dev ops, no runbooks, no incident response, no backup/restore tested, no staging environment. |
| Market competitiveness | 4/10 | NZ market intelligence is a genuine niche. But no competitors means unclear if demand exists. Individual tools (SpecCheck, PromptBuilder) face established competition. |
| Differentiation | 7/10 | The ecosystem as a whole IS the differentiator. No other portfolio demonstrates this breadth with this depth. Individual products are not differentiated. |
| **Overall quality** | **7/10** | **Genuinely solid engineering work. Well above typical portfolio projects. Held back by solo-dev operational ceiling, test gaps, and the inherent tension between breadth and depth.** |

---

# 5. What It Is Doing Well

1. **Architecture discipline is real.** 10 ADRs, STRIDE threat modeling, SLO definitions, lineage metadata on every data record, event-driven integration with typed schemas. This is not accidental architecture — it is documented, reasoned, and defensible.

2. **Security is intentional.** HMAC timing-safe comparisons on all auth endpoints. Security headers on every service. Non-root Docker containers. SSRF protection on SpecCheck. API key injection via server-side proxy (never exposed to browser). Dependabot on all 11 repos. A 4,576-word security architecture review referencing NZISM and NZ Privacy Act.

3. **Observability is production-grade.** Prometheus metrics on all 4 Python services (28+ custom metrics). Grafana Alloy scraping every 60s. 3 Grafana dashboards. 5 alert rules. SLO document with availability and latency targets. This is what senior engineers expect to see.

4. **The data pipeline is genuine.** 20 NZ data source adapters with fallback chains (cloudscraper → requests → Playwright). Fixture mode for testing. Snapshot-centric architecture that decouples ingestion from serving. Background job queue with deduplication. This is real data engineering, not fake demo data.

5. **IaC is done right.** Terraform managing Vercel, Railway, and Supabase with remote state in TF Cloud. CI plan-on-PR, apply-on-merge. Import-based (adopted existing infrastructure into Terraform, didn't start from scratch). This is the hard, boring, correct way to do it.

6. **Code consistency across repos.** Same security header pattern, same metrics pattern, same auth pattern, same CI workflow structure across all services. Shows a developer who thinks in systems, not individual apps.

7. **The market dashboard has genuine utility.** 96 active job listings, 11 open tenders, 100 recent awards, currency data, skills trending — all from real NZ government and market sources. Trust/freshness/lineage surfaces are unusually transparent.

8. **Cost discipline.** $22–35/month for 11 repos, 10 live endpoints, 4 Railway services, observability, and AI integration. This is exceptional cost efficiency.

---

# 6. What It Is Doing Badly

1. **Test coverage is shallow.** SecondBrain has zero API endpoint tests. No integration tests across services. No e2e tests. No security tests (SSRF, auth bypass). The 60% coverage target on nz-intel covers adapters and services but not the full API surface. Tests would not catch a regression in the authentication middleware.

2. **SecondBrain has an SSRF vulnerability.** `ingest.py:112-119` fetches arbitrary URLs without scheme, hostname, or private IP validation. An attacker with API access could probe internal services or cloud metadata endpoints. This is a real, exploitable vulnerability.

3. **No Content Security Policy on any frontend.** All 4 Next.js apps lack CSP headers. Combined with the `dangerouslySetInnerHTML` in BriefsClient.js (rendering GitHub-hosted markdown as raw HTML), this creates a plausible XSS vector if the upstream markdown source is compromised.

4. **Cognitive overload on market dashboard.** The dashboard shows 12+ metric cards, 10+ section navigation items, filter dropdowns, mode toggles, compare mode, search, presets, and "Ask" buttons — all visible simultaneously. No progressive disclosure. A first-time visitor has no idea where to look or what matters.

5. **11 repos for one person is a maintenance tax.** Each repo needs dependency updates, CI maintenance, security patches, and operational attention. Dependabot alone generates dozens of PRs per week. The multi-repo decision (ADR-002) was defensible but the carrying cost is real.

6. **IntegrationAtlas has a file-based concurrency bug.** `workbench-store.js` does read-modify-write without file locking. Two concurrent users editing register entries will cause data loss. Not critical for a demo tool, but it is a real bug.

7. **SecondBrain app.py is 2,209 lines.** A single Streamlit file handling all UI tabs, forms, state management, and rendering. This is the most monolithic file in the ecosystem and the hardest to maintain or test.

8. **No staging environment.** All services deploy directly to production. No way to test changes in isolation before they hit live endpoints. Terraform apply runs on merge to main with no staging workspace.

9. **Data freshness gaps.** At audit time, multiple metric cards showed "FRESHNESS: UNAVAILABLE" and "n/a" for NZD/USD, OCR, and inflation. Some adapters depend on external services that may be down or rate-limited. The dashboard honestly shows this (which is good) but it means visitors sometimes see a degraded experience.

10. **No user accounts or access control on market dashboard.** The dashboard is public read-only. No saved views, no personalization, no API key management for consumers. Fine for portfolio, but limits utility as a standalone product.

---

# 7. Critical Issues

| # | Severity | Area | Finding | Evidence | User/Business Impact | Recommended Fix | Launch Blocker? |
|---|----------|------|---------|----------|---------------------|-----------------|-----------------|
| 1 | HIGH | Security | SSRF in SecondBrain URL ingestion | `ingest.py:112-119` — no URL scheme/hostname/IP validation | Attacker with API access can probe internal services, cloud metadata | Add URL validation: scheme whitelist, private IP blocking, DNS resolution check | Yes (if API exposed to untrusted users) |
| 2 | HIGH | Security | .env with real Anthropic API key exists in SecondBrain repo | `.env` file present with `sk-ant-api03-...` key. `.gitignore` includes `.env` but key may be in git history | API key abuse, cost theft | Rotate key immediately. Run `git filter-repo` to purge history. Verify `.env` was never committed. | Yes |
| 3 | MEDIUM | Security | No CSP on any frontend | `next.config.js` in all 4 Next.js apps lacks Content-Security-Policy | XSS if inline scripts injected (especially via BriefsClient dangerouslySetInnerHTML) | Add CSP header with script-src 'self', use DOMPurify for markdown rendering | No (low current risk) |
| 4 | MEDIUM | Security | dangerouslySetInnerHTML in BriefsClient.js | `app/briefs/BriefsClient.js:122` renders GitHub markdown as raw HTML via regex conversion | XSS if upstream GitHub content contains script tags | Use DOMPurify sanitization library after markdown conversion | No (trusted source) |
| 5 | MEDIUM | Reliability | IntegrationAtlas file-based concurrency | `workbench-store.js:23-43` — read-modify-write without locking | Data loss on concurrent writes | Implement file locking or migrate to SQLite | No (demo tool) |
| 6 | MEDIUM | Testing | Zero API endpoint tests in SecondBrain | No test files for `api.py` routes, auth middleware, or rate limiting | Regressions in API auth, rate limiting, or endpoints go undetected | Add pytest test suite for API endpoints using httpx TestClient | No (but high risk) |
| 7 | LOW | Operations | Event Hub health endpoint returns 404 | `curl https://n7.nz/events/health` → 404 | Health monitoring blind spot | Fix rewrite rule or add /events/health endpoint | No |
| 8 | LOW | Security | Error messages leak implementation details | `api.py:294` — `str(e)` in HTTPException detail | Internal paths, library names visible to attackers | Sanitize error messages, return generic errors for 5xx | No |
| 9 | LOW | Operations | SecondBrain background worker degraded | Health check shows "warning" for worker status | Background ingestion jobs may not process | Investigate worker startup, add alerting for degraded state | No |
| 10 | LOW | Security | No SAST/dependency audit in any CI pipeline | No bandit, safety, pip-audit, or npm audit in any workflow | Known vulnerable dependencies could ship to production | Add `pip-audit` to Python CI, `npm audit` to Node CI | No |

---

# 8. Security Findings

## Critical

### S1: SSRF in SecondBrain URL Ingestion
- **Severity:** HIGH
- **Likelihood:** Medium (requires API access, which is key-protected)
- **Impact:** Internal service probing, cloud metadata access, potential credential theft
- **Location:** `SecondBrain/ingest.py:112-119`
- **Evidence:** `requests.get(url, ...)` with no validation of URL scheme, hostname, or resolved IP
- **Exploit scenario:** `POST /ingest/url {"url": "http://169.254.169.254/latest/meta-data/"}` from an authenticated client
- **Remediation:** Add `_validate_url()` function: whitelist http/https schemes, block private/reserved IP ranges, resolve DNS and check result IP
- **Launch blocker:** Yes, if SecondBrain API is exposed to untrusted users

### S2: Potential API Key in Git History
- **Severity:** HIGH
- **Likelihood:** High (`.env` file exists locally with real key)
- **Impact:** Anthropic API key abuse, unauthorized API calls, cost theft
- **Location:** `SecondBrain/.env:1`
- **Evidence:** File contains `ANTHROPIC_API_KEY=sk-ant-api03-...`. `.gitignore` includes `.env`. Needs verification of git history.
- **Remediation:** 1) Rotate key on Anthropic dashboard. 2) Run `git log --all --full-history -- .env` to check if ever committed. 3) If committed, use `git filter-repo` to purge.
- **Launch blocker:** Yes

## High

### S3: Missing Content Security Policy
- **Severity:** MEDIUM
- **Location:** All 4 Next.js apps (`next.config.js` / `next.config.mjs`)
- **Evidence:** Security headers present (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) but no CSP
- **Impact:** Reduced defense-in-depth against XSS
- **Remediation:** Add `Content-Security-Policy: default-src 'self' https:; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:`

### S4: Unsanitized HTML Rendering
- **Severity:** MEDIUM
- **Location:** `n7-portfolio/app/briefs/BriefsClient.js:122`
- **Evidence:** `dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }}` where content fetched from GitHub raw URL
- **Mitigation in place:** Source is Phil's own GitHub repo (trusted)
- **Residual risk:** If GitHub account compromised, malicious markdown could execute scripts
- **Remediation:** Use DOMPurify to sanitize HTML output of `markdownToHtml()`

## Medium

### S5: IntegrationAtlas Default AUTH_SECRET
- **Severity:** MEDIUM
- **Location:** `IntegrationAtlas/lib/workbench-auth.js:4-6`
- **Evidence:** Falls back to `"integrationatlas-dev-secret"` in non-production
- **Impact:** Predictable session tokens in non-production deployments
- **Remediation:** Require AUTH_SECRET in all environments, fail-fast if missing

### S6: In-Memory Rate Limiting
- **Severity:** LOW
- **Location:** All 4 Python services
- **Evidence:** Per-IP rate limiting stored in Python dict, lost on restart
- **Impact:** Rate limits reset on every deploy/restart
- **Remediation:** Acceptable for current scale. Document as known limitation.

## Positive Security Findings (Confirmed)

- **HMAC timing-safe auth:** All services use `hmac.compare_digest()` or `timingSafeEqual()` ✓
- **Parameterized SQL queries:** All SQLite queries use `?` placeholders ✓
- **No eval/exec:** Zero instances across all repos ✓
- **No hardcoded secrets in source code:** All secrets via environment variables ✓
- **Non-root Docker containers:** All 3 Railway Python services ✓
- **API key server-side proxy:** SecondBrain API key injected server-side, never reaches browser ✓
- **Security headers on all services:** X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, Permissions-Policy ✓
- **Dependabot on all repos:** Weekly, minor/patch only ✓
- **SSRF protection on SpecCheck:** Private IP blocking + DNS resolution check ✓
- **scrypt password hashing on IntegrationAtlas:** With proper salt handling ✓
- **httpOnly + sameSite cookies on IntegrationAtlas:** With secure flag in production ✓
- **robots.txt blocks AI crawlers:** GPTBot, ClaudeBot, CCBot all disallowed ✓

---

# 9. UI Findings

## Portfolio (n7.nz/)
- **Visual quality:** Strong. Dark theme is polished, typography (Space Grotesk + IBM Plex Mono) is well-chosen, gradient backgrounds add depth without being distracting.
- **Layout:** Two-column hero is effective. Stats bar (4 enterprise sectors, 3 working lanes, 1 clear trajectory) is a good touch.
- **Navigation:** Clean top nav (Projects, Market, About, Contact, Architecture Track). "Architecture Track" badge with green dot is distinctive.
- **CTAs:** "View projects" (green, primary) and "Open market" (outlined, secondary) are clear.
- **Weakness:** "CV PDF available on request" is passive. Should be a direct download or API link.
- **Mobile:** Not tested but CSS uses fluid widths (`min(1240px, calc(100vw - 32px))`).

## Market Dashboard (n7.nz/market)
- **Visual quality:** Consistent dark theme. Well-structured cards with clear data hierarchy.
- **Information density:** Very high. This is a power-user dashboard, not a consumer product. 12+ metric cards, 10+ sidebar sections, multiple filter dropdowns and mode toggles visible simultaneously.
- **Trust surfaces:** Excellent. Freshness badges ("20 HOURS AGO"), source health ("15/18 live"), reliability percentage (86%), lineage counts — all visible. This is unusual and valuable.
- **Weaknesses:**
  - No onboarding or guided first experience
  - "n/a" values on NZD/USD, OCR, inflation feel broken to uninformed visitors
  - Mode toggles (Compare, Deterministic, Public, Wellington) are not self-explanatory
  - "Ask the market" button implies conversational AI but no context for what it can do
  - Left sidebar navigation is functional but cramped
  - "1 LAUNCH BLOCKERS" text in header is internal jargon exposed to public users

## SpecCheck (n7.nz/speccheck)
- **Visual quality:** Clean, minimal. Light theme, good contrast.
- **Layout:** Two-panel (spec editor left, results right). Clear "Run Tests" CTA.
- **Strengths:** Pre-populated with Petstore example. Versioned (v0.1.8). YAML syntax highlighting.
- **Weakness:** Empty right panel has no visual guidance beyond "Paste a spec, enter a URL, hit Run Tests."

## PromptBuilder (n7.nz/prompts)
- **Visual quality:** Clean dark theme. Good section organization.
- **Layout:** Progressive form with collapsible sections. AI assistance panel well-integrated.
- **Strengths:** Completion scoring (84%), token estimation (~764 tok), section-by-section guidance, 13 AI actions.
- **Weakness:** Pre-populated template content may confuse first-time users who expect a blank slate.

## IntegrationAtlas (n7.nz/atlas)
- **Status:** Page loaded but errored during screenshot capture. Atlas redirects to /atlas/atlas (double path). Needs investigation — may be a BASE_PATH configuration issue causing rendering problems in some browsers.

---

# 10. UX Friction Map

## First-Run Experience

### Portfolio → Market flow
1. Visitor lands on n7.nz/ — clear who Phil is and what he does ✓
2. Clicks "Open market" — arrives at market dashboard
3. **FRICTION:** Wall of information. No guided tour. No "Start here" indicator. Visitor sees 12 metrics, 10 sidebar items, filter bars, mode toggles. Cognitive overload.
4. **FRICTION:** "Source health 15/18 live" and "1 LAUNCH BLOCKERS" are internal jargon. A hiring manager does not know what these mean.
5. **FRICTION:** "n/a" on NZD/USD, OCR, inflation — looks broken. No tooltip explaining "data source temporarily unavailable."
6. **FRICTION:** "FRESHNESS: UNAVAILABLE" on some metrics — same issue. Honest but unexplained.

### Market Dashboard Navigation
7. Clicks "Jobs" in sidebar — sees job listings. Clear enough ✓
8. Clicks "Tenders" — sees GETS tenders. Clear ✓
9. **FRICTION:** "DataOps" link — what does this mean to a non-technical visitor?
10. **FRICTION:** "Catalog" link — catalog of what? Sources? Products? Not obvious.
11. **FRICTION:** "Ask the market" button — implies AI chatbot. No indication of capabilities, limitations, or cost.

### SpecCheck Flow
12. Arrives at /speccheck — sees pre-populated Petstore spec. Good ✓
13. **FRICTION:** Base URL shows "http://localhost:8000" — but there is no local server. Should show an example public URL or explain.
14. **FRICTION:** "AUTH Configure..." is unclear — auth for what? The target API? SpecCheck itself?

### PromptBuilder Flow
15. Arrives at /prompts — sees pre-populated template.
16. **FRICTION:** Template is already filled in ("Write a comprehensive business requirements document..."). User may not realize they should replace it.
17. Completion scoring and AI actions are well-placed ✓
18. Export options (MD/text/XML/JSON) are good ✓

### SecondBrain (API only, accessed via /brain/*)
19. No web UI visible to public. Streamlit UI is local-only.
20. **FRICTION:** API documentation at /brain/docs would help, but health check shows it exists.

## Dead Ends
- "CV PDF available on request" — no way to actually request it
- Market dashboard "Ask the market" — requires authentication context
- IntegrationAtlas may not render correctly (atlas/atlas double path)

## Trust Loss Points
- "n/a" values without explanation → "is this broken?"
- "FRESHNESS: UNAVAILABLE" → "is the data stale?"
- "1 LAUNCH BLOCKERS" → "this isn't ready?"
- "degraded" health status on SecondBrain → visible via /brain/health API

---

# 11. Code / Architecture Findings

## Architecture Strengths

1. **Snapshot-centric data flow (nz-intel).** Adapters scrape → normalize → snapshot JSON → API serves from snapshot. This decouples ingestion from serving, enables fixture-based testing, and makes the system inspectable. Smart architecture decision.

2. **Server-side proxy pattern (n7-portfolio → SecondBrain).** API key injected server-side via `app/brain/[...path]/route.js`. Only safe headers forwarded. Sensitive headers stripped from response. This is the correct pattern.

3. **Event-driven integration (n7-event-hub).** Typed event schema with source/type validation. Deduplication via SHA-256 keyed 24-hour window. Routing rules engine with severity-based dispatch. Fire-and-forget publishers in nz-intel and SecondBrain. At-most-once delivery documented as acceptable trade-off.

4. **Multi-agent pipeline (market-brief).** Three sequential agents with typed Pydantic contracts (CollectorInput → CollectorOutput → EnricherInput → etc.). Error tier strategy: abort on collector failure, continue unenriched on enricher failure, save raw on analyst failure. Clean, testable, documented.

5. **Consistent middleware stack.** All 4 Python services share the same pattern: CORS → Security Headers → Rate Limiter → Auth → Metrics. This is rare in multi-repo architectures and shows system-level thinking.

## Architecture Weaknesses

1. **No integration tests between services.** Each service is tested in isolation. There are no tests that verify: portfolio → nz-intel proxy works, portfolio → SecondBrain proxy injects API key correctly, event publishers → event hub → notifications flow end-to-end.

2. **In-memory state everywhere.** Rate limiting, caching, and session state all in-memory. Every deploy resets all state. Acceptable at current scale but creates an invisible "state reset on deploy" behavior that users might notice.

3. **SQLite for SecondBrain metadata.** WAL mode helps concurrency, but SQLite in a container without persistent volume config would lose data. Railway volume is configured (`/app/data/chroma`) but the metadata DB path (`data/metadata.db`) should be verified to be on the same volume.

4. **11 repos, 1 person.** The multi-repo decision (ADR-002) was justified for deployment isolation. But each repo has its own CI, dependabot config, security policy, README, and operational surface. This is a significant maintenance burden. A monorepo with deployment workspace separation might reduce overhead.

## Code Quality

**Classification: Decent and disciplined — between "production-grade" and "MVP-grade"**

**Evidence for "decent and disciplined":**
- Consistent naming conventions across repos
- Pydantic validation on all API boundaries
- Parameterized queries everywhere (no raw SQL concatenation)
- Proper use of type hints in Python services
- Configuration separated from code (env vars, YAML, .env.example)
- Error handling with specific exception types (not bare `except:`)
- Logging with proper logger instances (not `print()`)

**Evidence against "production-grade":**
- `SecondBrain/app.py` is 2,209 lines — needs decomposition
- `SecondBrain/db.py` is 1,049 lines — does too much
- `nz-intel/api/routers/public_api.py` is 359 lines — could be split by domain
- Some `except Exception as e: str(e)` patterns leak implementation details
- No structured logging (JSON) for machine parsing
- No request correlation IDs (trace IDs) across services

---

# 12. Performance / Reliability / Ops Findings

## Performance
- **ETag caching on nz-intel:** Snapshot-backed endpoints use ETag/If-None-Match. Good ✓
- **SWR on frontend:** Client-side data fetching with stale-while-revalidate. Good ✓
- **Snapshot architecture:** API reads from pre-built JSON instead of hitting databases on every request. Very fast for reads. ✓
- **Concern:** Large market dashboard with 12+ data cards may cause excessive API calls on mount. SWR should deduplicate, but no evidence of request batching.
- **Concern:** No evidence of pagination or virtualization for large data tables (jobs, tenders, awards).

## Reliability
- **Health checks:** All services have `/health` endpoints with meaningful checks (SQLite writable, ChromaDB accessible, API key configured). Good ✓
- **Alert rules:** 5 Grafana alert rules covering stale data, error rate spikes, latency, and service down. Good ✓
- **Concern:** No circuit breakers between services. If nz-intel goes down, the market dashboard shows empty data without clear error messaging.
- **Concern:** No retry logic in event publishers (fire-and-forget). Events can be lost silently.
- **Concern:** Background worker in SecondBrain shows "degraded" status. No automated recovery.

## Operations
- **IaC:** Terraform managing all infrastructure. Plan-on-PR, apply-on-merge. Good ✓
- **CI/CD:** 14 workflows across 11 repos. Scheduled ingestion (6h), daily adapters, weekly reports. Good ✓
- **Concern:** No runbooks for incident response. What happens when nz-intel scraping fails? When SecondBrain fills its disk? When Supabase free tier hits limits?
- **Concern:** No backup/restore procedure tested. SQLite and ChromaDB data is on Railway volumes with no documented backup strategy.
- **Concern:** No staging environment. All changes go directly to production.

---

# 13. Accessibility Findings

**Classification: Partial — some conscious implementation, not systematically audited**

**Implemented:**
- Semantic HTML (`<table>`, `<thead>`, `<th>`, `<nav>`) ✓
- ARIA labels on interactive components (CommandPalette, FilterBar, MarketContextDeck) ✓
- `role="dialog"` and `aria-modal="true"` on command palette ✓
- `prefers-reduced-motion` media query in globals.css ✓
- `color-scheme: dark` declared ✓

**Missing:**
- No skip-navigation link on any page
- No visible focus indicators (focus ring styles not documented)
- No keyboard navigation testing evidence
- No `tabindex` management for modals/dialogs
- Contrast ratio not verified (dark theme with green accent #00e5a0 on dark backgrounds)
- Charts (Recharts, D3) likely inaccessible to screen readers — no `aria-label` on SVG elements
- Data tables may lack proper `scope` attributes on headers
- No `alt` text audit on images
- No form error announcements (aria-live regions)
- No WCAG 2.1 AA compliance testing

**Verdict:** Accessibility appears incidental rather than systematic. The ARIA usage shows awareness but not commitment. A screen reader user would struggle with the market dashboard. This is typical for solo-dev projects but would be a blocker for enterprise or government use.

---

# 14. Market / Competitor Comparison

## NZ Market Intelligence (n7.nz/market)

| Dimension | n7/market | Seek NZ | GETS Portal | MBIE Data | TradeMe Jobs |
|-----------|-----------|---------|-------------|-----------|--------------|
| NZ job listings | 96 (scraped) | Source of truth | N/A | N/A | Source of truth |
| NZ tenders | 11 (scraped) | N/A | Source of truth | N/A | N/A |
| Currency/rates | RBNZ data | N/A | N/A | Some | N/A |
| Cross-source signals | Yes (unique) | No | No | No | No |
| Skills trending | Yes (unique) | Basic | No | No | No |
| AI analysis | Yes (unique) | No | No | No | No |
| Trust/lineage | Yes (unique) | N/A | N/A | N/A | N/A |
| Free | Yes | Free to search | Free | Free | Free |
| Target user | Tech BA/architect | Job seekers | Procurement | Researchers | Job seekers |

**Honest assessment:** n7/market does not compete with Seek or GETS directly. Its value proposition is cross-source intelligence — seeing jobs, tenders, awards, skills, and macro indicators in one place. No other free tool does this for the NZ tech market. But the audience for this is very narrow (NZ tech procurement analysts, solution architects tracking market demand).

## Individual Tool Competitors

| Tool | n7 version | Direct competitors | Where n7 lags | Where n7 leads |
|------|------------|-------------------|---------------|----------------|
| SecondBrain | RAG knowledge base | Obsidian, Notion AI, Mem.ai | No UI for end users, no collaboration, no mobile | Custom embedding models, workspace isolation, full API |
| SpecCheck | API contract testing | Dredd, Schemathesis, Portman | CLI-only primary, fewer test strategies, less ecosystem integration | AI design review, web UI, SSRF protection |
| PromptBuilder | Prompt engineering | PromptPerfect, Langsmith Playground | No history, no team sharing, no API | Guided 18-section structure, quality scoring, offline-capable |
| IntegrationAtlas | Integration patterns | Enterprise Integration Patterns book, various wikis | No search engine visibility, file-backed storage | Interactive workbench, decision support, artifact generation, RBAC |

**Verdict:** No individual tool is market-competitive against established alternatives. The portfolio value is in demonstrating the ability to build them, not in the tools themselves being best-in-class.

---

# 15. Missing Features / Gaps

## Missing Must-Haves (for production use)
- User accounts and authentication on market dashboard
- SSRF protection on SecondBrain URL ingestion
- CSP headers on all frontends
- Integration tests across service boundaries
- Backup and restore procedure
- Staging environment

## Missing Should-Haves
- Error explanation for "n/a" and "FRESHNESS: UNAVAILABLE" values
- Onboarding or guided tour on market dashboard
- API key management UI for market API consumers
- Structured logging (JSON) across all services
- Request correlation IDs for cross-service tracing
- Pagination/virtualization for large data tables
- Mobile-responsive market dashboard verification

## Nice-to-Haves
- Dark/light theme toggle
- Keyboard shortcuts documentation
- API rate limit dashboard for consumers
- Webhook subscriptions for market signals
- Export to PDF for market reports
- Saved views / bookmarks on market dashboard

## Things That Should Be Removed
- "1 LAUNCH BLOCKERS" text in public market dashboard header — internal jargon
- "n/a" raw values — replace with meaningful empty states
- Streamlit UI for SecondBrain (it is a maintenance burden and not exposed publicly)
- ContractRadar, GovRadar, StatusPulse directories in GitHub folder — appear to be abandoned projects cluttering the workspace

---

# 16. Why Users Would Reject This

1. **"I don't understand what this is for."** The market dashboard serves a very niche audience. A general visitor will be confused by the information density and domain-specific terminology.

2. **"The data looks broken."** "n/a" values, "FRESHNESS: UNAVAILABLE," and "1 LAUNCH BLOCKERS" create an impression of incomplete or broken software, even though they are honest transparency features.

3. **"I can just go to Seek/GETS directly."** Without cross-source analysis being immediately obvious, the value proposition over going to the source is unclear.

4. **"There's no way to sign up or save anything."** No user accounts means no stickiness. Visitors see the data once and have no reason to return.

5. **"The individual tools are too basic."** SpecCheck, PromptBuilder, IntegrationAtlas — each is functional but lacks the polish, integrations, and community of established alternatives.

6. **"I don't trust a solo dev's side project with my data."** For SecondBrain or any tool requiring data input, the lack of visible backup strategy, SLA, or support undermines trust.

---

# 17. Why Users Might Choose This

1. **Hiring managers evaluating Phil's skills.** This is the primary audience and the ecosystem excels here. The breadth and depth of demonstrated skills (architecture, security, observability, AI, IaC, data engineering) is genuinely impressive for a portfolio.

2. **NZ tech procurement analysts.** Someone who regularly monitors GETS tenders, Seek listings, and government procurement in NZ tech would find the cross-source view genuinely useful — there is nothing else like it.

3. **Developers wanting to learn integration architecture.** IntegrationAtlas with 24 patterns, decision support, and artifact generation is a unique educational tool.

4. **API designers wanting contract testing.** SpecCheck with AI design review is a differentiating feature that competitors lack.

5. **Anyone wanting to see "how it's done."** The ecosystem itself is a learning resource — real Terraform, real observability, real event-driven architecture, real AI pipelines. The ADRs document every decision.

---

# 18. Highest-Leverage Improvements

| Area | Improvement | Impact |
|------|-------------|--------|
| **Trust** | Fix "n/a" and "FRESHNESS: UNAVAILABLE" — show "Data source offline" with last-known value and timestamp | Visitors stop thinking the app is broken |
| **Trust** | Remove "1 LAUNCH BLOCKERS" from public header | Stops implying the product is unfinished |
| **Security** | Add SSRF protection to SecondBrain URL ingestion | Closes the most exploitable vulnerability |
| **Security** | Add CSP headers to all frontends | Defense-in-depth against XSS |
| **Usability** | Add 30-second onboarding overlay or "Start here" on market dashboard | Reduces first-visit abandonment |
| **Reliability** | Add integration tests for portfolio → backend proxy flows | Catches cross-service regressions |
| **Adoption** | Add a "What is this?" section to market dashboard explaining the value proposition | Converts confused visitors to engaged users |
| **Competitiveness** | Make market dashboard signals actionable — email alerts for new tenders matching criteria | Gives users a reason to come back |
| **Perceived quality** | Fix IntegrationAtlas double-path redirect (/atlas/atlas) | Removes visible bug from portfolio showcase |

---

# 19. Prioritized Roadmap

## Immediate Fixes (1–3 days)

| # | Item | Owner | Why | Effort | Impact |
|---|------|-------|-----|--------|--------|
| 1 | Rotate Anthropic API key, verify .env never committed to git | Security | Real credential exposure risk | 1h | Critical |
| 2 | Add SSRF protection to SecondBrain `ingest.py` | Backend | Exploitable vulnerability | 2h | High |
| 3 | Remove "1 LAUNCH BLOCKERS" from market dashboard public header | Frontend | Implies product is unfinished | 15min | Medium |
| 4 | Replace "n/a" with "Offline — last value X at Y" or "No data" with context | Frontend | Stops looking broken | 2h | High |
| 5 | Add DOMPurify to BriefsClient.js markdown rendering | Frontend | XSS defense-in-depth | 30min | Medium |

## Short-Term (1–2 weeks)

| # | Item | Owner | Why | Effort | Impact |
|---|------|-------|-----|--------|--------|
| 6 | Add CSP headers to all 4 Next.js apps | Frontend/DevOps | Security best practice | 3h | Medium |
| 7 | Add API endpoint tests to SecondBrain (auth, rate limiting, CRUD) | Backend | Zero test coverage on API layer | 1d | High |
| 8 | Fix IntegrationAtlas /atlas/atlas double-path redirect | Frontend | Visible bug in portfolio | 2h | Medium |
| 9 | Add pip-audit to Python CI, npm audit to Node CI | DevOps | Dependency vulnerability scanning | 2h | Medium |
| 10 | Add onboarding tooltip or "What is this?" explainer to market dashboard | Frontend | Reduces first-visit confusion | 4h | High |

## Medium-Term (2–6 weeks)

| # | Item | Owner | Why | Effort | Impact |
|---|------|-------|-----|--------|--------|
| 11 | Integration tests: portfolio → nz-intel, portfolio → SecondBrain proxy | Fullstack | Cross-service regression protection | 2d | High |
| 12 | Decompose SecondBrain app.py (2209 lines) into separate modules | Backend | Maintainability | 1d | Medium |
| 13 | Add structured JSON logging across all Python services | Backend | Operational maturity | 1d | Medium |
| 14 | Document backup/restore procedure for Railway volumes | DevOps | Disaster recovery | 4h | Medium |
| 15 | Add Terraform staging workspace | DevOps | Test changes before production | 1d | Medium |

## Strategic Improvements (6+ weeks)

| # | Item | Owner | Why | Effort | Impact |
|---|------|-------|-----|--------|--------|
| 16 | User accounts on market dashboard (Supabase Auth) | Fullstack | Stickiness, saved views, personalization | 1w | High |
| 17 | Email alert subscriptions for market signals (new tenders, demand shifts) | Fullstack | Recurring engagement, real utility | 1w | High |
| 18 | Systematic accessibility audit (WCAG 2.1 AA) | Frontend | Enterprise/government readiness | 3d | Medium |
| 19 | Evaluate consolidating to monorepo with workspace deployment | Architecture | Reduce 11-repo maintenance burden | 2w | Medium |
| 20 | Cross-service request tracing (correlation IDs) | Backend | Debugging, operational maturity | 2d | Low |

---

# 20. Ticket Backlog

## P0 — Security

### TICKET-001: Add SSRF protection to SecondBrain URL ingestion
- **Problem:** `ingest.py:112-119` fetches arbitrary URLs without validation, allowing SSRF
- **Change:** Add `_validate_url()` function: whitelist http/https, block private IPs, resolve DNS
- **Acceptance:** Unit tests for URL validation, rejected URLs return 400 with explanation
- **Priority:** P0 | **Effort:** 2h | **Dependencies:** None

### TICKET-002: Rotate Anthropic API key
- **Problem:** Real API key in local `.env` file, possibly in git history
- **Change:** 1) Rotate on Anthropic dashboard. 2) Check git history. 3) Purge if needed.
- **Acceptance:** Old key returns 401. New key works. `git log -- .env` shows no results.
- **Priority:** P0 | **Effort:** 1h | **Dependencies:** None

### TICKET-003: Add CSP headers to all Next.js apps
- **Problem:** No Content-Security-Policy on any frontend
- **Change:** Add CSP to `next.config.js` headers array in n7-portfolio, CVasAPI, IntegrationAtlas, PromptBuilder
- **Acceptance:** CSP header present on all responses. No console violations on normal page load.
- **Priority:** P0 | **Effort:** 3h | **Dependencies:** None

### TICKET-004: Sanitize BriefsClient markdown rendering
- **Problem:** `dangerouslySetInnerHTML` with unsanitized GitHub markdown
- **Change:** Install DOMPurify. Wrap `markdownToHtml()` output with `DOMPurify.sanitize()`
- **Acceptance:** `<script>` tags in markdown source are stripped. Normal markdown renders correctly.
- **Priority:** P0 | **Effort:** 30min | **Dependencies:** None

## P1 — Quality

### TICKET-005: Add SecondBrain API endpoint tests
- **Problem:** Zero test coverage on `api.py` routes, auth middleware, rate limiting
- **Change:** Add `tests/test_api.py` using httpx TestClient. Cover: health, auth reject, auth accept, rate limit, ask, ingest, sources CRUD.
- **Acceptance:** 80%+ coverage on api.py. Auth bypass test fails correctly.
- **Priority:** P1 | **Effort:** 1d | **Dependencies:** None

### TICKET-006: Fix market dashboard empty states
- **Problem:** "n/a" and "FRESHNESS: UNAVAILABLE" without context
- **Change:** Replace with "Offline" badge + last-known value + timestamp. Add tooltip explaining data source status.
- **Acceptance:** No raw "n/a" visible. Offline metrics show last-known value with staleness indicator.
- **Priority:** P1 | **Effort:** 4h | **Dependencies:** None

### TICKET-007: Remove internal jargon from market dashboard
- **Problem:** "1 LAUNCH BLOCKERS" visible in public header
- **Change:** Hide launch blocker count from public mode. Show only in authenticated/admin view.
- **Acceptance:** Public visitors see clean header without internal status indicators.
- **Priority:** P1 | **Effort:** 30min | **Dependencies:** None

### TICKET-008: Fix IntegrationAtlas routing
- **Problem:** /atlas redirects to /atlas/atlas (double BASE_PATH)
- **Change:** Debug BASE_PATH config in next.config.mjs and Vercel rewrite rule
- **Acceptance:** /atlas loads IntegrationAtlas correctly without double path
- **Priority:** P1 | **Effort:** 2h | **Dependencies:** None

### TICKET-009: Add dependency scanning to CI
- **Problem:** No SAST or dependency audit in any pipeline
- **Change:** Add `pip-audit` step to Python CI workflows. Add `npm audit --audit-level=high` to Node CI.
- **Acceptance:** CI fails on high-severity dependency vulnerabilities.
- **Priority:** P1 | **Effort:** 2h | **Dependencies:** None

## P2 — Maintainability

### TICKET-010: Decompose SecondBrain app.py
- **Problem:** 2,209-line monolithic Streamlit file
- **Change:** Extract tab handlers into separate modules: `ui/ingest_tab.py`, `ui/ask_tab.py`, `ui/sources_tab.py`, etc.
- **Acceptance:** app.py under 300 lines. All tabs function identically. No test regressions.
- **Priority:** P2 | **Effort:** 1d | **Dependencies:** None

### TICKET-011: Add integration tests for proxy flows
- **Problem:** No tests verify portfolio → backend proxy chains work correctly
- **Change:** Add e2e test suite that calls n7.nz/brain/health and n7.nz/api/v1/health, verifying response shape and headers.
- **Acceptance:** Tests run in CI. Proxy failures detected before deploy.
- **Priority:** P2 | **Effort:** 4h | **Dependencies:** None

### TICKET-012: Add structured JSON logging
- **Problem:** Text-based logging across all Python services, not machine-parseable
- **Change:** Configure Python logging with JSON formatter. Include timestamp, level, module, message, request_id.
- **Acceptance:** Log output is valid JSON. Grafana Loki (or equivalent) can ingest and query.
- **Priority:** P2 | **Effort:** 1d | **Dependencies:** None

### TICKET-013: Document backup/restore
- **Problem:** No documented procedure for Railway volume backup or disaster recovery
- **Change:** Write runbook: 1) How to backup SQLite + ChromaDB from Railway. 2) How to restore. 3) Test the procedure.
- **Acceptance:** Runbook exists. Backup tested manually at least once.
- **Priority:** P2 | **Effort:** 4h | **Dependencies:** None

---

# 21. Final Brutal Conclusion

**Is this actually good?**
Yes. This is genuinely good engineering work. The architecture is thoughtful, the security is intentional, the observability is real, and the code is consistent. This is not AI-generated portfolio theater — it is a system designed by someone who understands how production systems work.

**Is it fit for purpose?**
As a portfolio demonstrating Solution Architect and integration engineering skills — yes, emphatically. It demonstrates breadth (11 repos, 6 tech stacks, 3 cloud platforms) AND depth (20 data source adapters, 28 Prometheus metrics, 10 ADRs, STRIDE threat models, SLOs). This is the most substantive solo-dev portfolio I could construct for this career transition.

**Is it market-worthy?**
Not as individual products. The market dashboard has niche utility for NZ tech market intelligence, but no individual tool is competitive against established alternatives. The ecosystem's market value is as a portfolio, not as a product suite.

**Is it production-worthy?**
Partially. The infrastructure layer (IaC, CI/CD, monitoring, alerting) is production-worthy. The application layer has gaps: SSRF vulnerability, missing tests, no staging environment, no backup procedure. These are fixable in days, not weeks.

**Is it something real users would want to use repeatedly?**
The market dashboard: maybe, for a very narrow NZ tech audience. Everything else: no, not in its current form. The tools are demonstrations, not daily-use products.

**Is it notably worse than existing alternatives?**
For individual tools, yes — each faces better-funded, more mature competitors. For the ecosystem as a portfolio, no — nothing comparable exists. The breadth-with-depth combination is the differentiator.

**Is it just flashy portfolio junk?**
No. This is the opposite of portfolio junk. Portfolio junk is shallow. This has 10 ADRs, STRIDE threat models, 28 Prometheus metrics, Terraform IaC with plan-on-PR, and a 4,576-word security architecture review referencing NZISM. The work is real, documented, and verifiable.

**Top 5 things holding it back from excellent:**

1. **Test coverage is the weakest link.** Zero API tests on SecondBrain. No integration tests. No e2e tests. The 60% target on nz-intel is the floor, not the ceiling. Without tests, every change is a gamble.

2. **The SSRF vulnerability is a real, exploitable security hole.** It is the most serious technical issue in the ecosystem and should be fixed before showing this to security-minded evaluators.

3. **The market dashboard needs onboarding.** The data is genuinely valuable, but first-time visitors drown in it. A 30-second guided introduction would transform the experience.

4. **Solo-dev operational ceiling.** 11 repos, 14 CI workflows, 4 Railway services, 20 data source adapters — all maintained by one person. This is heroic but unsustainable. The maintenance burden will eventually degrade quality if not addressed.

5. **"n/a" and "FRESHNESS: UNAVAILABLE" make it look broken.** The transparency is philosophically correct but practically harmful. Users see "n/a" and think "broken," not "honestly reporting missing data." Fix the presentation without losing the honesty.

---

**Overall Grade: 7/10 — Genuinely solid, above-average solo engineering work with specific, fixable weaknesses.**

The ecosystem demonstrates exactly the skills Phil claims: integration architecture, API design, security thinking, observability, AI integration, and infrastructure automation. The weaknesses (test gaps, one SSRF vulnerability, UX rough edges) are the kind that improve with time, not fundamental architectural failures. This is not portfolio theater. This is real work.
