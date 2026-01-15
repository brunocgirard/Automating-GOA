import streamlit as st
import os
import json
import sqlite3
import pandas as pd
import re
from typing import Dict, List, Optional, Any, Tuple
import traceback
import shutil
from datetime import datetime

# Import from modular page structure (refactored from monolithic ui_pages.py)
# Note: Can also import from src.ui.ui_pages for backward compatibility
from src.ui.pages import (
    show_welcome_page, show_client_dashboard_page, show_quote_processing,
    show_crm_management_page, show_chat_page, render_chat_ui, show_template_report_page
)
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection, 
    handle_selected_action, load_full_client_profile
)

# Import from existing utility modules
from src.utils.pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from src.utils import template_utils # Import the module itself
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical, extract_placeholder_schema # Import specific functions
from src.utils.llm_handler import (
    configure_gemini_client, get_machine_specific_fields_via_llm, answer_pdf_question,
    get_machine_specific_fields_with_confidence, get_confidence_level,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW
)
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.html_doc_filler import fill_and_generate_html
from src.utils.form_generator import generate_goa_form, extract_schema_from_excel, OUTPUT_HTML_PATH
from src.utils.db import (
    init_db, save_client_info, load_all_clients, get_client_by_id,
    update_client_record, save_priced_items, load_priced_items_for_quote,
    update_single_priced_item, delete_client_record, save_machines_data,
    load_machines_for_quote, save_machine_template_data, load_machine_template_data,
    save_document_content, load_document_content, save_goa_modification,
    load_goa_modifications, load_machine_templates_with_modifications,
    update_template_after_modifications, find_machines_by_name, load_all_processed_machines
)

# Define Template File Constants
TEMPLATE_FILE = os.path.join("templates", "template.docx")
SORTSTAR_TEMPLATE_FILE = os.path.join("templates", "goa_sortstar_temp.docx")

# --- Template Configuration Hub ---
# This dictionary centralizes the configuration for different template types.
TEMPLATE_CONFIGS = {
    "default": {
        "template_file": os.path.join("templates", "template.docx"),
        "explicit_mappings": template_utils.DEFAULT_EXPLICIT_MAPPINGS,
        "outline_file": "full_fields_outline.md",
        "is_sortstar": False
    },
    "sortstar": {
        "template_file": os.path.join("templates", "goa_sortstar_temp.docx"),
        "explicit_mappings": template_utils.SORTSTAR_EXPLICIT_MAPPINGS,
        "outline_file": "sortstar_fields_outline.md",
        "is_sortstar": True
    }
}

# --- App State Initialization ---
def initialize_session_state(is_new_processing_run=False):
    if "current_page" not in st.session_state: st.session_state.current_page = "Client Dashboard"
    if "current_client_profile" not in st.session_state: st.session_state.current_client_profile = None
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    if "profile_extraction_step" not in st.session_state: st.session_state.profile_extraction_step = None
    if "extracted_profile" not in st.session_state: st.session_state.extracted_profile = None
    if "confirmed_profile" not in st.session_state: st.session_state.confirmed_profile = None
    if "action_profile" not in st.session_state: st.session_state.action_profile = None 
    if "chat_context" not in st.session_state: st.session_state.chat_context = None
    if "quote_chat_history" not in st.session_state: st.session_state.quote_chat_history = []
    if "current_action" not in st.session_state: st.session_state.current_action = None
    if "processing_step" not in st.session_state: st.session_state.processing_step = 0
    if "selected_main_machines_profile" not in st.session_state: st.session_state.selected_main_machines_profile = []
    if "selected_common_options_profile" not in st.session_state: st.session_state.selected_common_options_profile = []
    if "profile_machine_confirmation_step" not in st.session_state: st.session_state.profile_machine_confirmation_step = "main_machines"
        
    if is_new_processing_run or 'run_key' not in st.session_state: 
        st.session_state.run_key = st.session_state.get('run_key', 0) + (1 if is_new_processing_run else 0)

    keys_to_reset_on_new_pdf_processing = [
        'extracted_profile', 'confirmed_profile', 'profile_extraction_step',
        'selected_main_machines_profile', 'selected_common_options_profile',
        'profile_machine_confirmation_step', 'action_profile', 'current_action',
        'chat_context', 'quote_chat_history'
    ]
    if is_new_processing_run: 
        for key in keys_to_reset_on_new_pdf_processing:
            if key == "profile_machine_confirmation_step": st.session_state[key] = "main_machines"
            elif key in ["selected_main_machines_profile", "selected_common_options_profile", "quote_chat_history"]: st.session_state[key] = []
            else: st.session_state[key] = None
    
    goa_processing_keys = [
        'full_pdf_text', 'processing_done', 'selected_pdf_descs', 'template_contexts',
        'llm_initial_filled_data', 'llm_corrected_filled_data', 'initial_docx_path',
        'corrected_docx_path', 'error_message', 'chat_log', 'correction_applied',
        'identified_machines_data', 'selected_machine_index', 'machine_specific_filled_data',
        'machine_docx_path', 'selected_machine_id', 'machine_confirmation_done',
        'common_options_confirmation_done', 'items_for_confirmation', 'selected_main_machines',
        'selected_common_options', 'manual_machine_grouping',
        'processing_step', 'preview_step_active', 'selected_machine_data', 'selected_machine_name',
        'original_llm_extraction'
    ]
    goa_defaults = {
        'full_pdf_text': "", 'processing_done': False, 'selected_pdf_descs': [], 'template_contexts': {},
        'llm_initial_filled_data': {}, 'llm_corrected_filled_data': {},
        'initial_docx_path': f"output_llm_initial_run{st.session_state.get('run_key',0)}.docx",
        'corrected_docx_path': f"output_llm_corrected_run{st.session_state.get('run_key',0)}.docx",
        'error_message': "", 'chat_log': [], 'correction_applied': False,
        'identified_machines_data': {}, 'selected_machine_index': 0, 'machine_specific_filled_data': {},
        'machine_docx_path': f"output_machine_specific_run{st.session_state.get('run_key',0)}.html",
        'selected_machine_id': None, 'machine_confirmation_done': False,
        'common_options_confirmation_done': False, 'items_for_confirmation': [],
        'selected_main_machines': [], 'selected_common_options': [],
        'manual_machine_grouping': {},
        'processing_step': 0,
        'preview_step_active': False, 'selected_machine_data': None, 'selected_machine_name': "",
        'original_llm_extraction': {}
    }
    for key in goa_processing_keys:
        if key not in st.session_state:
            st.session_state[key] = goa_defaults[key]

    if 'all_crm_clients' not in st.session_state: st.session_state.all_crm_clients = []
    if 'editing_client_id' not in st.session_state: st.session_state.editing_client_id = None
    if 'crm_data_loaded' not in st.session_state: st.session_state.crm_data_loaded = False
    if 'current_priced_items_for_editing' not in st.session_state: st.session_state.current_priced_items_for_editing = [] 
    if 'edited_priced_items_df' not in st.session_state: st.session_state.edited_priced_items_df = pd.DataFrame()
    if 'selected_client_for_detail_edit' not in st.session_state: st.session_state.selected_client_for_detail_edit = None 
    if 'edited_client_details_df' not in st.session_state: st.session_state.edited_client_details_df = pd.DataFrame()
    if 'confirming_delete_client_id' not in st.session_state: st.session_state.confirming_delete_client_id = None

