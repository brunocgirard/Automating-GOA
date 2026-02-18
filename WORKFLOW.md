# GOA LLM Application Workflow

## Documentation Change Format

For sections updated in this revision, changes are presented using this format:

> BEFORE  
> ~~old text~~  
> AFTER  
> new text

## High-Level Architecture

```
+-------------------+       HTTP/JSON       +-------------------+
|   Next.js React   | <------------------> |   FastAPI Backend  |
|   (frontend/)     |    localhost:3000     |   (api/)           |
|                   |    localhost:8000     |                   |
+-------------------+                       +-------------------+
                                                    |
                                            +-------+-------+
                                            |               |
                                      +-----v----+   +-----v------+
                                      |  SQLite  |   | Google     |
                                      |  (CRM)   |   | Gemini API |
                                      +----------+   +------------+
```

**Frontend**: Next.js (App Router) with shadcn/ui components, served on port 3000
**Backend**: FastAPI (Python), served on port 8000, CORS configured for frontend
**Database**: SQLite (`src/utils/db.py`) storing quotes, machines, templates, shipping data
> BEFORE  
> ~~**LLM**: Google Gemini (default: `gemini-2.5-flash`) via `google-genai` SDK, with optional OpenAI support~~  
> AFTER  
> **LLM**: Google Gemini via `google-genai` SDK (model pinned by `GOA_LLM_MODEL`, default `gemini-2.5-flash-lite`).

---

## Core Pipelines

### Pipeline 1: PDF Upload & Cataloging

**Purpose**: Upload a supplier quote PDF, extract line items and text, and store everything in the CRM database.

```
User uploads PDF
    |
    v
POST /api/quotes/upload  (api/routers/quotes.py)
    |
    v
extract_and_catalog()  (api/services/processing_service.py)
    |
    +---> Write PDF to temp file
    +---> extract_line_item_details(pdf_path)     -- tabular line items via pdf_utils
    +---> extract_full_pdf_text(pdf_path)          -- full text extraction
    +---> identify_machines_from_items(items)      -- heuristic machine grouping
    |
    v
Save to SQLite:
    - save_client_info()       -> clients table
    - save_priced_items()      -> priced_items table
    - save_document_content()  -> document_content table (full PDF text)
    - save_machines_data()     -> machines table (grouped machine JSON)
    |
    v
Return { quote_ref, items_count }
```

**Key files**:
- `api/routers/quotes.py` - Upload endpoint
- `api/services/processing_service.py:extract_and_catalog()` - Orchestration
- `src/utils/pdf_utils.py` - PDF text & table extraction
- `src/utils/db.py` - All database operations

---

### Pipeline 2: LLM Field Extraction (GOA Generation)

**Purpose**: Use Gemini to extract structured field data from the PDF to fill a General Order Acknowledgement (GOA) form template.

> BEFORE  
> ~~+---> get_machine_specific_fields_with_confidence()  (src/llm/extraction.py)~~  
> ~~+---> Rebalance oversized groups (max 180 fields per group)~~  
> ~~Return { filled_data, confidence_scores, suggestions }~~  
> AFTER
```
Frontend selects machine to process
    |
    v
GET /api/processing/machine-data/{machine_id}
    |  Returns: machine_data, main_item, options, common_items, full_pdf_text
    v
POST /api/processing/extract
    |
    v
run_extraction()  (api/services/processing_service.py)
    |
    +---> configure_gemini_client()  (src/llm/client.py)
    +---> get_contexts_for_machine()  -- load template schema from Excel or DOCX
    +---> Feature-flag routing:
            |
            +---> if EXTRACTION_FULL_PREFILL_V2_ENABLED=true:
            |       run_extraction_v2_full_prefill(...)
            |         |
            |         +---> Pass 1 fast prefill:
            |         |       - model: GOA_LLM_MODEL_DRAFT
            |         |       - lean RAG + grouped extraction
            |         |
            |         +---> Pass 1 confidence + dependency validation
            |         |
            |         +---> Pass 2 auto-repair subset:
            |         |       - model: GOA_LLM_MODEL_DEEP
            |         |       - forced critical text tags allowed
            |         |
            |         +---> Merge pass outputs (pass2 over pass1)
            |         +---> resolve_critical_text_fields(...) for constrained text fields
            |         +---> apply_post_processing_rules()
            |         +---> sanitize_extracted_fields()
            |         +---> estimate_extraction_confidence()
            |         +---> validate_field_dependencies()
            |
            +---> else:
                    _run_extraction_legacy(...)
    |
    v
Return { filled_data, confidence_scores, suggestions, metadata }
```

