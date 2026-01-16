# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

QuoteFlow Document Assistant automates generation of General Offer Arrangement (GOA) documents from PDF quotes using AI. It extracts data, populates templates, and maintains a customer database with modification tracking.

## Running the Application

```bash
# Install dependencies (use virtual environment)
pip install -r requirements.txt

# Set up environment
# Create .env file and add: GOOGLE_API_KEY=your_key_here

# Run the Streamlit application
streamlit run app.py

# Verification suite (run after modifications)
.venv\Scripts\python.exe verify_step1_environment.py  # Dependencies & DB
.venv\Scripts\python.exe verify_step2_langchain.py    # LangChain integration
.venv\Scripts\python.exe verify_step3_fewshot.py      # Few-shot learning
.venv\Scripts\python.exe verify_step4_html_templates.py  # Template system
.venv\Scripts\python.exe verify_step5_end_to_end.py   # Full workflow
```

## Architecture: Three Core Pipelines

### Pipeline 1: PDF → Database
```
PDF Upload
  ↓ src/utils/pdf_utils.py::extract_line_item_details()
  ↓ src/utils/pdf_utils.py::identify_machines_from_items()
  ↓ src/utils/crm_utils.py::save_client_info(), save_priced_items(), save_machines_data()
Database (SQLite)
```

**Key insight**: One PDF extraction feeds both immediate GOA generation and long-term CRM data.

### Pipeline 2: GOA Generation (Dual-Template System)
```
Select Machine
  ↓ app.py::get_contexts_for_machine() → Determines template type
  ├─→ Standard machines → HTML template (602 fields from Excel)
  │     ↓ src/utils/form_generator.py::extract_schema_from_excel()
  │     ↓ src/utils/llm_handler.py::get_machine_specific_fields_via_llm()
  │     ↓ src/utils/html_doc_filler.py::fill_and_generate_html()
  └─→ SortStar machines → Word template
        ↓ src/utils/doc_filler.py::fill_word_document_from_llm_data()
Generated Document
```

**Critical distinction**: Template selection based on regex pattern `\b(sortstar|unscrambler|bottle unscrambler)\b` in machine name. Standard uses HTML (Excel → HTML workflow), SortStar uses Word directly.

### Pipeline 3: Few-Shot Learning Enhancement
```
LLM Extraction Result
  ↓ src/utils/few_shot_learning.py::save_successful_extraction_as_example()
  ↓ Embeddings via GoogleGenerativeAIEmbeddings (768 dims)
  ↓ ChromaDB vector store (src/cache/few_shot_embeddings/)
Future Extractions (semantic similarity retrieval)
```

**Current state**: 6,239 examples stored. Semantic similarity selects relevant examples to improve LLM accuracy.

## LLM Integration Architecture

**Provider**: Google Gemini (`gemini-2.5-flash-lite`)
**Frameworks**:
- Raw: `google.generativeai` for basic calls
- Structured: `langchain_google_genai.ChatGoogleGenerativeAI` + `PydanticOutputParser` for type-safe outputs

**Pattern**:
1. Build Pydantic model from template schema dynamically
2. Use LangChain FewShotPromptTemplate with semantic example selection
3. Parse JSON output into validated Pydantic objects
4. Post-process with domain rules (src/utils/llm_handler.py::apply_post_processing_rules)

## Template System: Excel as Source of Truth

**For Standard GOA**:
1. Source: `templates/GOA_template.xlsx` (Form sheet, 602 fields)
2. Generator: `src/utils/form_generator.py::generate_goa_form()` creates `templates/goa_form.html`
3. Schema: Columns are [Section, Subsection, Sub-subsection, Field Name, Type, Placeholder]
4. Special handling: `options_listing` field auto-formats bullet lists (src/utils/html_doc_filler.py::format_options_listing)

**To add a field**:
- Add row to Excel → Regenerate HTML → Field automatically available
- LLM prompt in `llm_handler.py` must be updated to extract new field

**For SortStar GOA**:
- Direct Word template manipulation via `python-docx`
- No Excel source, fields hardcoded in template

## Database Schema (SQLite: data/crm_data.db)

**Core Tables**:
- `clients`: Customer info, keyed by quote_ref
- `priced_items`: Line items from PDF (JSON blob with description, price, quantity)
- `machines`: Machine groupings with add-ons (JSON blob)
- `machine_templates`: Saved field extractions per machine (for regeneration)
- `document_content`: Full PDF text storage (for chat/context)
- `few_shot_examples`: Training examples (machine_type, template_type, field_name, input_context, expected_output)
- `few_shot_feedback`: User corrections (currently unused)

