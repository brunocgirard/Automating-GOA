"""
DEPRECATED: This module is maintained for backward compatibility only.

This file has been refactored into domain-specific modules under src.utils.db:
- src.utils.db.base: Database initialization and connection
- src.utils.db.utils: Shared utility functions (price parsing, etc.)
- src.utils.db.clients: Client CRUD operations
- src.utils.db.items: Priced items operations
- src.utils.db.machines: Machine management
- src.utils.db.templates: Template data operations
- src.utils.db.modifications: Modification tracking
- src.utils.db.documents: Document content storage
- src.utils.db.few_shot: Few-shot learning operations

For new code, please import from src.utils.db directly:
    from src.utils.db import save_client_info, load_all_clients

This facade will be maintained for backward compatibility during the transition period.

Original file backed up as: src/utils/crm_utils.py.backup (96KB, 2800+ lines)
"""

# Import everything from the new modular structure
from src.utils.db import *

# Explicitly import all constants for backward compatibility
from src.utils.db.base import (
    DB_PATH,
    HTML_TEMPLATE_PATH,
    DOCX_TEMPLATE_PATH,
    TEMPLATE_FILE_PATH,
    init_db,
    get_connection
)

# Explicitly import all utility functions
from src.utils.db.utils import (
    parse_price_string
)

# Explicitly import all client operations
from src.utils.db.clients import (
    save_client_info,
    get_client_by_id,
    update_client_record,
    load_all_clients,
    delete_client_record
)

# Explicitly import all priced items operations
from src.utils.db.items import (
    save_priced_items,
    load_priced_items_for_quote,
    update_single_priced_item,
    calculate_common_items_price
)

# Explicitly import all machine operations
from src.utils.db.machines import (
    save_machines_data,
    load_machines_for_quote,
    find_machines_by_name,
    load_all_processed_machines,
    group_items_by_confirmed_machines,
    calculate_machine_price
)

# Explicitly import all template operations
from src.utils.db.templates import (
    save_machine_template_data,
    load_machine_template_data,
    load_machine_templates_with_modifications,
    update_template_after_modifications
)

# Explicitly import all modification tracking operations
from src.utils.db.modifications import (
    save_goa_modification,
    load_goa_modifications,
    save_bulk_goa_modifications
)

# Explicitly import all document content operations
from src.utils.db.documents import (
    save_document_content,
    load_document_content,
    delete_document_content
)

# Explicitly import all few-shot learning operations
from src.utils.db.few_shot import (
    save_few_shot_example,
    get_few_shot_examples,
    add_few_shot_feedback,
    get_few_shot_statistics,
    get_field_examples,
    get_all_field_names,
    create_sample_few_shot_data,
    get_similar_examples
)

# Optional: Uncomment to add deprecation warning on import
# import warnings
# warnings.warn(
#     "crm_utils is deprecated. Please import from src.utils.db instead.",
#     DeprecationWarning,
#     stacklevel=2
# )

# Maintain the __all__ export list for explicit API definition
__all__ = [
    # Constants
    'DB_PATH',
    'HTML_TEMPLATE_PATH',
    'DOCX_TEMPLATE_PATH',
    'TEMPLATE_FILE_PATH',

    # Base operations
    'init_db',
    'get_connection',

    # Utilities
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
