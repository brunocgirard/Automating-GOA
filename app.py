import streamlit as st
import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
import traceback
import shutil

# Import from new modules
from src.ui.ui_pages import (
    show_welcome_page, show_client_dashboard_page, show_quote_processing, 
    show_crm_management_page, show_chat_page, render_chat_ui
)
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection, 
    handle_selected_action, load_full_client_profile
)

# Import from existing utility modules
from src.utils.pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical, extract_placeholder_schema
from src.utils.llm_handler import configure_gemini_client, get_machine_specific_fields_via_llm, answer_pdf_question
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.crm_utils import (
    init_db, save_client_info, load_all_clients, get_client_by_id, 
    update_client_record, save_priced_items, load_priced_items_for_quote, 
    update_single_priced_item, delete_client_record, save_machines_data, 
    load_machines_for_quote, save_machine_template_data, load_machine_template_data, 
    save_document_content, load_document_content
)

# Define Template File Constants
TEMPLATE_FILE = os.path.join("templates", "template.docx")

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

def quick_extract_and_catalog(uploaded_pdf_file):
    temp_pdf_path = None
    try:
        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf_file.getbuffer())
        progress_placeholder = st.empty(); progress_placeholder.info("Extracting & Cataloging...")
        items = extract_line_item_details(temp_pdf_path)
        full_text = extract_full_pdf_text(temp_pdf_path)
        if not items: st.warning("No items extracted."); return None
        quote_ref = uploaded_pdf_file.name.split('.')[0]
        client_info = {"quote_ref": quote_ref, "customer_name": "", "machine_model": "", "country_destination": "", "sold_to_address": "", "ship_to_address": "", "telephone": "", "customer_contact_person": "", "customer_po": ""}
        if save_client_info(client_info):
            progress_placeholder.info(f"Client record for {quote_ref} created.")
            if save_priced_items(quote_ref, items): progress_placeholder.info(f"Saved {len(items)} items.")
            else: st.warning(f"Failed to save priced items for {quote_ref}.")
            if full_text and save_document_content(quote_ref, full_text, uploaded_pdf_file.name): progress_placeholder.info("Doc content saved.")
            else: st.warning("Failed to save doc content.")
            
            machine_data = identify_machines_from_items(items)
            if save_machines_data(quote_ref, machine_data): progress_placeholder.info("Machine grouping saved.")
            else: st.warning("Failed to save machine grouping.")

            progress_placeholder.success("Cataloging Complete!")
            load_crm_data()
            return {"quote_ref": quote_ref, "items": items}
        else: st.error(f"Failed to create client record for {quote_ref}."); return None
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
            for i, item in enumerate(st.session_state.selected_pdf_items_structured):
                if any(m.get("main_item") == item for m in initial_machine_data.get("machines", [])): preselected_machines.append(i)
                elif any(ci == item for ci in initial_machine_data.get("common_items", [])): preselected_common.append(i)
            st.session_state.selected_main_machines = preselected_machines
            st.session_state.selected_common_options = preselected_common
            st.session_state.selected_pdf_descs = [item.get("description","") for item in st.session_state.selected_pdf_items_structured if item.get("description")]
            if not st.session_state.selected_pdf_descs: st.warning("No descriptions extracted for LLM.")
            if not st.session_state.full_pdf_text: st.warning("Full PDF text extraction failed.")

            st.write("Analyzing GOA template...")
            # First get a list of all placeholders
            all_placeholders = extract_placeholders(template_file_path)
            if not all_placeholders: 
                st.error("No placeholders found in template.")
                return False
                
            # Try to extract the schema
            st.write("Extracting template schema...")
            try:
                st.session_state.template_contexts = extract_placeholder_schema(template_file_path)
                
                # Add diagnostic information
                using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), ""), dict)
                st.write(f"Using {'schema' if using_schema_format else 'legacy'} format with {len(st.session_state.template_contexts)} fields")
                
                # If schema extraction fails, try legacy format
                if not st.session_state.template_contexts:
                    st.warning("Schema extraction failed, trying legacy format")
                    st.session_state.template_contexts = extract_placeholder_context_hierarchical(template_file_path)
                    if not st.session_state.template_contexts:
                        st.error("Could not extract template contexts using either method.")
                        return False
            except Exception as e:
                st.error(f"Error extracting template schema: {e}")
                # Try legacy format
                st.warning("Falling back to legacy format due to error")
                st.session_state.template_contexts = extract_placeholder_context_hierarchical(template_file_path)
                if not st.session_state.template_contexts:
                    st.error("Could not extract template contexts using legacy method.")
                    return False
            
            # Create initial blank data dictionary based on schema type
            using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), ""), dict)
            if using_schema_format:
                initial_data_dict = {
                    key: ("NO" if schema_info.get("type") == "boolean" else "") 
                    for key, schema_info in st.session_state.template_contexts.items()
                }
            else:
                initial_data_dict = {ph: ("NO" if ph.endswith("_check") else "") for ph in all_placeholders}
                
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
            client_info_payload = {"quote_ref": uploaded_pdf_file.name.split('.')[0], "customer_name": "", "machine_model": "", "country_destination": "", "sold_to_address": "", "ship_to_address": "", "telephone": "", "customer_contact_person": "", "customer_po": ""}
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
        common_items = machine_data.get("common_items", [])
        if not common_items and st.session_state.identified_machines_data:
             common_items = st.session_state.identified_machines_data.get("common_items", [])

        with st.spinner(f"Processing machine for GOA: {machine_data.get('machine_name')}..."):
            # Check if template_contexts are valid before proceeding
            if not st.session_state.template_contexts:
                st.warning("Template contexts not found. Regenerating from template.")
                try:
                    # Try with the new schema format first
                    st.session_state.template_contexts = extract_placeholder_schema(template_file_path)
                    if not st.session_state.template_contexts:
                        # Fall back to legacy format if schema extraction fails
                        st.warning("Schema extraction failed, trying legacy format")
                        st.session_state.template_contexts = extract_placeholder_context_hierarchical(template_file_path)
                        if not st.session_state.template_contexts:
                            st.error("Could not extract template contexts using either method.")
                            return False
                except Exception as e:
                    st.error(f"Error extracting template contexts: {e}")
                    return False
            
            # Add diagnostic information
            using_schema_format = isinstance(next(iter(st.session_state.template_contexts.values()), ""), dict)
            st.info(f"Using {'schema' if using_schema_format else 'legacy'} format with {len(st.session_state.template_contexts)} fields")
            
            machine_filled_data = get_machine_specific_fields_via_llm(machine_data, common_items, st.session_state.template_contexts, st.session_state.full_pdf_text)
            st.session_state.machine_specific_filled_data = machine_filled_data
            machine_specific_output_path = f"output_{machine_data.get('machine_name', 'machine').replace(' ', '_')}_GOA.docx"
            
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
            if "id" in machine_data:
                save_machine_template_data(machine_data["id"], "GOA", machine_filled_data, machine_specific_output_path)
            return True
    except Exception as e: st.session_state.error_message = f"Machine GOA processing error: {e}"; traceback.print_exc(); return False

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
        if machines_data_from_db:
            app_machines_list = []
            app_common_items = [] 
            if machines_data_from_db[0].get("machine_data"): 
                app_common_items = machines_data_from_db[0].get("machine_data",{}).get("common_items", [])
            for machine_record in machines_data_from_db:
                app_machines_list.append(machine_record.get("machine_data", {}))
            st.session_state.identified_machines_data = {"machines": app_machines_list, "common_items": app_common_items}
        
        st.session_state.processing_done = True
        st.session_state.machine_confirmation_done = True
        st.session_state.common_options_confirmation_done = True
        st.session_state.processing_step = 3  # Skip directly to machine processing step
        
        # Always regenerate the template contexts when loading an existing document
        if os.path.exists(TEMPLATE_FILE):
            try:
                # First try with the new schema format
                st.session_state.template_contexts = extract_placeholder_schema(TEMPLATE_FILE)
                
                # Add debug message
                st.info(f"Template schema loaded with {len(st.session_state.template_contexts)} fields. Using new format: {isinstance(next(iter(st.session_state.template_contexts.values()), ''), dict)}")
                
                # If no fields were found or another issue occurred, try the legacy format
                if not st.session_state.template_contexts:
                    st.warning("Could not extract template schema, falling back to legacy format.")
                    st.session_state.template_contexts = extract_placeholder_context_hierarchical(TEMPLATE_FILE)
            except Exception as e:
                st.error(f"Error extracting template schema: {e}")
                # Fall back to legacy format
                st.session_state.template_contexts = extract_placeholder_context_hierarchical(TEMPLATE_FILE)
                st.info(f"Using legacy format: {len(st.session_state.template_contexts)} fields found")
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
    page_options = ["Client Dashboard", "Quote Processing", "CRM Management", "Chat"]
    
    # Set default page to Client Dashboard
    if st.session_state.current_page == "Welcome":
        st.session_state.current_page = "Client Dashboard"
    
    default_page_index = 0
    try: 
        default_page_index = page_options.index(st.session_state.current_page)
    except ValueError: 
        st.session_state.current_page = "Client Dashboard"
    
    selected_page = st.sidebar.radio("Go to", page_options, index=default_page_index, key="nav_radio")
    if selected_page != st.session_state.current_page:
        st.session_state.current_page = selected_page
        if selected_page == "Quote Processing": st.session_state.processing_step = 0
        if selected_page not in ["Client Dashboard"] and st.session_state.get("profile_extraction_step") is not None:
            if not (st.session_state.current_page == "Client Dashboard" and st.session_state.get("confirmed_profile")):
                st.session_state.profile_extraction_step = None; st.session_state.confirmed_profile = None; st.session_state.extracted_profile = None
        st.rerun()

    render_chat_ui()

    if st.session_state.current_page == "Client Dashboard": 
        show_client_dashboard_page()
    elif st.session_state.current_page == "Quote Processing": 
        show_quote_processing()
    elif st.session_state.current_page == "CRM Management": 
        show_crm_management_page()
    elif st.session_state.current_page == "Chat": 
        show_chat_page()

if __name__ == "__main__":
    main()
