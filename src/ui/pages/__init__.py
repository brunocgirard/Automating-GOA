"""
Page modules for the QuoteFlow Document Assistant.

This package contains individual page modules that were extracted from the
monolithic ui_pages.py file for improved maintainability and organization.

Each page module is responsible for rendering a specific page in the Streamlit application:
- welcome_page: Landing page with recent clients and quote upload
- client_dashboard_page: Client browsing, selection, and profile management
- quote_processing_page: Multi-step quote processing workflow (5 steps)
- crm_management_page: CRM data management with client/item editing
- machine_build_reports_page: Machine build report generation and viewing
- chat_page: Document-based chat interface with context switching

All page functions are exported here for convenient importing.
"""

from .welcome_page import show_welcome_page
from .client_dashboard_page import show_client_dashboard_page
from .quote_processing_page import show_quote_processing
from .crm_management_page import show_crm_management_page
from .machine_build_reports_page import show_template_report_page
from .chat_page import show_chat_page, handle_chat_context_switch, render_chat_ui

__all__ = [
    'show_welcome_page',
    'show_client_dashboard_page',
    'show_quote_processing',
    'show_crm_management_page',
    'show_template_report_page',
    'show_chat_page',
    'handle_chat_context_switch',
    'render_chat_ui',
]