# --- Helper Functions ---
def group_items_by_confirmed_machines(all_items, main_machine_indices, common_option_indices):
    machines = []
    common_items = []
    remaining_items = list(range(len(all_items)))
    for idx in common_option_indices:
        if idx in remaining_items: remaining_items.remove(idx); common_items.append(all_items[idx])
    for machine_idx in main_machine_indices:
        if machine_idx in remaining_items:
            remaining_items.remove(machine_idx)
            next_machine_idx = float('inf')
            for next_idx in main_machine_indices:
                if next_idx > machine_idx and next_idx < next_machine_idx: next_machine_idx = next_idx
            add_ons = []
            for idx in list(remaining_items): 
                if idx > machine_idx and (idx < next_machine_idx or next_machine_idx == float('inf')):
                    add_ons.append(all_items[idx]); remaining_items.remove(idx)
            machine_name = all_items[machine_idx].get('description', '').split('\n')[0]
            machines.append({"machine_name": machine_name, "main_item": all_items[machine_idx], "add_ons": add_ons})
    for idx in remaining_items: common_items.append(all_items[idx])
    return {"machines": machines, "common_items": common_items}

def calculate_machine_price(machine_data):
    total_price = 0.0
    main_item = machine_data.get("main_item", {})
    main_price = main_item.get("item_price_numeric", 0); 
    if main_price is not None: total_price += main_price
    for item in machine_data.get("add_ons", []):
        addon_price = item.get("item_price_numeric", 0)
        if addon_price is not None: total_price += addon_price
    return total_price

def calculate_common_items_price(common_items):
    total_price = 0.0
    for item in common_items:
        item_price = item.get("item_price_numeric", 0)
        if item_price is not None: total_price += item_price
    return total_price

def quick_extract_and_catalog(uploaded_pdf_file, existing_client_id=None):
    temp_pdf_path = None
    try:
        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf_file.getbuffer())
        progress_placeholder = st.empty(); progress_placeholder.info("Extracting & Cataloging...")
        items = extract_line_item_details(temp_pdf_path)
        full_text = extract_full_pdf_text(temp_pdf_path)
        if not items: st.warning("No items extracted."); return None
        
        # Generate a quote reference from the filename
        quote_ref = uploaded_pdf_file.name.split('.')[0]
        
        # Initialize client info
        # Try to infer machine model early for template selection downstream
        machine_model_guess = ""
        identified_machines_early = identify_machines_from_items(items)
        if identified_machines_early and identified_machines_early.get("machines"):
            # Use the first identified machine name as a guess
            machine_model_guess = identified_machines_early["machines"][0].get("machine_name", "")
        
        client_info = {"quote_ref": quote_ref, "customer_name": "", "machine_model": machine_model_guess, "country_destination": "", "sold_to_address": "", "ship_to_address": "", "telephone": "", "customer_contact_person": "", "customer_po": ""}
        
        # If existing client ID is provided, get their info and update only the quote_ref
        if existing_client_id:
            existing_client = get_client_by_id(existing_client_id)
            if existing_client:
                # Create a new quote record linked to the existing client
                linked_quote_ref = f"{existing_client['quote_ref']}_{quote_ref}"
                client_info = existing_client.copy()
                client_info["quote_ref"] = linked_quote_ref
                progress_placeholder.info(f"Linking to existing client: {existing_client['customer_name']}")
            else:
                progress_placeholder.warning(f"Existing client ID {existing_client_id} not found. Creating new client.")
        
        if save_client_info(client_info):
            progress_placeholder.info(f"Client record for {client_info['quote_ref']} created.")
            if save_priced_items(client_info['quote_ref'], items): progress_placeholder.info(f"Saved {len(items)} items.")
            else: st.warning(f"Failed to save priced items for {client_info['quote_ref']}.")
            if full_text and save_document_content(client_info['quote_ref'], full_text, uploaded_pdf_file.name): progress_placeholder.info("Doc content saved.")
            else: st.warning("Failed to save doc content.")
            
            machine_data = identify_machines_from_items(items)
            if save_machines_data(client_info['quote_ref'], machine_data): progress_placeholder.info("Machine grouping saved.")
            else: st.warning("Failed to save machine grouping.")

            progress_placeholder.success("Cataloging Complete!")
            load_crm_data()
            return {"quote_ref": client_info['quote_ref'], "items": items}
        else: st.error(f"Failed to create client record for {client_info['quote_ref']}."); return None
    except Exception as e: st.error(f"Quick extract error: {e}"); traceback.print_exc(); return None
    finally: 
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)

