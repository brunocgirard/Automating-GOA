# State-aware prompt for this app

Use this prompt when requesting changes to the Streamlit GOA/CRM app. It guides the assistant to inspect current state, confirm intent, and then implement with minimal churn. Emphasize clarity, invariants, and examples to reduce ambiguity.

```
You are working on the Streamlit GOA/CRM app. First, briefly summarize what you see in the repo that’s relevant to the request (current flows, key files, data sources, UI patterns). Then confirm what I’m trying to do, and explain how to apply it in this app’s context before coding.

What I need now (describe/confirm):
- Desired change/feature: {I will describe; restate in your own words}
- Where it should surface (UI area/page/section): {infer from current UI or ask if unclear}
- Persistence: how/where to save; which functions to call (report current functions/paths you find)
- Verification: how to confirm it works; any tests/manual steps (suggest based on current flows)

Use these clarifications, but answer them yourself when the code makes it clear; only ask if uncertain:
1) Which data source/mappings to use (Excel schema, template_utils, etc.)?
2) Where to read/write (DB functions, file paths)?
3) Any UI constraints (section editor, hide keys, preview behavior)?
4) Should outputs (HTML/PDF) be regenerated after save?
5) State invariants up front (what must not change: layout, styling, behaviors); list acceptance criteria and provide before/after examples when possible.

Workflow you should follow:
- Report current state relevant to the request (files, functions, UI patterns).
- Restate the goal and how it fits the current architecture; call out invariants to preserve.
- If anything is unclear, ask concise yes/no or short-choice questions; prefer minimal, localized changes.
- Propose a short plan (2–4 steps); then implement minimal changes.
- Summarize what changed (paths), how to verify (e.g., regenerate outputs, view editor/preview/download), acceptance checks, and follow-ups.
```
