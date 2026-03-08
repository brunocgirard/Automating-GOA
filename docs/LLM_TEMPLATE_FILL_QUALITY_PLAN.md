# LLM Template Fill Quality Plan

## Purpose

This document captures the current analysis of why the LLM misses valid GOA fields, especially checkbox fields, and defines:

1. What needs to change in the extraction pipeline.
2. What business/domain information the user needs to provide.
3. A draft template for collecting that information.

The goal is to improve GOA template fill quality by giving the LLM better structured meaning, not just more raw text.

## Current Findings

### 1. The LLM sees field labels, but field meaning is still too weak

Checkbox guidance is currently derived mostly from:

- the field key
- the field description from the template
- auto-generated synonyms
- auto-generated positive indicators

These are generated in:

- `src/utils/template_utils.py`
- `generate_synonyms_for_checkbox()`
- `generate_positive_indicators()`

This works for literal or near-literal matches, but not for domain-equivalent phrases.

Example:

- Template field: `Stack Light with Buzzer Option`
- Quote wording: `Three (X 3) colour status beacon light with audible alarm`

The system does not explicitly know:

- `stack light` ~= `status beacon light` ~= `tower light`
- `buzzer` ~= `audible alarm`

So the LLM must infer that mapping on its own, which is unreliable.

### 2. Main machine bullet points are available, but only as general context

The main item bullet-point subitems are now parsed and included in the grouped extraction flow, but they are still used as:

- machine context in the prompt
- RAG query hints

They are not yet attached directly to relevant checkbox fields as field-local evidence.

This means the LLM still has to make a second inference:

- "This machine bullet likely supports that checkbox"

That is weaker than explicitly telling it:

- "These machine features are relevant to this checkbox"

### 3. The production path is compact by design

The active extraction passes in `api/services/processing_service.py` use:

- `compact_prompt=True`
- reduced checkbox synonyms
- reduced checkbox indicator counts

This helps speed and token control, but it also reduces semantic support for ambiguous fields.

### 4. The repair pass is weak against false `NO` values

The repair selection logic mainly retries:

- low-confidence text fields
- invalid checkboxes
- low-confidence `YES` checkboxes

It usually does not re-check a checkbox that was confidently set to `NO`, even when that `NO` is wrong.

This means false negatives can survive the pipeline.

### 5. Post-processing is mostly cleanup, not semantic interpretation

The current post-processing layer is good at:

- normalization
- mutual exclusivity rules
- a few domain-specific corrections

It is not yet designed as a general "semantic bridge" between vendor wording and GOA field intent.

## Core Problem

The system currently gives the LLM:

- raw machine wording
- raw field wording

But it does not consistently provide:

- domain vocabulary equivalence
- feature-to-field relevance
- a second-pass check for likely false `NO` checkboxes

That is why increasing prompt text alone will not reliably solve the issue.

## What The LLM Actually Needs

To fill GOA templates better, the LLM needs four things:

### 1. A domain vocabulary layer

A curated list of equivalent phrases and vendor terminology.

Examples:

- `stack light` = `tower light` = `status beacon light`
- `buzzer` = `audible alarm`
- `hopper sensor` = `low level sensor` (if true in your domain)

This should be explicit and machine-readable.

### 2. A feature-to-field mapping layer

The system should know that certain phrases or bundled features strongly support specific GOA fields.

Examples:

- If the machine description includes `status beacon light` and `audible alarm`, then `Stack Light with Buzzer Option` is likely `YES`.
- If the description includes a phrase that implies multiple subfeatures, the related checkbox set should be evaluated together.

### 3. A false-negative recovery step

The system needs a specific pass that asks:

- "Which checkboxes are currently `NO` but have supporting evidence in the machine descriptions or PDF?"

This is separate from the normal repair pass.

### 4. Real corrected examples

The most valuable training signal is not generic prompt tuning. It is a small set of real jobs showing:

- source wording
- the expected GOA output
- which fields were corrected manually

This gives the system a reliable way to discover recurring misses.

## Recommended Implementation Plan

## Phase 0: Add Observability

Before changing extraction behavior further, the system should expose the evidence path for missed fields.

### Implementation

Add structured logging for:

- parsed main-item subitems
- per-group prompt text
- RAG note and selected chunk count
- fields that remained `NO`
- fields changed by post-processing

