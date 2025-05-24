import streamlit as st
import os
import json
import pandas as pd # For st.dataframe
from typing import Dict, List
import traceback # For detailed error logging
import shutil # For copying files
import uuid
from datetime import datetime

# Import your existing utility functions
from pdf_utils import extract_line_item_details, extract_full_pdf_text, extract_text_from_pdf
from template_utils import extract_placeholders, extract_placeholder_context_hierarchical, identify_machine_groups
from llm_handler import configure_gemini_client, get_all_fields_via_llm, get_llm_chat_update, answer_pdf_question # Added answer_pdf_question
from doc_filler import fill_word_document_from_llm_data
from crm_utils import init_db, save_client_info, load_all_clients, get_client_by_id, update_client_record, save_priced_items, load_priced_items_for_quote, update_single_priced_item, delete_client_record

# --- App State Initialization (using st.session_state) ---
def initialize_session_state(is_new_processing_run=False):
    if is_new_processing_run or 'run_key' not in st.session_state: # Initialize/reset run_key on new processing
        st.session_state.run_key = st.session_state.get('run_key', 0) + (1 if is_new_processing_run else 0)

    # Initialize other states as before, ensuring they are reset if is_new_processing_run is True
    keys_to_reset = [
        'full_pdf_text', 'processing_done', 'selected_pdf_descs', 'template_contexts',
        'llm_initial_filled_data', 'llm_corrected_filled_data', 'initial_docx_path',
        'corrected_docx_path', 'error_message', 'chat_log', 'correction_applied',
        'all_crm_clients', 'editing_client_id'
    ]
    default_values = {
        'full_pdf_text': "", 'processing_done': False, 'selected_pdf_descs': [], 'template_contexts': {},
        'llm_initial_filled_data': {}, 'llm_corrected_filled_data': {}, 
        'initial_docx_path': f"output_llm_initial_run{st.session_state.run_key}.docx",
        'corrected_docx_path': f"output_llm_corrected_run{st.session_state.run_key}.docx",
        'error_message': "", 'chat_log': [], 'correction_applied': False,
        'all_crm_clients': [], 'editing_client_id': None
    }
    for key in keys_to_reset:
        if key not in st.session_state or is_new_processing_run:
            st.session_state[key] = default_values[key]

    if 'crm_data_loaded' not in st.session_state: # This one loads once unless refreshed
        st.session_state.crm_data_loaded = False
    if 'crm_form_data' not in st.session_state or is_new_processing_run: # Reset form on new run too
        st.session_state.crm_form_data = {
            'quote_ref': '', 'customer_name': '', 'machine_model': '', 'country_destination': '',
            'sold_to_address': '', 'ship_to_address': '', 'telephone': '', 
            'customer_contact_person': '', 'customer_po': ''
        }

    if 'current_priced_items_for_editing' not in st.session_state or is_new_processing_run:
        st.session_state.current_priced_items_for_editing = [] # Store original items for comparison
    if 'edited_priced_items_df' not in st.session_state or is_new_processing_run: # Store DataFrame from data_editor
        st.session_state.edited_priced_items_df = pd.DataFrame()

    if 'selected_client_for_detail_edit' not in st.session_state or is_new_processing_run:
        st.session_state.selected_client_for_detail_edit = None # Stores the dict of the client being edited
    if 'edited_client_details_df' not in st.session_state or is_new_processing_run:
        st.session_state.edited_client_details_df = pd.DataFrame() # For the client detail data_editor

    if 'confirming_delete_client_id' not in st.session_state or is_new_processing_run:
        st.session_state.confirming_delete_client_id = None # Store ID of client pending delete confirmation

initialize_session_state() # Call it once at the start
init_db() # Initialize CRM database at app startup

# --- Helper Functions for App --- 