**Extraction strategies (current)**:
1. **V2 Full-Prefill Two-Pass** (primary): Fast full-template pass + automatic repair pass before user review.
2. **Legacy Single-Pass Path** (fallback): Used only when V2 feature flag is disabled.
3. **Chat Update**: Interactive corrections via `get_llm_chat_update`.
4. **CRM Mapping**: Map existing CRM data to new document templates via `map_crm_to_document_via_llm`.

**Field types**:
- **Checkbox fields** (key ends with `_check`): Value is `"YES"` or `"NO"`
- **Text fields**: Extracted string or empty `""`

### Comment Field Governance (User-Entry Only)

> BEFORE  
> ~~No explicit comment-field governance section in this workflow.~~  
> AFTER
Comment fields are intentionally left for manual user input to simplify extraction behavior.

- Scope: all string fields whose schema description contains `Comment` or `Comments`.
- LLM extraction must return empty string for those fields.
- Post-processing must clear any accidental non-empty comment output.
- Dedicated deterministic logic can still populate specific fields when explicitly implemented.
- Existing non-comment logic (for example start-up/commissioning option handling) remains unchanged.

**Key files**:
> BEFORE  
> ~~`src/llm/client.py` - Gemini/OpenAI client configuration (`_CompatGenerativeModel` adapter)~~  
> AFTER  
> `src/llm/client.py` - Gemini client configuration and per-model cache
- `src/llm/extraction.py` - All extraction functions
- `src/llm/constants.py` - Field groups, confidence levels, field metadata
- `src/llm/confidence.py` - Confidence estimation
- `src/llm/validation.py` - Field dependency & response validation
- `src/llm/post_processing.py` - Post-extraction normalization
- `src/llm/critical_text_resolver.py` - Deterministic resolver for constrained text fields
- `src/llm/qa.py` - PDF question answering
- `src/utils/pdf_rag.py` - RAG context building (chunk PDF by relevance)
- `src/utils/few_shot_learning.py` - Basic few-shot examples
- `src/utils/few_shot_enhanced.py` - Semantic few-shot via ChromaDB

---

### Pipeline 3: GOA Document Generation

**Purpose**: Take extracted/edited field data and produce the final GOA document (HTML or DOCX).

```
POST /api/processing/generate
    |
    v
generate_document()  (api/services/processing_service.py)
    |
    +---> Determine template type:
    |       Standard machine -> HTML (from Excel template)
    |       SortStar machine -> DOCX (from Word template)
    |
    +---> build_options_listing()  -- construct options text from machine items
    |
    +---> Standard path:
    |       generate_goa_form()           -- Excel -> HTML template
    |       fill_and_generate_html()      -- fill placeholders in HTML
    |       Output: output_{name}_GOA.html
    |
    +---> SortStar path:
    |       fill_word_document_from_llm_data()  -- fill DOCX template
    |       Output: output_SORTSTAR_{name}_GOA.docx
    |
    v
save_generated_template()  -- persist to machine_templates table
Return { file_path, machine_id, machine_template_id }
```

**Template sources**:
- `templates/GOA_template.xlsx` - Standard GOA form schema (source of truth for field definitions)
- `templates/template.docx` - Standard Word template
- `templates/GOA_Sortstar_Temp.docx` - SortStar-specific Word template
- `templates/goa_form.html` - Generated HTML form template

**Key files**:
- `src/utils/form_generator.py` - Excel-to-HTML template generation
- `src/utils/html_doc_filler.py` - HTML placeholder filling
- `src/utils/doc_filler.py` - DOCX placeholder filling
- `src/utils/template_utils.py` - Template schema extraction, explicit mappings

---

### Pipeline 4: GOA Form Editor (Builder)

**Purpose**: View, edit, and regenerate GOA forms through a rich UI.

