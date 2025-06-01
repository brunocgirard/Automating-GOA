# GOA LLM Project

## Project Structure

The project has been organized into the following structure:

```
GOA_LLM/
├── app.py                    # Main application entry point
├── main.py                   # Alternative entry point for batch processing
├── initialize_db.py          # Script to initialize the database with latest schema
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
├── config/                   # Configuration files
│   ├── .gitignore
│   ├── mapping.py
│   ├── mapping_mailmerge.txt
│   └── requirements.txt
├── docs/                     # Documentation
│   ├── client_profile_plan.md
│   ├── integration_plan.md
│   ├── README.md             # This file
│   └── Refactoring Plan.md
└── backup/                   # Backup files
    └── (various backup files)
```

## Running the Application

To run the application:

1. Install the required dependencies:
   ```
   pip install -r config/requirements.txt
   ```

2. Initialize the database with the latest schema:
   ```
   python initialize_db.py
   ```

3. Run the main application:
   ```
   streamlit run app.py
   ```

## Development

The project is organized by functionality:

- `utils/`: Core utility functions that are used across the application
- `ui/`: User interface components and page rendering
- `workflows/`: Business logic related to specific workflows
- `generators/`: Document generation utilities

When adding new functionality, add it to the appropriate module based on its purpose.

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