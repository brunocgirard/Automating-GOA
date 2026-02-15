# Product Requirements Document: Workflow Template Designer

## Vision

A **consulting + SaaS hybrid** that helps businesses automate their document workflows:

1. **Discovery**: Client uploads sample documents, we analyze their workflow
2. **Design**: LLM proposes templates based on document structure
3. **Deploy**: Clean, user-friendly UI for daily document processing

**Value Proposition**: "Tell us about your document pain points. We'll analyze your workflow and build templates that turn hours of manual work into minutes of review."

---

## Target Market

- B2B companies with repetitive document workflows
- Industries: Manufacturing, Legal, Insurance, Real Estate, Healthcare
- Pain point: Manual data entry from source documents into standardized templates
- Company size: SMB (10-200 employees) with 1-5 people doing document work

---

## Core Product: Workflow Template Designer

### What It Does

1. **Workflow Discovery**
   - Client describes their current process (intake form or conversation)
   - Client uploads 3-5 sample documents (source → output examples)
   - LLM analyzes documents to understand structure and data flow

2. **Template Proposal**
   - System identifies: input fields, output structure, transformation rules
   - Generates proposed HTML template with mapped fields
   - Shows client: "We found X fields in your source docs that map to Y outputs"

3. **Template Customization**
   - Drag-and-drop field editor
   - Section reordering
   - Add/remove fields
   - Live preview of changes

4. **Document Processing Portal**
   - Upload source documents
   - Review pre-filled templates (edit before finalizing)
   - Download/export completed documents
   - Batch processing for multiple documents

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LOVABLE FRONTEND                         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Onboarding │  │  Template   │  │  Document   │         │
│  │    Wizard   │  │   Editor    │  │  Processor  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  Focus: Clean UX, non-technical users, mobile-friendly     │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                          │
│                                                             │
│  /api/workflows     - Workflow discovery & analysis         │
│  /api/templates     - Template generation & customization   │
│  /api/documents     - Document upload & processing          │
│  /api/clients       - Client management & billing           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM INTELLIGENCE                         │
│                                                             │
│  Document Analysis:                                         │
│  - Extract structure from sample documents                  │
│  - Identify field types (text, number, date, checkbox)      │
│  - Detect patterns across multiple samples                  │
│                                                             │
│  Template Generation:                                       │
│  - Propose field mappings (source → output)                 │
│  - Generate HTML template structure                         │
│  - Suggest validation rules                                 │
│                                                             │
│  Document Processing:                                       │
│  - Extract data from new documents                          │
│  - Fill templates with extracted data                       │
│  - Flag low-confidence extractions for review               │
└─────────────────────────────────────────────────────────────┘
```

---

## User Journeys

### Journey 1: New Client Onboarding

```
1. Landing Page
   └─> "Start Free Trial" button

2. Workflow Intake Form
   - What documents do you process? (dropdown + free text)
   - How many per week? (range selector)
   - What's painful about your current process? (text area)
   - Upload 3-5 sample documents (drag & drop)

3. Analysis Screen (loading state)
   - "Analyzing your documents..."
   - Progress indicators
   - Fun facts about time savings

4. Proposal Screen
   - "We found 12 fields in your invoices"
   - Visual field map: Source Doc → Template
   - "Estimated time savings: 2 hours/week"
   - "Customize Template" or "Looks Good" buttons

5. Template Editor
   - Live preview on right
   - Field list on left (drag to reorder)
   - Click field to edit: name, type, validation
   - Add custom fields button

6. Test It Out
   - Upload a new document
   - See it processed in real-time
   - Edit any incorrect fields
   - Download result

7. Pricing & Signup
   - Show plan options
   - Collect payment
   - Create account
```

### Journey 2: Daily Document Processing

```
1. Login → Dashboard
   - Recent documents
   - Quick stats (processed this week, time saved)
   - "Upload New" button

2. Upload Documents
   - Drag & drop zone
   - Select template (if multiple)
   - "Process" button

3. Review & Edit
   - Pre-filled template preview
   - Confidence indicators on fields
   - Click to edit any field
   - "Approve" button

4. Download/Export
   - PDF, HTML, or DOCX
   - Email to recipient option
   - Save to cloud storage option
