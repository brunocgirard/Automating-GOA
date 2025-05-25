# GOA LLM Project

## Project Structure

The project has been organized into the following structure:

```
GOA_LLM/
├── app.py                    # Main application entry point
├── main.py                   # Alternative entry point for batch processing
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

2. Run the main application:
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