# Technology Stack

## Overview
This project leverages a Python-based ecosystem, with Streamlit providing the web interface and Langchain orchestrating interactions with Large Language Models (LLMs). Data persistence is handled by SQLite for CRM functionalities and ChromaDB for efficient vector embeddings in the context of few-shot learning. A robust set of libraries is employed for comprehensive document processing, including PDF parsing and Word document generation.

## Core Technologies

### Programming Language
*   **Python**: The primary programming language used across the application for its versatility, extensive library support, and suitability for AI/ML tasks.

### Web Framework
*   **Streamlit**: Utilized for building the user-friendly web interface, enabling rapid development and interactive data applications.

### LLM Integration
*   **Langchain**: Serves as the framework for developing applications powered by language models, facilitating prompt management, chaining, and integration with various LLMs.
*   **Google Generative AI**: The specific Large Language Model (LLM) provider integrated into the system for intelligent data extraction and document generation.

### Databases
*   **SQLite**: Used as a lightweight, file-based relational database for managing CRM data, client profiles, and historical information.
*   **ChromaDB**: Employed as a vector database for storing and querying vector embeddings, crucial for the few-shot learning loop and efficient retrieval of similar examples.

### Document Processing and Manipulation
*   **pdfplumber**: For advanced parsing and extraction of text and tables from PDF documents.
*   **python-docx**: For programmatically creating, modifying, and generating Microsoft Word (.docx) files.
*   **PyPDF2**: A pure-Python PDF library capable of splitting, merging, cropping, and transforming PDF pages.
*   **openpyxl**: Used for reading and writing Excel 2010 xlsx/xlsm/xltx/xltm files, particularly for handling complex Excel-driven HTML templates.
*   **beautifulsoup4**: A Python library for parsing HTML and XML documents, likely used in conjunction with `weasyprint` for HTML template processing.
*   **weasyprint**: A visual rendering engine that can turn HTML and CSS into PDFs, used for generating previewable HTML forms that convert to final documents.