def perform_initial_processing(uploaded_pdf_file, template_file_path):
    goa_defaults_reinit = {
        'full_pdf_text': "", 'processing_done': False, 'selected_pdf_descs': [], 'template_contexts': {},
        'llm_initial_filled_data': {}, 'llm_corrected_filled_data': {}, 
        'initial_docx_path': f"output_llm_initial_run{st.session_state.run_key}.docx",
        'corrected_docx_path': f"output_llm_corrected_run{st.session_state.run_key}.docx",
        'error_message': "", 'chat_log': [], 'correction_applied': False,
        'identified_machines_data': {}, 'selected_machine_index': 0, 'machine_specific_filled_data': {},
        'machine_docx_path': f"output_machine_specific_run{st.session_state.run_key}.html",
        'selected_machine_id': None, 'machine_confirmation_done': False,
        'common_options_confirmation_done': False, 'items_for_confirmation': [],
        'selected_main_machines': [], 'selected_common_options': [],
        'manual_machine_grouping': {},
        'processing_step': 0 
    }
    for key, val in goa_defaults_reinit.items(): st.session_state[key] = val
    
    temp_pdf_path = None 
    try:
        if not configure_gemini_client(): st.session_state.error_message = "LLM client config failed."; return False
        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf_file.getbuffer())
        with st.status("Processing PDF & Template for GOA...", expanded=True) as status_bar:
            st.write("Extracting data from PDF...")
            st.session_state.selected_pdf_items_structured = extract_line_item_details(temp_pdf_path)
            st.session_state.full_pdf_text = extract_full_pdf_text(temp_pdf_path)
            st.session_state.items_for_confirmation = st.session_state.selected_pdf_items_structured
            
            initial_machine_data = identify_machines_from_items(st.session_state.selected_pdf_items_structured)
            
            # This logic is no longer needed here, it will be handled per-machine.
            # The main purpose here is to extract and save the raw data from the PDF.
            # The template-specific logic is now in `process_machine_specific_data`.

            # Initialize with empty selections to avoid confusion - let users select manually
            # for i, item in enumerate(st.session_state.selected_pdf_items_structured):
            #     if any(m.get("main_item") == item for m in initial_machine_data.get("machines", [])): preselected_machines.append(i)
            #     elif any(ci == item for ci in initial_machine_data.get("common_items", [])): preselected_common.append(i)
            st.session_state.selected_main_machines = []
            st.session_state.selected_common_options = []
            st.session_state.selected_pdf_descs = [item.get("description","") for item in st.session_state.selected_pdf_items_structured if item.get("description")]
            if not st.session_state.selected_pdf_descs: st.warning("No descriptions extracted for LLM.")
            if not st.session_state.full_pdf_text: st.warning("Full PDF text extraction failed.")

            st.write("Data extraction complete. Machine-specific templates will be analyzed when 'Generate GOA' is clicked.")
            
            st.session_state.identified_machines_data = initial_machine_data

            status_bar.update(label="Saving GOA data to CRM...")
            
            # Create client info - check if we should use an existing client
            existing_client_id = st.session_state.get("selected_existing_client_id", None)
            client_info_payload = {"quote_ref": uploaded_pdf_file.name.split('.')[0], "customer_name": "", "machine_model": "", "country_destination": "", "sold_to_address": "", "ship_to_address": "", "telephone": "", "customer_contact_person": "", "customer_po": ""}
            
            if existing_client_id:
                existing_client = get_client_by_id(existing_client_id)
                if existing_client:
                    # Create a linked quote reference that combines the existing client and this quote
                    linked_quote_ref = f"{existing_client['quote_ref']}_{client_info_payload['quote_ref']}"
                    client_info_payload = existing_client.copy()
                    client_info_payload["quote_ref"] = linked_quote_ref
                    st.write(f"Linking to existing client: {existing_client['customer_name']}")
                else:
                    st.warning(f"Existing client ID {existing_client_id} not found. Creating new client.")
            
            if save_client_info(client_info_payload):
                st.write(f"Client info for GOA '{client_info_payload['quote_ref']}' saved.")
                if st.session_state.selected_pdf_items_structured and save_priced_items(client_info_payload['quote_ref'], st.session_state.selected_pdf_items_structured): st.write("Priced items for GOA saved.")
                else: st.warning("Failed to save priced items for GOA.")
                if st.session_state.full_pdf_text and save_document_content(client_info_payload['quote_ref'], st.session_state.full_pdf_text, uploaded_pdf_file.name): st.write("GOA doc content saved.")
                else: st.warning("Failed to save GOA doc content.")
                load_crm_data()
            else: st.warning(f"Failed to save client info for GOA '{client_info_payload['quote_ref']}'.")
            status_bar.update(label="GOA Initial Processing Complete!", state="complete", expanded=False)
        st.session_state.processing_done = True; return True
    except Exception as e: st.session_state.error_message = f"GOA processing error: {e}"; traceback.print_exc(); return False
    finally: 
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)

