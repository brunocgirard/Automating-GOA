# QuoteFlow Document Assistant

QuoteFlow is a Streamlit-based application designed to streamline the processing of machinery quotes and the generation of related commercial documents. It leverages Large Language Models (LLMs) to extract information from PDF quotes and populate various document templates.

## Features

- **Client Profile Workflow**: Upload PDF quotes to automatically extract client information and build comprehensive client profiles.
- **Interactive Profile Confirmation**: Review and edit LLM-extracted client data and machine groupings before saving.
- **Action Selection Hub**: After a profile is created, choose from a range of actions:
    - Generate General Order Agreements (GOA)
    - Create Export Documents (Packing Slips, Commercial Invoices, Certificates of Origin)
    - Edit client profiles
    - Chat with the quote data using an LLM assistant
- **GOA Document Processing**: Specialized workflow for General Order Agreements, including machine-specific data extraction and template filling.
- **CRM Management**: 
    - View and edit client records.
    - Manage priced items (line items) associated with each client/quote.
    - Securely delete client records and all associated data.
- **Machine Identification**: Automatically identifies main machines and their add-ons from quote line items. Users can confirm and adjust these groupings.
- **Context-Aware Chat**: Engage in conversations about specific quotes or general application functionality.
- **Data Persistence**: Client profiles, processed quote data, and generated document metadata are stored in a local SQLite database.
- **Modular Design**: Separate modules for PDF processing, LLM interaction, document filling, CRM utilities, and document-specific data generation.

## Workflow Overview

1.  **Welcome Page**: 
    *   Upload a new PDF quote to start the client profile extraction process.
    *   Alternatively, navigate directly to other sections like Client Dashboard or Quote Processing.
2.  **Client Profile Extraction & Confirmation**:
    *   The system extracts standard client information and line items using an LLM.
    *   Users review and confirm/edit the extracted client details.
    *   Users interactively confirm main machines and common options from the quote's line items.
    *   The confirmed profile (client info, line items, machine groupings, full PDF text) is saved to the database.
3.  **Client Dashboard**:
    *   View a list of all saved client profiles.
    *   Search and select a client to proceed.
4.  **Action Selection Hub** (displayed on the Welcome page after a client is selected from the Dashboard or a new profile is confirmed):
    *   Choose an action for the selected client profile (Generate GOA, Export Docs, Edit Profile, Chat).
5.  **Action Execution**:
    *   **Generate GOA**: Navigates to the Quote Processing wizard, pre-populated with the client's quote data.
    *   **Export Documents**: Navigates to the Export Documents page, allowing selection of machines and document type (Packing Slip, Commercial Invoice, etc.).
    *   **Edit Profile**: Navigates to the CRM Management page with the client pre-selected for editing.
    *   **Chat with Quote**: Opens a dedicated chat interface pre-loaded with the context of the selected client's quote.
6.  **Quote Processing (GOA)**:
    *   A step-by-step wizard for processing quotes specifically for GOA documents.
    *   Includes machine selection, common options confirmation, and LLM-powered template filling.
7.  **CRM Management**:
    *   View all client records.
    *   Edit client details and associated priced items.
    *   Delete client records.
    *   Manually add new client records.

## Setup and Running

1.  **Clone the repository** (if applicable).
2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up your Google API Key**:
    *   Create a `.env` file in the root directory.
    *   Add your Google API key: `GOOGLE_API_KEY="YOUR_API_KEY_HERE"`
5.  **Place your template files** in the root directory:
    *   `template.docx` (for GOA)
    *   `Packing Slip.docx`
    *   `Commercial Invoice.docx`
    *   `CERTIFICATION OF ORIGIN_NAFTA.docx`
6.  **Initialize the database** (if running for the first time or after schema changes):
    *   The application will attempt to create `crm_data.db` on first run.
    *   If you've made changes to `crm_utils.py` affecting table structures, delete the old `crm_data.db` file before running the app.
7.  **Run the Streamlit application**:
    ```bash
    streamlit run app.py
    ```

## Modules

- `app.py`: Main Streamlit application, UI, and workflow logic.
- `crm_utils.py`: Database interaction (SQLite).
- `doc_filler.py`: Fills Word document templates.
- `document_generators.py`: Prepares data for specific export document types.
- `llm_handler.py`: Manages interaction with the Google Generative AI (Gemini).
- `mapping_mailmerge.txt`: List of standard fields for client profile extraction.
- `pdf_utils.py`: PDF text and table extraction.
- `template_utils.py`: Extracts placeholders and context from Word templates.

## Future Enhancements

- More robust LLM prompting for even better data extraction accuracy.
- Direct visual editing of document previews.
- Advanced search and filtering in CRM.
- User roles and permissions. 