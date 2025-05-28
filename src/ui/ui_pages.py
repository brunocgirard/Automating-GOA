import streamlit as st
import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
import traceback
import shutil

# Import from other modules
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection, 
    handle_selected_action, load_full_client_profile
)

# Import from utility modules
from src.utils.pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical
from src.utils.llm_handler import configure_gemini_client, get_machine_specific_fields_via_llm, answer_pdf_question
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.crm_utils import (
    init_db, save_client_info, load_all_clients, get_client_by_id, 
    update_client_record, save_priced_items, load_priced_items_for_quote, 
    update_single_priced_item, delete_client_record, save_machines_data, 
    load_machines_for_quote, save_machine_template_data, load_machine_template_data, 
    save_document_content, load_document_content
)
from src.generators.document_generators import generate_packing_slip_data, generate_commercial_invoice_data, generate_certificate_of_origin_data

# Moved from app.py
def show_welcome_page():
    """
    Displays the welcome page interface with quote upload and client dashboard access
    """
    st.title("QuoteFlow Document Assistant")
    
    # Status check for existing client profiles
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "action_selection":
        if "confirmed_profile" in st.session_state and st.session_state.confirmed_profile:
            return show_action_selection(st.session_state.confirmed_profile)
    
    st.subheader("📂 Recent Client Profiles")
    client_profiles_container = st.container()
    
    with client_profiles_container:
        if st.session_state.all_crm_clients and len(st.session_state.all_crm_clients) > 0:
            recent_clients = st.session_state.all_crm_clients[:5]  # Show 5 most recent
            for client_summary_item in recent_clients:
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"### {client_summary_item.get('customer_name', 'Unnamed Client')}")
                        st.markdown(f"**Quote:** {client_summary_item.get('quote_ref', 'N/A')}")
                        if client_summary_item.get('machine_model'): 
                            st.markdown(f"**Machine(s):** {client_summary_item.get('machine_model', 'Unknown')}")
                    with col2:
                        if st.button("View Details", key=f"view_client_{client_summary_item.get('id')}", use_container_width=True):
                            full_profile_data = load_full_client_profile(client_summary_item.get('quote_ref'))
                            if full_profile_data:
                                st.session_state.confirmed_profile = full_profile_data
                                st.session_state.profile_extraction_step = "action_selection" 
                                st.rerun()
                            else: st.error(f"Could not load full profile for {client_summary_item.get('quote_ref')}.")
            st.markdown("&nbsp;") 
            if len(st.session_state.all_crm_clients) > 5:
                if st.button("View All Clients", use_container_width=True):
                    st.session_state.current_page = "Client Dashboard"
                    st.rerun()
        else:
            st.info("No client profiles found. Upload a quote below to create a new profile.")
    
    st.markdown("---")
    st.subheader("📤 Upload New Quote")
    uploaded_file = st.file_uploader("Choose a PDF quote to process", type=["pdf"], key="pdf_uploader_welcome")
    
    if uploaded_file is not None:
        st.markdown(f"Uploaded: **{uploaded_file.name}**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Extract Full Profile", key="extract_profile_btn", type="primary", use_container_width=True):
                st.session_state.extracted_profile = extract_client_profile(uploaded_file)
                if st.session_state.extracted_profile:
                    st.session_state.profile_extraction_step = "confirmation"
                    st.rerun()
                else:
                    st.error("Failed to extract profile from the uploaded PDF.")
        
        with col2:
            if st.button("Quick Catalog Only", key="quick_catalog_btn", use_container_width=True):
                from app import quick_extract_and_catalog
                result = quick_extract_and_catalog(uploaded_file)
                if result:
                    st.success(f"Quote {result['quote_ref']} cataloged with {len(result['items'])} items.")
                    st.session_state.all_crm_clients = load_all_clients() # Refresh
                else:
                    st.error("Failed to catalog the uploaded PDF.")
    
    # Profile extraction workflow - confirmation step
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "confirmation":
        if "extracted_profile" in st.session_state and st.session_state.extracted_profile:
            # Show confirmation UI
            st.session_state.confirmed_profile = confirm_client_profile(st.session_state.extracted_profile)
            if st.session_state.confirmed_profile:
                st.session_state.profile_extraction_step = "action_selection"
                st.rerun()