```
Frontend loads saved GOA form
    |
    v
GET /api/processing/goa-form/{machine_template_id}
    |  Returns: template_data, field_labels, modifications, rendered HTML
    v
User edits fields in the GOA Field Editor
    |
    v
PUT /api/processing/goa-form/{machine_template_id}
    |
    +---> Save updated template_data to DB
    +---> Track modifications (field-level change history)
    +---> Optionally regenerate output document
    +---> Return updated HTML preview
    v
POST /api/processing/goa-form/{id}/generate-document
    |  Regenerate the final output file (HTML or DOCX)
    v
GET /api/processing/goa-form/{id}/file
    |  Download the generated file
```

**Frontend components**:
- `goa-form-page-client.tsx` - GOA form viewer with HTML preview
- `goa-field-editor.tsx` - Field-level editor with confidence indicators
- `goa-form-viewer.tsx` - HTML preview via iframe
- `goa-document-builder-page-client.tsx` - Full builder with schema-driven editing
- `extraction-viewer.tsx` - View extraction results with confidence scores
- `document-builder.tsx` - Document generation controls

**GOA Form Schema** (`GET /api/processing/goa-schema`):
- Dynamically built from Excel template rows
- Organized into sections > groups > fields
- Each field has: key, label, type (text/textarea/checkbox/number)

---

### Pipeline 5: Shipping Documents

**Purpose**: Generate shipping documents (Packing Slip, Commercial Invoice, Certificate of Origin) from quote/CRM data.

```
Frontend navigates to Shipping Documents page
    |
    v
GET /api/shipping/{quote_id}/prefill
    |  Returns: pre-populated shipping state from CRM data
    |  (client info, machines, crates, trucks, meta)
    v
User edits shipping details in the UI:
    - Client info (addresses, contact, PO)
    - Machine details (serial #, HS code, unit price)
    - Crate dimensions & weights per machine
    - Truck assignments
    - Meta info (broker, origin criterion, certifier)
    |
    v
POST /api/shipping/{quote_id}/save
    |  Persist shipping state to DB
    v
POST /api/shipping/{quote_id}/generate
    |
    +---> generate_shipping_documents()  (api/services/shipping_doc_service.py)
    |       +---> Render Packing Slip (DOCX)
    |       +---> Render Commercial Invoice (DOCX)
    |       +---> Render Certificate of Origin (DOCX)
    |       +---> If "all": ZIP all documents together
    v
Return: FileResponse (DOCX or ZIP)
```

**Shipping document types** (`ShippingDocumentType`):
- `packing_slip` - Crate dimensions, weights, truck assignments
- `commercial_invoice` - Itemized pricing, HS codes, incoterms
- `certificate_origin` - USMCA/CUSMA compliance, origin criteria
- `all` - ZIP bundle of all three

**Frontend components**:
- `shipping-documents-page-client.tsx` - Main shipping page with tabbed editing
- `packing-slip-preview.tsx` - Packing slip preview/edit
- `commercial-invoice-preview.tsx` - Invoice preview/edit
- `certificate-origin-preview.tsx` - Certificate preview/edit

**Data model** (`ShippingDocumentState`):
```typescript
{
  quoteId, quoteRef,
  client: { company, addresses, PO, incoterm, ... },
  machines: [{ machineName, model, hsCode, serialNumber, unitPrice, truckId, crates: [...] }],
  trucks: [{ id, name }],
  meta: { brokerInfo, originCriterion, certifierName, countryOfOrigin, ... }
}
```

---

## Frontend Architecture

### Tech Stack
- **Framework**: Next.js 14+ (App Router)
- **UI Library**: shadcn/ui (Radix primitives + Tailwind CSS)
- **State Management**: React `useState`/`useEffect` (no global store)
- **API Layer**: `frontend/src/lib/api.ts` - centralized fetch wrapper

### Page Structure (App Router)

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Dashboard | Quote list with client filter sidebar |
| `/quotes/[id]` | Quote Edit | Edit quote details & view machines |
| `/quotes/[id]/preview` | Quote Preview | Read-only quote view |
| `/quotes/[id]/client-info` | Client Info | Edit client/shipping details |
| `/client-info` | Client Info | Standalone client info editor |
| `/processing` | Processing | Multi-step machine processing wizard |
| `/goa/[machineTemplateId]` | GOA Form | View/preview saved GOA form |
| `/goa/[machineTemplateId]/builder` | GOA Builder | Full field editor + document generation |
| `/shipping-documents` | Shipping Docs | Shipping document editor & generator |
| `/reports` | Reports | Machine reports viewer |

