import streamlit as st
import os
import json
import pandas as pd # For st.dataframe
from typing import Dict, List, Optional
import traceback # For detailed error logging

# Import utility functions from the project
from pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from template_utils import extract_placeholder_context_hierarchical # If needed for profile confirmation display
from llm_handler import configure_gemini_client, answer_pdf_question # For client profile extraction, chat features
from crm_utils import save_client_info, save_priced_items, save_machines_data, save_document_content, load_document_content, get_client_by_id, load_priced_items_for_quote, load_machines_for_quote, load_all_clients

# Moved from app.py
def extract_client_profile(pdf_path):
    """
    Extract standard client information from PDF and build comprehensive profile
    """
    try:
        # Extract full text for LLM processing
        full_text = extract_full_pdf_text(pdf_path)
        
        # Extract line items
        line_items = extract_line_item_details(pdf_path)
        
        # Define standard fields based on mapping_mailmerge.txt
        standard_fields = [
            "Company",
            "Customer",
            "Machine",
            "Quote No",
            "Serial Number",
            "Sold to/Address 1",
            "Sold to/Address 2",
            "Sold to/Address 3",
            "Ship to/Address 1",
            "Ship to/Address 2",
            "Ship to/Address 3",
            "Telefone",
            "Customer PO",
            "Order date",
            "Via",
            "Incoterm",
            "Tax ID",
            "H.S",
            "Customer Number",
            "Customer contact"
        ]
        
        # Use LLM to extract client information with specific field focus
        prompt = f"""
        Extract all of the following standard fields from this quote PDF text.
        Be thorough and find as many as possible.
        Return results in JSON format with exactly these field names:
        
        {', '.join(standard_fields)}
        
        If a value is not found for a field, return an empty string for that field.
        Ensure all fields are present in the JSON, even if their values are empty.
        
        PDF text:
        {full_text[:8000]}  # Increased text limit slightly
        """
        
        if not configure_gemini_client():
            return None
            
        client_info = {}
        try:
            # Use the LLM to extract client info
            from llm_handler import GENERATIVE_MODEL, genai # Directly use the configured model
            generation_config = genai.types.GenerationConfig(
                temperature=0.2, # Lower temperature for more focused output
                top_p=0.95,
                max_output_tokens=2048
            )
            response = GENERATIVE_MODEL.generate_content(
                prompt,
                generation_config=generation_config
            )
            response_text = response.text
            
            # Try to parse as JSON
            import json
            import re
            
            # Look for JSON pattern in the response
            json_match = re.search(r'{.*}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                client_info = json.loads(json_str)
            else:
                # Fallback to extracting quote ref from filename
                client_info = {
                    "Quote No": os.path.basename(pdf_path).split('.')[0],
                    "Customer": "",
                    "Company": ""
                }
        except Exception as e:
            print(f"Error extracting client info via LLM: {e}")
            # Fallback to simple extraction
            client_info = {
                "Quote No": os.path.basename(pdf_path).split('.')[0],
                "Customer": "",
                "Company": ""
            }
        
        # Map standard fields to client_info structure
        mapped_client_info = {
            "client_name": client_info.get("Customer", "") or client_info.get("Company", ""),
            "quote_ref": client_info.get("Quote No", os.path.basename(pdf_path).split('.')[0]),
            "contact_person": client_info.get("Customer contact", ""),
            "phone": client_info.get("Telefone", ""),
            "billing_address": "\n".join([
                client_info.get("Sold to/Address 1", ""),
                client_info.get("Sold to/Address 2", ""),
                client_info.get("Sold to/Address 3", "")
            ]).strip(),
            "shipping_address": "\n".join([
                client_info.get("Ship to/Address 1", ""),
                client_info.get("Ship to/Address 2", ""),
                client_info.get("Ship to/Address 3", "")
            ]).strip(),
            # "machine_model": client_info.get("Machine", ""), # Removed single machine model
            "customer_po": client_info.get("Customer PO", ""),
            "incoterm": client_info.get("Incoterm", ""),
            "quote_date": client_info.get("Order date", "")
        }
        
        # Identify machines from line items
        # We need group_items_by_confirmed_machines here, or a simplified version
        # For now, let's use the existing identify_machines_from_items for initial grouping
        machines_data = identify_machines_from_items(line_items)
        
        # Build the complete profile
        profile = {
            "client_info": mapped_client_info,
            "standard_fields": client_info,  # Keep original extraction for reference
            "line_items": line_items,
            "machines_data": machines_data, # This will be refined by user confirmation
            "full_text": full_text,
            "pdf_filename": os.path.basename(pdf_path)
        }
        
        return profile
    except Exception as e:
        print(f"Error in extract_client_profile: {e}")
        traceback.print_exc()
        return None

def confirm_client_profile(extracted_profile):
    """
    Display UI for confirming and editing client profile information
    Returns confirmed profile data
    """
    st.subheader("📋 Confirm Client Profile")
    
    if not extracted_profile:
        st.error("No profile data to confirm.")
        return None
    
    # Import group_items_by_confirmed_machines from app.py or app_utils.py if moved
    # For now, assuming it's accessible or defined in this scope if needed for re-grouping during confirmation
    from app import group_items_by_confirmed_machines # Temporary direct import

    # Initialize session state for machine confirmation if not present
    if "selected_main_machines_profile" not in st.session_state:
        st.session_state.selected_main_machines_profile = []
    if "selected_common_options_profile" not in st.session_state:
        st.session_state.selected_common_options_profile = []
    if "profile_machine_confirmation_step" not in st.session_state:
        st.session_state.profile_machine_confirmation_step = "main_machines"

    # Create a copy for editing
    confirmed_profile = extracted_profile.copy()
    client_info = confirmed_profile.get("client_info", {}).copy()
    standard_fields = confirmed_profile.get("standard_fields", {}).copy()
    
    # Client Information Form
    st.markdown("### 1. Client Information")
    with st.form("client_info_form"):
        tab1, tab2 = st.tabs(["Basic Info", "Advanced Info"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                client_info["client_name"] = st.text_input(
                    "Client/Company Name", 
                    value=client_info.get("client_name", "")
                )
                client_info["contact_person"] = st.text_input(
                    "Contact Person", 
                    value=client_info.get("contact_person", "")
                )
                client_info["phone"] = st.text_input(
                    "Phone", 
                    value=client_info.get("phone", "")
                )
                client_info["quote_ref"] = st.text_input(
                    "Quote Reference", 
                    value=client_info.get("quote_ref", "") or confirmed_profile.get("pdf_filename", "").split('.')[0]
                )
            
            with col2:
                client_info["customer_po"] = st.text_input(
                    "Customer PO", 
                    value=client_info.get("customer_po", "")
                )
                client_info["quote_date"] = st.text_input(
                    "Quote Date", 
                    value=client_info.get("quote_date", "")
                )
                client_info["incoterm"] = st.text_input(
                    "Incoterm", 
                    value=client_info.get("incoterm", "")
                )
                client_info["country_destination"] = st.text_input( # Added country_destination
                    "Country Destination",
                    value=client_info.get("country_destination", "")
                )
        
        with tab2:
            col1, col2 = st.columns(2)
            
            with col1:
                client_info["billing_address"] = st.text_area(
                    "Billing Address", 
                    value=client_info.get("billing_address", ""),
                    height=150
                )
                
                standard_fields["Tax ID"] = st.text_input(
                    "Tax ID",
                    value=standard_fields.get("Tax ID", "")
                )
                
                standard_fields["H.S"] = st.text_input(
                    "H.S Code",
                    value=standard_fields.get("H.S", "")
                )
            
            with col2:
                client_info["shipping_address"] = st.text_area(
                    "Shipping Address", 
                    value=client_info.get("shipping_address", ""),
                    height=150
                )
                
                standard_fields["Via"] = st.text_input(
                    "Shipping Method",
                    value=standard_fields.get("Via", "")
                )
                
                standard_fields["Serial Number"] = st.text_input(
                    "Serial Number",
                    value=standard_fields.get("Serial Number", "")
                )
        
        # Only show confirm profile button if machine grouping is done
        if st.session_state.profile_machine_confirmation_step == "done":
            submit_button = st.form_submit_button("Confirm and Save Profile")
        else:
            st.form_submit_button("Next: Confirm Machines", disabled=True)
            submit_button = False
    
    confirmed_profile["client_info"] = client_info
    confirmed_profile["standard_fields"] = standard_fields
    
    st.markdown("### 2. Confirm Identified Machines")
    items_for_machine_confirmation = confirmed_profile.get("line_items", [])
    
    if not items_for_machine_confirmation:
        st.info("No line items found in the quote to identify machines.")
        st.session_state.profile_machine_confirmation_step = "done"
    
    elif st.session_state.profile_machine_confirmation_step == "main_machines":
        st.markdown("Select all items that are **main machines**.")
        selected_indices_main = []
        with st.container():
            for i, item in enumerate(items_for_machine_confirmation):
                desc = item.get('description', 'No description')
                first_line = desc.split('\n')[0] if '\n' in desc else desc
                price_str = item.get('selection_text', '') or item.get('item_price_str', '')
                display_text = f"{first_line} ({price_str})"
                is_preselected = i in st.session_state.selected_main_machines_profile
                if st.checkbox(display_text, value=is_preselected, key=f"profile_machine_cb_{i}"):
                    selected_indices_main.append(i)
        st.session_state.selected_main_machines_profile = selected_indices_main
        if st.button("Confirm Main Machines", key="profile_confirm_main_machines"):
            if not selected_indices_main:
                st.warning("Please select at least one main machine.")
            else:
                st.session_state.profile_machine_confirmation_step = "common_options"
                st.rerun()
                
    elif st.session_state.profile_machine_confirmation_step == "common_options":
        st.markdown("Select items that are **common options** (applying to all machines).")
        main_machine_indices = st.session_state.selected_main_machines_profile
        available_indices_common = []
        available_options_common = []
        for i, item in enumerate(items_for_machine_confirmation):
            if i not in main_machine_indices:
                desc = item.get('description', 'No description')
                first_line = desc.split('\n')[0] if '\n' in desc else desc
                price_str = item.get('selection_text', '') or item.get('item_price_str', '')
                display_text = f"{first_line} ({price_str})"
                available_indices_common.append(i)
                available_options_common.append(display_text)
        selected_positions_common = []
        with st.container():
            for pos, i in enumerate(available_indices_common):
                display_text = available_options_common[pos]
                is_preselected = i in st.session_state.selected_common_options_profile
                if st.checkbox(display_text, value=is_preselected, key=f"profile_common_cb_{i}"):
                    selected_positions_common.append(pos)
        selected_indices_common = [available_indices_common[pos] for pos in selected_positions_common]
        st.session_state.selected_common_options_profile = selected_indices_common
        col_back, col_confirm_common = st.columns(2)
        with col_back:
            if st.button("Back to Main Machines", key="profile_back_to_main"):
                st.session_state.profile_machine_confirmation_step = "main_machines"
                st.rerun()
        with col_confirm_common:
            if st.button("Confirm Common Options & Group Machines", key="profile_confirm_common", type="primary"):
                updated_machines_data = group_items_by_confirmed_machines(
                    items_for_machine_confirmation,
                    st.session_state.selected_main_machines_profile,
                    st.session_state.selected_common_options_profile
                )
                confirmed_profile["machines_data"] = updated_machines_data
                st.session_state.extracted_profile["machines_data"] = updated_machines_data
                st.session_state.profile_machine_confirmation_step = "done"
                st.success("Machines re-grouped based on your selection.")
                st.rerun()
                
    elif st.session_state.profile_machine_confirmation_step == "done":
        st.markdown("### Machine Groupings")
        machines = confirmed_profile.get("machines_data", {}).get("machines", [])
        if machines:
            for i, machine in enumerate(machines):
                with st.expander(f"Machine {i+1}: {machine.get('machine_name', 'Unknown')}", expanded=i==0):
                    st.markdown(f"**Main Item:** {machine.get('main_item', {}).get('description', 'No description')}")
                    add_ons = machine.get('add_ons', [])
                    if add_ons:
                        st.markdown(f"**Add-ons:** {len(add_ons)} items")
                        for j, addon in enumerate(add_ons[:3]):
                            st.markdown(f"- {addon.get('description', '')[:100]}...")
                        if len(add_ons) > 3:
                            st.markdown(f"- ... and {len(add_ons) - 3} more add-ons")
                    else:
                        st.markdown("**Add-ons:** None")
        else:
            st.info("No machines identified based on current selections.")
        common_items = confirmed_profile.get("machines_data", {}).get("common_items", [])
        if common_items:
            with st.expander("Common Items"):
                st.markdown(f"**{len(common_items)} common items**")
                for item in common_items:
                    st.markdown(f"- {item.get('description', '')[:100]}...")
        if st.button("Re-confirm Machines", key="profile_reconfirm_machines"):
            st.session_state.profile_machine_confirmation_step = "main_machines"
            st.rerun()

    if submit_button and st.session_state.profile_machine_confirmation_step == "done":
        if client_info.get("client_name") and client_info.get("quote_ref"):
            client_record = {
                "quote_ref": client_info.get("quote_ref"),
                "customer_name": client_info.get("client_name"),
                "machine_model": ", ".join([m.get("machine_name", "") for m in confirmed_profile.get("machines_data", {}).get("machines", [])]),
                "country_destination": client_info.get("country_destination", ""),
                "sold_to_address": client_info.get("billing_address"),
                "ship_to_address": client_info.get("shipping_address"),
                "telephone": client_info.get("phone"),
                "customer_contact_person": client_info.get("contact_person"),
                "customer_po": client_info.get("customer_po"),
                "incoterm": client_info.get("incoterm"),
                "quote_date": client_info.get("quote_date")
            }
            client_record["tax_id"] = standard_fields.get("Tax ID", "")
            client_record["hs_code"] = standard_fields.get("H.S", "")
            client_record["shipping_method"] = standard_fields.get("Via", "")
            client_record["serial_number"] = standard_fields.get("Serial Number", "")
            
            if save_client_info(client_record):
                st.success("Client profile saved to database.")
                if confirmed_profile.get("line_items"):
                    save_priced_items(client_info.get("quote_ref"), confirmed_profile.get("line_items"))
                if confirmed_profile.get("machines_data"):
                    save_machines_data(client_info.get("quote_ref"), confirmed_profile.get("machines_data"))
                save_document_content(
                    client_info.get("quote_ref"),
                    confirmed_profile.get("full_text", ""),
                    confirmed_profile.get("pdf_filename", "")
                )
                # Call load_crm_data from app.py or pass it as an argument if needed to refresh lists
                # For now, assuming direct call might error or session_state is used by load_crm_data directly
                st.session_state.all_crm_clients = load_all_clients() # Direct call to refresh
                return confirmed_profile
            else:
                st.error("Failed to save client profile to database.")
                return None
        else:
            st.warning("Client name and quote reference are required to save.")
            return None
    return None

def show_action_selection(client_profile):
    """
    Display action selection hub interface
    """
    st.subheader("🎯 Select an Action")
    if not client_profile:
        st.error("No client profile data available.")
        return None
    client_info = client_profile.get("client_info", {})
    standard_fields = client_profile.get("standard_fields", {})
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.markdown(f"### {client_info.get('client_name', 'Unknown Client')}")
            st.markdown(f"**Quote:** {client_info.get('quote_ref', 'N/A')}")
            st.markdown(f"**Contact:** {client_info.get('contact_person', 'N/A')}")
            if client_info.get("phone"): st.markdown(f"**Phone:** {client_info.get('phone', 'N/A')}")
        with col2:
            machines_list = client_profile.get("machines_data", {}).get("machines", [])
            if machines_list:
                models_str = ", ".join([m.get("machine_name", "Unknown") for m in machines_list[:3]])
                if len(machines_list) > 3: models_str += f" and {len(machines_list) - 3} more"
                st.markdown(f"**Machine Models:** {models_str}")
            else: st.markdown("**Machine Models:** Not Identified")
            if client_info.get("incoterm"): st.markdown(f"**Incoterm:** {client_info.get('incoterm', 'N/A')}")
            if client_info.get("quote_date"): st.markdown(f"**Date:** {client_info.get('quote_date', 'N/A')}")
            if client_info.get("customer_po"): st.markdown(f"**PO:** {client_info.get('customer_po', 'N/A')}")
        with col3:
            machines_count = len(client_profile.get("machines_data", {}).get("machines", []))
            items_count = len(client_profile.get("line_items", []))
            st.metric("Machines", machines_count)
            st.metric("Line Items", items_count)
    st.markdown("### Available Actions")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 📄 Generate GOA Document")
            st.markdown("Create General Order Agreement documents for specific machines")
            if st.button("Generate GOA", key="action_goa", use_container_width=True):
                st.session_state.current_action = "goa_generation"
                st.session_state.action_profile = client_profile
                return "goa_generation"
    with col2:
        with st.container(border=True):
            st.markdown("### 📦 Export Documents")
            st.markdown("Create packing slips, commercial invoices and certificates")
            if st.button("Export Documents", key="action_export", use_container_width=True):
                st.session_state.current_action = "export_documents"
                st.session_state.action_profile = client_profile
                return "export_documents"
    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.markdown("### ✏️ Edit Profile")
            st.markdown("Update client information and manage machines")
            if st.button("Edit Profile", key="action_edit", use_container_width=True):
                st.session_state.current_action = "edit_profile"
                st.session_state.action_profile = client_profile
                return "edit_profile"
    with col4:
        with st.container(border=True):
            st.markdown("### 💬 Chat with Quote")
            st.markdown("Ask questions about the quote and get answers")
            if st.button("Chat Interface", key="action_chat", use_container_width=True):
                st.session_state.current_action = "chat"
                st.session_state.action_profile = client_profile
                return "chat"
    with st.expander("View Full Profile Details", expanded=False):
        tab1, tab2 = st.tabs(["Addresses", "Additional Fields"])
        with tab1:
            col1, col2 = st.columns(2)
            with col1: st.markdown("**Billing Address:**"); st.text(client_info.get("billing_address", "Not provided"))
            with col2: st.markdown("**Shipping Address:**"); st.text(client_info.get("shipping_address", "Not provided"))
        with tab2:
            st.markdown("**Additional Information:**")
            extra_fields = [(k,v) for k,v in standard_fields.items() if v and k not in ["Customer", "Company", "Quote No", "Machine"]]
            if extra_fields: [st.markdown(f"**{k}:** {v}") for k,v in extra_fields]
            else: st.info("No additional information available")
    return None

def handle_selected_action(action, profile_data):
    """
    Route to the appropriate function based on selected action
    """
    # TEMPLATE_FILE might be needed if not globally accessible in app.py
    TEMPLATE_FILE = "template.docx" # Define locally if needed or pass as arg

    if action == "goa_generation":
        st.session_state.current_page = "Quote Processing"
        st.session_state.processing_step = 1
        st.session_state.full_pdf_text = profile_data.get("full_text", "")
        st.session_state.items_for_confirmation = profile_data.get("line_items", [])
        st.session_state.processing_done = True
        if os.path.exists(TEMPLATE_FILE):
            st.session_state.template_contexts = extract_placeholder_context_hierarchical(TEMPLATE_FILE)
        machines_data = profile_data.get("machines_data", {})
        st.session_state.selected_main_machines = []
        st.session_state.selected_common_options = []
        for i, item in enumerate(st.session_state.items_for_confirmation):
            is_main_machine = any(machine.get("main_item") == item for machine in machines_data.get("machines", []))
            if is_main_machine: st.session_state.selected_main_machines.append(i)
            elif any(common_item == item for common_item in machines_data.get("common_items", [])):
                 st.session_state.selected_common_options.append(i)
        return
    elif action == "export_documents":
        st.session_state.current_page = "Export Documents"
        client_info = profile_data.get("client_info", {})
        quote_ref = client_info.get("quote_ref")
        if st.session_state.all_crm_clients:
            st.session_state.selected_client_for_detail_edit = next((c for c in st.session_state.all_crm_clients if c.get("quote_ref") == quote_ref), None)
        return
    elif action == "edit_profile":
        st.session_state.current_page = "CRM Management"
        client_info = profile_data.get("client_info", {})
        quote_ref = client_info.get("quote_ref")
        if st.session_state.all_crm_clients:
            selected_client = next((c for c in st.session_state.all_crm_clients if c.get("quote_ref") == quote_ref), None)
            if selected_client:
                st.session_state.selected_client_for_detail_edit = selected_client
                st.session_state.editing_client_id = selected_client.get("id")
        return
    elif action == "chat":
        st.session_state.current_page = "Chat"
        st.session_state.chat_context = {
            "full_pdf_text": profile_data.get("full_text", ""),
            "client_info": profile_data.get("client_info", {})
        }
        return
    return

def load_full_client_profile(quote_ref: str) -> Optional[Dict]:
    """Loads all data for a client to reconstruct the profile object."""
    client_info_db = None
    if st.session_state.all_crm_clients:
        client_summary = next((c for c in st.session_state.all_crm_clients if c.get("quote_ref") == quote_ref), None)
        if client_summary: client_info_db = get_client_by_id(client_summary.get("id"))
    if not client_info_db: return None

    client_info_app_structure = {
        "client_name": client_info_db.get("customer_name", ""), "quote_ref": client_info_db.get("quote_ref", ""),
        "contact_person": client_info_db.get("customer_contact_person", ""), "phone": client_info_db.get("telephone", ""),
        "billing_address": client_info_db.get("sold_to_address", ""), "shipping_address": client_info_db.get("ship_to_address", ""),
        "customer_po": client_info_db.get("customer_po", ""), "incoterm": client_info_db.get("incoterm", ""),
        "quote_date": client_info_db.get("quote_date", ""), "country_destination": client_info_db.get("country_destination", "")
    }
    line_items = load_priced_items_for_quote(quote_ref)
    machines_data_db = load_machines_for_quote(quote_ref)
    app_machines_list, app_common_items = [], []
    if machines_data_db and isinstance(machines_data_db, list) and len(machines_data_db) > 0 and machines_data_db[0].get("machine_data"):
        app_common_items = machines_data_db[0].get("machine_data", {}).get("common_items", [])
    for machine_record in machines_data_db or []:
        machine_detail = machine_record.get("machine_data", {})
        app_machines_list.append({
            "machine_name": machine_detail.get("machine_name"), "main_item": machine_detail.get("main_item"),
            "add_ons": machine_detail.get("add_ons", [])
        })
    machines_data_app_structure = {"machines": app_machines_list, "common_items": app_common_items}
    doc_content = load_document_content(quote_ref)
    full_text = doc_content.get("full_pdf_text", "") if doc_content else ""
    pdf_filename = doc_content.get("pdf_filename", "") if doc_content else ""
    standard_fields_reconstructed = {
        "Company": client_info_app_structure.get("client_name"), "Customer": client_info_app_structure.get("client_name"),
        "Machine": client_info_db.get("machine_model"), "Quote No": client_info_app_structure.get("quote_ref"),
        "Telefone": client_info_app_structure.get("phone"), "Customer contact": client_info_app_structure.get("contact_person"),
        "Customer PO": client_info_app_structure.get("customer_po"), "Order date": client_info_app_structure.get("quote_date"),
        "Incoterm": client_info_app_structure.get("incoterm"),
        "Sold to/Address 1": client_info_app_structure.get("billing_address", "").split('\n')[0] if client_info_app_structure.get("billing_address") else "",
        # Add other Sold to/Ship to address lines similarly if needed for standard_fields reconstruction
    }
    profile = {
        "client_info": client_info_app_structure, "standard_fields": standard_fields_reconstructed, 
        "line_items": line_items, "machines_data": machines_data_app_structure,
        "full_text": full_text, "pdf_filename": pdf_filename
    }
    return profile 