def perform_initial_processing(uploaded_pdf_file, template_file_path):
    initialize_session_state(is_new_processing_run=True) # Reset state for a new run

    try:
        with st.spinner("Processing PDF..."):
            # Save uploaded file temporarily
            temp_pdf_path = save_uploaded_file(uploaded_pdf_file)
            if not temp_pdf_path:
                st.error("Failed to save uploaded file.")
                return

            # Extract text and tables
            st.session_state.full_pdf_text = extract_text_from_pdf(temp_pdf_path)
            st.session_state.selected_pdf_items_structured = extract_line_item_details(temp_pdf_path)
            
            # Get template contexts
            st.session_state.template_contexts = extract_placeholder_context_hierarchical(template_file_path)
            
            # Extract selected items descriptions for LLM
            st.session_state.selected_pdf_descs = [item["description"] for item in st.session_state.selected_pdf_items_structured]
            
            # Identify machine groups
            machine_groups = identify_machine_groups(st.session_state.selected_pdf_descs, st.session_state.full_pdf_text)
            st.session_state.machine_groups = machine_groups
            
            # Store machine names for selection
            st.session_state.available_machines = [name for name in machine_groups.keys() if name != "COMMON"]
            
            # Initialize data dictionary with defaults
            initial_data_dict = {key: ("NO" if key.endswith("_check") else "") for key in st.session_state.template_contexts.keys()}
            
            # Get initial LLM data for all machines
            llm_data_from_api = get_all_fields_via_llm(st.session_state.selected_pdf_descs, st.session_state.template_contexts, st.session_state.full_pdf_text)
            initial_data_dict.update(llm_data_from_api)
            st.session_state.llm_initial_filled_data = initial_data_dict.copy()
            st.session_state.llm_corrected_filled_data = initial_data_dict.copy()

            # Save to CRM with machine grouping
            status_bar.update(label="Saving to CRM...")
            client_info_payload = {
                "quote_ref": initial_data_dict.get("quote", uploaded_pdf_file.name),
                "customer_name": initial_data_dict.get("customer", ""),
                "machine_model": initial_data_dict.get("machine", ""),
                "country_destination": initial_data_dict.get("country", ""),
                "sold_to_address": initial_data_dict.get("sold_to_address", ""),
                "ship_to_address": initial_data_dict.get("ship_to_address", ""),
                "telephone": initial_data_dict.get("telephone", ""),
                "customer_contact_person": initial_data_dict.get("customer_contact_person", ""),
                "customer_po": initial_data_dict.get("customer_po", "")
            }

            if not client_info_payload["quote_ref"]:
                st.warning("Quote Reference is missing. CRM entry may be incomplete or fail if quote_ref is mandatory.")
            
            # Save main client info
            if save_client_info(client_info_payload):
                st.write(f"Main client info for '{client_info_payload['quote_ref']}' saved/updated.")
                
                # Save priced items with machine grouping
                if st.session_state.selected_pdf_items_structured:
                    # Add machine group and item type to each item
                    for item in st.session_state.selected_pdf_items_structured:
                        for machine_name, items in machine_groups.items():
                            for group_item in items:
                                if group_item["description"] == item["description"]:
                                    item["machine_group"] = machine_name
                                    item["item_type"] = group_item["type"]
                                    break
                    
                    if save_priced_items(client_info_payload['quote_ref'], st.session_state.selected_pdf_items_structured):
                        st.write(f"Priced items for '{client_info_payload['quote_ref']}' saved.")
                    else:
                        st.warning(f"Failed to save priced items for '{client_info_payload['quote_ref']}'.")
                else:
                    st.write(f"No structured selected items found to save as priced items for '{client_info_payload['quote_ref']}'.")
                
                load_crm_data()
            else: 
                st.warning(f"Failed to save main client info for quote '{client_info_payload['quote_ref']}'. Priced items not saved.")
            
            status_bar.update(label="Processing Complete!", state="complete", expanded=False)
        
        st.session_state.processing_done = True
    except Exception as e:
        st.session_state.error_message = f"Initial processing error: {e}"
        st.text(traceback.format_exc())
        if 'status_bar' in locals() and status_bar is not None:
            status_bar.update(label="Error!", state="error", expanded=True)
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

# --- Function to load CRM data --- 
def load_crm_data():
    """Load CRM data and update session state"""
    st.session_state.all_crm_clients = load_all_clients()
    st.session_state.crm_data_loaded = True