### Key UI Patterns
- **Step Indicator**: Processing page uses a multi-step wizard (load quote -> select machine -> process)
- **HTML Preview Frame**: GOA forms rendered as HTML in a sandboxed iframe (`html-preview-frame.tsx`)
- **Client Filter Context**: Sidebar filter persists selected client across dashboard (`client-filter-context.tsx`)
- **Upload Dialog**: PDF upload with optional existing client linking

---

## Backend API Routes

### Quotes (`/api/quotes`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/quotes` | List all quotes |
| GET | `/api/quotes/{id}` | Get quote by ID |
| PUT | `/api/quotes/{id}` | Update quote fields |
| DELETE | `/api/quotes/{id}` | Delete quote |
| POST | `/api/quotes/upload` | Upload PDF quote |

### Machines (`/api/machines`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/machines/all` | List all machines |
| GET | `/api/quotes/{id}/machines` | List machines for quote |
| GET | `/api/machines/{id}/template` | Get machine template data |
| PUT | `/api/machines/{id}/template` | Save/update template data |

### Processing (`/api/processing`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/processing/identify` | Auto-identify machines from line items |
| POST | `/api/processing/group` | Group items by confirmed machines |
| GET | `/api/processing/items/{ref}` | Get priced items for quote |
| GET | `/api/processing/artifacts/{ref}` | Get full processing artifacts |
| GET | `/api/processing/machine-data/{id}` | Get machine processing data |
| POST | `/api/processing/extract` | Run LLM extraction |
| POST | `/api/processing/generate` | Generate GOA document |
| POST | `/api/processing/fill-form` | Render GOA HTML preview |
| GET | `/api/processing/goa-schema` | Get GOA form field schema |
| GET | `/api/processing/goa-forms` | List all saved GOA forms |
| GET | `/api/processing/goa-form/{id}` | Get saved GOA form detail |
| PUT | `/api/processing/goa-form/{id}` | Save GOA form edits |
| POST | `/api/processing/goa-form/{id}/generate-document` | Regenerate GOA output |
| GET | `/api/processing/goa-form/{id}/file` | Download GOA file |
| POST | `/api/generate-document` | Generate with full options |

### Shipping (`/api/shipping`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/shipping/{id}/prefill` | Get pre-populated shipping data |
| POST | `/api/shipping/{id}/save` | Save shipping state |
| GET | `/api/shipping/{id}/load` | Load saved shipping state |
| POST | `/api/shipping/{id}/generate` | Generate shipping documents |

### Reports (`/api/reports`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/reports/{machine_id}` | Get machine report |
| GET | `/api/reports/{machine_id}/summary` | Get summary report |

---

## Database Schema (SQLite)

Managed by `src/utils/db.py` with `init_db()` called on app startup.

**Core tables**:
- `clients` - Quote/client records (quote_ref, customer_name, addresses, etc.)
- `priced_items` - Extracted line items from PDFs
- `document_content` - Full PDF text storage
- `machines` - Machine groupings with JSON payload (main_item, add_ons, common_items)
- `machine_templates` - Generated GOA template data (template_data_json, output_preferences_json, generated_file_path)
- `goa_modifications` - Field-level change tracking for GOA forms
- `shipping_documents` - Persisted shipping document state

---

## LLM Configuration

### Environment Variables

