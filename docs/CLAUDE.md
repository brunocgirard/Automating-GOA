# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

QuoteFlow Document Assistant automates generation of General Offer Arrangement (GOA) documents from PDF quotes using AI. It extracts data via Google Gemini, populates templates, and maintains a customer database. The app uses a **FastAPI** backend with a **Next.js (React)** frontend.

## Running the Application

```bash
# Backend (FastAPI)
pip install -r requirements.txt
cp .env.example .env  # Add GEMINI_API_KEY
uvicorn api.main:app --reload --port 8000

# Frontend (Next.js)
cd frontend
npm install
cp .env.example .env.local  # Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev  # Runs on port 3000

# Run tests
.venv\Scripts\python.exe -m pytest tests/ -v
```

## Project Structure

```
GOA_LLM/
├── api/                          # FastAPI backend
│   ├── main.py                   # App entry point, CORS, router registration
│   ├── models/schemas.py         # Pydantic request/response models
│   ├── routers/
│   │   ├── quotes.py             # CRUD /quotes, POST /quotes/upload
│   │   ├── machines.py           # /machines, /machines/{id}/template
│   │   ├── processing.py         # /processing/extract, /generate, /goa-form/*
│   │   ├── reports.py            # /reports/{machine_id}
│   │   └── shipping.py           # /shipping/{quote_id}/prefill, /save, /generate
│   └── services/
│       ├── processing_service.py # Orchestrates extraction + document generation
│       ├── profile_service.py    # Client profile management
│       ├── report_service.py     # Report generation
│       └── shipping_doc_service.py
│
├── src/                          # Shared business logic
│   ├── llm/                      # LLM modules (PRODUCTION - canonical)
│   │   ├── client.py             # Gemini client config (model via GOA_LLM_MODEL env)
│   │   ├── extraction.py         # Field extraction via LangChain
│   │   ├── confidence.py         # Confidence scoring with fuzzy/unit matching
│   │   ├── post_processing.py    # Domain-specific field corrections
│   │   ├── validation.py         # Field validation + checkbox coercion
│   │   ├── qa.py                 # PDF Q&A
│   │   └── constants.py          # Field grouping constants
│   ├── utils/
│   │   ├── llm_handler.py        # Compatibility shim → forwards to src.llm
│   │   ├── pdf_utils.py          # PDF text/table extraction (pdfplumber)
│   │   ├── pdf_rag.py            # RAG chunking for PDF context (50-60K budgets)
│   │   ├── quote_library.py      # QUOTE_LIBRARY.txt parser with fuzzy matching
│   │   ├── machine_type.py       # Machine type detection (lookup table)
│   │   ├── form_generator.py     # Excel -> HTML form generation
│   │   ├── html_doc_filler.py    # HTML template population
│   │   ├── doc_filler.py         # Word (DOCX) template population
│   │   ├── template_utils.py     # Template analysis utilities
│   │   ├── few_shot_enhanced.py  # Semantic similarity (ChromaDB)
│   │   ├── few_shot_learning.py  # Basic few-shot learning
│   │   └── db/                   # Database operations (SQLite)
│   │       ├── base.py           # DB init & connection
│   │       ├── clients.py        # Client CRUD
│   │       ├── items.py          # Priced items
│   │       ├── machines.py       # Machine data
│   │       ├── templates.py      # Template storage
│   │       ├── modifications.py  # GOA edit tracking
│   │       ├── documents.py      # PDF text storage
│   │       ├── few_shot.py       # Few-shot examples (3-layer validation)
│   │       └── shipping.py       # Shipping documents
│   ├── generators/
│   │   └── document_generators.py
│   └── workflows/
│       └── profile_workflow.py
│
├── frontend/                     # Next.js React SPA
│   └── src/
│       ├── app/                  # Pages (App Router)
│       │   ├── page.tsx          # Dashboard (quote list)
│       │   ├── processing/       # Machine selection + extraction
│       │   ├── quotes/[id]/      # Quote details, preview, client-info
│       │   ├── goa/[machineTemplateId]/  # GOA form viewer + builder
│       │   ├── reports/          # Machine build reports
│       │   ├── shipping-documents/
│       │   └── client-info/
│       ├── components/           # React components
│       └── lib/
│           ├── api.ts            # API client (fetch wrapper)
│           └── types.ts          # TypeScript interfaces
│
├── templates/                    # Template files
│   ├── GOA_template.xlsx         # Source of truth (602 fields)
│   ├── GOA_Sortstar_Temp.docx   # SortStar Word template
│   └── *.pdf                    # Sample quotes
│
├── QUOTE_LIBRARY.txt            # Machine specs catalog (integrated via quote_library.py)
├── data/crm_data.db             # SQLite database
├── .env                         # GEMINI_API_KEY, DATABASE_PATH, CORS_ORIGINS, GOA_LLM_MODEL
└── .env.example
```

## Architecture: Core Pipelines

### Pipeline 1: PDF Upload -> Database
```
POST /quotes/upload (PDF file)
  -> pdf_utils.py::extract_line_item_details()
  -> pdf_utils.py::identify_machines_from_items()
  -> db: clients, priced_items, machines, document_content
```

### Pipeline 2: GOA Generation (Dual-Template System)
```
POST /processing/extract (machine_id)
  -> processing_service.py::run_extraction()
  -> Detect template type via machine_type.py (lookup table)
  ├── Standard -> HTML template (602 fields from Excel)
  │     -> src/llm/extraction.py (LangChain + Gemini)
  │     -> html_doc_filler.py::fill_and_generate_html()
  └── SortStar -> Word template
        -> doc_filler.py::fill_word_document_from_llm_data()
```

**Machine type detection**: Centralized in `src/utils/machine_type.py` using `_MACHINE_FAMILIES` lookup table with `re.IGNORECASE`. Covers RoboSort, ThunderStar, SortStar, LabelStar, and filling machines.