def run_llm_extraction_only(machine_data):
    """
    Runs LLM extraction and stores results in session state.
    Does NOT generate document or save to database.

    Args:
        machine_data: Dictionary containing machine information

    Returns:
        bool: Success status

    Session State Output:
        - machine_specific_filled_data: Dict of extracted fields
        - selected_machine_data: Full machine data for later use
        - selected_machine_name: Machine name
    """
    try:
        if not configure_gemini_client():
            st.session_state.error_message = "LLM client config failed."
            return False

        st.info(f"Extracting data for machine: {machine_data.get('machine_name', 'Unknown')}")

        common_items = machine_data.get("common_items", [])
        if not common_items and st.session_state.identified_machines_data:
             common_items = st.session_state.identified_machines_data.get("common_items", [])

        # --- DEBUG LOGGING ---
        print("\n--- DEBUG: run_llm_extraction_only ---")
        print(f"Machine Data: {json.dumps(machine_data, indent=2)}")
        print(f"Common Items: {json.dumps(common_items, indent=2)}")
        print("------------------------------------------\n")
        # --- END DEBUG LOGGING ---

        with st.spinner(f"Extracting fields for: {machine_data.get('machine_name')}..."):
            template_contexts, template_file_path, is_sortstar_template = get_contexts_for_machine(machine_data)

            if not template_contexts:
                st.error(f"Could not load template contexts for machine: {machine_data.get('machine_name')}")
                return False

            # --- Rehydrate machine data from DB (source of truth for selected items) ---
            refreshed_machine_data = machine_data
            try:
                if "id" in machine_data and machine_data["id"]:
                    conn = sqlite3.connect("data/crm_data.db")
                    cur = conn.cursor()
                    cur.execute("SELECT machine_data_json FROM machines WHERE id = ?", (machine_data["id"],))
                    row = cur.fetchone()
                    if row:
                        refreshed_machine_data = json.loads(row[0])
                    conn.close()
            except Exception as e:
                print(f"Warning: could not reload machine data from DB for gating: {e}")

            # Prefer common_items from refreshed machine data
            if refreshed_machine_data and refreshed_machine_data.get("common_items"):
                common_items = refreshed_machine_data.get("common_items", common_items)
            machine_data_for_processing = refreshed_machine_data or machine_data

            # Use the enhanced extraction with confidence scoring
            machine_filled_data, confidence_scores, suggestions = get_machine_specific_fields_with_confidence(
                machine_data_for_processing,
                common_items,
                template_contexts,
                st.session_state.full_pdf_text
            )

            # Store extracted data in session state for preview
            st.session_state.machine_specific_filled_data = machine_filled_data
            # IMPORTANT: Save original extraction for comparison (for few-shot learning)
            st.session_state.original_llm_extraction = machine_filled_data.copy()
            # Store confidence scores for UI display
            st.session_state.field_confidence_scores = confidence_scores
            # Store field dependency suggestions
            st.session_state.field_dependency_suggestions = suggestions
            st.session_state.selected_machine_data = machine_data_for_processing
            st.session_state.selected_machine_name = machine_data.get('machine_name', 'machine')

            # Calculate confidence summary for display
            high_conf = sum(1 for c in confidence_scores.values() if c >= CONFIDENCE_HIGH)
            med_conf = sum(1 for c in confidence_scores.values() if CONFIDENCE_MEDIUM <= c < CONFIDENCE_HIGH)
            low_conf = sum(1 for c in confidence_scores.values() if c < CONFIDENCE_MEDIUM)

            st.success(f"Extracted {len(machine_filled_data)} fields successfully!")

            # Show confidence summary
            if low_conf > 0:
                st.warning(f"Confidence Summary: {high_conf} high, {med_conf} medium, {low_conf} low-confidence fields that may need review")
            return True

    except Exception as e:
        st.session_state.error_message = f"LLM extraction error: {e}"
        traceback.print_exc()
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False


def save_user_corrections_as_training_examples(
    original_data: Dict[str, Any],
    edited_data: Dict[str, Any],
    machine_data: Dict,
    common_items: List[Dict],
    full_pdf_text: str,
    machine_type: str
) -> int:
    """
    Compares original LLM extraction with user-edited data and saves corrections
    as high-quality training examples for few-shot learning.

    Args:
        original_data: Original LLM extraction
        edited_data: User-edited data from preview
        machine_data: Machine information
        common_items: Common items list
        full_pdf_text: Full PDF text
        machine_type: Determined machine type

    Returns:
        int: Number of corrections saved
    """
    from src.utils.few_shot_learning import (
        determine_machine_type,
        save_successful_extraction_as_example,
        extract_field_context_for_example
    )

    corrections_count = 0

    for field_key, edited_value in edited_data.items():
        original_value = original_data.get(field_key)

        # Check if user made a correction
        if edited_value != original_value:
            # Skip if user just cleared a suspicious value to empty
            if edited_value in [None, ""]:
                continue

            # Save the corrected value as a high-quality training example
            try:
                success = save_successful_extraction_as_example(
                    field_name=field_key,
                    field_value=edited_value,
                    machine_data=machine_data,
                    common_items=common_items,
                    full_pdf_text=full_pdf_text,
                    machine_type=machine_type,
                    template_type="GOA",
                    source_machine_id=machine_data.get('id'),
                    confidence_score=1.0  # User-corrected = highest confidence
                )

                if success:
                    corrections_count += 1
                    print(f"[Few-Shot] Saved user correction for field: {field_key}")

            except Exception as e:
                print(f"[Few-Shot] Failed to save correction for {field_key}: {e}")

    return corrections_count


