import streamlit as st
import os
import json
import pandas as pd
import re
from typing import Dict, List, Optional, Any
import traceback
import shutil
from datetime import datetime

# Import from new modules
from src.ui.ui_pages import (
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
from src.utils import sortstar_template_utils
from src.utils.llm_handler import configure_gemini_client, get_machine_specific_fields_via_llm, answer_pdf_question
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.crm_utils import (
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
        'processing_step' 
    ]
    goa_defaults = {
        'full_pdf_text': "", 'processing_done': False, 'selected_pdf_descs': [], 'template_contexts': {},
        'llm_initial_filled_data': {}, 'llm_corrected_filled_data': {}, 
        'initial_docx_path': f"output_llm_initial_run{st.session_state.get('run_key',0)}.docx",
        'corrected_docx_path': f"output_llm_corrected_run{st.session_state.get('run_key',0)}.docx",
        'error_message': "", 'chat_log': [], 'correction_applied': False,
        'identified_machines_data': {}, 'selected_machine_index': 0, 'machine_specific_filled_data': {},
        'machine_docx_path': f"output_machine_specific_run{st.session_state.get('run_key',0)}.docx",
        'selected_machine_id': None, 'machine_confirmation_done': False,
        'common_options_confirmation_done': False, 'items_for_confirmation': [],
        'selected_main_machines': [], 'selected_common_options': [],
        'manual_machine_grouping': {},
        'processing_step': 0 
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
        'machine_docx_path': f"output_machine_specific_run{st.session_state.run_key}.docx",
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
            preselected_machines, preselected_common = [], []
            
            # Determine if any machine is a SortStar for template selection
            is_sortstar_machine_present = False
            sortstar_aliases = ["sortstar", "unscrambler", "bottle unscrambler"] # Added "bottle unscrambler"
            if initial_machine_data.get("machines"):
                for machine_info in initial_machine_data["machines"]:
                    machine_name_lower = machine_info.get("machine_name", "").lower()
                    if any(alias in machine_name_lower for alias in sortstar_aliases):
                        is_sortstar_machine_present = True
                        st.write(f"SortStar/Unscrambler machine identified: {machine_info.get('machine_name')}. Using SortStar template.")
                        template_file_path = SORTSTAR_TEMPLATE_FILE # Override template path
                        # Adjust output doc names for SortStar
                        st.session_state.initial_docx_path = f"output_sortstar_initial_run{st.session_state.run_key}.docx"
                        st.session_state.corrected_docx_path = f"output_sortstar_corrected_run{st.session_state.run_key}.docx"
                        st.session_state.machine_docx_path = f"output_sortstar_specific_run{st.session_state.run_key}.docx"
                        break # Assuming one SortStar means all associated GOAs use SortStar template for this run
            
            # Choose utility functions based on template
            current_template_utils = sortstar_template_utils if is_sortstar_machine_present else template_utils
            
            for i, item in enumerate(st.session_state.selected_pdf_items_structured):
                if any(m.get("main_item") == item for m in initial_machine_data.get("machines", [])): preselected_machines.append(i)
                elif any(ci == item for ci in initial_machine_data.get("common_items", [])): preselected_common.append(i)
            st.session_state.selected_main_machines = preselected_machines
            st.session_state.selected_common_options = preselected_common
            st.session_state.selected_pdf_descs = [item.get("description","") for item in st.session_state.selected_pdf_items_structured if item.get("description")]
            if not st.session_state.selected_pdf_descs: st.warning("No descriptions extracted for LLM.")
            if not st.session_state.full_pdf_text: st.warning("Full PDF text extraction failed.")

            st.write(f"Analyzing GOA template: {template_file_path}...")
            all_placeholders = current_template_utils.extract_placeholders(template_file_path)
            if not all_placeholders: 
                st.error(f"No placeholders found in template: {template_file_path}")
                return False
                
            st.write("Extracting template schema/context...")
            try:
                outline_filename = "sortstar_fields_outline.md" if is_sortstar_machine_present else "full_fields_outline.md"
                outline_path = outline_filename # Assuming it's in the root, adjust if it's in src/utils or templates
                
                if is_sortstar_machine_present:
                     # For SortStar, hierarchical context might be more direct initially if schema/outline is simpler
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                        template_file_path,
                        enhance_with_outline=os.path.exists(outline_path), # Only enhance if outline exists
                        outline_path=outline_path
                    )
                    if not st.session_state.template_contexts : # Fallback to schema if context is empty
                         st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)

                elif os.path.exists(outline_path): # For general template with outline
                    st.write(f"Using enhanced context extraction with outline file: {outline_path}")
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                        template_file_path, 
                        enhance_with_outline=True,
                        outline_path=outline_path
                    )
                    if not st.session_state.template_contexts: # Fallback if hierarchical fails
                         st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)
                else: # General template without outline
                    st.info(f"Outline file '{outline_path}' not found, using standard schema extraction for {template_file_path}")
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)
                
                if not st.session_state.template_contexts:
                    st.error(f"Could not extract template contexts from {template_file_path} using available methods.")
                    return False

                using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), {}), dict)
                st.write(f"Template context/schema extracted. Using {'schema' if using_schema_format else 'hierarchical context'} format with {len(st.session_state.template_contexts)} fields for {template_file_path}")

            except Exception as e:
                st.error(f"Error extracting template schema/context: {e}")
                st.warning("Falling back to basic placeholder list due to error.")
                st.session_state.template_contexts = {ph: ph for ph in all_placeholders} # Basic fallback
            
            using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), {}), dict)
            if using_schema_format:
                initial_data_dict = {
                    key: ("NO" if schema_info.get("type") == "boolean" else "") 
                    for key, schema_info in st.session_state.template_contexts.items()
                }
            else: # Hierarchical context (dict of str:str) or basic fallback (dict of str:str)
                initial_data_dict = {ph: ("NO" if ph.endswith("_check") else "") for ph in st.session_state.template_contexts.keys()}
                
            st.session_state.llm_initial_filled_data = initial_data_dict.copy()
            st.session_state.llm_corrected_filled_data = initial_data_dict.copy()
            st.write(f"Creating initial blank GOA template: {st.session_state.initial_docx_path}...")
            
            # Add diagnostic information about the data being used for initial template
            with st.expander("Preview of template data", expanded=False):
                # Take first 5 fields to show as example
                sample_data = {k: v for i, (k, v) in enumerate(initial_data_dict.items()) if i < 5}
                st.write(sample_data)
                st.write(f"Total fields: {len(initial_data_dict)}")
            
            fill_word_document_from_llm_data(template_file_path, initial_data_dict, st.session_state.initial_docx_path)
            if os.path.exists(st.session_state.initial_docx_path): 
                shutil.copy(st.session_state.initial_docx_path, st.session_state.corrected_docx_path)
                st.success(f"Initial template created successfully: {st.session_state.initial_docx_path}")
            else: 
                st.error(f"Initial GOA doc {st.session_state.initial_docx_path} not created.")
                return False
            
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

