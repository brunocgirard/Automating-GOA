"""
UI modules for the GOA LLM application.

This module provides backward compatibility by re-exporting page functions
from the new modular structure (src.ui.pages).

The original monolithic ui_pages.py (3,415 lines) has been split into:
- Individual page modules in src/ui/pages/
- Reusable components in src/ui/pages/components/
- Shared utilities in src/ui/shared/

All page functions are re-exported here to maintain backward compatibility
with existing imports in app.py and other files.
"""

# Re-export page functions from the new modular structure
from src.ui.pages import (
    show_welcome_page,
    show_client_dashboard_page,
    show_quote_processing,
    show_crm_management_page,
    show_template_report_page,
    show_chat_page,
    handle_chat_context_switch,
    render_chat_ui,
)

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