### Pipeline 3: Few-Shot Learning
```
Successful extraction
  -> few_shot_learning.py (with pre-filter validation)
  -> db/few_shot.py (3-layer validation: call-site, insert, retrieval)
  -> ChromaDB vector store (768-dim embeddings)
  -> Future extractions use semantic similarity
```

### Pipeline 4: QUOTE_LIBRARY Context
```
Machine detected (e.g., "RoboSort 4")
  -> quote_library.py::get_quote_library_context()
  -> Fuzzy match against QUOTE_LIBRARY.txt sections
  -> Inject matched specs into LLM prompt
```

## LLM Integration

**Provider**: Google Gemini (model configurable via `GOA_LLM_MODEL` env var, default `gemini-2.5-flash-lite`)
**Frameworks**: LangChain (`ChatGoogleGenerativeAI` + `PydanticOutputParser`)
**PDF context**: RAG chunking via `pdf_rag.py` (50-60K char budgets, not truncated)

**Pattern**:
1. Build Pydantic model from template schema dynamically
2. Retrieve relevant QUOTE_LIBRARY sections (fuzzy match)
3. Build RAG context from PDF (chunked, scored, top-K selected)
4. Use LangChain FewShotPromptTemplate with semantic example selection
5. Parse JSON output into validated Pydantic objects
6. Post-process with domain rules (`src/llm/post_processing.py`)
7. Validate + coerce fields (`src/llm/validation.py`)
8. Score confidence (`src/llm/confidence.py` - fuzzy + unit normalization)

## Template System

**Standard GOA (HTML)**:
1. Source: `templates/GOA_template.xlsx` (Form sheet, 602 fields)
2. Generator: `form_generator.py::generate_goa_form()` -> `templates/goa_form.html`
3. Filler: `html_doc_filler.py::fill_and_generate_html()`
4. Special: `options_listing` field auto-formats bullet lists

**SortStar GOA (Word)**:
- Template: `templates/GOA_Sortstar_Temp.docx`
- Filler: `doc_filler.py::fill_word_document_from_llm_data()`
- Checkboxes: YES -> checkmark, NO -> empty box (Unicode)

**To add a field**: Add row to Excel -> Regenerate HTML -> Field automatically available

## Database Schema (SQLite: data/crm_data.db)

**Core Tables**:
- `clients`: Customer info, keyed by quote_ref
- `priced_items`: Line items from PDF
- `machines`: Machine groupings with add-ons (JSON blob)
- `machine_templates`: Saved field extractions per machine
- `document_content`: Full PDF text storage
- `few_shot_examples`: Training examples (3-layer validated)
- `goa_modifications`: Field edit tracking

**All CRUD**: `src/utils/db/` package (modular: clients.py, items.py, machines.py, etc.)

## API Endpoints (Key Routes)

**Quotes**: `GET/POST/PUT/DELETE /quotes/*` - CRUD + PDF upload
**Machines**: `GET /machines/*`, `GET/PUT /machines/{id}/template`
**Processing**: `POST /processing/extract`, `/generate`, `/fill-form`
**GOA Forms**: `GET/PUT /processing/goa-form/{id}`, `POST .../generate-document`, `GET .../file`
**Reports**: `GET /reports/{machine_id}`
**Shipping**: `GET/POST /shipping/{quote_id}/*`

## Environment Variables

```bash
GEMINI_API_KEY=           # Google Gemini API key
DATABASE_PATH=data/crm_data.db
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
GOA_LLM_MODEL=gemini-2.5-flash-lite  # Pinned model version
QUOTE_LIBRARY_PATH=       # Optional, defaults to QUOTE_LIBRARY.txt
QUOTE_LIBRARY_MAX_SECTIONS=2
QUOTE_LIBRARY_MAX_CHARS=14000
```

## Platform Constraints (Windows)

1. **Path handling**: Use `pathlib.Path` (handles `/` and `\`)
2. **Unicode in console**: Use ASCII only (`[OK]` not checkmarks)
3. **Case sensitivity**: NTFS is case-insensitive but preserving

## Modification Protocol

**Before any change**:
1. Read all affected files completely
2. Identify which pipeline(s) impacted (PDF, GOA, Few-Shot, QUOTE_LIBRARY)
3. Check if database schema change needed
4. Determine if both templates (HTML & Word) affected

**After any change**:
1. Run `pytest tests/ -v`
2. Test with sample PDFs in `templates/`
3. Test both template types if logic changed

**Critical files**:
- `api/main.py`: FastAPI app, CORS, router registration
- `api/services/processing_service.py`: Extraction + generation orchestration
- `src/llm/extraction.py`: LLM prompts, field extraction
- `src/utils/db/`: All database operations
- `src/utils/form_generator.py`: Excel -> HTML conversion
- `templates/GOA_template.xlsx`: Field schema source of truth

## Known Gotchas

1. **`src/utils/llm_handler.py` is a shim**: All real logic lives in `src/llm/`. The handler just forwards via `__getattr__`.

2. **Few-shot validation is 3-layer**: Pre-filter at call site -> `_is_valid_example_payload` at DB insert -> `_row_is_valid_example` at retrieval. All three must pass.

3. **QUOTE_LIBRARY context**: Automatically matched by machine name and injected into prompts. Configurable via env vars. PDF quote data takes priority over library specs in case of conflict.

4. **PDF RAG, not truncation**: PDF text is chunked and scored, not truncated. Budgets are 50-60K chars. Only few-shot example storage uses a 2K char snippet.

5. **Machine detection**: Centralized in `src/utils/machine_type.py` with `_MACHINE_FAMILIES` lookup table. All patterns use `re.IGNORECASE`.