def generate_and_save_document():
    """
    Generates document from session state data and saves to database.
    Assumes LLM extraction already completed via run_llm_extraction_only().

    Session State Input:
        - machine_specific_filled_data: Edited field values
        - selected_machine_data: Machine info
        - selected_machine_name: Machine name
        - identified_machines_data: For common items

    Returns:
        bool: Success status

    Session State Output:
        - machine_docx_path: Path to generated document
        - selected_machine_id: Database machine ID
    """
    try:
        # Retrieve data from session state
        machine_filled_data = st.session_state.get('machine_specific_filled_data')
        machine_data = st.session_state.get('selected_machine_data')
        machine_name = st.session_state.get('selected_machine_name', 'machine')

        if not machine_filled_data or not machine_data:
            st.error("No extracted data found in session. Please run LLM extraction first.")
            return False

        # Get common items
        common_items = machine_data.get("common_items", [])
        if not common_items and st.session_state.identified_machines_data:
            common_items = st.session_state.identified_machines_data.get("common_items", [])

        with st.spinner(f"Generating document for: {machine_name}..."):
            # Load template contexts to determine machine type
            template_contexts, template_file_path, is_sortstar_template = get_contexts_for_machine(machine_data)

            if not template_contexts:
                st.error(f"Could not load template contexts for machine: {machine_name}")
                return False

            clean_name = re.sub(r'[\\/*?:"<>|]', "_", machine_name.replace(' ', '_'))

            # --- Always regenerate options_listing from the currently selected machine items ---
            selected_details = []

            def summarize_item(label, item):
                desc = (item or {}).get("description", "").strip()
                if not desc:
                    return None
                if "•" in desc:
                    desc = desc.split("•", 1)[0].strip()
                return f"- {label}: {desc}"

            main_line = summarize_item("Main Machine", machine_data.get("main_item"))
            if main_line:
                selected_details.append(main_line)

            for addon in (machine_data.get("add_ons") or []):
                line = summarize_item("Add-on", addon)
                if line:
                    selected_details.append(line)

            for common in (common_items or []):
                line = summarize_item("Common Item", common)
                if line:
                    selected_details.append(line)

            if selected_details:
                machine_filled_data["options_listing"] = "Selected Options and Specifications:\n" + "\n".join(selected_details)
            else:
                machine_filled_data["options_listing"] = "No options or specifications selected for this machine."

            # Ensure the filled data includes options_listing for downstream HTML/Docx generation
            if "options_listing" in st.session_state.machine_specific_filled_data:
                machine_filled_data["options_listing"] = st.session_state.machine_specific_filled_data["options_listing"]

            # Set the output path based on machine type
            is_sortstar_machine = is_sortstar_template
            if is_sortstar_machine:
                machine_specific_output_path = f"output_SORTSTAR_{clean_name}_GOA.docx"
            else:
                machine_specific_output_path = f"output_{clean_name}_GOA.html"

            # Check that we have data before filling
            if not machine_filled_data:
                st.error("No data available to fill the template.")
                return False

            if is_sortstar_machine:
                # Keep Word logic for SortStar for now
                fill_word_document_from_llm_data(template_file_path, machine_filled_data, machine_specific_output_path)
            else:
                # Use HTML logic for standard GOA
                # 1. Regenerate form to ensure it's up to date
                if not generate_goa_form():
                    st.error("Failed to generate HTML form template.")
                    return False

                # 2. Fill HTML and save
                # We use the generated OUTPUT_HTML_PATH as the template source
                fill_and_generate_html(str(OUTPUT_HTML_PATH), machine_filled_data, machine_specific_output_path)

            if not os.path.exists(machine_specific_output_path):
                st.error(f"Failed to create output file: {machine_specific_output_path}")
                return False

            st.session_state.machine_docx_path = machine_specific_output_path

            # Save machine template data to database
            # Make sure we have a machine ID - check for "id" in machine_data
            machine_id = None
            if "id" in machine_data:
                machine_id = machine_data["id"]
                st.success(f"Using existing machine ID: {machine_id}")
            else:
                # We need to find or create a machine record in the database
                # First, determine the quote_ref
                quote_ref = None

                # Try several methods to get the quote_ref
                if "client_quote_ref" in machine_data:
                    quote_ref = machine_data["client_quote_ref"]
                    st.info(f"Found quote_ref in machine_data: {quote_ref}")
                elif st.session_state.items_for_confirmation and len(st.session_state.items_for_confirmation) > 0:
                    quote_ref = st.session_state.items_for_confirmation[0].get("client_quote_ref", "")
                    if quote_ref:
                        st.info(f"Found quote_ref in items_for_confirmation: {quote_ref}")

                # If still not found, try to extract from file info
                if not quote_ref:
                    # Try to extract from the file name if available
                    if hasattr(st.session_state, "pdf_filename") and st.session_state.pdf_filename:
                        match = re.search(r'([A-Za-z0-9-]+)\.pdf', st.session_state.pdf_filename)
                        if match:
                            quote_ref = match.group(1)
                            st.info(f"Extracted quote_ref from filename: {quote_ref}")

                    # If still no quote_ref, use machine name as fallback
                    if not quote_ref:
                        machine_name_ref = machine_data.get("machine_name", "")
                        if machine_name_ref:
                            # Sanitize machine name to use as quote_ref
                            quote_ref = re.sub(r'[^A-Za-z0-9-]', '_', machine_name_ref)
                            st.warning(f"Using machine name as quote_ref fallback: {quote_ref}")
                        else:
                            quote_ref = f"unknown_quote_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            st.warning(f"Using generated quote_ref fallback: {quote_ref}")

                # Ensure we have a valid quote_ref
                if not quote_ref:
                    st.error("Could not determine quote_ref. Cannot save machine data.")
                    return False

                st.info(f"Using quote_ref: {quote_ref}")

                # Check if we already have this machine in the database

                # First check if a machine with this name already exists in any quote
                machine_name_db = machine_data.get("machine_name", "")
                matching_machines = find_machines_by_name(machine_name_db)

                if matching_machines:
                    st.success(f"Found {len(matching_machines)} existing machine(s) with name '{machine_name_db}'")
                    # Use the first matching machine
                    machine_id = matching_machines[0]["id"]
                    st.success(f"Using existing machine ID: {machine_id}")
                else:
                    # Ensure the client record exists first
                    client_info = {"quote_ref": quote_ref, "customer_name": "", "machine_model": machine_data.get("machine_name", "")}
                    st.info(f"Ensuring client record exists for quote_ref: {quote_ref}")
                    save_client_info(client_info)

                    # Now check for existing machines in this quote
                    machines_from_db = load_machines_for_quote(quote_ref)

                    # Look for a matching machine name
                    matching_machine = next((m for m in machines_from_db if m["machine_name"] == machine_name_db), None)

                    if matching_machine:
                        machine_id = matching_machine["id"]
                        st.success(f"Found existing machine ID: {machine_id}")
                    else:
                        # Need to create a new machine record
                        st.info(f"Creating new machine record for {machine_name_db} with quote_ref: {quote_ref}")

                        # Make sure machine_data has client_quote_ref
                        machine_data_copy = machine_data.copy()
                        machine_data_copy["client_quote_ref"] = quote_ref

                        machine_group = {"machines": [machine_data_copy], "common_items": common_items}

                        if save_machines_data(quote_ref, machine_group):
                            # Get the newly created machine ID
                            machines_from_db = load_machines_for_quote(quote_ref)
                            matching_machine = next((m for m in machines_from_db if m["machine_name"] == machine_name_db), None)
                            if matching_machine:
                                machine_id = matching_machine["id"]
                                st.success(f"Created new machine with ID: {machine_id}")
                            else:
                                st.warning("Created machine record but couldn't retrieve its ID")
                                # Additional debugging
                                st.info(f"Machines in DB after creation: {len(machines_from_db)}")
                                for m in machines_from_db:
                                    st.info(f"- Machine: {m['machine_name']} (ID: {m['id']})")
                        else:
                            st.error(f"Failed to save machine data to database for quote_ref: {quote_ref}")
                            # Additional error details
                            st.info(f"Machine data: {machine_data_copy}")
                            st.info(f"Common items: {len(common_items)} items")

            # Now save the template data
            if machine_id:
                from src.utils.db import save_machine_template_data
                st.info(f"Saving template data for machine ID: {machine_id}")
                if save_machine_template_data(machine_id, "GOA", machine_filled_data, machine_specific_output_path):
                    st.success(f"Document generated and saved successfully: {machine_specific_output_path}")

                    # Store the machine ID in the session for future use
                    st.session_state.selected_machine_id = machine_id

                    # Save user corrections as training examples for few-shot learning
                    try:
                        original_data = st.session_state.get('original_llm_extraction', {})
                        if original_data:
                            from src.utils.few_shot_learning import determine_machine_type
                            machine_name = machine_data.get("machine_name", "")
                            machine_type = determine_machine_type(machine_name)

                            corrections_saved = save_user_corrections_as_training_examples(
                                original_data=original_data,
                                edited_data=machine_filled_data,
                                machine_data=machine_data,
                                common_items=common_items,
                                full_pdf_text=st.session_state.get('full_pdf_text', ''),
                                machine_type=machine_type
                            )

                            if corrections_saved > 0:
                                st.info(f"[Few-Shot Learning] Saved {corrections_saved} user correction(s) as training examples")
                    except Exception as correction_error:
                        print(f"[Few-Shot] Failed to save corrections: {correction_error}")
                        # Don't fail the whole operation if correction saving fails
                else:
                    st.warning("Failed to save template data to database")
            else:
                st.error("No machine ID available, template data not saved to database")

            return True

    except Exception as e:
        st.session_state.error_message = f"Document generation error: {e}"
        traceback.print_exc()
        st.error(f"Detailed error: {traceback.format_exc()}")
        return False