# --- Streamlit UI --- 
st.set_page_config(layout="wide", page_title="GOA LLM Assistant")
st.title("📄 GOA Document Assistant with LLM")

# Load CRM data once on first load if not already loaded
if not st.session_state.crm_data_loaded:
    load_crm_data()

# --- Sidebar for Upload ONLY ---
st.sidebar.header("📤 Upload Files")
TEMPLATE_FILE = "template.docx"
if not os.path.exists(TEMPLATE_FILE): st.sidebar.error(f"Template '{TEMPLATE_FILE}' not found."); st.stop()
uploaded_pdf = st.sidebar.file_uploader("Choose PDF", type="pdf", key=f"pdf_uploader_{st.session_state.run_key}")

if uploaded_pdf:
    st.sidebar.markdown(f"**Uploaded:** `{uploaded_pdf.name}`")
    if st.sidebar.button("🚀 Process Document", type="primary", key=f"process_btn_{st.session_state.run_key}"):
        perform_initial_processing(uploaded_pdf, TEMPLATE_FILE)
# --- End Sidebar Upload ---

if st.session_state.error_message: st.error(st.session_state.error_message)

# --- Main Page Tabs ---
tab_processor, tab_crm_management = st.tabs(["📄 Document Processor", "📒 CRM Management"])

