# GOA LLM Project

## 1. Project Purpose
The GOA LLM Project aims to streamline and automate the process of generating General Offer Arrangement (GOA) documents from PDF quotes. It leverages Large Language Models (LLMs) for intelligent data extraction from quotes, populates standardized Word templates, and provides a user interface for managing and modifying these templates, particularly after client kickoff meetings. The system is designed to improve accuracy, reduce manual effort, and maintain a traceable history of document modifications for manufacturing and sales workflows.

## 2. Features Overview
- **Automated PDF Quote Parsing:** Extracts text and table data from uploaded PDF quote documents.
- **LLM-Powered Data Extraction:** Utilizes Google's Generative AI (Gemini) to intelligently identify and extract relevant information (customer details, machine specifications, selected options, etc.) from parsed quote content.
- **Dynamic Word Document Generation:** Populates predefined `.docx` GOA templates with the extracted data, filling in placeholders.
- **Database Storage:** Stores client information, machine details, extracted quote data, and template modification history in an SQLite database.
- **Web Interface:** A Streamlit application provides a user-friendly interface for:
    - Processing new quotes.
    - Reviewing LLM-extracted data.
    - Triggering document generation.
    - Managing and applying modifications to machine-specific GOA templates.
- **Template Modification Tracking:** Allows users to select specific fields in a machine's GOA, modify their values, provide reasons for changes, and save these modifications.
- **Hierarchical Template Summary:** Displays a structured, hierarchical view of selected options within a GOA template, making it easier to review and understand the configuration.
- **Document Regeneration:** Enables regeneration of GOA documents incorporating all saved modifications.

## 3. Getting Started

### 3.1. Prerequisites
- Python 3.9+
- Git (for cloning the repository, if applicable)