def show_client_dashboard_page():
    """
    Displays the client dashboard interface for browsing and selecting clients
    """
    st.title("📊 Client Dashboard")
    
    # Status check for existing client profiles
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "action_selection":
        if "confirmed_profile" in st.session_state and st.session_state.confirmed_profile:
            action = show_action_selection(st.session_state.confirmed_profile)
            if action:
                handle_selected_action(action, st.session_state.confirmed_profile)
                st.rerun()
            return
    
    # Upload section
    with st.expander("Upload New Quote", expanded=False):
        uploaded_file = st.file_uploader("Choose a PDF quote to process", type=["pdf"], key="pdf_uploader_dashboard")
        
        if uploaded_file is not None:
            st.markdown(f"Uploaded: **{uploaded_file.name}**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Extract Full Profile", key="extract_profile_dash_btn", type="primary", use_container_width=True):
                    st.session_state.extracted_profile = extract_client_profile(uploaded_file)
                    if st.session_state.extracted_profile:
                        st.session_state.profile_extraction_step = "confirmation"
                        st.rerun()
                    else:
                        st.error("Failed to extract profile from the uploaded PDF.")
            
            with col2:
                if st.button("Quick Catalog Only", key="quick_catalog_dash_btn", use_container_width=True):
                    from app import quick_extract_and_catalog
                    result = quick_extract_and_catalog(uploaded_file)
                    if result:
                        st.success(f"Quote {result['quote_ref']} cataloged with {len(result['items'])} items.")
                        st.session_state.all_crm_clients = load_all_clients() # Refresh
                    else:
                        st.error("Failed to catalog the uploaded PDF.")
    
    # Client browser
    st.subheader("Client Browser")
    if st.session_state.all_crm_clients and len(st.session_state.all_crm_clients) > 0:
        st.markdown("Select a client to view their profile and available actions.")
        
        # Search and filter
        search_term = st.text_input("Search by name or quote reference:", key="client_search")
        
        filtered_clients = st.session_state.all_crm_clients
        if search_term:
            filtered_clients = [
                c for c in st.session_state.all_crm_clients
                if search_term.lower() in c.get('customer_name', '').lower() 
                or search_term.lower() in c.get('quote_ref', '').lower()
            ]
        
        # Display clients
        for client_item in filtered_clients:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### {client_item.get('customer_name', 'Unnamed Client')}")
                    st.markdown(f"**Quote:** {client_item.get('quote_ref', 'N/A')}")
                    if client_item.get('machine_model'): 
                        st.markdown(f"**Machine(s):** {client_item.get('machine_model', 'Unknown')}")
                with col2:
                    if st.button("View Details", key=f"view_client_dash_{client_item.get('id')}", use_container_width=True):
                        full_profile_data = load_full_client_profile(client_item.get('quote_ref'))
                        if full_profile_data:
                            st.session_state.confirmed_profile = full_profile_data
                            st.session_state.profile_extraction_step = "action_selection" 
                            st.rerun()
                        else: st.error(f"Could not load full profile for {client_item.get('quote_ref')}.")
    else:
        st.info("No clients found. Upload a new quote to create a client profile.")
    
    # Profile extraction workflow - confirmation step
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "confirmation":
        if "extracted_profile" in st.session_state and st.session_state.extracted_profile:
            # Show confirmation UI
            st.session_state.confirmed_profile = confirm_client_profile(st.session_state.extracted_profile)
            if st.session_state.confirmed_profile:
                st.session_state.profile_extraction_step = "action_selection"
                st.rerun()