def process_machine_specific_data(machine_data, template_file_path):
    try:
        if not configure_gemini_client(): st.session_state.error_message = "LLM client config failed."; return False
        
        st.info(f"Processing machine: {machine_data.get('machine_name', 'Unknown')}")
        if "id" in machine_data:
            st.info(f"Machine already has ID: {machine_data['id']}")
        
        common_items = machine_data.get("common_items", [])
        if not common_items and st.session_state.identified_machines_data:
             common_items = st.session_state.identified_machines_data.get("common_items", [])

        # Determine if this is a SortStar machine for template/utils selection
        is_sortstar_machine = False
        sortstar_aliases = ["sortstar", "unscrambler", "bottle unscrambler"] # Added "bottle unscrambler"
        machine_name_lower = machine_data.get("machine_name", "").lower()
        if any(alias in machine_name_lower for alias in sortstar_aliases):
            is_sortstar_machine = True
            template_file_path = SORTSTAR_TEMPLATE_FILE # Override template
            st.info(f"Identified as SortStar/Unscrambler. Using template: {template_file_path}")
        
        current_template_utils = sortstar_template_utils if is_sortstar_machine else template_utils
        # Ensure the correct template_file_path is used if not overridden (e.g. called from resume)
        if not is_sortstar_machine and template_file_path != TEMPLATE_FILE : # Check if it was default
             template_file_path = TEMPLATE_FILE # Default if not sortstar

        with st.spinner(f"Processing machine for GOA: {machine_data.get('machine_name')} using {template_file_path}..."):
            if not st.session_state.template_contexts or \
               (is_sortstar_machine and not any("SortStar" in str(v) for v in st.session_state.template_contexts.values())) or \
               (not is_sortstar_machine and any("SortStar" in str(v) for v in st.session_state.template_contexts.values())): # Crude check if context matches machine type
                st.warning(f"Template contexts might be incorrect for {'SortStar' if is_sortstar_machine else 'general'} machine or not found. Regenerating from: {template_file_path}")
                try:
                    outline_filename = "sortstar_fields_outline.md" if is_sortstar_machine else "full_fields_outline.md"
                    outline_path = outline_filename # adjust if needed

                    if is_sortstar_machine:
                        st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                            template_file_path,
                            enhance_with_outline=os.path.exists(outline_path),
                            outline_path=outline_path
                        )
                        if not st.session_state.template_contexts: # Fallback
                             st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)
                    elif os.path.exists(outline_path):
                        st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                            template_file_path, enhance_with_outline=True, outline_path=outline_path
                        )
                        if not st.session_state.template_contexts: # Fallback
                             st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)
                    else:
                        st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(template_file_path)

                    if not st.session_state.template_contexts:
                        st.error(f"Could not extract template contexts from {template_file_path}")
                        return False
                except Exception as e:
                    st.error(f"Error re-extracting template contexts for {template_file_path}: {e}")
                    return False
            
            using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), {}), dict)
            st.info(f"Using {'schema' if using_schema_format else 'hierarchical context'} format with {len(st.session_state.template_contexts)} fields for {template_file_path}")
            
            machine_filled_data = get_machine_specific_fields_via_llm(machine_data, common_items, st.session_state.template_contexts, st.session_state.full_pdf_text)
            st.session_state.machine_specific_filled_data = machine_filled_data

            machine_name = machine_data.get('machine_name', 'machine')
            clean_name = re.sub(r'[\\/*?মুখের<>|]', "_", machine_name.replace(' ', '_')) # Sanitize name more robustly
            
            # Generate options_listing for both regular and SortStar machines using the same logic
            selected_details = []
            
            # First, include actual add-ons from the PDF for both template types
            # This is what's shown in the regular template in the picture
            if machine_data and "add_ons" in machine_data and machine_data["add_ons"]:
                for i, addon in enumerate(machine_data["add_ons"], 1):
                    if "description" in addon and addon["description"]:
                        # Format description nicely
                        desc_lines = addon["description"].split('\n')
                        main_desc = desc_lines[0] if desc_lines else addon["description"]
                        selected_details.append(f"- Add-on {i}: {main_desc}")
            
            # If no add-ons were found, fall back to template fields (original behavior)
            if not selected_details and st.session_state.template_contexts and st.session_state.machine_specific_filled_data:
                using_schema_format_local = isinstance(next(iter(st.session_state.template_contexts.values()), {}), dict)
                for field_key, context_info in st.session_state.template_contexts.items():
                    if field_key == "options_listing":
                        continue # Skip the options_listing field itself

                    field_value = st.session_state.machine_specific_filled_data.get(field_key, "")
                    is_checkbox_field = False
                    description = ""

                    if using_schema_format_local:
                        is_checkbox_field = context_info.get("type") == "boolean"
                        description = context_info.get("description", field_key)
                    else: # Hierarchical context (dict of str:str) or basic fallback
                        is_checkbox_field = field_key.endswith("_check")
                        description = str(context_info) # context_info is the description string
                        
                        # Special handling for SortStar hierarchical paths
                        if is_sortstar_machine and ">" in description:
                            # Extract the most specific part of the description (last part after ">")
                            parts = [p.strip() for p in description.split(" > ")]
                            if len(parts) > 1:
                                description = parts[-1]  # Use only the most specific part
                    
                    # Skip fields with 'none' or similar values
                    if any(term in str(field_value).lower() for term in ["none", "not selected", "not specified"]):
                        continue
                        
                    # Skip if the description contains "none" or similar
                    if any(term in str(description).lower() for term in ["none", "not selected", "not specified"]):
                        continue

                    # Include selected items
                    if is_checkbox_field and str(field_value).upper() == "YES":
                        selected_details.append(f"• {description}")
                    elif not is_checkbox_field and field_value and field_key not in ["customer", "machine", "quote", "options_listing"]:
                        # Only add non-checkbox fields if they have meaningful content
                        if isinstance(field_value, str) and field_value.strip() and field_value.lower() not in ["no", "false", "0"]:
                            selected_details.append(f"• {description}: {field_value}")
            
            if selected_details:
                st.session_state.machine_specific_filled_data["options_listing"] = "Selected Options and Specifications:\n" + "\n".join(selected_details)
            else:
                st.session_state.machine_specific_filled_data["options_listing"] = "No options or specifications selected for this machine."
            
            # Set the output path based on machine type
            if is_sortstar_machine:
                machine_specific_output_path = f"output_SORTSTAR_{clean_name}_GOA.docx"
            else:
                machine_specific_output_path = f"output_{clean_name}_GOA.docx"
            
            # Check that we have data before filling
            if not machine_filled_data:
                st.error("No data received from LLM to fill the template.")
                return False
                
            # Show sample of the data for debugging
            with st.expander("Preview of data from LLM", expanded=False):
                # Take first 5 fields to show as example
                sample_data = {k: v for i, (k, v) in enumerate(machine_filled_data.items()) if i < 5}
                st.write(sample_data)
                st.write(f"Total fields: {len(machine_filled_data)}")
            
            fill_word_document_from_llm_data(template_file_path, machine_filled_data, machine_specific_output_path)
            
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
                        machine_name = machine_data.get("machine_name", "")
                        if machine_name:
                            # Sanitize machine name to use as quote_ref
                            quote_ref = re.sub(r'[^A-Za-z0-9-]', '_', machine_name)
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
                machine_name = machine_data.get("machine_name", "")
                matching_machines = find_machines_by_name(machine_name)
                
                if matching_machines:
                    st.success(f"Found {len(matching_machines)} existing machine(s) with name '{machine_name}'")
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
                    matching_machine = next((m for m in machines_from_db if m["machine_name"] == machine_name), None)
                    
                    if matching_machine:
                        machine_id = matching_machine["id"]
                        st.success(f"Found existing machine ID: {machine_id}")
                    else:
                        # Need to create a new machine record
                        st.info(f"Creating new machine record for {machine_name} with quote_ref: {quote_ref}")
                        
                        # Make sure machine_data has client_quote_ref
                        machine_data_copy = machine_data.copy()
                        machine_data_copy["client_quote_ref"] = quote_ref
                        
                        machine_group = {"machines": [machine_data_copy], "common_items": common_items}
                        
                        if save_machines_data(quote_ref, machine_group):
                            # Get the newly created machine ID
                            machines_from_db = load_machines_for_quote(quote_ref)
                            matching_machine = next((m for m in machines_from_db if m["machine_name"] == machine_name), None)
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
                from src.utils.crm_utils import save_machine_template_data
                st.info(f"Saving template data for machine ID: {machine_id}")
                if save_machine_template_data(machine_id, "GOA", machine_filled_data, machine_specific_output_path):
                    st.success(f"Saved GOA template data for machine ID: {machine_id}")
                    
                    # Store the machine ID in the session for future use
                    st.session_state.selected_machine_id = machine_id
                else:
                    st.warning("Failed to save template data to database")
            else:
                st.error("No machine ID available, template data not saved to database")
                
            return True
    except Exception as e: 
        st.session_state.error_message = f"Machine GOA processing error: {e}"
        traceback.print_exc()
        st.error(f"Detailed error: {traceback.format_exc()}")
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
        
        # Determine if SortStar machine is present to select correct template utils and path
        is_sortstar_machine_present = False
        current_template_file_path = TEMPLATE_FILE # Default
        if machines_data_from_db:
            for machine_record_outer in machines_data_from_db: # Iterate through list of machine records
                 # machine_record_outer itself is the dict like {'id': ..., 'client_quote_ref': ..., 'machine_name': ..., 'machine_data': ...}
                machine_name_lower = machine_record_outer.get("machine_name", "").lower()
                sortstar_aliases = ["sortstar", "unscrambler", "bottle unscrambler"] # Added "bottle unscrambler"
                if any(alias in machine_name_lower for alias in sortstar_aliases):
                    is_sortstar_machine_present = True
                    current_template_file_path = SORTSTAR_TEMPLATE_FILE
                    st.info(f"SortStar/Unscrambler machine detected ({machine_record_outer.get('machine_name')}) in loaded data. Using SortStar template utils.")
                    break
        
        current_template_utils = sortstar_template_utils if is_sortstar_machine_present else template_utils

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
        
        if os.path.exists(current_template_file_path):
            try:
                outline_filename = "sortstar_fields_outline.md" if is_sortstar_machine_present else "full_fields_outline.md"
                outline_path = outline_filename # adjust as needed

                if is_sortstar_machine_present:
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                        current_template_file_path,
                        enhance_with_outline=os.path.exists(outline_path),
                        outline_path=outline_path
                    )
                    if not st.session_state.template_contexts: # Fallback
                         st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(current_template_file_path)

                elif os.path.exists(outline_path):
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_context_hierarchical(
                        current_template_file_path, 
                        enhance_with_outline=True,
                        outline_path=outline_path
                    )
                    if not st.session_state.template_contexts: # Fallback
                         st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(current_template_file_path)
                else:
                    st.session_state.template_contexts = current_template_utils.extract_placeholder_schema(current_template_file_path)

                if not st.session_state.template_contexts:
                     st.warning(f"Could not extract template contexts from {current_template_file_path} on load_previous_document.")
                     # Basic fallback:
                     all_placeholders_fallback = current_template_utils.extract_placeholders(current_template_file_path)
                     st.session_state.template_contexts = {ph: ph for ph in all_placeholders_fallback}

                st.info(f"Template contexts loaded for {current_template_file_path} with {len(st.session_state.template_contexts)} fields.")
            except Exception as e:
                st.error(f"Error extracting template schema/context in load_previous_document: {e}")
                all_placeholders_fallback = current_template_utils.extract_placeholders(current_template_file_path)
                st.session_state.template_contexts = {ph: ph for ph in all_placeholders_fallback} # Basic fallback
                
        else:
            st.error(f"Template file {TEMPLATE_FILE} not found")
        
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

