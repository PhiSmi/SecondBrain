# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | Yes |

## Reporting a Vulnerability

If you discover a security vulnerability in SecondBrain, please report it responsibly.

**Contact:** phil@n7.nz

**What to include:**
- Description of the vulnerability
- Steps to reproduce
- Affected endpoints or components
- Potential impact

**Response timeline:**
- Acknowledgement within 48 hours
- Assessment and triage within 7 days
- Fix or mitigation plan within 30 days for confirmed issues

## Scope

The following are in scope for security reports:

- API endpoints under n7.nz/brain/*
- Authentication and authorisation bypass
- Input validation failures (SQL injection, SSRF via /ingest/url)
- Data exfiltration from the knowledge base
- Credential exposure

The following are out of scope:

- Denial of service through volumetric attacks
- Social engineering
- Findings from automated scanners without demonstrated impact
- Issues in third-party dependencies (report these upstream)
- The Streamlit UI (local-only interface, not publicly deployed)

## Security Architecture

- **Authentication:** API key gating (in progress)
- **Data storage:** SQLite (local) + ChromaDB (local vector store)
- **Secrets:** Environment variables via Railway dashboard; .env gitignored for local dev
- **Dependencies:** Pinned to exact versions in requirements.txt
- **LLM integration:** Anthropic Claude API; API key server-side only
