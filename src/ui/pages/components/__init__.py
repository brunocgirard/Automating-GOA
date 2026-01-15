"""
UI Component modules for the QuoteFlow Document Assistant.

This package contains reusable UI components used across multiple pages:
- template_components: Template display and summary utilities
- goa_report_components: GOA report generation and HTML formatting
- form_editor_components: GOA field editing and modification tracking

These components are extracted from the original ui_pages.py for better
code organization and reusability.
"""

from .template_components import (
    generate_template_summary,
    show_template_items_table,
    show_template_summary,
)

from .goa_report_components import (
    generate_printable_report,
    show_printable_report,
    show_printable_summary_report,
    generate_machine_build_summary_html,
)

from .form_editor_components import (
    show_goa_modifications_ui,
    display_template_editor,
)

__all__ = [
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