### 3.2. Installation & Setup
1.  **Clone the Repository** (if you haven't already):
    ```bash
    # git clone <repository_url>
    # cd GOA_LLM
    ```
2.  **Create and Activate a Virtual Environment** (Recommended):
    ```bash
    python -m venv .venv
    ```
    - On Windows:
      ```bash
      .venv\Scripts\activate
      ```
    - On macOS/Linux:
      ```bash
      source .venv/bin/activate
      ```
3.  **Install Dependencies:**
    From the project root directory (`GOA_LLM/`):
    ```bash
    pip install -r requirements.txt
    ```
4.  **Environment Variables:**
    Create a file named `.env` in the project root directory (`GOA_LLM/.env`). This file is used to store sensitive information like API keys. Add your Google API key to it:
    ```env
    GOOGLE_API_KEY="YOUR_GOOGLE_AI_STUDIO_API_KEY"
    ```
    Replace `"YOUR_GOOGLE_AI_STUDIO_API_KEY"` with your actual API key for Google Generative AI services. The application uses `python-dotenv` to load this variable.

5.  **Initialize the Database:**
    Run the initialization script from the project root directory:
    ```bash
    python initialize_db.py
    ```
    This will create the `data/crm_data.db` SQLite database file and set up the necessary tables if they don't exist.

### 3.3. Running the Application
Ensure your virtual environment is activated and you are in the project root directory.
```bash
streamlit run app.py
```
This will start the Streamlit application, and it should open in your default web browser.

## 4. How to Use (User Guide)

The application interface is organized into several tabs:

1.  **Quote Processing:**
    *   **Upload PDF Quote:** Select or drag-and-drop a PDF quote file.
    *   **Process Quote:** Click the button to initiate PDF parsing and LLM data extraction.
    *   **Review Extracted Data:** The extracted information (customer, machine, fields) will be displayed. Verify its accuracy.
    *   **Save to Database:** Save the extracted and verified data to the CRM database.
    *   **(Generate Document):** (Functionality for direct document generation from this tab might exist or be planned).

2.  **CRM Dashboard:**
    *   View and manage existing clients, machines, and processed quote data stored in the database.
    *   (Details on search/filter/edit capabilities can be added here).

3.  **Template Modifications:**
    *   **Select Machine:** Choose a machine (for which a GOA has been processed) from the dropdown.
    *   **View Hierarchical Summary:** The application displays a structured summary of the selected options for the chosen machine's GOA template.
    *   **Modify Fields:**
        *   Select a field key from the available placeholders/fields.
        *   Enter the `Modified Value` for the field.
        *   Provide a `Reason for Modification`.
        *   Click `Save Modification`.
    *   **View Modification History:** A table shows all saved modifications for the selected machine.
    *   **Download Modified Document:** After saving modifications, click this button to regenerate the GOA Word document with all applied changes. The document reflects the current state of the template based on the accumulated modifications.

## 5. Project Structure

The project has been organized into the following structure:

```
GOA_LLM/
├── app.py                    # Main application entry point
├── main.py                   # Alternative entry point for batch processing
├── initialize_db.py          # Script to initialize the database with latest schema
├── requirements.txt          # Project dependencies (including testing)
├── pytest.ini                # Pytest configuration
├── src/                      # Source code directory
│   ├── __init__.py           # Makes src a proper Python package
│   ├── ui/                   # UI-related modules
│   │   ├── __init__.py
│   │   └── ui_pages.py       # UI page rendering functions
│   ├── utils/                # Utility modules
│   │   ├── __init__.py
│   │   ├── crm_utils.py      # Database operations
│   │   ├── doc_filler.py     # Document filling utilities
│   │   ├── llm_handler.py    # LLM API interactions
│   │   ├── pdf_utils.py      # PDF parsing utilities
│   │   └── template_utils.py # Template handling utilities
│   ├── workflows/            # Business logic workflows
│   │   ├── __init__.py
│   │   └── profile_workflow.py # Client profile handling
│   └── generators/           # Document generation
│       ├── __init__.py
│       └── document_generators.py # Document generation utilities
├── tests/                    # Automated tests
│   └── test_template_utils.py # Tests for template_utils
├── scripts_to_archive/       # Archived development/diagnostic scripts
├── config/                   # Configuration files (legacy or specific)
│   ├── .gitignore
│   ├── mapping.py
│   ├── mapping_mailmerge.txt
│   # requirements.txt here is now superseded by the root one
├── docs/                     # Documentation
│   ├── client_profile_plan.md
│   ├── integration_plan.md
│   ├── README.md             # This file
│   └── Refactoring Plan.md
└── backup/                   # Backup files
    └── (various backup files)
```

## 6. Development

The project is organized by functionality:

- `src/utils/`: Core utility functions that are used across the application
- `src/ui/`: User interface components and page rendering
- `src/workflows/`: Business logic related to specific workflows
- `src/generators/`: Document generation utilities
- `tests/`: Automated tests for the project.

When adding new functionality, add it to the appropriate module based on its purpose. Corresponding tests should be added in the `tests/` directory.

## 7. Testing

This project uses `pytest` for automated testing.

**Running Tests:**

1.  Ensure you have installed all development dependencies (which are now the main dependencies):
    ```bash
    pip install -r requirements.txt 
    ```

2.  Run tests from the project root directory:
    ```bash
    pytest
    ```
    Or for more verbose output:
    ```bash
    pytest -v
    ```

Tests are located in the `tests/` directory. The `pytest.ini` file in the project root is configured to automatically discover and run these tests and manage Python import paths.

Currently, unit tests cover parts of the `src/utils/template_utils.py` module.

## 8. Project Cleanup

Various development and diagnostic scripts that were used during the development process have been archived into the `scripts_to_archive/` directory to keep the project root clean. Core utility scripts like `initialize_db.py` remain at the root.

## Features

### GOA Template Modifications

The application now supports tracking and managing modifications made to GOA templates after kickoff meetings. This feature allows you to:

1. **Track Changes**: Store a history of modifications made to GOA templates for each machine
2. **Record Reasons**: Document why changes were made (e.g., "Client request in kickoff meeting")
3. **Regenerate Documents**: Apply modifications and regenerate documents with the latest changes

To use this feature:

1. Process a machine for GOA in the Quote Processing workflow
2. Go to the "Template Modifications" tab
3. Select the machine to modify
4. Choose a field to modify, enter the new value and reason
5. Save the modification
6. Regenerate the document with all applied modifications

All modifications are stored in the database and linked to specific machine templates, allowing for full traceability of changes.

### Hierarchical Template Summary

The application now provides a structured, hierarchical view of selected items in the GOA template. This feature:

1. **Organizes by Section**: Groups selected options by categories like "Control & Programming Specifications"
2. **Shows User-Friendly Names**: Displays both the human-readable names and technical field keys
3. **Highlights Selected Values**: Makes it easy to see what options are enabled in the template

The summary appears in the Template Modifications tab, giving you a clear overview of what has been selected for each machine's GOA. This makes it easier to:

- Quickly review what options have been selected for a machine
- Identify which section a particular option belongs to
- Find the correct field key when you need to make modifications

This hierarchical view is particularly useful during kickoff meetings when you need to review selected options with clients and make adjustments based on their feedback. 
