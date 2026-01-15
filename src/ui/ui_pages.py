"""
DEPRECATED: This module is maintained for backward compatibility only.

This file has been refactored into modular page and component modules under src.ui.pages:

Page Modules:
- src.ui.pages.welcome_page: Landing page with quote upload
- src.ui.pages.client_dashboard_page: Client browsing and selection
- src.ui.pages.quote_processing_page: Multi-step quote processing workflow
- src.ui.pages.crm_management_page: CRM data management
- src.ui.pages.machine_build_reports_page: Machine build report generation
- src.ui.pages.chat_page: Document-based chat interface

Component Modules:
- src.ui.pages.components.template_components: Template display utilities
- src.ui.pages.components.goa_report_components: Report generation utilities
- src.ui.pages.components.form_editor_components: GOA field editing utilities

For new code, please import from src.ui.pages directly:
    from src.ui.pages import show_quote_processing, show_client_dashboard_page
    from src.ui.pages.components import generate_printable_report

This facade will be maintained for backward compatibility during the transition period.

Original file backed up as: src/ui/ui_pages.py.backup (191KB, 3415 lines)
"""

# Import all page functions from the new modular structure
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

# Import all component functions for backward compatibility
from src.ui.pages.components import (
    # Template components
    generate_template_summary,
    show_template_items_table,
    show_template_summary,
    # Report components
    generate_printable_report,
    show_printable_report,
    show_printable_summary_report,
    generate_machine_build_summary_html,
    # Editor components
    show_goa_modifications_ui,
    display_template_editor,
)

# Optional: Uncomment to add deprecation warning on import
# import warnings
# warnings.warn(
#     "ui_pages is deprecated. Please import from src.ui.pages instead.",
#     DeprecationWarning,
#     stacklevel=2
# )

# Maintain the __all__ export list for explicit API definition
__all__ = [
    # Page functions
    'show_welcome_page',
    'show_client_dashboard_page',
    'show_quote_processing',
    'show_crm_management_page',
    'show_template_report_page',
    'show_chat_page',
    'handle_chat_context_switch',
    'render_chat_ui',

    # Template components
    'generate_template_summary',
    'show_template_items_table',
    'show_template_summary',

    # Report components
    'generate_printable_report',
    'show_printable_report',
    'show_printable_summary_report',
    'generate_machine_build_summary_html',

    # Editor components
    'show_goa_modifications_ui',
    'display_template_editor',
]
