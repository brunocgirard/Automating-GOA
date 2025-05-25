# App.py Refactoring Plan

## Objective
To improve the modularity and readability of `app.py` by splitting its content into more focused Python modules. This will make the codebase easier to maintain and understand as it grows.

## Core Modules to Create

1.  **`ui_pages.py`**: This module will contain the primary functions responsible for rendering the different pages/views of the Streamlit application.
2.  **`profile_workflow.py`**: This module will encapsulate the logic related to the client profile extraction, confirmation, and action selection workflow.
3.  **`app_utils.py`** (Optional - for now, keeping helpers in `app.py` or their most relevant new module): This module could hold general helper functions currently in `app.py` that don't fit neatly into `ui_pages.py` or `profile_workflow.py` (e.g., `group_items_by_confirmed_machines`, `calculate_machine_price`, `calculate_common_items_price`, `get_current_context`, `process_chat_query`, `render_chat_ui`). For this iteration, we will primarily focus on moving page display and profile workflow functions.

## Function Migration Plan

### 1. Functions to move to `profile_workflow.py`:
    - `extract_client_profile(pdf_path)`
    - `confirm_client_profile(extracted_profile)`
    - `show_action_selection(client_profile)`
    - `handle_selected_action(action, profile_data)`
    - `load_full_client_profile(quote_ref: str)`

### 2. Functions to move to `ui_pages.py`:
    - `show_welcome_page()`
    - `show_client_dashboard_page()`
    - `show_quote_processing()`
    - `show_export_documents()` (Need to ensure its original content for generating export documents is fully present or restored)
    - `show_crm_management_page()`
    - `show_chat_page()`
    - `render_chat_ui()` (This is a UI component, fits well here)

### 3. Functions to remain in (or be called from) `app.py` (Main Application Logic):
    - `initialize_session_state()`
    - `init_db()` (Called at startup)
    - `load_crm_data()` (Session state related)
    - `perform_initial_processing()` (Core GOA processing logic, potentially could be moved to a `processing_utils.py` later)
    - `process_machine_specific_data()` (Core GOA processing logic)
    - `load_previous_document()` (GOA specific loading)
    - `quick_extract_and_catalog()` (Alternative processing path)
    - `generate_export_document()` (Though called by `show_export_documents`, the core generation logic might stay if complex, or move with its UI page) - *Decision: Move with `show_export_documents` for now if it's tightly coupled, or `app_utils.py` if more general.*
    - `group_items_by_confirmed_machines()` - *Decision: Move to `app_utils.py` or keep in `app.py` if not too large.*
    - `calculate_machine_price()` - *Decision: Move to `app_utils.py` or keep in `app.py`.*
    - `calculate_common_items_price()` - *Decision: Move to `app_utils.py` or keep in `app.py`.*
    - `get_current_context()` - *Decision: Could go to `app_utils.py`.*
    - `process_chat_query()` - *Decision: Could go to `app_utils.py` or `llm_handler.py` if very LLM specific.*
    - The main application flow control (sidebar navigation, page display logic based on `st.session_state.current_page`).

## `app.py` Modifications
- Remove all functions that have been moved to other modules.
- Add `import` statements for the new modules:
    ```python
    from ui_pages import show_welcome_page, show_client_dashboard_page, ...
    from profile_workflow import extract_client_profile, confirm_client_profile, ...
    # from app_utils import ... (if created)
    ```
- Ensure that all calls to the moved functions within `app.py` are updated to use the new module references (e.g., `ui_pages.show_welcome_page()`).
- Pass `st` (Streamlit object) and `st.session_state` to functions in other modules if they need to access Streamlit functionalities or session state directly. Alternatively, pass specific session state variables as arguments and return values to update them.

## Refactoring Steps

1.  **Backup `app.py`**: Create a safe backup of the current `app.py` file. (Already done as `app.py.backup_interactive_template`, can make another one like `app.py.pre_refactor`)
2.  **Create `profile_workflow.py`**:
    *   Copy the identified profile workflow functions into this new file.
    *   Add necessary imports at the top of `profile_workflow.py` (e.g., `os`, `json`, `streamlit as st`, `crm_utils`, `pdf_utils`, `llm_handler`).
3.  **Create `ui_pages.py`**:
    *   Copy the identified UI page functions into this new file.
    *   Add necessary imports at the top of `ui_pages.py` (e.g., `streamlit as st`, `pandas as pd`, `os`, `profile_workflow` if it calls functions from there, other utility modules like `crm_utils`, `doc_filler`, `document_generators`).
4.  **(Optional) Create `app_utils.py`**:
    *   Move remaining helper functions if deemed necessary.
    *   Add necessary imports.
5.  **Refactor `app.py`**:
    *   Delete the moved functions from `app.py`.
    *   Add the new import statements for `ui_pages` and `profile_workflow` (and `app_utils` if created).
    *   Update all internal calls to the moved functions to use their new module prefixes (e.g., `ui_pages.show_welcome_page()`).
    *   Carefully manage dependencies:
        *   Functions in `ui_pages.py` might need to call functions in `profile_workflow.py` (e.g., `show_welcome_page` might trigger profile extraction and confirmation).
        *   Ensure `st.session_state` is accessed consistently. It's a global-like object within a Streamlit session, so direct access (`st.session_state.some_key`) will work across modules as long as `import streamlit as st` is present.
6.  **Testing**:
    *   Run the application (`streamlit run app.py`).
    *   Thoroughly test all navigation paths and functionalities to ensure everything works as before the refactor.
    *   Pay close attention to workflows involving client profile creation, action selection, GOA processing, and CRM interactions.

## Considerations:
- **Circular Dependencies**: Be mindful to avoid circular dependencies between the new modules. For instance, `ui_pages` might import `profile_workflow`, but `profile_workflow` should ideally not import `ui_pages`.
- **Streamlit Object (`st`) and Session State (`st.session_state`)**: Functions moved to new modules will still need access to `st` for UI elements and `st.session_state` for state management. Ensure `import streamlit as st` is in each new file where these are used.
- **Global Variables**: If `app.py` uses any global variables (like `TEMPLATE_FILE`), ensure these are handled appropriately (e.g., passed as arguments, defined as constants in a config module, or re-defined where needed). `GENERATIVE_MODEL` in `llm_handler.py` is an example of a module-level global.

This refactoring will significantly improve the organization of the project. 