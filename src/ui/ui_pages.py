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
    st.title("Welcome to the QuoteFlow Document Assistant")
    if st.session_state.get("profile_extraction_step") == "action_selection" and st.session_state.get("confirmed_profile"):
        action = show_action_selection(st.session_state.get("confirmed_profile"))
        if action:
            handle_selected_action(action, st.session_state.get("confirmed_profile"))
            st.rerun()
        return
    st.markdown("""
    ## What This Application Does
    This tool helps you process machine quotes to generate various documents and manage client data.
    
    ## Getting Started
    Upload a quote PDF to extract client profile information or process it directly.
    """)
    uploaded_pdf = st.file_uploader("Choose PDF Quote", type="pdf", key="welcome_page_uploader")
    if uploaded_pdf:
        st.session_state.extracted_profile = None
        st.session_state.confirmed_profile = None
        st.session_state.profile_extraction_step = "ready_to_extract"
        st.session_state.selected_main_machines_profile = []
        st.session_state.selected_common_options_profile = []
        st.session_state.profile_machine_confirmation_step = "main_machines"
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Extract Client Profile", type="primary"):
                with st.spinner("Extracting client profile..."):
                    temp_pdf_path = os.path.join(".", uploaded_pdf.name)
                    try:
                        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf.getbuffer())
                        profile = extract_client_profile(temp_pdf_path)
                        if profile:
                            st.session_state.extracted_profile = profile
                            st.session_state.profile_extraction_step = "confirm"
                            st.rerun()
                        else: st.error("Failed to extract client profile. Please try again.")
                    finally:
                        if os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
        with col2:
            if st.button("🚀 Process Document Directly (GOA)", key="direct_process_btn"):
                st.session_state.current_page = "Quote Processing"
                TEMPLATE_FILE = "template.docx"
                if not os.path.exists(TEMPLATE_FILE): st.error(f"Template '{TEMPLATE_FILE}' not found.")
                else:
                    from app import perform_initial_processing # Assuming it's in app.py
                    if perform_initial_processing(uploaded_pdf, TEMPLATE_FILE):
                        st.session_state.processing_step = 1
                    else: st.error("Failed to start direct document processing.")
                st.rerun()
    if st.session_state.get("profile_extraction_step") == "confirm":
        if st.session_state.get("extracted_profile"):
            confirmed_profile_data = confirm_client_profile(st.session_state.get("extracted_profile"))
            if confirmed_profile_data:
                st.session_state.confirmed_profile = confirmed_profile_data
                st.session_state.current_client_profile = confirmed_profile_data 
                st.session_state.current_page = "Client Dashboard"
                st.session_state.profile_extraction_step = None 
                st.rerun()
        else: st.info("Upload a PDF to extract and confirm a client profile.")
    st.markdown("---")
    st.markdown("### Alternative Options")
    col_alt1, col_alt2, col_alt3 = st.columns(3)
    with col_alt1: 
        if st.button("👤 Client Dashboard", key="goto_dashboard"): 
            st.session_state.current_page = "Client Dashboard"; st.rerun()
    with col_alt2: 
        if st.button("⚙️ Process Quote for GOA", key="goto_processing"): 
            st.session_state.current_page = "Quote Processing"; st.rerun()
    with col_alt3: 
        if st.button("📒 View CRM Data", key="goto_crm"): 
            st.session_state.current_page = "CRM Management"; st.rerun()

def show_client_dashboard_page():
    st.title("👤 Client Dashboard")
    st.markdown("Select a client to view their profile and available actions, or upload a new quote on the Welcome page.")
    if not st.session_state.get('crm_data_loaded', False):
        from app import load_crm_data # Assuming it's in app.py
        load_crm_data()
    clients = st.session_state.all_crm_clients
    if not clients:
        st.info("No clients found. Upload a quote on the Welcome page to create a client profile.")
        if st.button("Go to Welcome Page", key="dash_to_welcome_no_clients"): st.session_state.current_page = "Welcome"; st.rerun()
        return
    search_term = st.text_input("Search clients (by name or quote ref)", key="client_dashboard_search_input")
    filtered_clients = [c for c in clients if (search_term.lower() in c.get("customer_name", "").lower() or 
                                            search_term.lower() in c.get("quote_ref", "").lower())] if search_term else clients
    if not filtered_clients and search_term: st.warning(f"No clients found matching '{search_term}'.")
    for client_summary_item in filtered_clients:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1: st.subheader(f"{client_summary_item.get('customer_name', 'N/A')}"); st.caption(f"Quote Ref: {client_summary_item.get('quote_ref', 'N/A')}")
            with col2: 
                processing_date_str = client_summary_item.get('processing_date', 'N/A'); 
                try: formatted_date = pd.to_datetime(processing_date_str).strftime('%Y-%m-%d %H:%M')
                except: formatted_date = processing_date_str
                st.caption(f"Last Processed: {formatted_date}")
            with col3:
                if st.button("View Actions", key=f"view_actions_{client_summary_item.get('id')}", use_container_width=True):
                    with st.spinner(f"Loading profile for {client_summary_item.get('quote_ref')}..."):
                        full_profile_data = load_full_client_profile(client_summary_item.get("quote_ref"))
                    if full_profile_data:
                        st.session_state.confirmed_profile = full_profile_data
                        st.session_state.profile_extraction_step = "action_selection" 
                        st.session_state.current_page = "Welcome" 
                        st.rerun()
                    else: st.error(f"Could not load full profile for {client_summary_item.get('quote_ref')}.")
            st.markdown("&nbsp;") 

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
        st.markdown("---"); 
        if st.button("Go to Export Documents Page", key="goa_goto_export"): st.session_state.current_page = "Export Documents"; st.rerun()

