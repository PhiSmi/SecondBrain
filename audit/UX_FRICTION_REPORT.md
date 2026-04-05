# UX Friction Report — n7.nz Ecosystem

**Date:** 2026-04-05
**Method:** Manual walkthrough of all live endpoints + code review

---

## Journey 1: First-Time Portfolio Visitor

### Step 1: Land on n7.nz/
- **Experience:** Clean, professional portfolio page. Dark theme, clear hierarchy, strong typography.
- **Friction:** None. Purpose is immediately clear.
- **Grade:** A

### Step 2: Scan hero section
- **Experience:** Name, role, tagline, working lanes, CTA buttons all visible.
- **Friction:** Minor — "CV PDF available on request" is passive. No link, no mailto, no form. Dead end.
- **Grade:** B+

### Step 3: Click "Open market"
- **Experience:** Navigates to /market. Page loads quickly.
- **Friction:** Significant. Immediate information overload:
  - 12+ metric cards
  - 10 sidebar navigation items
  - 3 filter dropdowns
  - 7 mode toggle buttons
  - 4 preset buttons
  - Search bar
  - Compare mode
  - "Ask" button
  All visible simultaneously. No guidance on where to start.
- **Grade:** D

### Step 4: Try to understand market dashboard
- **Friction points:**
  - "Source health 15/18 live" — what are sources? Live vs what?
  - "1 LAUNCH BLOCKERS" — this isn't ready?
  - "Freshness 2026-04-04 08:11" — fresher than I expected, but what does freshness mean here?
  - "PUBLIC MODE" — am I on a limited view? What's the full view?
  - "Deterministic only Off" — what does this toggle do?
  - "Wellington mode" — geographic filter? Why is it separate from the "All NZ" dropdown?
  - Several metric cards show "n/a" and "FRESHNESS: UNAVAILABLE" — looks broken
- **Grade:** D-

### Step 5: Scroll to data sections
- **Experience:** Cards with "Explain" and "Inputs" buttons on each metric. "What changed" signal feed. "Time Travel" scrubber.
- **Friction:** "Explain" button — explain what? Does this call AI? Is it free? The button gives no indication.
- **Grade:** C

---

## Journey 2: NZ Tech Market Analyst (Target User)

### Step 1: Navigate to Jobs section
- **Experience:** Left sidebar → Jobs. Job listings visible.
- **Friction:** Minimal. Job listings with titles, companies, regions visible.
- **Grade:** B

### Step 2: Navigate to Tenders
- **Experience:** GETS tenders listed with agencies, dates, status.
- **Friction:** Minimal. Clear enough for someone who knows GETS.
- **Grade:** B

### Step 3: Try cross-source analysis
- **Friction:** How do I see which skills appear in both jobs AND tenders? Compare mode says "Pick agencies, suppliers, or skills to compare" but it is not immediately obvious how to use it.
- **Grade:** C

### Step 4: Check currency/macro
- **Friction:** NZD/USD shows "n/a." OCR shows "n/a." Inflation shows "n/a." Three of the four macro metrics are unavailable. This section looks abandoned.
- **Grade:** F (for this specific section at this time)

### Step 5: Read reports
- **Experience:** "Weekly 2026 W13" report available. Links to markdown.
- **Friction:** Report is generated prose — clear and readable.
- **Grade:** B+

---

## Journey 3: SpecCheck User

### Step 1: Arrive at /speccheck
- **Experience:** Clean two-panel layout. Pre-loaded Petstore example.
- **Friction:** None on arrival.
- **Grade:** A-

### Step 2: Try to run tests
- **Friction:** Base URL shows "http://localhost:8000" — I don't have a local server. Where should I point this? No example public URL provided.
- **Grade:** C

### Step 3: Understand auth
- **Friction:** "AUTH Configure..." — auth for what exactly? My target API? SpecCheck itself? Clicking shows a text field with placeholder "Bearer eyJhbGci..." — OK, it's for the target API. But the label "Configure..." is vague.
- **Grade:** C+

---

## Journey 4: PromptBuilder User

### Step 1: Arrive at /prompts
- **Experience:** Pre-populated template "BA Requirements Document." Guided sections visible.
- **Friction:** Template is already filled in. Am I supposed to modify it? Replace it? Start fresh? No clear "New prompt" or "Start blank" option visible.
- **Grade:** C+

### Step 2: Explore AI assistance
- **Experience:** "Enhance," "Rewrite Clearly," "Make Specific" buttons visible. Completion score (84%) shown.
- **Friction:** Minimal. AI actions are well-labeled.
- **Grade:** B+

### Step 3: Export
- **Experience:** Multiple export formats available (MD, text, XML, JSON).
- **Friction:** Minimal. Clear and functional.
- **Grade:** A-

---

## Journey 5: IntegrationAtlas User

### Step 1: Navigate to /atlas
- **Friction:** CRITICAL — page redirects to /atlas/atlas and may error in some browsers. Screenshot capture failed during audit. This is a broken first impression.
- **Grade:** F (if broken) / Could not fully evaluate

---

## Friction Summary

| Surface | First-Visit Grade | Returning User Grade | Critical Friction Points |
|---------|-------------------|----------------------|-------------------------|
| Portfolio (/) | A | A- | "CV PDF on request" dead end |
| Market (/market) | D | B | Information overload, "n/a" values, internal jargon |
| SpecCheck (/speccheck) | B | B+ | Localhost default URL, vague auth label |
| PromptBuilder (/prompts) | C+ | B+ | Pre-filled template confusion |
| IntegrationAtlas (/atlas) | F? | Unknown | Possibly broken routing |
| Briefs (/briefs) | B | B | Simple, functional |

---

## Top 5 UX Fixes by Impact

1. **Market dashboard onboarding** — Add a "Welcome to n7/market" modal or guided tour for first visit. Explain what the dashboard shows, what freshness/lineage/trust mean, and where to start. Dismiss permanently after first view.

2. **Fix "n/a" empty states** — Replace raw "n/a" with contextual empty states: "Data source offline — last updated [date]" or "No data available for this metric." Add tooltip explaining why.

3. **Remove internal jargon** — Hide "1 LAUNCH BLOCKERS" from public view. Change "Deterministic only" to "AI-free mode" or similar user-friendly label. Change "PUBLIC MODE" to just show a small badge if relevant.

4. **Fix IntegrationAtlas routing** — The /atlas/atlas double path is a broken portfolio showcase. This should be the highest-priority visible bug fix.

5. **SpecCheck default URL** — Change placeholder from "http://localhost:8000" to a working public API URL (e.g., "https://petstore3.swagger.io") so first-time users can run tests immediately without setup.