def process_machine_specific_data(machine_data):
    """
    Backward-compatible wrapper for direct processing without preview.
    Used by CRM Management and other non-quote-processing flows.

    Combines LLM extraction and document generation into a single operation.

    Args:
        machine_data: Dictionary containing machine information

    Returns:
        bool: Success status
    """
    # Call the two-step process: extraction then generation
    if run_llm_extraction_only(machine_data):
        return generate_and_save_document()
    return False


def load_crm_data(): st.session_state.all_crm_clients = load_all_clients(); st.session_state.crm_data_loaded = True

def load_previous_document(client_id):
    try:
        current_run_key = st.session_state.run_key 
        st.session_state.run_key = current_run_key
        
        client_data_db = get_client_by_id(client_id)
        if not client_data_db: st.error(f"Client ID {client_id} not found."); return False
        quote_ref = client_data_db.get("quote_ref")
        doc_content = load_document_content(quote_ref)
        if not doc_content: st.error(f"Doc content for {quote_ref} not found."); return False
        st.session_state.full_pdf_text = doc_content.get("full_pdf_text", "")
        priced_items = load_priced_items_for_quote(quote_ref)
        st.session_state.selected_pdf_items_structured = priced_items
        st.session_state.items_for_confirmation = priced_items
        st.session_state.selected_pdf_descs = [item.get("description","") for item in priced_items if item.get("description")]
        
        machines_data_from_db = load_machines_for_quote(quote_ref)
        
        # This section is simplified as contexts are now loaded on-demand per machine.
        # We just need to load the machine data.
        
        if machines_data_from_db:
            app_machines_list = []
            app_common_items = [] 
            # The structure seems to be a list of machine records, each potentially having 'machine_data'
            # Let's assume common items might be in the first record's machine_data if structured that way,
            # or handle it more generally if needed.
            # For simplicity, if machine_data is a string (JSON), parse it.
            for machine_record in machines_data_from_db:
                machine_data_content = machine_record.get("machine_data")
                if isinstance(machine_data_content, str):
                    try:
                        machine_data_content = json.loads(machine_data_content)
                    except json.JSONDecodeError:
                        st.warning(f"Could not parse machine_data JSON for machine {machine_record.get('machine_name')}")
                        machine_data_content = {} # empty dict as fallback
                
                # Add machine_name and id from the parent record into the machine_data_content if not present
                # This makes the structure consistent with what process_machine_specific_data might expect
                if "machine_name" not in machine_data_content: machine_data_content["machine_name"] = machine_record.get("machine_name")
                if "id" not in machine_data_content: machine_data_content["id"] = machine_record.get("id")


                app_machines_list.append(machine_data_content) # Add the (parsed) machine_data content
                
                # Consolidate common items from all machine records if they exist there
                # This assumes common_items might be duplicated or spread; better to aggregate.
                if isinstance(machine_data_content, dict) and "common_items" in machine_data_content:
                    app_common_items.extend(machine_data_content["common_items"])

            # Deduplicate common items
            # To handle list of dicts, we need a more robust deduplication
            unique_common_items = []
            seen_common_item_descs = set()
            for item in app_common_items:
                desc = item.get("description")
                if desc not in seen_common_item_descs:
                    unique_common_items.append(item)
                    seen_common_item_descs.add(desc)
            
            st.session_state.identified_machines_data = {"machines": app_machines_list, "common_items": unique_common_items}
        
        st.session_state.processing_done = True
        st.session_state.machine_confirmation_done = True
        st.session_state.common_options_confirmation_done = True
        st.session_state.processing_step = 3  # Skip directly to machine processing step
        
        st.info(f"Loaded previous quote {quote_ref}. Please select a machine to process.")
        
        return True
    except Exception as e: st.error(f"Error loading previous GOA doc: {e}"); traceback.print_exc(); return False

