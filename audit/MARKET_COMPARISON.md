# Market & Competitor Comparison — n7.nz Ecosystem

**Date:** 2026-04-05

---

## Ecosystem Positioning

The n7.nz ecosystem is not a single product competing in a single market. It is a portfolio platform containing 6+ distinct tools. Each tool faces different competitive dynamics.

---

## 1. NZ Market Intelligence Dashboard (n7.nz/market)

### Competitive Landscape

| Dimension | n7/market | Seek NZ | GETS Portal | MBIE Data | TradeMe Jobs | LinkedIn Talent Insights |
|-----------|-----------|---------|-------------|-----------|--------------|--------------------------|
| NZ job listings | 96 (scraped) | Source | N/A | N/A | Source | Partial |
| NZ tenders | 11 (scraped) | N/A | Source | N/A | N/A | N/A |
| Procurement awards | 127 (scraped) | N/A | Partial | N/A | N/A | N/A |
| Currency/rates | RBNZ (scraped) | N/A | N/A | Some | N/A | N/A |
| Cross-source signals | Yes | No | No | No | No | Limited |
| Skills trending | Yes | Basic | No | No | No | Yes (paid) |
| AI analysis | Yes (Claude) | No | No | No | No | No |
| Data lineage/trust | Yes | N/A | N/A | N/A | N/A | N/A |
| Price | Free | Free search | Free | Free | Free search | $10k+/yr |

### Assessment
- **Unique value:** Cross-source NZ tech market intelligence in one view. No free alternative exists.
- **Weakness:** Very narrow audience (NZ tech procurement, ~100-500 potential users). No user accounts, no saved views, no alerts.
- **Threat:** LinkedIn Talent Insights does similar cross-source analysis but globally and at enterprise price. MBIE could build their own dashboard.
- **Opportunity:** Email alerts for new tenders/jobs matching criteria. Saved search filters. API access for programmatic consumers.

---

## 2. SecondBrain (n7.nz/brain/*)

### Competitive Landscape

| Dimension | SecondBrain | Obsidian + Plugins | Notion AI | Mem.ai | Khoj |
|-----------|-------------|-------------------|-----------|--------|------|
| RAG knowledge base | Yes | Via plugins | Yes (paid) | Yes | Yes |
| Custom embeddings | Yes (4 models) | No | No | No | Yes |
| API-first | Yes (21 endpoints) | No | Limited | No | Yes |
| Self-hosted | Yes | Desktop app | No | No | Yes |
| Multi-workspace | Yes | Vaults | Workspaces | Auto | No |
| Web UI | Streamlit (local) | Desktop | Web | Web | Web |
| Mobile | No | Yes | Yes | Yes | Limited |
| Collaboration | No | Limited | Yes | No | No |
| Price | Free (self-host) | Free + $50/yr | $10/mo | $15/mo | Free |

### Assessment
- **Strength:** API-first design, custom embedding models, self-hosted, workspace isolation.
- **Weakness:** No web UI for end users (Streamlit is local-only). No collaboration. No mobile. No rich text editing.
- **Verdict:** Useful as a personal tool and portfolio demonstration. Not competitive as a product against Notion AI or Mem.ai. Khoj is the closest comparable open-source alternative and is more mature.

---

## 3. SpecCheck (n7.nz/speccheck)

### Competitive Landscape

| Dimension | SpecCheck | Schemathesis | Dredd | Portman | Optic |
|-----------|-----------|-------------|-------|---------|-------|
| OpenAPI contract testing | Yes | Yes | Yes | Yes | Yes |
| AI design review | Yes (unique) | No | No | No | No |
| Web UI | Yes | No | No | No | Yes |
| CLI | Yes | Yes | Yes | Yes | Yes |
| SSRF protection | Yes | N/A | N/A | N/A | N/A |
| Property-based testing | No | Yes | No | Yes | No |
| Community/ecosystem | Small | Large | Large | Medium | Medium |
| Price | Free | Free | Free | Free | Free/paid |