### Why this matters

Without this, improvements are based on guesswork instead of visible failures.

## Phase 1: Add a Curated Field Semantic Overlay

This is the highest-value improvement.

### Goal

Create an override layer for checkbox fields that supplements the generic synonym generation with business-specific semantics.

### Proposed artifact

Add a new config file, for example:

- `config/goa_field_semantic_overrides.json`

### Each field entry should support

- `aliases`: alternate terms that mean the same feature
- `positive_evidence`: phrases that strongly imply `YES`
- `negative_evidence`: phrases that strongly imply `NO`
- `related_terms`: nearby terms that increase relevance during RAG
- `machine_families`: optional machine-family-specific variants
- `notes`: human explanation for maintenance

### Implementation steps

1. Load the semantic overlay during schema generation.
2. Merge it into the field metadata.
3. Feed those values into the grouped prompt builder.
4. Feed those values into RAG hint generation.
5. Prefer overlay data over generic auto-generated synonyms when present.

### Expected impact

This directly improves semantic matching without depending on the LLM to invent domain equivalences.

## Phase 2: Make Machine Descriptions Field-Aware

### Goal

Convert machine descriptions into normalized feature evidence and attach the most relevant evidence to each checkbox.

### Implementation concept

Instead of only placing machine descriptions in a global `MACHINE CONTEXT` block:

1. Parse `main_item`, `add_ons`, and `common_items` into individual feature strings.
2. Score each feature against each checkbox using:
   - field aliases
   - positive evidence phrases
   - related terms
3. For each checkbox, include the top 1-3 matching machine features directly in the field line or in a nearby evidence block.

### Example direction

Instead of only:

- `Main item includes:`

Use:

- `el_0369_check | C | ... | machine_evidence=status beacon light; audible alarm`

### Expected impact

This reduces the inference distance between:

- machine wording
- the checkbox the LLM must decide

## Phase 3: Add a False-NO Repair Pass

### Goal

Re-evaluate likely false negative checkboxes after pass 1.

### Implementation concept

Add a targeted post-pass that selects checkboxes meeting conditions such as:

- currently `NO`
- evidence found in machine descriptions, add-ons, or common items
- evidence found in retrieved PDF chunks
- high lexical overlap with aliases or positive evidence phrases

Then re-run only those fields with a tighter yes/no prompt.

### Why this matters

The current repair path is biased toward fixing uncertain `YES` values, not missed `NO` values.

## Phase 4: Add Deterministic Rules For Stable Business Logic

### Goal

For recurring, high-confidence mappings, use explicit rule-based corrections.

### Appropriate use cases

- domain phrases that always imply a checkbox
- machine-family-specific bundled features
- known vendor phrasing that is stable over time

### Implementation location

- `src/llm/post_processing.py`

### Important constraint

This should be a targeted supplement, not the primary extraction strategy.

## Phase 5: Build an Evaluation Set

### Goal

Track whether changes actually improve template fill quality.

### Suggested dataset

Collect 10-30 representative jobs with:

- machine family
- source quote PDF
- main item / add-on / common item descriptions
- final expected GOA values
- manually corrected fields

### Suggested success metrics

- checkbox false-negative rate
- checkbox precision
- number of manual corrections per job
- number of corrected false `NO` values after the new repair pass

## What The User Needs To Provide

The most useful information is business-specific meaning, not more raw PDFs.

## A. Phrase Equivalences (Highest Priority)

Provide a list of phrases that mean the same thing in your business context.

This is the most important missing input.

Examples:

- `status beacon light` => `stack light`
- `tower light` => `stack light`
- `audible alarm` => `buzzer`

For each equivalence, specify:

- source phrase
- normalized concept
- confidence
- machine family (if specific)
- notes

## B. Bundle-to-Field Rules

Provide known bundled feature relationships.

Examples:

- If wording X appears, fields A, B, and C should be `YES`.
- If a "base package" is selected, these subfeatures are included unless excluded.

This is critical for machine bullet points and included feature bundles.

## C. False Negative Examples

Provide examples where the system said `NO` but the correct value was `YES`.

For each case, include:

- exact phrase from quote or machine description
- field key
- field label
- expected value
- why it should have been selected

These examples will drive the first semantic overlay and the first deterministic rules.

## D. Negative / Non-Match Examples

Provide examples of similar wording that should not trigger a field.