def get_current_context():
    if st.session_state.current_page == "Welcome": return ("general", None)
    elif st.session_state.current_page == "Quote Processing" and st.session_state.full_pdf_text:
        return ("quote", {"full_pdf_text": st.session_state.full_pdf_text, "selected_pdf_descs": st.session_state.selected_pdf_descs, "template_contexts": st.session_state.template_contexts})
    elif st.session_state.current_page == "Chat" and "chat_context" in st.session_state and st.session_state.chat_context:
        # Add context handling for Chat page
        chat_ctx = st.session_state.chat_context
        return ("quote", {
            "full_pdf_text": chat_ctx.get("full_pdf_text", ""),
            "selected_pdf_descs": [], # Could be empty as we're focusing on full text search
            "template_contexts": {}   # Not needed for simple PDF chat
        })
    elif st.session_state.selected_client_for_detail_edit:
        return ("client", st.session_state.selected_client_for_detail_edit)
    elif st.session_state.current_page == "CRM Management": return ("crm", None)
    return ("general", None)

def get_contexts_for_machine(machine_record: Dict[str, Any]) -> Tuple[Dict[str, Any], str, bool]:
    """
    Loads and returns the correct template contexts, file path, and a boolean indicating
    if it's a SortStar machine.
    """
    machine_name_lower = machine_record.get("machine_name", "").lower()
    
    # Determine which configuration to use
    config_key = "default"
    sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
    if re.search(sortstar_pattern, machine_name_lower):
        config_key = "sortstar"
        
    config = TEMPLATE_CONFIGS[config_key]
    
    active_template_file = config["template_file"]
    contexts = {}
    
    # Check existence of source based on config type
    source_exists = False
    if config_key == "default":
        # For default, source is the Excel file
        source_exists = os.path.exists(os.path.join("templates", "GOA_template.xlsx"))
    else:
        # For others (SortStar), source is the docx template
        source_exists = os.path.exists(active_template_file)

    if source_exists:
        try:
            if config_key == "default":
                # For default GOA, extract schema from Excel source of truth
                print("Extracting schema from Excel for default config")
                contexts = extract_schema_from_excel()
            else:
                # Use the unified function from template_utils
                # The schema extraction is more robust and suitable for both types
                contexts = template_utils.extract_placeholder_schema(
                    template_path=active_template_file,
                    explicit_mappings=config["explicit_mappings"],
                    is_sortstar=config["is_sortstar"]
                )

            if not contexts:
                st.warning(f"Could not extract any contexts from {active_template_file}. Trying hierarchical extraction as fallback.")
                # Fallback to hierarchical context extraction if schema fails
                contexts = template_utils.extract_placeholder_context_hierarchical(
                    template_path=active_template_file,
                    explicit_placeholder_mappings=config["explicit_mappings"],
                    enhance_with_outline=os.path.exists(config["outline_file"]),
                    outline_path=config["outline_file"],
                    is_sortstar=config["is_sortstar"]
                )

            if not contexts:
                st.error(f"All context extraction methods failed for {active_template_file}. Falling back to basic placeholders.")
                all_placeholders = template_utils.extract_placeholders(active_template_file)
                contexts = {ph: ph for ph in all_placeholders}
            
            print(f"Loaded contexts for {machine_record.get('machine_name')} using '{config_key}' config ({len(contexts)} fields).")

        except Exception as e:
            st.error(f"Error extracting template schema/context for {config_key}: {e}")
            traceback.print_exc()
            contexts = {} # Final fallback on error
    else:
        st.warning(f"Template file {active_template_file} not found for '{config_key}' config.")
        contexts = {}

    return contexts, active_template_file, config["is_sortstar"]