with tab_processor:
    st.header("📝 Document Processing & Chat")
    if st.session_state.processing_done:
        st.subheader("📊 Processing Results")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📌 Selected PDF Item Descriptions**")
            with st.expander("View Extracted PDF Descriptions", expanded=False):
                st.json(st.session_state.selected_pdf_descs if st.session_state.selected_pdf_descs else [])
        with col2:
            st.markdown("**🤖 LLM Processed Template Fields**")
            data_to_display = st.session_state.llm_corrected_filled_data if st.session_state.correction_applied else st.session_state.llm_initial_filled_data
            if data_to_display and st.session_state.template_contexts:
                show_all = st.checkbox("Show all fields (incl. NOs)", key=f"show_all_proc_{st.session_state.run_key}")
                display_items = []
                yes_count = 0
                for k, v_ctx in sorted(st.session_state.template_contexts.items()):
                    if k.endswith("_check"):
                        val = data_to_display.get(k, "NO")
                        emoji = "✅" if val == "YES" else "❌"
                        if val == "YES" or show_all:
                            display_items.append(f"{emoji} **{v_ctx}** (`{k}`): {val}")
                            if val == "YES": yes_count +=1
                st.markdown(f"_Displaying {yes_count if not show_all else len(display_items)} fields:_ ")
                for item in display_items: st.markdown(item)
                with st.expander("View Raw JSON", expanded=False): st.json(data_to_display)
            else: st.info("LLM data not ready.")

        st.subheader("📂 Downloads")
        dl_c1, dl_c2 = st.columns(2)
        with dl_c1:
            if os.path.exists(st.session_state.initial_docx_path):
                with open(st.session_state.initial_docx_path, "rb") as fp:
                    st.download_button("Initial Document", fp, os.path.basename(st.session_state.initial_docx_path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_init_{st.session_state.run_key}")
        with dl_c2:
            if st.session_state.correction_applied and os.path.exists(st.session_state.corrected_docx_path):
                with open(st.session_state.corrected_docx_path, "rb") as fp:
                    st.download_button("Corrected Document", fp, os.path.basename(st.session_state.corrected_docx_path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary", key=f"dl_corr_{st.session_state.run_key}")
            elif st.session_state.processing_done : st.info("Correct via chat for an updated document.")
        st.markdown("---")
        
        st.subheader("💬 Interactive Chat") 
        if st.session_state.chat_log:
            with st.expander("View Chat Log", expanded=True):
                for role, content in st.session_state.chat_log:
                    st.markdown(f"**{role.capitalize()}:** {content}")
        user_chat_msg = st.text_input("Ask a question or give a correction:", key=f"chat_msg_{st.session_state.run_key}")
        if st.button("Send Message", key=f"send_msg_btn_{st.session_state.run_key}"):
            if user_chat_msg and st.session_state.processing_done:
                st.session_state.chat_log.append(("user", user_chat_msg))
                is_q = user_chat_msg.strip().endswith("?")
                with st.spinner("🤖 Thinking..."):
                    try:
                        if is_q:
                            ans = answer_pdf_question(user_chat_msg, st.session_state.selected_pdf_descs, st.session_state.full_pdf_text, st.session_state.template_contexts)
                            st.session_state.chat_log.append(("assistant", ans))
                        else: 
                            updated_llm_data = get_llm_chat_update(st.session_state.llm_corrected_filled_data, user_chat_msg, st.session_state.selected_pdf_descs, st.session_state.template_contexts, st.session_state.full_pdf_text)
                            st.session_state.llm_corrected_filled_data = updated_llm_data 
                            fill_word_document_from_llm_data(TEMPLATE_FILE, st.session_state.llm_corrected_filled_data, st.session_state.corrected_docx_path)
                            st.session_state.correction_applied = True
                            st.session_state.chat_log.append(("assistant", f"Correction applied. Doc '{os.path.basename(st.session_state.corrected_docx_path)}' updated."))
                        st.rerun()
                    except Exception as e:
                        st.session_state.error_message = f"Chat error: {e}"; st.text(traceback.format_exc())
            elif not st.session_state.processing_done: st.warning("Process a document first.")
            else: st.warning("Enter question/correction.")
    else:
        st.info("👈 Upload a PDF and click 'Process Document' in the sidebar to begin.")

with tab_crm_management:
    st.header("📒 CRM Management")
    if st.button("Refresh CRM List", key=f"refresh_crm_main_tab_{st.session_state.run_key}"):
        load_crm_data()
        st.success("CRM data refreshed.")

    st.subheader("Client Records")
    
    # --- Select Client to View/Edit Details & Priced Items ---
    client_options_display = ["Select a Client Record..."] + \
                             [f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')} (ID: {c.get('id')})" 
                              for c in st.session_state.all_crm_clients]
    
    selected_client_option_str_for_view = st.selectbox(
        "Select Client to View/Edit Details:", 
        client_options_display, 
        key=f"crm_select_for_view_main_tab_{st.session_state.run_key}", 
        index=0
    )

    client_detail_editor_placeholder = st.empty()
    save_button_placeholder = st.empty()
    delete_section_placeholder = st.empty() # Placeholder for the entire delete UI section
    priced_items_placeholder = st.empty()

    if selected_client_option_str_for_view != "Select a Client Record...":
        try:
            selected_id_for_view = int(selected_client_option_str_for_view.split("(ID: ")[-1][:-1])
            if st.session_state.selected_client_for_detail_edit is None or st.session_state.selected_client_for_detail_edit.get('id') != selected_id_for_view:
                st.session_state.selected_client_for_detail_edit = get_client_by_id(selected_id_for_view)
                st.session_state.editing_client_id = selected_id_for_view
                st.session_state.confirming_delete_client_id = None # Reset delete confirmation if client changes
            
            client_to_display_and_edit = st.session_state.selected_client_for_detail_edit

            if client_to_display_and_edit:
                with client_detail_editor_placeholder.container():
                    st.markdown("**Edit Client Details:**")
                    client_detail_list = [{
                        'id': client_to_display_and_edit.get('id'), 
                        'quote_ref': client_to_display_and_edit.get('quote_ref',''),
                        'customer_name': client_to_display_and_edit.get('customer_name',''),
                        'machine_model': client_to_display_and_edit.get('machine_model',''),
                        'country_destination': client_to_display_and_edit.get('country_destination',''),
                        'sold_to_address': client_to_display_and_edit.get('sold_to_address',''),
                        'ship_to_address': client_to_display_and_edit.get('ship_to_address',''),
                        'telephone': client_to_display_and_edit.get('telephone',''),
                        'customer_contact_person': client_to_display_and_edit.get('customer_contact_person',''),
                        'customer_po': client_to_display_and_edit.get('customer_po','')
                    }]
                    df_for_editor = pd.DataFrame(client_detail_list)
                    
                    # The edited_df from data_editor is the new state
                    edited_df_output = st.data_editor(
                        df_for_editor,
                        key=f"client_detail_editor_{client_to_display_and_edit.get('id', 'new')}",
                        num_rows="fixed", hide_index=True, use_container_width=True,
                        column_config={ 
                            "id": None, 
                            "quote_ref": st.column_config.TextColumn("Quote Ref (Required)", required=True),
                            "sold_to_address": st.column_config.TextColumn("Sold To Address", width="medium"),
                            "ship_to_address": st.column_config.TextColumn("Ship To Address", width="medium"),
                        }
                    )
                    st.session_state.edited_client_details_df = edited_df_output # Always store the output

                with save_button_placeholder.container():
                    if st.button("💾 Save Client Detail Changes", key=f"save_details_btn_{client_to_display_and_edit.get('id', 'new')}"):
                        if not st.session_state.edited_client_details_df.empty:
                            updated_row = st.session_state.edited_client_details_df.iloc[0].to_dict()
                            client_id_to_update = client_to_display_and_edit.get('id') # Get ID from originally loaded client
                            update_payload = { k: v for k, v in updated_row.items() if k != 'id' } # Exclude ID from payload
                            
                            if not update_payload.get('quote_ref'):
                                st.error("Quote Reference is required!")
                            elif update_client_record(client_id_to_update, update_payload):
                                st.success("Client details updated!")
                                load_crm_data() # Refresh full CRM list
                                st.session_state.selected_client_for_detail_edit = get_client_by_id(client_id_to_update) # Refresh this client's view
                                st.rerun()
                            else: st.error("Failed to update client details.")
                        else: st.warning("No client data in editor to save.")
                
                # --- Delete Button and Confirmation Logic ---
                with delete_section_placeholder.container():
                    st.markdown("--- Delete Record ---") # Changed header slightly
                    current_client_id = client_to_display_and_edit.get('id')
                    current_quote_ref = client_to_display_and_edit.get('quote_ref')

                    # If we are not currently confirming a delete for this specific client, show the initial delete button.
                    if st.session_state.confirming_delete_client_id != current_client_id:
                        if st.button("🗑️ Initiate Delete Sequence", key=f"init_del_btn_{current_client_id}"):
                            st.session_state.confirming_delete_client_id = current_client_id
                            st.rerun() # Rerun to show the confirmation state
                    
                    # If we ARE confirming a delete for THIS client, show warning and final delete button.
                    if st.session_state.confirming_delete_client_id == current_client_id:
                        st.warning(f"**CONFIRM DELETION**: Are you sure you want to permanently delete all data for client ID {current_client_id} (Quote: {current_quote_ref})? This action cannot be undone.")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button(f"YES, DELETE ID {current_client_id}", key=f"confirm_del_btn_{current_client_id}", type="primary"):
                                st.write(f"DEBUG: Attempting to delete client ID: {current_client_id}") # Debug
                                if delete_client_record(current_client_id):
                                    st.success(f"Client record ID {current_client_id} and associated data deleted.")
                                    load_crm_data()
                                    st.session_state.selected_client_for_detail_edit = None
                                    st.session_state.editing_client_id = None
                                    st.session_state.edited_client_details_df = pd.DataFrame()
                                    st.session_state.confirming_delete_client_id = None # Reset confirmation state
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete client record ID {current_client_id}.")
                                    st.session_state.confirming_delete_client_id = None # Reset on failure too
                                    st.rerun()
                        with col_cancel:
                            if st.button("Cancel Deletion", key=f"cancel_del_btn_{current_client_id}"):
                                st.session_state.confirming_delete_client_id = None
                                st.info("Deletion cancelled.")
                                st.rerun()
                # ---------------------------------------------
                st.markdown("---")
                # --- Display Priced Items for this selected client ---
                with priced_items_placeholder.container():
                    quote_ref_for_items = client_to_display_and_edit.get('quote_ref')
                    st.subheader(f"Priced Items for Quote: {quote_ref_for_items}")
                    
                    # Load or use already loaded items for editing
                    # We need a way to know if this is the first load for the data_editor for this client
                    # or if it's a re-render after an edit. Let's always reload for simplicity now.
                    priced_items_for_quote = load_priced_items_for_quote(quote_ref_for_items)
                    st.session_state.current_priced_items_for_editing = priced_items_for_quote # Store original

                    if priced_items_for_quote:
                        df_priced_items = pd.DataFrame(priced_items_for_quote)
                        # Define column configuration for st.data_editor if needed (e.g., column order, types)
                        # For now, default configuration will be used.
                        # Only allow editing of description, quantity, and price_str. ID is hidden, numeric price is derived.
                        editable_df = df_priced_items[['id', 'item_description', 'item_quantity', 'item_price_str']].copy()
                        
                        st.markdown("**Edit Priced Items:**")
                        # Key the data_editor to ensure it re-renders when the underlying selection changes
                        edited_df = st.data_editor(
                            editable_df, 
                            key=f"data_editor_priced_items_{st.session_state.editing_client_id}",
                            num_rows="dynamic", # Allow adding/deleting rows (more advanced, start with fixed)
                            # disabled=["id"], # Make id column non-editable if displayed or hide it
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "id": None, # Hide ID column from editor
                                "item_description": st.column_config.TextColumn("Description", width="large", required=True),
                                "item_quantity": st.column_config.TextColumn("Qty"), # Text for flexibility like "As required"
                                "item_price_str": st.column_config.TextColumn("Price (Text)")
                            }
                        )
                        st.session_state.edited_priced_items_df = edited_df # Store edited df

                        if st.button("💾 Save Priced Item Changes", key=f"save_priced_items_btn_{st.session_state.editing_client_id}"):
                            changes_applied = 0
                            if not st.session_state.edited_priced_items_df.empty:
                                for index, edited_row in st.session_state.edited_priced_items_df.iterrows():
                                    item_id = edited_row.get('id') # Get original ID
                                    original_item = next((item for item in st.session_state.current_priced_items_for_editing if item['id'] == item_id), None)
                                    
                                    if original_item:
                                        # Check if anything actually changed for this row
                                        if (original_item.get('item_description') != edited_row.get('item_description') or
                                            str(original_item.get('item_quantity', '')) != str(edited_row.get('item_quantity', '')) or # Compare as strings
                                            str(original_item.get('item_price_str', '')) != str(edited_row.get('item_price_str', ''))):
                                            
                                            update_payload = {
                                                'item_description': edited_row.get('item_description'),
                                                'item_quantity': edited_row.get('item_quantity'),
                                                'item_price_str': edited_row.get('item_price_str')
                                            }
                                            if update_single_priced_item(item_id, update_payload):
                                                changes_applied += 1
                                            else:
                                                st.error(f"Failed to update item ID {item_id}.")
                            # else: Item might be a new row if num_rows="dynamic" and add works (not fully implemented here)

                            if changes_applied > 0:
                                st.success(f"{changes_applied} priced item(s) updated successfully!")
                                load_crm_data() # Reload all clients to reflect potential changes in display elsewhere if needed
                                st.rerun() # Rerun to refresh the data_editor with fresh data from DB
                            else:
                                st.info("No changes detected in priced items to save.")
                    else:
                        st.info("No priced items recorded for this quote to edit.")
        except Exception as e:
            st.error(f"Error in CRM client display/edit/delete section: {e}"); traceback.print_exc()
    else: # Nothing selected in the main client dropdown
        client_detail_editor_placeholder.empty()
        save_button_placeholder.empty()
        delete_section_placeholder.empty()
        priced_items_placeholder.empty()
        st.session_state.confirming_delete_client_id = None # Ensure confirmation state is reset
        st.info("Select a client record above to view or edit its details and priced items.")

    # --- Add New Client Form (Can be a separate button/form or integrated differently) ---
    with st.expander("Manually Add New Client Record"):
        with st.form(key=f"crm_add_new_form_{st.session_state.run_key}"):
            st.markdown("**Enter New Client Details:**")
            new_quote_ref = st.text_input("Quote Reference (Required)", key=f"new_qr_{st.session_state.run_key}")
            new_cust_name = st.text_input("Customer Name", key=f"new_cn_{st.session_state.run_key}")
            # ... (add all other text inputs for new client) ...
            new_machine_model = st.text_input("Machine Model", key=f"new_mm_{st.session_state.run_key}")
            new_country = st.text_input("Country Destination", key=f"new_cd_{st.session_state.run_key}")
            new_sold_addr = st.text_area("Sold To Address", key=f"new_sta_{st.session_state.run_key}")
            new_ship_addr = st.text_area("Ship To Address", key=f"new_shipta_{st.session_state.run_key}")
            new_tel = st.text_input("Telephone", key=f"new_tel_{st.session_state.run_key}")
            new_contact = st.text_input("Customer Contact", key=f"new_ccp_{st.session_state.run_key}")
            new_po = st.text_input("Customer PO", key=f"new_cpo_{st.session_state.run_key}")

            submit_new_client_button = st.form_submit_button("➕ Add New Client to CRM")
            if submit_new_client_button:
                if not new_quote_ref:
                    st.error("Quote Reference is required for new client.")
                else:
                    new_client_data = {
                        'quote_ref': new_quote_ref, 'customer_name': new_cust_name,
                        'machine_model': new_machine_model, 'country_destination': new_country,
                        'sold_to_address': new_sold_addr, 'ship_to_address': new_ship_addr,
                        'telephone': new_tel, 'customer_contact_person': new_contact,
                        'customer_po': new_po
                    }
                    if save_client_info(new_client_data): # save_client_info handles INSERT
                        st.success("New client added successfully!")
                        load_crm_data()
                        st.rerun()
                    else:
                        st.error("Failed to add new client.")
    st.markdown("---")
    st.subheader("All Client Records Table")
    if st.session_state.all_crm_clients:
        df_all_clients = pd.DataFrame(st.session_state.all_crm_clients)
        # Add new fields to the display list for the main CRM table
        all_clients_cols = ['id', 'quote_ref', 'customer_name', 'machine_model', 'country_destination', 
                            'sold_to_address', 'ship_to_address', 'telephone', 
                            'customer_contact_person', 'customer_po', 'processing_date']
        df_all_clients_final = df_all_clients[[c for c in all_clients_cols if c in df_all_clients.columns]]
        st.dataframe(df_all_clients_final, use_container_width=True, hide_index=True)
    else:
        st.info("No client records in CRM yet.")

def main():
    st.title("GOA Document Generator")
    
    # Initialize session state if needed
    if 'run_key' not in st.session_state:
        st.session_state.run_key = str(uuid.uuid4())
    
    # File upload section
    uploaded_pdf_file = st.file_uploader("Upload Quote PDF", type=['pdf'])
    template_file_path = "GOA_template.docx"  # Your template file
    
    if uploaded_pdf_file:
        if 'processing_done' not in st.session_state or not st.session_state.processing_done:
            with st.spinner("Processing..."):
                status_bar = st.progress(0, text="Starting...")
                perform_initial_processing(uploaded_pdf_file, template_file_path)
        
        # Machine selection
        if 'available_machines' in st.session_state and st.session_state.available_machines:
            st.subheader("Select Machine for GOA")
            selected_machine = st.selectbox(
                "Choose a machine to generate GOA for:",
                options=st.session_state.available_machines,
                key="machine_selector"
            )
            
            if selected_machine:
                # Get machine-specific data
                machine_specific_data = get_all_fields_via_llm(
                    st.session_state.selected_pdf_descs,
                    st.session_state.template_contexts,
                    st.session_state.full_pdf_text,
                    target_machine=selected_machine
                )
                
                # Update the document with machine-specific data
                st.session_state.llm_corrected_filled_data = machine_specific_data
                
                # Generate document for selected machine
                output_filename = f"GOA_{selected_machine.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                fill_word_document_from_llm_data(template_file_path, machine_specific_data, output_filename)
                
                # Provide download link
                with open(output_filename, 'rb') as docx_file:
                    st.download_button(
                        label="Download GOA Document",
                        data=docx_file,
                        file_name=output_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
        
        # Rest of your existing UI code...

if __name__ == "__main__":
    main()