This prevents over-triggering once alias matching becomes stronger.

## E. Machine-Family Glossaries

Provide a short list of terms used for each machine family, such as:

- SortStar
- fillers
- counters
- cappers

This allows machine-specific semantics instead of one global vocabulary.

## F. A Small Evaluation Set

Provide a small set of completed jobs where the expected output is known.

This is needed to verify that changes improve results instead of shifting errors around.

## Draft Data Collection Templates

Use the following sections as a starting point when gathering information.

## 1. Phrase Equivalence Template

Copy and fill this table:

| Source Phrase | Normalized Concept | Related GOA Field(s) | Machine Family | Confidence (High/Med/Low) | Notes |
| --- | --- | --- | --- | --- | --- |
| status beacon light | stack light | el_0369_check | SortStar | High | Often used instead of stack light |
| audible alarm | buzzer | el_0369_check | SortStar | High | Usually paired with beacon light |
|  |  |  |  |  |  |

## 2. Bundle Rule Template

Copy and fill this table:

| Trigger Phrase / Package | Implied Field(s) | Scope (main item/add-on/common item/PDF) | Machine Family | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| Three colour status beacon light with audible alarm | el_0369_check | main item | SortStar | High | Should map to stack light with buzzer |
|  |  |  |  |  |  |

## 3. False Negative Log Template

Copy and fill this table:

| Job / Quote Ref | Exact Source Phrase | Field Key | Field Label | Model Output | Expected | Source Location | Why It Should Be YES |
| --- | --- | --- | --- | --- | --- | --- | --- |
| IDEXX SortStar example | Three (X 3) colour status beacon light with audible alarm | el_0369_check | Stack Light with Buzzer Option | NO | YES | main item bullet | Beacon light + audible alarm implies stack light with buzzer |
|  |  |  |  |  |  |  |  |

## 4. Negative Example Template

Copy and fill this table:

| Exact Phrase | Nearby Similar Field | Should Trigger? | Why Not |
| --- | --- | --- | --- |
|  |  | NO |  |

## 5. Machine Family Glossary Template

Copy and fill this table:

| Machine Family | Term Used In Quotes | Normalized Internal Concept | Notes |
| --- | --- | --- | --- |
| SortStar | status beacon light | stack light | Common vendor phrasing |
| SortStar | audible alarm | buzzer | Often paired with beacon |
|  |  |  |  |

## 6. Evaluation Set Template

Create a list of candidate jobs:

| Job / Quote Ref | Machine Family | Known Problem Areas | Template Completed Manually? | Good Candidate For Testing? |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Draft Machine-Readable Overlay Format

The following draft shows the kind of structured data that would be useful to implement.

```json
{
  "el_0369_check": {
    "aliases": [
      "stack light",
      "tower light",
      "status beacon light",
      "beacon light"
    ],
    "positive_evidence": [
      "audible alarm",
      "with buzzer",
      "with audible alarm",
      "three colour status beacon light with audible alarm"
    ],
    "negative_evidence": [
      "without buzzer",
      "no audible alarm"
    ],
    "related_terms": [
      "signal light",
      "tri-color beacon",
      "status light"
    ],
    "machine_families": [
      "sortstar"
    ],
    "notes": "Use when quote wording differs from the GOA label but the intended feature is equivalent."
  }
}
```

This is only a draft example. The real file should be built from repeated business patterns, not guesswork.

## Suggested Working Order

To minimize risk and get measurable progress, the recommended order is:

1. Gather phrase equivalences and false-negative examples.
2. Build the semantic overlay file.
3. Merge the overlay into field metadata.
4. Use the overlay in prompt construction and RAG hints.
5. Add the false-`NO` repair pass.
6. Add a small number of deterministic rules for stable cases.
7. Validate against an evaluation set.

## What You Can Start Collecting Right Now

If time is limited, start with these three items only:

1. A list of 20-50 phrase equivalences.
2. A list of 10-20 false negative examples.
3. A list of 5-10 bundle rules for common machine families.

That is enough to build the first practical version of the semantic overlay.

## Next Implementation Target

The best first code change is:

1. Add a field semantic overlay file.
2. Merge it into schema generation.
3. Feed it into grouped extraction prompt construction.

This gives the LLM better semantic tools immediately, without requiring a full pipeline redesign.