**All CRUD**: `src/utils/crm_utils.py` (2,800+ lines, comprehensive)

## State Management (Streamlit)

**Session state lives in**: `app.py::initialize_session_state()`

**Critical state keys**:
- `processing_done`: Gates multi-step workflows
- `identified_machines_data`: Dict with {machines: [...], common_items: [...]}
- `selected_machine_id`: Links to database machine record
- `machine_docx_path` / `machine_specific_filled_data`: Output artifacts
- `run_key`: Increments on new PDF processing, ensures unique output filenames

**Navigation**: Five pages (Client Dashboard, Quote Processing, CRM Management, Machine Build Reports, Chat) in `src/ui/ui_pages.py`

## Platform Constraints (Windows-Specific)

**Critical**: This runs on Windows (win32).

**Issues to avoid**:
1. **Unicode in console output** → Use ASCII only (`[OK]` not `✓`, `[WARN]` not `⚠`)
   - Already fixed in `src/utils/llm_handler.py:27`
2. **Path handling** → Always use `pathlib.Path`, handles both `/` and `\`
3. **Line endings** → Git may auto-convert, be aware
4. **Case sensitivity** → NTFS is case-insensitive but preserving

## Modification Protocol

**Before any change**:
1. Read all affected files completely
2. Identify which pipeline(s) impacted (PDF, GOA, Few-Shot)
3. Check if database schema change needed
4. Determine if both templates (HTML & Word) affected

**After any change**:
1. Run verification scripts (see "Running the Application")
2. Test with sample PDF: `templates/CQC-25-2638R5-NP.pdf` or `templates/UME-23-0001CN-R5-V2.pdf`
3. Verify database integrity (check record counts didn't corrupt)
4. Test both template types if logic changed

**Critical files**:
- `app.py`: Main orchestration, template selection, session state
- `src/utils/llm_handler.py`: LLM prompts, post-processing rules
- `src/utils/crm_utils.py`: All database operations
- `src/utils/form_generator.py`: Excel → HTML conversion
- `templates/GOA_template.xlsx`: Field schema source of truth

## Key Functions Reference

**PDF Processing**:
- `extract_line_item_details(pdf_path)` → List[Dict] of items
- `identify_machines_from_items(items)` → {machines: [...], common_items: [...]}

**LLM Operations**:
- `configure_gemini_client()` → Initialize (call once at startup)
- `get_machine_specific_fields_via_llm(machine_data, common_items, template_contexts, full_pdf_text)` → Dict[field_name, value]

**Database**:
- `save_client_info(client_dict)` → bool
- `load_machines_for_quote(quote_ref)` → List[Dict] (includes DB id)
- `save_machine_template_data(machine_id, template_type, field_data, output_path)` → bool

**Templates**:
- `generate_goa_form()` → bool (regenerates HTML from Excel)
- `fill_and_generate_html(template_path, data_dict, output_path)` → bool

## Known Gotchas

1. **Machine ID propagation**: Machine records need `id` field from DB for template saves. If missing, search by name or create new record. See `app.py::process_machine_specific_data()` lines 430-529.

2. **Options listing regeneration**: Always rebuild from selected items, don't rely on stale data. See `app.py:356-384`.

3. **Template context caching**: Contexts loaded per-machine on-demand. Don't cache globally. See `app.py::get_contexts_for_machine()`.

4. **Few-shot manager singleton**: Use `get_few_shot_manager()` not direct `FewShotManager()` to reuse embeddings. See `src/utils/few_shot_enhanced.py:28`.

5. **Streamlit reruns**: Any UI change triggers full rerun. Expensive operations (LLM calls, DB writes) gated by session state flags.

## For the quoteflow-modifier Agent

See `AGENT_MODIFICATION_PROMPT.md` for comprehensive agent instructions including:
- Complete data flow diagrams
- Modification scenarios with step-by-step guides
- Improvement proposal framework
- State-aware modification protocol
- Risk assessment guidelines

**Current system status** (as of last verification):
- 108/117 verification tests passing (92.3%)
- 6,239 few-shot examples available
- 602 fields in standard template
- 10 clients, 215 items, 15 machines in database
- All critical systems operational

## Documentation References

- `README.md`: User-facing setup and workflow diagram
- `VERIFICATION_REPORT.md`: Detailed test results, system status
- `VERIFICATION_SUMMARY.md`: Quick status overview
- `AGENT_MODIFICATION_PROMPT.md`: Complete agent operating manual
- `API_KEY_SETUP.md`: Google API key configuration
- `full_fields_outline.md`: Field descriptions for standard template