def show_quote_processing():
    st.title("📄 Quote Processing")
    processing_steps = ["Upload Quote", "Identify Main Machines", "Select Common Options", "Process Machine"]
    current_step = st.session_state.processing_step
    progress_percentage = current_step / (len(processing_steps) - 1) if len(processing_steps) > 1 else 0
    st.progress(progress_percentage)
    st.subheader(f"Step {current_step + 1}: {processing_steps[current_step]}")

    from app import perform_initial_processing, quick_extract_and_catalog, load_previous_document, group_items_by_confirmed_machines, process_machine_specific_data, TEMPLATE_FILE
    
    if current_step == 0:
        st.markdown("Upload a PDF quote to begin processing for GOA or catalog data.")
        uploaded_pdf = st.file_uploader("Choose PDF for GOA Processing", type="pdf", key=f"pdf_uploader_goa_{st.session_state.run_key}")
        if uploaded_pdf:
            st.markdown(f"**Uploaded:** `{uploaded_pdf.name}`")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Process for GOA", type="primary", key=f"process_btn_goa_{st.session_state.run_key}"):
                    if not os.path.exists(TEMPLATE_FILE): st.error(f"Template '{TEMPLATE_FILE}' not found.")
                    else:
                        perform_initial_processing(uploaded_pdf, TEMPLATE_FILE)
                        if st.session_state.processing_done: st.session_state.processing_step = 1; st.rerun()
            with col2:
                if st.button("📊 Just Catalog Data (from GOA)", key="quick_catalog_goa_btn"):
                    result = quick_extract_and_catalog(uploaded_pdf)
                    if result: st.success(f"Quote {result['quote_ref']} cataloged.")
                    else: st.error("Failed to catalog data.")
        st.subheader("📂 Or Load Previous Document for GOA")
        if st.session_state.all_crm_clients:
            quotes = [(c['id'], f"{c.get('customer_name', 'Unknown')} - {c.get('quote_ref', 'Unknown')}") for c in st.session_state.all_crm_clients]
            if quotes:
                selected_quote_id = st.selectbox("Select a previous quote for GOA:", options=[q[0] for q in quotes], format_func=lambda x: next((q[1] for q in quotes if q[0] == x), ""), key="load_prev_quote_goa")
                if st.button("📥 Load Selected Quote for GOA", key="load_quote_goa_btn"):
                    with st.spinner("Loading document..."): 
                        if load_previous_document(selected_quote_id): st.success("Document loaded!"); st.session_state.processing_step = 1; st.rerun()
            else: st.info("No previous quotes to load for GOA.")
    elif current_step == 1:
        if not st.session_state.machine_confirmation_done:
            st.markdown("Select **main machines** for the GOA.")
            items = st.session_state.items_for_confirmation
            if items:
                selected_indices = []
                with st.container():
                    for i, item in enumerate(items):
                        desc = item.get('description', 'No desc'); first_line = desc.split('\n')[0] if '\n' in desc else desc
                        price_str = item.get('item_price_str', ''); display_text = f"{first_line} {price_str}"
                        is_preselected = i in st.session_state.selected_main_machines
                        if st.checkbox(display_text, value=is_preselected, key=f"goa_machine_cb_{i}"): selected_indices.append(i)
                st.session_state.selected_main_machines = selected_indices
                col1, col2 = st.columns(2)
                with col1: 
                    if st.button("⬅️ Back (GOA Upload)", key="goa_back_upload"): st.session_state.processing_step = 0; st.rerun()
                with col2:
                    if st.button("Next ➡️ (GOA Main Machines)", key="goa_confirm_machines_btn", type="primary"):
                        if not selected_indices: st.warning("Select at least one main machine.")
                        else: st.session_state.machine_confirmation_done = True; st.session_state.processing_step = 2; st.rerun()
            else: 
                st.warning("No items for confirmation.")
                if st.button("⬅️ Back to GOA Upload", key="goa_back_upload_no_items"): st.session_state.processing_step = 0; st.rerun()
        else: st.session_state.processing_step = 2; st.rerun()
    elif current_step == 2:
        if not st.session_state.common_options_confirmation_done:
            st.markdown("Select **common options** for the GOA.")
            items = st.session_state.items_for_confirmation
            if items:
                main_machine_indices = st.session_state.selected_main_machines
                available_options = [(i, item) for i, item in enumerate(items) if i not in main_machine_indices]
                selected_indices_common = []
                with st.container():
                    for i, item_data in available_options:
                        desc = item_data.get('description', 'No desc'); first_line = desc.split('\n')[0] if '\n' in desc else desc
                        price_str = item_data.get('item_price_str', ''); display_text = f"{first_line} {price_str}"
                        is_preselected = i in st.session_state.selected_common_options
                        if st.checkbox(display_text, value=is_preselected, key=f"goa_common_cb_{i}"): selected_indices_common.append(i)
                st.session_state.selected_common_options = selected_indices_common
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Back (GOA Main Machines)", key="goa_back_machines"): st.session_state.machine_confirmation_done = False; st.session_state.processing_step = 1; st.rerun()
                with col2:
                    if st.button("Next ➡️ (GOA Common Options)", key="goa_confirm_common_btn", type="primary"):
                        grouped_data = group_items_by_confirmed_machines(items, st.session_state.selected_main_machines, st.session_state.selected_common_options)
                        st.session_state.identified_machines_data = grouped_data
                        quote_ref = items[0].get('client_quote_ref') if items and items[0].get('client_quote_ref') else "unknown_goa_quote"
                        if save_machines_data(quote_ref, grouped_data): st.success("Machine groupings saved.")
                        else: st.warning("Failed to save machine groupings.")
                        st.session_state.common_options_confirmation_done = True; st.session_state.processing_step = 3; st.rerun()
            else: 
                st.warning("No items for GOA common options.")
                if st.button("⬅️ Back to GOA Upload (No Common)", key="goa_back_upload_no_common"): st.session_state.processing_step = 0; st.rerun()
        else: st.session_state.processing_step = 3; st.rerun()
    elif current_step == 3:
        st.subheader("🔍 Select Machine to Process for GOA")
        machines = st.session_state.identified_machines_data.get("machines", [])
        if machines:
            machine_options = [m.get('machine_name', 'Unknown Machine') for m in machines]
            selected_machine_idx = st.selectbox("Choose machine for GOA:", range(len(machine_options)), format_func=lambda i: machine_options[i], key=f"goa_machine_select_{st.session_state.run_key}")
            st.session_state.selected_machine_index = selected_machine_idx
            selected_machine = machines[selected_machine_idx]
            with st.expander(f"Details: {selected_machine.get('machine_name')}", expanded=True):
                st.markdown(f"**Main Item:** {selected_machine.get('main_item', {}).get('description', 'N/A')}")
                st.markdown(f"**Add-ons:** {len(selected_machine.get('add_ons', []))} items")
            col1, col2 = st.columns(2)
            with col1: 
                if st.button("⬅️ Back (GOA Common Options)", key="goa_back_common"): st.session_state.common_options_confirmation_done = False; st.session_state.processing_step = 2; st.rerun()
            with col2:
                if st.button("🔨 Process Selected Machine for GOA", key=f"process_goa_machine_btn_{st.session_state.run_key}", type="primary"):
                    if not os.path.exists(TEMPLATE_FILE): st.error(f"Template '{TEMPLATE_FILE}' not found.")
                    else:
                        success = process_machine_specific_data(selected_machine, TEMPLATE_FILE)
                        if success: st.success(f"Machine '{selected_machine.get('machine_name')}' processed for GOA!")
                        if hasattr(st.session_state, 'machine_docx_path') and os.path.exists(st.session_state.machine_docx_path):
                            st.subheader("📂 GOA Document Download")
                            with open(st.session_state.machine_docx_path, "rb") as fp:
                                st.download_button("Download GOA Document", fp, os.path.basename(st.session_state.machine_docx_path), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_goa_machine_{st.session_state.run_key}", type="primary")
        else: 
            st.warning("No machines for GOA processing.")
            if st.button("⬅️ Start Over (GOA No Machines)", key="goa_restart_no_machines"): st.session_state.processing_step = 0; st.rerun()

def show_crm_management_page():
    st.title("📒 CRM Management")
    from app import load_crm_data, quick_extract_and_catalog, update_single_priced_item # Ensure update_single_priced_item is imported

    if st.button("Refresh CRM List", key=f"refresh_crm_main_tab_{st.session_state.run_key}"):
        load_crm_data(); st.success("CRM data refreshed.")
    with st.expander("Quick Catalog New Quote", expanded=False):
        st.markdown("Upload PDF to extract data and create new client record.")
        uploaded_pdf_crm = st.file_uploader("Choose PDF for CRM Quick Catalog", type="pdf", key=f"crm_quick_upload_{st.session_state.run_key}")
        if uploaded_pdf_crm and st.button("Catalog This Quote", type="primary", key="crm_quick_catalog_btn"):
            result = quick_extract_and_catalog(uploaded_pdf_crm)
            if result: st.success(f"Quote {result['quote_ref']} cataloged."); load_crm_data(); st.rerun()
            else: st.error("Failed to catalog data.")
    st.subheader("Client Records")
    client_options_display = ["Select a Client Record..."] + [f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')} (ID: {c.get('id')})" for c in st.session_state.all_crm_clients]
    selected_client_option_str_for_view = st.selectbox("Select Client to View/Edit Details:", client_options_display, key=f"crm_select_for_view_main_tab_{st.session_state.run_key}", index=0)
    
    client_detail_editor_placeholder = st.empty()
    save_button_placeholder = st.empty()
    delete_section_placeholder = st.empty()

    if selected_client_option_str_for_view != "Select a Client Record...":
        try:
            selected_id_for_view = int(selected_client_option_str_for_view.split("(ID: ")[-1][:-1])
            if st.session_state.selected_client_for_detail_edit is None or st.session_state.selected_client_for_detail_edit.get('id') != selected_id_for_view:
                st.session_state.selected_client_for_detail_edit = get_client_by_id(selected_id_for_view)
                st.session_state.editing_client_id = selected_id_for_view
                st.session_state.confirming_delete_client_id = None
            client_to_display_and_edit = st.session_state.selected_client_for_detail_edit
            if client_to_display_and_edit:
                client_tab1, client_tab2, client_tab3 = st.tabs(["📋 Client Details", "💲 Priced Items", "📤 Upload PDF (Client)"])
                with client_tab1:
                    with client_detail_editor_placeholder.container():
                        st.markdown("**Edit Client Details:**")
                        client_detail_list = [{'id': client_to_display_and_edit.get('id'), 'quote_ref': client_to_display_and_edit.get('quote_ref',''), 'customer_name': client_to_display_and_edit.get('customer_name',''), 'machine_model': client_to_display_and_edit.get('machine_model',''), 'country_destination': client_to_display_and_edit.get('country_destination',''), 'sold_to_address': client_to_display_and_edit.get('sold_to_address',''), 'ship_to_address': client_to_display_and_edit.get('ship_to_address',''), 'telephone': client_to_display_and_edit.get('telephone',''), 'customer_contact_person': client_to_display_and_edit.get('customer_contact_person',''), 'customer_po': client_to_display_and_edit.get('customer_po','')}]
                        df_for_editor = pd.DataFrame(client_detail_list)
                        edited_df_output = st.data_editor(df_for_editor, key=f"client_detail_editor_{client_to_display_and_edit.get('id', 'new')}", num_rows="fixed", hide_index=True, use_container_width=True, column_config={ "id": None, "quote_ref": st.column_config.TextColumn("Quote Ref (Required)", required=True), "sold_to_address": st.column_config.TextColumn("Sold To Address", width="medium"), "ship_to_address": st.column_config.TextColumn("Ship To Address", width="medium"), })
                        st.session_state.edited_client_details_df = edited_df_output
                    with save_button_placeholder.container():
                        if st.button("💾 Save Client Detail Changes", key=f"save_details_btn_{client_to_display_and_edit.get('id', 'new')}"):
                            if not st.session_state.edited_client_details_df.empty:
                                updated_row = st.session_state.edited_client_details_df.iloc[0].to_dict()
                                client_id_to_update = client_to_display_and_edit.get('id'); update_payload = { k: v for k, v in updated_row.items() if k != 'id' }
                                if not update_payload.get('quote_ref'): st.error("Quote Reference is required!")
                                elif update_client_record(client_id_to_update, update_payload): st.success("Client details updated!"); load_crm_data(); st.session_state.selected_client_for_detail_edit = get_client_by_id(client_id_to_update); st.rerun()
                                else: st.error("Failed to update client details.")
                            else: st.warning("No client data in editor to save.")
                    with delete_section_placeholder.container():
                        st.markdown("--- Delete Record ---")
                        current_client_id = client_to_display_and_edit.get('id'); current_quote_ref = client_to_display_and_edit.get('quote_ref')
                        if st.session_state.confirming_delete_client_id != current_client_id:
                            if st.button("🗑️ Initiate Delete Sequence", key=f"init_del_btn_{current_client_id}"): st.session_state.confirming_delete_client_id = current_client_id; st.rerun()
                        if st.session_state.confirming_delete_client_id == current_client_id:
                            st.warning(f"**CONFIRM DELETION**: All data for client ID {current_client_id} (Quote: {current_quote_ref}) will be lost.")
                            col_confirm, col_cancel = st.columns(2)
                            with col_confirm: 
                                if st.button(f"YES, DELETE ID {current_client_id}", key=f"confirm_del_btn_{current_client_id}", type="primary"):
                                    if delete_client_record(current_client_id): st.success(f"Client record ID {current_client_id} deleted."); load_crm_data(); st.session_state.selected_client_for_detail_edit = None; st.session_state.editing_client_id = None; st.session_state.edited_client_details_df = pd.DataFrame(); st.session_state.confirming_delete_client_id = None; st.rerun()
                                    else: st.error(f"Failed to delete client ID {current_client_id}."); st.session_state.confirming_delete_client_id = None; st.rerun()
                            with col_cancel: 
                                if st.button("Cancel Deletion", key=f"cancel_del_btn_{current_client_id}"): st.session_state.confirming_delete_client_id = None; st.info("Deletion cancelled."); st.rerun()
                with client_tab2: 
                    quote_ref_for_items = client_to_display_and_edit.get('quote_ref'); st.subheader(f"Priced Items for Quote: {quote_ref_for_items}")
                    priced_items_for_quote = load_priced_items_for_quote(quote_ref_for_items); st.session_state.current_priced_items_for_editing = priced_items_for_quote
                    if priced_items_for_quote:
                        df_priced_items = pd.DataFrame(priced_items_for_quote); editable_df = df_priced_items[['id', 'item_description', 'item_quantity', 'item_price_str']].copy()
                        st.markdown("**Edit Priced Items:**")
                        edited_df = st.data_editor(editable_df, key=f"data_editor_priced_items_{st.session_state.editing_client_id}", num_rows="dynamic", hide_index=True, use_container_width=True, column_config={"id": None, "item_description": st.column_config.TextColumn("Description", width="large", required=True), "item_quantity": st.column_config.TextColumn("Qty"), "item_price_str": st.column_config.TextColumn("Price (Text)")})
                        st.session_state.edited_priced_items_df = edited_df
                        if st.button("💾 Save Priced Item Changes", key=f"save_priced_items_btn_{st.session_state.editing_client_id}"):
                            changes_applied = 0
                            if not st.session_state.edited_priced_items_df.empty:
                                for _, edited_row in st.session_state.edited_priced_items_df.iterrows():
                                    item_id = edited_row.get('id') 
                                    original_item = next((item for item in st.session_state.current_priced_items_for_editing if item['id'] == item_id), None)
                                    if original_item and (original_item.get('item_description') != edited_row.get('item_description') or str(original_item.get('item_quantity', '')) != str(edited_row.get('item_quantity', '')) or str(original_item.get('item_price_str', '')) != str(edited_row.get('item_price_str', ''))):
                                        update_payload = {'item_description': edited_row.get('item_description'), 'item_quantity': edited_row.get('item_quantity'), 'item_price_str': edited_row.get('item_price_str')}
                                        if update_single_priced_item(item_id, update_payload): changes_applied += 1
                                        else: st.error(f"Failed to update item ID {item_id}.")
                            if changes_applied > 0: st.success(f"{changes_applied} item(s) updated!"); load_crm_data(); st.rerun()
                            else: st.info("No changes to save in priced items.")
                    else: st.info("No priced items for this quote.")
                with client_tab3: 
                    st.subheader(f"📤 Upload PDF to {client_to_display_and_edit.get('customer_name', '')}")
                    quote_ref_for_upload = client_to_display_and_edit.get('quote_ref')
                    uploaded_pdf_client = st.file_uploader("Choose PDF for this client", type="pdf", key=f"client_pdf_upload_{quote_ref_for_upload}")
                    # Logic for client-specific PDF upload and processing would go here
        except Exception as e: st.error(f"Error in CRM client display: {e}"); traceback.print_exc()
    else: st.info("Select a client to view/edit details.")
    with st.expander("Manually Add New Client Record"):
        with st.form(key=f"crm_add_new_form_{st.session_state.run_key}"):
            st.markdown("**Enter New Client Details:**")
            new_quote_ref = st.text_input("Quote Ref (Req)", key=f"new_qr_{st.session_state.run_key}")
            new_cust_name = st.text_input("Customer Name", key=f"new_cn_{st.session_state.run_key}")
            new_machine_model = st.text_input("Machine Model", key=f"new_mm_{st.session_state.run_key}")
            new_country = st.text_input("Country Destination", key=f"new_cd_{st.session_state.run_key}")
            new_sold_addr = st.text_area("Sold To Address", key=f"new_sta_{st.session_state.run_key}")
            new_ship_addr = st.text_area("Ship To Address", key=f"new_shipta_{st.session_state.run_key}")
            new_tel = st.text_input("Telephone", key=f"new_tel_{st.session_state.run_key}")
            new_contact = st.text_input("Customer Contact", key=f"new_ccp_{st.session_state.run_key}")
            new_po = st.text_input("Customer PO", key=f"new_cpo_{st.session_state.run_key}")
            if st.form_submit_button("➕ Add New Client"):
                if not new_quote_ref: st.error("Quote Reference is required.")
                else: 
                    new_client_data = {'quote_ref': new_quote_ref, 'customer_name': new_cust_name, 'machine_model': new_machine_model, 'country_destination': new_country, 'sold_to_address': new_sold_addr, 'ship_to_address': new_ship_addr, 'telephone': new_tel, 'customer_contact_person': new_contact, 'customer_po': new_po}
                    if save_client_info(new_client_data): st.success("New client added!"); load_crm_data(); st.rerun()
                    else: st.error("Failed to add new client.")
    st.markdown("---"); st.subheader("All Client Records Table")
    if st.session_state.all_crm_clients:
        df_all_clients = pd.DataFrame(st.session_state.all_crm_clients)
        all_clients_cols = ['id', 'quote_ref', 'customer_name', 'machine_model', 'country_destination', 'sold_to_address', 'ship_to_address', 'telephone', 'customer_contact_person', 'customer_po', 'processing_date']
        df_all_clients_final = df_all_clients[[c for c in all_clients_cols if c in df_all_clients.columns]]
        st.dataframe(df_all_clients_final, use_container_width=True, hide_index=True)
    else: st.info("No client records found.")

def show_chat_page():
    st.title("💬 Chat Interface")
    
    # Check if we have a specific chat context
    if "chat_context" in st.session_state and st.session_state.chat_context:
        chat_context = st.session_state.chat_context
        context_client = chat_context.get("client_info", {})
        
        # Get PDF size for warning
        full_pdf_text = chat_context.get("full_pdf_text", "")
        pdf_size_kb = len(full_pdf_text) / 1024
        
        # Display context information
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("### Current Chat Context")
                if context_client:
                    st.markdown(f"**Client:** {context_client.get('client_name', 'Unknown')}")
                    st.markdown(f"**Quote:** {context_client.get('quote_ref', 'Unknown')}")
                else:
                    st.markdown("No specific client context.")
            with col2:
                # Display PDF size warning if applicable
                if pdf_size_kb > 100:
                    st.warning(f"PDF Size: {pdf_size_kb:.1f} KB")
                    st.markdown("*Large PDFs may cause slower responses*")
                else:
                    st.info(f"PDF Size: {pdf_size_kb:.1f} KB")
        
        # Show selected items from profile if available
        if "action_profile" in st.session_state and st.session_state.action_profile:
            profile_data = st.session_state.action_profile
            
            # Show machines if available
            machines = profile_data.get("machines_data", {}).get("machines", [])
            if machines:
                with st.expander("Available Machines (You can ask about these)", expanded=True):
                    for i, machine in enumerate(machines):
                        machine_name = machine.get("machine_name", "Unknown Machine")
                        st.markdown(f"**Machine {i+1}:** {machine_name}")
                        main_item = machine.get("main_item", {})
                        if main_item and "description" in main_item:
                            st.markdown(f"*Main Item:* {main_item.get('description', '')[:100]}...")
            
            # Show selected items if available
            line_items = profile_data.get("line_items", [])
            if line_items:
                with st.expander("Selected Items (You can ask about these)", expanded=False):
                    for i, item in enumerate(line_items[:10]):  # Limit to first 10 items
                        if "description" in item:
                            desc = item.get("description", "")
                            first_line = desc.split('\n')[0] if '\n' in desc else desc
                            st.markdown(f"- {first_line}")
                    if len(line_items) > 10:
                        st.caption(f"... and {len(line_items) - 10} more items")
    else:
        # No context
        st.info("Please try selecting the quote and the 'Chat with Quote' action again from the Client Dashboard.")
        if st.button("Return to Client Dashboard"):
            st.session_state.current_page = "Client Dashboard"
            st.rerun()
        return
    
    # Reset button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 New Chat"):
            st.session_state.quote_chat_history = []
            st.rerun()
    with col2:
        if pdf_size_kb > 200:
            st.warning("⚠️ This is a very large PDF. Chat processing may be slow and could time out.")
    
    # Chat message container
    if "quote_chat_history" not in st.session_state:
        st.session_state.quote_chat_history = []
    
    # Display chat history
    for msg in st.session_state.quote_chat_history:
        role = msg.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(msg.get("content", ""))
    
    # Processing indicator for ongoing queries
    if "chat_processing" not in st.session_state:
        st.session_state.chat_processing = False
    
    # Chat input
    user_input = st.chat_input("Ask a question about the quote...", disabled=st.session_state.chat_processing)
    if user_input and not st.session_state.chat_processing:
        # Add user message to chat history
        st.session_state.quote_chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Set processing flag to avoid multiple queries
        st.session_state.chat_processing = True
        st.rerun()
    
    # Process the query (after rerun if needed)
    if st.session_state.chat_processing and st.session_state.quote_chat_history and st.session_state.quote_chat_history[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.status("Analyzing document...", expanded=True) as status:
                try:
                    status.update(label="Retrieving relevant document sections...")
                    
                    from app import process_chat_query, get_current_context
                    context_type, context_data = get_current_context()
                    
                    status.update(label="Generating response...")
                    ai_response = process_chat_query(st.session_state.quote_chat_history[-1]["content"], context_type, context_data)
                    
                    # Success - update status
                    status.update(label="✅ Response ready", state="complete")
                    
                    # Add response to history
                    st.session_state.quote_chat_history.append({"role": "assistant", "content": ai_response})
                    
                    # Display the response
                    st.markdown(ai_response)
                    
                except Exception as e:
                    # Handle errors in processing
                    error_message = f"Sorry, I encountered an error processing your query: {str(e)}"
                    st.error(error_message)
                    
                    # Add error to chat history
                    st.session_state.quote_chat_history.append({"role": "assistant", "content": error_message})
                    
                    # Update status to show error
                    status.update(label="❌ Error in processing", state="error")
                    
                finally:
                    # Clear processing flag
                    st.session_state.chat_processing = False
                    
        # Rerun one more time to refresh the UI with the complete response
        st.rerun()
    
    # Return button
    if st.button("⬅️ Back to Client Dashboard"):
        st.session_state.current_page = "Client Dashboard"
        if st.session_state.profile_extraction_step == "action_selection":
            # Action hub is on Client Dashboard
            pass
        else:
            st.session_state.chat_context = None
            st.session_state.quote_chat_history = []
            st.session_state.chat_processing = False
        st.rerun()

def render_chat_ui(): 
    with st.sidebar.expander("💬 Chat Assistant", expanded=False):
        from app import get_current_context, process_chat_query 
        context_type, context_data = get_current_context()
        
        # Show context information
        if context_type == "quote": 
            st.markdown("**Context:** Quote processing")
            # Display PDF size for context
            if context_data and "full_pdf_text" in context_data:
                pdf_size_kb = len(context_data["full_pdf_text"]) / 1024
                if pdf_size_kb > 100:
                    st.caption(f"PDF Size: {pdf_size_kb:.1f}KB (large)")
        elif context_type == "client" and context_data: 
            st.markdown(f"**Context:** Client {context_data.get('customer_name', '')}")
        elif context_type == "crm": 
            st.markdown("**Context:** CRM management")
        else: 
            st.markdown("**Context:** General assistance")
        
        # Initialize processing state if not present
        if "sidebar_chat_processing" not in st.session_state:
            st.session_state.sidebar_chat_processing = False
            
        # Chat input
        user_query = st.text_input(
            "Ask a question:", 
            key="sidebar_chat_query",
            disabled=st.session_state.sidebar_chat_processing
        )
        
        # Process button
        if st.button("Send", key="send_chat_query_sidebar", disabled=st.session_state.sidebar_chat_processing):
            if user_query:
                # Add query to history
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                
                # Set processing flag
                st.session_state.sidebar_chat_processing = True
                
                # Trigger rerun to show processing state
                st.rerun()
        
        # Process the query (after rerun)
        if st.session_state.sidebar_chat_processing and st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
            with st.status("Processing...", expanded=True) as status:
                try:
                    # Get the last query from history
                    last_query = st.session_state.chat_history[-1]["content"]
                    
                    # Process the query
                    response = process_chat_query(last_query, context_type, context_data)
                    
                    # Add response to history
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    
                    # Clear input
                    st.session_state.sidebar_chat_query = ""
                    
                    # Update status
                    status.update(label="✅ Done", state="complete")
                    
                except Exception as e:
                    # Handle errors
                    error_msg = f"Error: {str(e)}"
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                    status.update(label="❌ Error", state="error")
                
                finally:
                    # Clear processing flag
                    st.session_state.sidebar_chat_processing = False
                
                # Rerun to refresh UI
                st.rerun()
        
        # Display chat history
        if st.session_state.chat_history:
            st.markdown("### Chat History")
            max_display = min(5, len(st.session_state.chat_history))
            for msg in st.session_state.chat_history[-max_display:]:
                if msg["role"] == "user": 
                    st.markdown(f"**You:** {msg['content']}")
                else: 
                    st.markdown(f"**Assistant:** {msg['content']}")
            
            if st.button("Clear History", key="clear_chat_sidebar"): 
                st.session_state.chat_history = []
                st.rerun() 