> BEFORE  
> ~~| `GOA_LLM_MODEL` | LLM model name | `gemini-2.5-flash` |~~  
> ~~| `GOA_LLM_PROVIDER` | Provider (`gemini` or `openai`) | Auto-detected |~~  
> ~~| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | - |~~  
> ~~| `LLM_MAX_FIELDS_PER_GROUP` | Max fields per extraction group | 180 |~~  
> ~~| `LLM_RAG_MAX_CHARS_PER_GROUP` | Max PDF chars per RAG group | 40000 |~~  
> AFTER
| Variable | Purpose | Default |
|----------|---------|---------|
| `GOOGLE_API_KEY` | Gemini API key | Required |
| `GEMINI_API_KEY` | Alias for GOOGLE_API_KEY | - |
| `GOA_LLM_MODEL` | Pinned base LLM model | `gemini-2.5-flash-lite` |
| `GOA_LLM_MODEL_DRAFT` | Pass 1 fast-prefill model | `gemini-2.5-flash-lite` |
| `GOA_LLM_MODEL_DEEP` | Pass 2 repair model | `gemini-2.5-flash` |
| `EXTRACTION_FULL_PREFILL_V2_ENABLED` | Enable V2 two-pass extraction | `false` |
| `LLM_PASS1_RAG_MAX_CHARS` | Pass 1 RAG budget (chars) | `12000` |
| `LLM_PASS2_RAG_MAX_CHARS` | Pass 2 RAG budget (chars) | `22000` |
| `LLM_PASS1_GROUP_MAX_FIELDS` | Pass 1 max fields per group | `60` |
| `LLM_PASS2_GROUP_MAX_FIELDS` | Pass 2 max fields per group | `35` |
| `LLM_EXTRACTION_MAX_CONCURRENCY` | Group extraction concurrency | `3` |
| `LLM_RAG_WEIGHTED_HINTS_ENABLED` | Enable weighted primary/secondary RAG hints | `true` |
| `LLM_CRITICAL_TEXT_RESOLVER_ENABLED` | Enable constrained text resolver | `true` |
| `LLM_FORCE_PASS2_CRITICAL_TEXT` | Force pass 2 for critical text fields | `true` |
| `LLM_CRITICAL_TEXT_TAGS` | Critical semantic tags for pass 2/resolver | `direction,voltage,hz,phases` |
| `FEW_SHOT_EMBEDDING_MODEL` | Optional semantic embedding model override | `models/text-embedding-004` fallback |
| `DISABLE_ALL_FEW_SHOT` | Disable few-shot learning | false |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://127.0.0.1:3000` |

### LLM Client Architecture
> BEFORE  
> ~~The `src/llm/client.py` module provides a compatibility layer:~~  
> ~~`_CompatGenerativeModel` wraps the new `google.genai.Client` SDK with the old `GenerativeModel.generate_content()` interface~~  
> ~~`_OpenAIMarker` serves as a placeholder for OpenAI; actual OpenAI calls use LangChain's `ChatOpenAI` in extraction.py~~  
> AFTER
The `src/llm/client.py` module is Gemini-focused for this workflow:
- `configure_gemini_client()` initializes the base Gemini model from environment settings.
- `get_generative_model(model_name_override)` supports pass-level model selection and model-instance caching.
- The extraction pipeline uses this client for both Pass 1 (`GOA_LLM_MODEL_DRAFT`) and Pass 2 (`GOA_LLM_MODEL_DEEP`).

---

## Few-Shot Learning System

The application maintains a learning loop:
1. After each successful extraction, high-confidence results are saved as few-shot examples
2. Future extractions are enhanced with relevant examples from the database
3. Two modes:
   - **Basic**: Exact machine type matching (`src/utils/few_shot_learning.py`)
   - **Enhanced**: Semantic similarity via ChromaDB embeddings (`src/utils/few_shot_enhanced.py`)
4. Can be disabled via `DISABLE_ALL_FEW_SHOT=true`

---

## Processing Workflow (End-to-End User Journey)

1. **Upload Quote PDF** -> Dashboard upload dialog -> `POST /api/quotes/upload`
2. **View Quote** -> Dashboard table -> click quote row -> Quote detail page
3. **Edit Client Info** -> Client info page -> `PUT /api/quotes/{id}`
4. **Process Machine** -> Processing page wizard:
   - Step 1: Load quote artifacts
   - Step 2: Select/confirm machine groupings
   > BEFORE  
   > ~~- Step 3: Run LLM extraction -> Review results -> Generate GOA document~~  
   > AFTER  
   > - Step 3: Run auto two-pass extraction -> Review low-confidence fields -> Fill user-owned comment fields -> Generate GOA document
5. **Edit GOA Form** -> GOA Builder page -> Edit fields -> Save -> Regenerate document
6. **Generate Shipping Docs** -> Shipping page -> Edit details -> Download Packing Slip / Invoice / Certificate
7. **View Reports** -> Reports page -> Select machine -> View HTML report
