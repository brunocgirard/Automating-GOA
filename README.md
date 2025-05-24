# GOA Document Assistant

A powerful tool for processing machine quotes to generate General Order Agreements (GOA), packing slips, and commercial invoices.

## Features

- **Quote Processing**: Extract and process data from PDF quotes
- **Machine Identification**: Automatically detect multiple machines within a single quote
- **User Confirmation Interface**: Two-step process to confirm main machines and common options
- **Document Generation**: Create GOA documents for specific machines
- **Export Documents**: Generate packing slips and commercial invoices
- **Client Management**: Store and manage client information in a database
- **Context-Aware Chat Assistant**: Get help with processing quotes and document generation

## Technical Overview

This application is built with:
- **Streamlit**: For the web interface
- **LLM Integration**: For intelligent data extraction and processing
- **PDF Processing**: Extract structured data from quote PDFs
- **Database Storage**: Save client information, quote details, and machine specifications
- **Document Generation**: Create filled Word documents based on templates

## Project Structure

- `app.py`: Main application file
- `pdf_utils.py`: PDF extraction utilities
- `template_utils.py`: Document template handling
- `llm_handler.py`: LLM integration for data extraction
- `doc_filler.py`: Document generation utilities
- `crm_utils.py`: Database management
- `document_generators.py`: Export document generation

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `streamlit run app.py`

## Usage

1. Upload a quote PDF
2. Identify main machines and common options
3. Process machine-specific data
4. Generate export documents as needed

## Future Enhancements

- Enhanced machine learning capabilities for better quote interpretation
- Additional export document types
- Integration with external CRM systems
- Batch processing of multiple quotes 