def get_contexts_for_machine(machine_record: Dict[str, Any]) -> Dict[str, Any]:
    """Loads and returns the correct template contexts for a given machine record."""
    machine_name_lower = machine_record.get("machine_name", "").lower()
    is_sortstar_machine = False
    sortstar_aliases = ["sortstar", "unscrambler", "bottle unscrambler"]
    if any(alias in machine_name_lower for alias in sortstar_aliases):
        is_sortstar_machine = True

    active_template_file = SORTSTAR_TEMPLATE_FILE if is_sortstar_machine else TEMPLATE_FILE
    active_template_utils = sortstar_template_utils if is_sortstar_machine else template_utils
    outline_filename = "sortstar_fields_outline.md" if is_sortstar_machine else "full_fields_outline.md"
    # Assuming outline_path is relative to the root or a known location, adjust if necessary.
    outline_path = outline_filename 

    contexts = {}
    if os.path.exists(active_template_file):
        try:
            if is_sortstar_machine:
                contexts = active_template_utils.extract_placeholder_context_hierarchical(
                    active_template_file,
                    enhance_with_outline=os.path.exists(outline_path),
                    outline_path=outline_path
                )
                if not contexts: # Fallback
                    contexts = active_template_utils.extract_placeholder_schema(active_template_file)
            elif os.path.exists(outline_path): # General template with outline
                contexts = active_template_utils.extract_placeholder_context_hierarchical(
                    active_template_file, 
                    enhance_with_outline=True,
                    outline_path=outline_path
                )
                if not contexts: # Fallback
                    contexts = active_template_utils.extract_placeholder_schema(active_template_file)
            else: # General template without outline
                contexts = active_template_utils.extract_placeholder_schema(active_template_file)
            
            if not contexts: # Ultimate fallback if all methods fail
                all_placeholders = active_template_utils.extract_placeholders(active_template_file)
                contexts = {ph: ph for ph in all_placeholders}
            
            print(f"Loaded contexts for {machine_record.get('machine_name')} using {active_template_file} ({len(contexts)} fields).")
        except Exception as e:
            st.error(f"Error loading template contexts for {machine_record.get('machine_name')} in get_contexts_for_machine: {e}")
            # Basic fallback in case of error
            try:
                all_placeholders = active_template_utils.extract_placeholders(active_template_file)
                contexts = {ph: ph for ph in all_placeholders}
            except: contexts = {} # Final fallback
    else:
        st.warning(f"Template file {active_template_file} not found for {machine_record.get('machine_name')}.")
        contexts = {}
    return contexts

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
