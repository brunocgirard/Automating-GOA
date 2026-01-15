"""
Database utilities package - refactored from monolithic crm_utils.py

This package provides a clean, organized interface to all database operations
for the QuoteFlow Document Assistant application.

Modules:
- base: Database initialization and connection management
- utils: Shared utility functions (price parsing, etc.)
- clients: Client/quote CRUD operations
- items: Priced items operations (line items from PDF quotes)
- machines: Machine management and grouping operations
- templates: Template data storage and retrieval
- modifications: Modification tracking for GOA documents
- documents: Document content storage (full PDF text)
- few_shot: Few-shot learning operations and examples

Usage:
    from src.utils.db import init_db, save_client_info, load_machines_for_quote

    # Initialize database
    init_db()

    # Save client information
    client_data = {'quote_ref': 'ABC-123', 'customer_name': 'ACME Corp'}
    save_client_info(client_data)

    # Load machines
    machines = load_machines_for_quote('ABC-123')
"""

# Base and utilities
from .base import (
    DB_PATH,
    HTML_TEMPLATE_PATH,
    DOCX_TEMPLATE_PATH,
    TEMPLATE_FILE_PATH,
    init_db,
    get_connection
)

from .utils import (
    parse_price_string
)

# Client operations
from .clients import (
    save_client_info,
    get_client_by_id,
    update_client_record,
    load_all_clients,
    delete_client_record
)

# Priced items operations
from .items import (
    save_priced_items,
    load_priced_items_for_quote,
    update_single_priced_item,
    calculate_common_items_price
)

# Machine operations
from .machines import (
    save_machines_data,
    load_machines_for_quote,
    find_machines_by_name,
    load_all_processed_machines,
    group_items_by_confirmed_machines,
    calculate_machine_price
)

# Template operations
from .templates import (
    save_machine_template_data,
    load_machine_template_data,
    load_machine_templates_with_modifications,
    update_template_after_modifications
)

# Modification tracking operations
from .modifications import (
    save_goa_modification,
    load_goa_modifications,
    save_bulk_goa_modifications
)

# Document content operations
from .documents import (
    save_document_content,
    load_document_content,
    delete_document_content
)

# Few-shot learning operations
from .few_shot import (
    save_few_shot_example,
    get_few_shot_examples,
    add_few_shot_feedback,
    get_few_shot_statistics,
    get_field_examples,
    get_all_field_names,
    create_sample_few_shot_data,
    get_similar_examples
)

# Public API - all exported names
__all__ = [
    # Base and utilities
    'DB_PATH',
    'HTML_TEMPLATE_PATH',
    'DOCX_TEMPLATE_PATH',
    'TEMPLATE_FILE_PATH',
    'init_db',
    'get_connection',
    'parse_price_string',

    # Client operations
    'save_client_info',
    'get_client_by_id',
    'update_client_record',
    'load_all_clients',
    'delete_client_record',

    # Priced items operations
    'save_priced_items',
    'load_priced_items_for_quote',
    'update_single_priced_item',
    'calculate_common_items_price',

    # Machine operations
    'save_machines_data',
    'load_machines_for_quote',
    'find_machines_by_name',
    'load_all_processed_machines',
    'group_items_by_confirmed_machines',
    'calculate_machine_price',

    # Template operations
    'save_machine_template_data',
    'load_machine_template_data',
    'load_machine_templates_with_modifications',
    'update_template_after_modifications',

    # Modification tracking operations
    'save_goa_modification',
    'load_goa_modifications',
    'save_bulk_goa_modifications',

    # Document content operations
    'save_document_content',
    'load_document_content',
    'delete_document_content',

    # Few-shot learning operations
    'save_few_shot_example',
    'get_few_shot_examples',
    'add_few_shot_feedback',
    'get_few_shot_statistics',
    'get_field_examples',
    'get_all_field_names',
    'create_sample_few_shot_data',
    'get_similar_examples',
]