### Assessment
- **Differentiator:** AI-powered spec design review is unique. No competitor offers Claude-based architectural critique of OpenAPI specs.
- **Weakness:** Smaller test strategy set than Schemathesis. No property-based testing. Small community.
- **Opportunity:** The AI review feature could be a standalone SaaS product. "Paste your OpenAPI spec, get an architectural review" is a compelling pitch.

---

## 4. IntegrationAtlas (n7.nz/atlas)

### Competitive Landscape

| Dimension | IntegrationAtlas | EIP Book | MuleSoft Patterns | AsyncAPI Studio |
|-----------|-----------------|----------|-------------------|-----------------|
| Pattern catalog | 24 patterns | 65+ | Extensive | Focused on async |
| Interactive | Yes | No (book) | Partial | Yes |
| Decision support | Yes (unique) | No | No | No |
| Artifact generation | 18 types (unique) | No | Templates | Schema generation |
| RBAC | Yes (4 roles) | N/A | Enterprise | N/A |
| AI copilot | Yes (4 modes) | No | No | No |
| Price | Free | $50 book | Enterprise | Free |

### Assessment
- **Differentiator:** Interactive decision support + artifact generation + AI copilot. No other free tool combines these.
- **Weakness:** 24 patterns vs 65+ in the canonical EIP book. File-backed storage limits scalability. Potential routing bug (/atlas/atlas).
- **Opportunity:** Could be a genuinely useful teaching tool for integration architecture courses.

---

## 5. PromptBuilder (n7.nz/prompts)

### Competitive Landscape

| Dimension | PromptBuilder | PromptPerfect | Langsmith | Anthropic Console | ChatGPT |
|-----------|---------------|---------------|-----------|-------------------|---------|
| Guided sections | 18 (unique) | No | Playground | Workbench | No |
| Quality scoring | Yes (unique) | Score | Eval | No | No |
| Templates | 11 | Many | Some | No | No |
| Multi-model | Yes (selector) | Yes | LangChain | Anthropic only | OpenAI only |
| Undo/redo | 50-state | No | No | No | No |
| Offline capable | Yes | No | No | No | No |
| Price | Free | $10+/mo | Free tier | Free | Free |

### Assessment
- **Differentiator:** 18-section guided structure with AI-powered quality scoring. No competitor offers this level of prompt engineering guidance.
- **Weakness:** No history (across sessions), no team sharing, no API. Single-session tool.
- **Opportunity:** The guided structure approach could serve enterprise prompt governance needs.

---

## 6. Portfolio as a Whole

### What Hiring Managers Compare Against

| Dimension | n7.nz Ecosystem | Typical SA Portfolio | Best SA Portfolios |
|-----------|-----------------|---------------------|-------------------|
| Live services | 10 endpoints | 0-2 | 3-5 |
| IaC | Terraform (3 providers) | None | Terraform/Pulumi |
| Observability | Prometheus + Grafana | None | Basic monitoring |
| Security documentation | STRIDE + NZISM review | Basic README | Threat model |
| ADRs | 10 documented decisions | 0-2 | 3-5 |
| CI/CD | 14 workflows | 1-2 | 3-5 |
| Data engineering | 20 source adapters | None | Basic ETL |
| AI integration | 5 Claude integrations | 1 chatbot | 2-3 integrations |
| Event architecture | Event bus + routing | None | Basic pub/sub |
| Cost discipline | $25/month | Varies | Varies |

### Verdict
The n7.nz ecosystem is in the top tier of solution architect portfolios. The breadth-with-depth combination — IaC + observability + security + event architecture + AI + data engineering — running live, monitored, and documented — is exceptional for a solo developer.

---

## Strategic Positioning Recommendations

1. **Lead with the ecosystem, not individual tools.** The competitive advantage is the system, not any single component.

2. **Market dashboard is the best product candidate.** It serves a real niche (NZ tech market intelligence) with no free competitor. Add user accounts and email alerts to create stickiness.

3. **SpecCheck AI review is the best SaaS candidate.** "AI-powered API design review" is a clear, sellable value proposition with no direct competitor.

4. **Don't try to compete with Notion/Obsidian.** SecondBrain is a demonstration, not a product. Position it as such.

5. **IntegrationAtlas has educational value.** Consider partnering with integration architecture training providers.