```

---

## Implementation Phases

### Phase 1: Core Backend (Week 1-2)

**Goal**: API that can analyze documents and generate templates

#### 1.1 Project Setup
- [ ] Create `src/api/` directory structure
- [ ] Set up FastAPI with CORS
- [ ] Add API key authentication
- [ ] Create Pydantic models for requests/responses

#### 1.2 Workflow Analysis Endpoint
- [ ] `POST /api/workflows/analyze`
  - Input: Multiple PDF files + workflow description
  - Process: LLM analyzes structure across all samples
  - Output: Proposed field schema with types and mappings

#### 1.3 Template Generation Endpoint
- [ ] `POST /api/templates/generate`
  - Input: Field schema + customization options
  - Process: Generate HTML template
  - Output: Template ID + HTML preview

#### 1.4 Document Processing Endpoint
- [ ] `POST /api/documents/process`
  - Input: PDF file + template ID
  - Process: Extract data, fill template
  - Output: Filled template + confidence scores

### Phase 2: Lovable Frontend (Week 3-4)

**Goal**: Beautiful, intuitive UI for non-technical users

#### 2.1 Onboarding Flow
- [ ] Landing page with clear value prop
- [ ] Workflow intake form
- [ ] Document upload with drag & drop
- [ ] Analysis loading state
- [ ] Proposal display with field mapping visual

#### 2.2 Template Editor
- [ ] Field list with drag-to-reorder
- [ ] Field property editor (name, type, validation)
- [ ] Live preview panel
- [ ] Save/discard buttons

#### 2.3 Document Processor
- [ ] Upload zone
- [ ] Processing status
- [ ] Review/edit interface with confidence indicators
- [ ] Download options

#### 2.4 Dashboard
- [ ] Recent documents list
- [ ] Quick stats
- [ ] Template management

### Phase 3: Polish & Launch (Week 5-6)

#### 3.1 UX Improvements
- [ ] Loading states and animations
- [ ] Error handling with helpful messages
- [ ] Mobile responsiveness
- [ ] Keyboard shortcuts

#### 3.2 Integration
- [ ] Connect Lovable to FastAPI
- [ ] End-to-end testing
- [ ] Performance optimization

#### 3.3 Billing
- [ ] Stripe integration
- [ ] Usage tracking
- [ ] Plan limits enforcement

---

## LLM Prompting Strategy

### Document Analysis Prompt

```
You are analyzing business documents to understand their structure.

Given these sample documents from a client's workflow:
{documents}

The client describes their process as:
{workflow_description}

Identify:
1. All fields/data points present in the documents
2. Field types (text, number, date, currency, checkbox, etc.)
3. Which fields appear consistently across samples
4. Relationships between fields (e.g., subtotal + tax = total)
5. Any validation rules that should apply

Output as structured JSON:
{
  "fields": [...],
  "relationships": [...],
  "suggested_template_sections": [...]
}
```

### Template Generation Prompt

```
Generate an HTML template for document processing.

Field schema:
{field_schema}

Requirements:
- Clean, professional design
- Logical section groupings
- Clear field labels
- Print-friendly layout

Output valid HTML with inline CSS.
```

---

## Reference Implementation

The existing GOA codebase provides patterns for:

| Capability | Reference File | What to Learn |
|------------|----------------|---------------|
| PDF text extraction | `src/utils/pdf_utils.py` | How to extract text/tables from PDFs |
| LLM field extraction | `src/llm/extraction.py` | Structured prompting for data extraction |
| HTML template filling | `src/utils/html_doc_filler.py` | DOM manipulation for template filling |
| Confidence scoring | `src/llm/confidence.py` | Rating extraction reliability |
| Few-shot learning | `src/utils/few_shot_learning.py` | Improving accuracy over time |

**Note**: These files are domain-specific (packaging machinery). Use them as **inspiration for patterns**, not direct code reuse. Each client's templates will be generated fresh based on their workflow.

---

## Success Metrics

### MVP Launch
- [ ] Can onboard a new client in < 10 minutes
- [ ] Template generation accuracy > 80% on first try
- [ ] Document processing time < 30 seconds
- [ ] User can customize template without technical help
- [ ] NPS > 40 from beta testers

### Growth
- [ ] 10 paying clients in first 3 months
- [ ] < 5% churn rate
- [ ] Average client processes 50+ documents/month
- [ ] 3+ referrals per satisfied client

---

## Pricing Model (Draft)

| Plan | Price | Documents/mo | Templates | Features |
|------|-------|--------------|-----------|----------|
| Starter | $29/mo | 100 | 2 | Basic support |
| Pro | $79/mo | 500 | 10 | Priority support, batch processing |
| Business | $199/mo | 2000 | Unlimited | API access, custom integrations |
| Enterprise | Custom | Unlimited | Unlimited | Dedicated support, SLA |

---

## Open Questions

1. **Hosting**: Railway vs Render vs Google Cloud Run for backend?
2. **LLM Provider**: Stick with Gemini or offer OpenAI option?
3. **Document Storage**: Where to store uploaded documents securely?
4. **White-label**: Should clients be able to brand their portal?
5. **Integrations**: Which to prioritize? (Google Drive, Dropbox, Salesforce, etc.)

---

## Next Steps

1. **Validate demand**: Talk to 5 potential clients about their document pain points
2. **Build API MVP**: Document analysis + template generation endpoints
3. **Create Lovable prototype**: Onboarding flow + template editor
4. **Beta test**: 3-5 clients using the system for real work
5. **Iterate**: Fix issues, improve UX based on feedback
6. **Launch**: Public release with pricing