def process_chat_query(query, context_type, context_data=None):
    if not query: return "Please enter a question."
    if context_type == "quote" and context_data:
        # For chat page context, let's try to enrich the context with selected PDF descriptions
        # from the action_profile if available
        selected_pdf_descs = context_data.get("selected_pdf_descs", [])
        
        # If we don't have any selected descriptions but we have action_profile, get them from there
        if not selected_pdf_descs and "action_profile" in st.session_state and st.session_state.action_profile:
            profile_data = st.session_state.action_profile
            
            # Get machine descriptions
            machines = profile_data.get("machines_data", {}).get("machines", [])
            if machines:
                for machine in machines:
                    main_item = machine.get("main_item", {})
                    if main_item and "description" in main_item:
                        selected_pdf_descs.append(f"Machine {machine.get('machine_name', 'Unknown')}: {main_item.get('description', '')}")
                    
                    # Add first few add-ons for context
                    add_ons = machine.get("add_ons", [])
                    if add_ons:
                        for i, addon in enumerate(add_ons[:3]):
                            if "description" in addon:
                                selected_pdf_descs.append(f"Add-on for {machine.get('machine_name', 'Unknown')}: {addon.get('description', '')}")
            
            # Get line item descriptions if we still don't have enough context
            if len(selected_pdf_descs) < 5:
                line_items = profile_data.get("line_items", [])
                for item in line_items[:10]:
                    if "description" in item and item.get("description") not in selected_pdf_descs:
                        selected_pdf_descs.append(item.get("description", ""))
        
        # Call answer_pdf_question with the enriched context
        return answer_pdf_question(
            query, 
            selected_pdf_descs, 
            context_data.get("full_pdf_text", ""), 
            context_data.get("template_contexts", {})
        )
    elif context_type == "client" and context_data:
        quote_ref = context_data.get('quote_ref')
        if quote_ref:
            doc_content = load_document_content(quote_ref)
            if doc_content and doc_content.get("full_pdf_text"): 
                return answer_pdf_question(query, [], doc_content.get("full_pdf_text", ""), {})
        return f"I can help with client {context_data.get('customer_name', '')}, but detailed quote info might not be loaded for this chat."
    if "what can you do" in query.lower(): return "I can help process quotes, generate documents, and manage client data."
    return "I'm not sure how to answer that. Try asking about a specific quote or client if one is active."

# --- Main App Flow ---
def main():
    st.set_page_config(layout="wide", page_title="QuoteFlow Document Assistant")
    initialize_session_state()
    init_db() 
    if not st.session_state.crm_data_loaded: load_crm_data()
    
    if st.session_state.error_message: st.error(st.session_state.error_message); st.session_state.error_message = ""

    st.sidebar.title("Navigation")
    page_options = ["Client Dashboard", "Quote Processing", "CRM Management", "Machine Build Reports", "Chat"]
    
    # Set default page to Client Dashboard
    if st.session_state.current_page == "Welcome":
        st.session_state.current_page = "Client Dashboard"
    
    default_page_index = 0
    try: 
        default_page_index = page_options.index(st.session_state.current_page)
    except ValueError: 
        st.session_state.current_page = "Client Dashboard"
        default_page_index = 0
    
    selected_page = st.sidebar.radio("Go to", page_options, index=default_page_index, key="nav_radio")
    
    if selected_page != st.session_state.current_page:
        st.session_state.current_page = selected_page
        if selected_page == "Quote Processing": st.session_state.processing_step = 0
        if selected_page not in ["Client Dashboard"] and st.session_state.get("profile_extraction_step") is not None:
            if not (st.session_state.current_page == "Client Dashboard" and st.session_state.get("confirmed_profile")):
                st.session_state.profile_extraction_step = None; st.session_state.confirmed_profile = None; st.session_state.extracted_profile = None
        st.rerun()

    if st.session_state.current_page == "Client Dashboard": 
        show_client_dashboard_page()
    elif st.session_state.current_page == "Quote Processing": 
        show_quote_processing()
    elif st.session_state.current_page == "CRM Management": 
        show_crm_management_page()
    elif st.session_state.current_page == "Machine Build Reports":
        show_template_report_page()
    elif st.session_state.current_page == "Chat": 
        show_chat_page()

if __name__ == "__main__":
    main()