def show_export_documents():
    st.title("📦 Export Documents")
    from app import generate_export_document, calculate_machine_price, TEMPLATE_PACKING_SLIP, TEMPLATE_COMMERCIAL_INVOICE, TEMPLATE_CERTIFICATE_OF_ORIGIN

    st.subheader("Select Client for Export Documents")
    client_options_display = ["Select a Client..."] + [f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')} (ID: {c.get('id')})" for c in st.session_state.all_crm_clients]
    selected_client_option_str = st.selectbox("Choose client:", client_options_display, key=f"export_client_select_{st.session_state.run_key}", index=0)

    if selected_client_option_str != "Select a Client...":
        try:
            selected_id = int(selected_client_option_str.split("(ID: ")[-1][:-1])
            client_data = get_client_by_id(selected_id)
            if client_data:
                st.session_state.selected_client_for_detail_edit = client_data
                quote_ref = client_data.get('quote_ref')
                machines_data_db = load_machines_for_quote(quote_ref)
                
                if machines_data_db:
                    st.subheader("Generate Export Documents")
                    processed_machines = []
                    for machine_db_item in machines_data_db:
                        machine_detail = machine_db_item.get("machine_data", {})
                        machine_detail["id"] = machine_db_item.get("id")
                        processed_machines.append(machine_detail)
                    
                    common_items_from_profile = [] 
                    if processed_machines: common_items_from_profile = processed_machines[0].get("common_items", [])
                    st.session_state.identified_machines_data = {"machines": processed_machines, "common_items": common_items_from_profile}

                    with st.form(key=f"export_docs_form_{client_data.get('id')}"):
                        st.markdown("Select machines for export documents:")
                        selected_machine_indices_for_export = []
                        for i, machine_to_select in enumerate(processed_machines):
                            machine_name = machine_to_select.get("machine_name", f"Machine {i+1}")
                            machine_price = calculate_machine_price(machine_to_select)
                            if st.checkbox(f"{machine_name} (${machine_price:.2f})", value=True, key=f"export_sel_mach_{client_data.get('id')}_{i}"):
                                selected_machine_indices_for_export.append(i)
                        
                        include_common_for_export = st.checkbox("Include common items", value=True, key=f"export_inc_common_{client_data.get('id')}")
                        
                        available_templates_for_export = []
                        if os.path.exists(TEMPLATE_PACKING_SLIP): available_templates_for_export.append("Packing Slip")
                        if os.path.exists(TEMPLATE_COMMERCIAL_INVOICE): available_templates_for_export.append("Commercial Invoice")
                        if os.path.exists(TEMPLATE_CERTIFICATE_OF_ORIGIN): available_templates_for_export.append("Certificate of Origin")
                        
                        if not available_templates_for_export: 
                            st.warning("No export document templates found.")
                            template_type_export = None
                        else: 
                            template_type_export = st.radio("Select document type:", available_templates_for_export, key=f"export_template_type_{client_data.get('id')}")
                        
                        submit_export_button = st.form_submit_button("Generate Selected Export Document")

                    if submit_export_button:
                        if not selected_machine_indices_for_export: st.warning("Please select at least one machine.")
                        elif template_type_export:
                            selected_machines_for_doc = [processed_machines[i] for i in selected_machine_indices_for_export]
                            doc_type_map = {"Packing Slip": ("packing_slip", TEMPLATE_PACKING_SLIP), 
                                            "Commercial Invoice": ("commercial_invoice", TEMPLATE_COMMERCIAL_INVOICE),
                                            "Certificate of Origin": ("certificate_of_origin", TEMPLATE_CERTIFICATE_OF_ORIGIN)}
                            doc_type_key, template_path_for_doc = doc_type_map.get(template_type_export, (None,None))

                            if doc_type_key and template_path_for_doc:
                                if doc_type_key == "packing_slip":
                                    initial_packing_slip_data = generate_packing_slip_data(client_data, st.session_state.identified_machines_data.get("common_items", []) + [item for machine in selected_machines_for_doc for item in [machine.get("main_item")] + machine.get("add_ons",[]) if item])
                                    st.session_state.interactive_packing_slip_data = initial_packing_slip_data
                                    st.session_state.packing_slip_template_contexts = extract_placeholder_context_hierarchical(template_path_for_doc)
                                    st.session_state.show_packing_slip_editor = True
                                    st.session_state.current_packing_slip_client_data = client_data
                                    st.session_state.current_packing_slip_selected_machines = selected_machines_for_doc
                                    st.session_state.current_packing_slip_include_common = include_common_for_export
                                    st.session_state.current_packing_slip_template_path = template_path_for_doc
                                    st.rerun()
                                else:
                                    with st.spinner(f"Generating {template_type_export}..."):
                                        output_path = generate_export_document(doc_type_key, selected_machines_for_doc, include_common_for_export, template_path_for_doc, client_data)
                                        if output_path and os.path.exists(output_path):
                                            st.success(f"{template_type_export} generated: {os.path.basename(output_path)}")
                                            with open(output_path, "rb") as f: st.download_button(f"Download {template_type_export}", f, file_name=os.path.basename(output_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                                        else: st.error(f"Failed to generate {template_type_export}.")
                            else: st.error("Selected document type or template path is invalid.")
                        else: st.error("Please select a document type.")
                
                if st.session_state.get("show_packing_slip_editor", False):
                    st.subheader(f"📝 Edit Packing Slip Data for {client_data.get('customer_name')}")
                    interactive_data = st.session_state.interactive_packing_slip_data
                    template_contexts = st.session_state.packing_slip_template_contexts
                    edited_data_from_ui = {}
                    for ph, context_desc in template_contexts.items():
                        current_val = interactive_data.get(ph, "")
                        user_label = f"{context_desc} (Placeholder: {ph})" if context_desc and context_desc != ph else ph
                        if ph.endswith("_check"):
                            edited_data_from_ui[ph] = st.selectbox(user_label, options=["YES", "NO"], index=0 if current_val == "NO" else 1, key=f"edit_ps_{ph}")
                        else:
                            edited_data_from_ui[ph] = st.text_input(user_label, value=current_val, key=f"edit_ps_{ph}")
                    
                    if st.button("💾 Save Changes and Generate Packing Slip", key="save_generate_ps"):
                        st.session_state.interactive_packing_slip_data = edited_data_from_ui
                        current_client_data = st.session_state.current_packing_slip_client_data
                        current_template_path = st.session_state.current_packing_slip_template_path
                        output_filename_ps = f"packing_slip_{current_client_data.get('quote_ref', 'client')}_{st.session_state.run_key}.docx"
                        fill_word_document_from_llm_data(current_template_path, st.session_state.interactive_packing_slip_data, output_filename_ps)
                        if os.path.exists(output_filename_ps):
                            st.success(f"Packing Slip generated with your edits: {output_filename_ps}")
                            with open(output_filename_ps, "rb") as fp_ps: 
                                st.download_button("Download Edited Packing Slip", fp_ps, os.path.basename(output_filename_ps), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key="dl_edited_ps")
                        else: st.error("Failed to generate packing slip with edits.")
                        st.session_state.show_packing_slip_editor = False
                        st.rerun()

                elif not machines_data_db:
                    st.warning("No machines identified for this client. Process their quote first or upload PDF below.")
                    pdf_for_export_processing = st.file_uploader("Upload Quote PDF to process for export documents:", type="pdf", key=f"export_pdf_direct_upload_{client_data.get('id')}")
                    if pdf_for_export_processing and st.button("Process Uploaded PDF for Export", key=f"process_export_direct_pdf_{client_data.get('id')}"):
                        from app import quick_extract_and_catalog
                        with st.spinner("Processing PDF for export..."):
                            qec_result = quick_extract_and_catalog(pdf_for_export_processing)
                            if qec_result:
                                st.success(f"PDF processed and cataloged for quote {qec_result.get('quote_ref')}. Please re-select client to see machines.")
                                st.rerun()
                            else: st.error("Failed to process uploaded PDF for export.")
            else: st.error(f"Could not load client data for ID: {selected_id}")
        except ValueError:
             st.error("Invalid client selection string.")
        except Exception as e:
            st.error(f"Error in Export Documents: {e}"); traceback.print_exc()
    else:
        st.info("Select a client to generate export documents.")

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
                client_tab1, client_tab2, client_tab3, client_tab4 = st.tabs(["📋 Client Details", "💲 Priced Items", "📄 Export Docs (Client)", "📤 Upload PDF (Client)"])
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
                    st.subheader("📄 Generate Export Documents (Client Focus)")
                    show_export_documents()
                with client_tab4: 
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
    st.title("💬 Chat with Quote")
    
    chat_context = st.session_state.get("chat_context")
    # Retrieve the action_profile that was set when entering the chat page
    # This profile is essential for returning to the action hub correctly.
    action_profile_for_chat = st.session_state.get("action_profile") 

    if not chat_context or not action_profile_for_chat:
        st.warning("No quote context available for chat or initiating profile missing.")
        st.info("Please try selecting the quote and the 'Chat with Quote' action again from the Client Dashboard or Welcome Page.")
        if st.button("Return to Welcome Page"):
            st.session_state.current_page = "Welcome"
            st.session_state.chat_context = None
            st.session_state.action_profile = None # Clear this too
            st.session_state.quote_chat_history = []
            st.session_state.profile_extraction_step = None # Ensure welcome page starts fresh if context is lost
            st.session_state.confirmed_profile = None
            st.rerun()
        return
    
    client_info = chat_context.get("client_info", {})
    if client_info: st.markdown(f"**Client:** {client_info.get('client_name', 'N/A')} - **Quote:** {client_info.get('quote_ref', 'N/A')}")
    st.markdown("### Ask about this quote")
    if "quote_chat_history" not in st.session_state: st.session_state.quote_chat_history = []
    for message in st.session_state.quote_chat_history: 
        with st.chat_message(message["role"]): st.write(message["content"])
    if prompt := st.chat_input("Your question..."):
        st.session_state.quote_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.write(prompt)
        with st.spinner("Thinking..."):
            try:
                full_pdf_text = st.session_state.chat_context.get("full_pdf_text", "")
                # Assuming answer_pdf_question is available from llm_handler
                from src.utils.llm_handler import answer_pdf_question 
                response = answer_pdf_question(prompt, [], full_pdf_text, {})
                st.session_state.quote_chat_history.append({"role": "assistant", "content": response})
                with st.chat_message("assistant"): st.write(response)
            except Exception as e: st.error(f"Error in chat: {e}"); traceback.print_exc()
    st.markdown("---")
    if st.button("Return to Action Selection", key="chat_return_actions"):
        # Use the action_profile_for_chat that was stored when entering the chat page
        if action_profile_for_chat:
            st.session_state.confirmed_profile = action_profile_for_chat 
            st.session_state.profile_extraction_step = "action_selection"
            st.session_state.current_page = "Welcome" # Action hub is on Welcome
        else:
            # Fallback if action_profile_for_chat was somehow lost, though the check at the start should prevent this.
            st.session_state.current_page = "Welcome"
            st.session_state.profile_extraction_step = None 
            st.session_state.confirmed_profile = None
        
        # Always clear chat-specific states when leaving the chat page this way
        st.session_state.chat_context = None
        st.session_state.quote_chat_history = []
        st.session_state.action_profile = None # Clear the specific action_profile for chat too
        st.rerun()

def render_chat_ui(): 
    with st.sidebar.expander("💬 Chat Assistant", expanded=False):
        from app import get_current_context, process_chat_query 
        context_type, context_data = get_current_context()
        if context_type == "quote": st.markdown("**Context:** Quote processing")
        elif context_type == "client" and context_data: st.markdown(f"**Context:** Client {context_data.get('customer_name', '')}")
        elif context_type == "crm": st.markdown("**Context:** CRM management")
        else: st.markdown("**Context:** General assistance")
        user_query = st.text_input("Ask a question:", key="sidebar_chat_query")
        if st.button("Send", key="send_chat_query_sidebar"):
            if user_query:
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                response = process_chat_query(user_query, context_type, context_data)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.session_state.sidebar_chat_query = ""; st.rerun()
        if st.session_state.chat_history:
            st.markdown("### Chat History (Sidebar)")
            max_display = min(5, len(st.session_state.chat_history))
            for msg in st.session_state.chat_history[-max_display:]:
                if msg["role"] == "user": st.markdown(f"**You:** {msg['content']}")
                else: st.markdown(f"**Assistant:** {msg['content']}")
            if st.button("Clear History", key="clear_chat_sidebar"): st.session_state.chat_history = []; st.rerun() 