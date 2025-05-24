"""
GOA Document Assistant - Streamlit Application
"""
import streamlit as st
import os
import json
import pandas as pd
from typing import Dict, List
import traceback
import shutil

# Import utility functions
from pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from template_utils import extract_placeholders, extract_placeholder_context_hierarchical
from llm_handler import configure_gemini_client, get_all_fields_via_llm, get_machine_specific_fields_via_llm, get_llm_chat_update, answer_pdf_question
from doc_filler import fill_word_document_from_llm_data
from crm_utils import init_db, save_client_info, load_all_clients, get_client_by_id, update_client_record, save_priced_items, load_priced_items_for_quote, update_single_priced_item, delete_client_record, save_machines_data, load_machines_for_quote, save_machine_template_data, load_machine_template_data, save_document_content, load_document_content
from document_generators import generate_packing_slip_data, generate_commercial_invoice_data, generate_certificate_of_origin_data

# Initialize session state
def initialize_session_state(is_new_processing_run=False):
    """Initialize all session state variables."""
    # Initialize navigation and pages
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Welcome"
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Initialize processing step for wizard-style interface
    if "processing_step" not in st.session_state:
        st.session_state.processing_step = 0
    
    if is_new_processing_run or 'run_key' not in st.session_state: 
        st.session_state.run_key = st.session_state.get('run_key', 0) + (1 if is_new_processing_run else 0)

    # Reset other state variables
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

    # Add machine processing variables
    machine_keys_to_reset = [
        'identified_machines_data', 'selected_machine_index', 'machine_specific_filled_data', 
        'machine_docx_path', 'selected_machine_id', 'machine_confirmation_done',
        'common_options_confirmation_done', 'items_for_confirmation', 'selected_main_machines',
        'selected_common_options', 'manual_machine_grouping'
    ]
    machine_default_values = {
        'identified_machines_data': {}, 'selected_machine_index': 0, 'machine_specific_filled_data': {},
        'machine_docx_path': f"output_machine_specific_run{st.session_state.run_key}.docx",
        'selected_machine_id': None, 'machine_confirmation_done': False,
        'common_options_confirmation_done': False, 'items_for_confirmation': [],
        'selected_main_machines': [], 'selected_common_options': [],
        'manual_machine_grouping': {}
    }
    for key in machine_keys_to_reset:
        if key not in st.session_state or is_new_processing_run:
            st.session_state[key] = machine_default_values[key]

    if 'crm_data_loaded' not in st.session_state:
        st.session_state.crm_data_loaded = False
    if 'crm_form_data' not in st.session_state or is_new_processing_run:
        st.session_state.crm_form_data = {
            'quote_ref': '', 'customer_name': '', 'machine_model': '', 'country_destination': '',
            'sold_to_address': '', 'ship_to_address': '', 'telephone': '', 
            'customer_contact_person': '', 'customer_po': ''
        }

    if 'current_priced_items_for_editing' not in st.session_state or is_new_processing_run:
        st.session_state.current_priced_items_for_editing = []
    if 'edited_priced_items_df' not in st.session_state or is_new_processing_run:
        st.session_state.edited_priced_items_df = pd.DataFrame()

    if 'selected_client_for_detail_edit' not in st.session_state or is_new_processing_run:
        st.session_state.selected_client_for_detail_edit = None
    if 'edited_client_details_df' not in st.session_state or is_new_processing_run:
        st.session_state.edited_client_details_df = pd.DataFrame()

    if 'confirming_delete_client_id' not in st.session_state or is_new_processing_run:
        st.session_state.confirming_delete_client_id = None

def group_items_by_confirmed_machines(all_items, main_machine_indices, common_option_indices):
    """
    Group items based on user-confirmed main machines and common options.
    
    Args:
        all_items: List of all line items from the PDF
        main_machine_indices: Indices of items confirmed as main machines
        common_option_indices: Indices of items confirmed as common options
        
    Returns:
        Dict with "machines" list and "common_items" list
    """
    machines = []
    common_items = []
    remaining_items = list(range(len(all_items)))
    
    # Remove common options from remaining items and add to common_items list
    for idx in common_option_indices:
        if idx in remaining_items:
            remaining_items.remove(idx)
            common_items.append(all_items[idx])
    
    # Process each main machine
    for machine_idx in main_machine_indices:
        if machine_idx in remaining_items:
            remaining_items.remove(machine_idx)
            
            # Find the next main machine index to determine add-ons range
            next_machine_idx = float('inf')
            for next_idx in main_machine_indices:
                if next_idx > machine_idx and next_idx < next_machine_idx:
                    next_machine_idx = next_idx
            
            # Collect add-ons between this machine and the next
            add_ons = []
            for idx in list(remaining_items):  # Use a copy to avoid modification during iteration
                if idx > machine_idx and (idx < next_machine_idx or next_machine_idx == float('inf')):
                    add_ons.append(all_items[idx])
                    remaining_items.remove(idx)
            
            # Create machine object
            machine_name = all_items[machine_idx].get('description', '').split('\n')[0]
            machines.append({
                "machine_name": machine_name,
                "main_item": all_items[machine_idx],
                "add_ons": add_ons
            })
    
    # Any remaining items go to common items
    for idx in remaining_items:
        common_items.append(all_items[idx])
    
    return {
        "machines": machines,
        "common_items": common_items
    }

# Function to generate export document
def generate_export_document(document_type, selected_machines, include_common_items, template_file_path, client_data):
    """
    Generate a packing slip or commercial invoice for selected machines
    
    Args:
        document_type: "packing_slip", "commercial_invoice", or "certificate_of_origin"
        selected_machines: List of selected machine data dictionaries
        include_common_items: Whether to include common items
        template_file_path: Path to the document template
        client_data: Client information from database
        
    Returns:
        Path to generated document
    """
    try:
        # Get common items if requested
        common_items = []
        if include_common_items and "identified_machines_data" in st.session_state:
            common_items = st.session_state.identified_machines_data.get("common_items", [])
        
        # Create a list of all items to include in the document
        all_items = []
        
        # Add main machines and their add-ons
        for machine in selected_machines:
            # Add main machine
            main_item = machine.get("main_item", {})
            if main_item:
                all_items.append(main_item)
            
            # Add this machine's add-ons
            add_ons = machine.get("add_ons", [])
            all_items.extend(add_ons)
        
        # Add common items if requested
        if include_common_items:
            all_items.extend(common_items)
        
        # Create a filename for the generated document
        machine_names = "_".join([m.get("machine_name", "").replace(" ", "") for m in selected_machines])
        if len(machine_names) > 30:  # Avoid extremely long filenames
            machine_names = machine_names[:30] + "..."
        
        output_filename = f"{document_type}_{machine_names}_{st.session_state.run_key}.docx"
        
        # Prepare data for the document based on its type
        if document_type == "packing_slip":
            document_data = generate_packing_slip_data(client_data, all_items)
            
        elif document_type == "commercial_invoice":
            document_data = generate_commercial_invoice_data(client_data, all_items)
            
        elif document_type == "certificate_of_origin":
            document_data = generate_certificate_of_origin_data(client_data, all_items)
            
        else:
            raise ValueError(f"Unknown document type: {document_type}")
        
        # Fill the document with the prepared data
        fill_word_document_from_llm_data(template_file_path, document_data, output_filename)
        
        return output_filename
        
    except Exception as e:
        st.error(f"Error generating {document_type}: {e}")
        st.text(traceback.format_exc())
        return None

def quick_extract_and_catalog(uploaded_pdf_file):
    """
    Quickly extract data from PDF and save to CRM without going through the full GOA process
    """
    temp_pdf_path = None
    try:
        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf_file.getbuffer())
        
        # Replace st.status with regular progress messaging
        progress_placeholder = st.empty()
        progress_placeholder.info("Extracting and Cataloging Data...")
        
        # Extract data from PDF
        progress_placeholder.info("Extracting data from PDF...")
        extracted_items = extract_line_item_details(temp_pdf_path)
        full_text = extract_full_pdf_text(temp_pdf_path)
        
        if not extracted_items:
            st.warning("No items were extracted from PDF tables.")
            return None
        
        # Attempt to extract basic client info
        # For simplicity, use filename as quote_ref
        quote_ref = uploaded_pdf_file.name.split('.')[0]
        
        # Prepare basic client data payload
        client_info_payload = {
            "quote_ref": quote_ref,
            "customer_name": "",  # Will be filled later in the UI
            "machine_model": "",
            "country_destination": "",
            "sold_to_address": "",
            "ship_to_address": "",
            "telephone": "",
            "customer_contact_person": "",
            "customer_po": ""
        }
        
        # Save to database
        if save_client_info(client_info_payload):
            progress_placeholder.info(f"Basic client record created for quote: {quote_ref}")
            
            # Save the items to the database
            if save_priced_items(quote_ref, extracted_items):
                progress_placeholder.info(f"Saved {len(extracted_items)} items to database.")
            else:
                st.warning(f"Failed to save priced items for quote: {quote_ref}")
            
            # Save full text for future use
            if save_document_content(quote_ref, full_text, uploaded_pdf_file.name):
                progress_placeholder.info(f"Document content saved for future reference.")
            else:
                st.warning(f"Failed to save document content.")
            
            # Auto-identify machines (optional, for reference)
            machine_list = identify_machines_from_items(extracted_items)
            
            # Convert the machine list to the expected format with "machines" and "common_items" keys
            machine_data = {"machines": [], "common_items": []}
            
            for machine in machine_list:
                if machine.get("is_main_machine", True):
                    # For main machines, create the expected structure
                    main_item = machine.get("items", [])[0] if machine.get("items") else {}
                    add_ons = machine.get("items", [])[1:] if len(machine.get("items", [])) > 1 else []
                    
                    machine_data["machines"].append({
                        "machine_name": machine.get("name", "Unknown Machine"),
                        "main_item": main_item,
                        "add_ons": add_ons
                    })
                else:
                    # For common items (non-machines), add all items to common_items list
                    machine_data["common_items"].extend(machine.get("items", []))
            
            # Save the properly formatted machine data
            if save_machines_data(quote_ref, machine_data):
                progress_placeholder.info(f"Preliminary machine grouping saved.")
                # Log the saved machine data for debugging
                if machine_data["machines"]:
                    progress_placeholder.info(f"Identified {len(machine_data['machines'])} machine(s):")
                    machine_details = []
                    for i, m in enumerate(machine_data["machines"]):
                        machine_details.append(f"  {i+1}. {m.get('machine_name', 'Unknown')}")
                    progress_placeholder.info("\n".join(machine_details))
            else:
                st.warning(f"Failed to save machine groupings.")
            
            # Update final status
            progress_placeholder.success("Cataloging Complete!")
            
            # Refresh the CRM data
            load_crm_data()
            return {"quote_ref": quote_ref, "items": extracted_items}
        else:
            st.error(f"Failed to create client record for quote: {quote_ref}")
            return None
    except Exception as e:
        st.error(f"Error in quick extraction: {e}")
        st.text(traceback.format_exc())
        return None
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)

def perform_initial_processing(uploaded_pdf_file, template_file_path):
    initialize_session_state(is_new_processing_run=True) # Reset state for a new run
    temp_pdf_path = None 
    try:
        if not configure_gemini_client():
            st.session_state.error_message = "Failed to configure LLM client. Check API key."
            return

        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf_file.getbuffer())
        
        with st.status("Processing PDF and Template...", expanded=True) as status_bar:
            st.write("Extracting data from PDF...")
            st.session_state.selected_pdf_items_structured = extract_line_item_details(temp_pdf_path)
            st.session_state.full_pdf_text = extract_full_pdf_text(temp_pdf_path)
            
            # Store items for confirmation (we'll let the user confirm machines rather than auto-detecting)
            st.session_state.items_for_confirmation = st.session_state.selected_pdf_items_structured
            
            # Make initial guesses for main machines and common options
            initial_machine_data = identify_machines_from_items(st.session_state.selected_pdf_items_structured)
            
            # Pre-select indices based on algorithm's best guesses
            preselected_machines = []
            preselected_common = []
            
            for i, item in enumerate(st.session_state.selected_pdf_items_structured):
                # Check if this item is a main item in any machine from the auto-detection
                is_main_machine = False
                for machine in initial_machine_data.get("machines", []):
                    if machine.get("main_item") == item:
                        is_main_machine = True
                        preselected_machines.append(i)
                        break
                
                # Check if this item is in common items from auto-detection
                if not is_main_machine:
                    for common_item in initial_machine_data.get("common_items", []):
                        if common_item == item:
                            preselected_common.append(i)
                            break
            
            st.session_state.selected_main_machines = preselected_machines
            st.session_state.selected_common_options = preselected_common
            
            # Extract selected descriptions for LLM backup
            st.session_state.selected_pdf_descs = [item.get("description","") for item in st.session_state.selected_pdf_items_structured if item.get("description")]

            if not st.session_state.selected_pdf_descs:
                st.warning("No selected item descriptions were extracted from PDF tables for LLM.")
            if not st.session_state.full_pdf_text: st.warning("Could not extract full text from PDF.")

            st.write("Analyzing template...")
            all_placeholders = extract_placeholders(template_file_path)
            st.session_state.template_contexts = extract_placeholder_context_hierarchical(template_file_path)
            if not st.session_state.template_contexts: raise ValueError("Could not extract placeholder contexts.")

            # Create default data dict
            initial_data_dict = {ph: ("NO" if ph.endswith("_check") else "") for ph in all_placeholders}

            # Skip initial LLM processing for all items - we'll process machine-specific later
            st.session_state.llm_initial_filled_data = initial_data_dict.copy()
            st.session_state.llm_corrected_filled_data = initial_data_dict.copy()

            # Create initial empty document for reference
            st.write(f"Creating initial blank document template: {st.session_state.initial_docx_path}...")
            fill_word_document_from_llm_data(template_file_path, initial_data_dict, st.session_state.initial_docx_path)
            if os.path.exists(st.session_state.initial_docx_path):
                 shutil.copy(st.session_state.initial_docx_path, st.session_state.corrected_docx_path)
            else:
                st.warning(f"Initial document {st.session_state.initial_docx_path} was not created. Cannot copy to corrected path.")
            
            status_bar.update(label="Saving to CRM...")
            # Prepare main client data 
            client_info_payload = {
                "quote_ref": uploaded_pdf_file.name.split('.')[0],  # Use filename as default quote_ref
                "customer_name": "",
                "machine_model": "",
                "country_destination": "",
                "sold_to_address": "",
                "ship_to_address": "",
                "telephone": "",
                "customer_contact_person": "",
                "customer_po": ""
            }
            
            # Save main client info
            if save_client_info(client_info_payload):
                st.write(f"Main client info for '{client_info_payload['quote_ref']}' saved/updated.")
                
                # Save priced items
                if st.session_state.selected_pdf_items_structured:
                    if save_priced_items(client_info_payload['quote_ref'], st.session_state.selected_pdf_items_structured):
                        st.write(f"Priced items for '{client_info_payload['quote_ref']}' saved.")
                    else:
                        st.warning(f"Failed to save priced items for '{client_info_payload['quote_ref']}'.")
                
                # Save PDF text content for future chat sessions
                if st.session_state.full_pdf_text:
                    if save_document_content(client_info_payload['quote_ref'], 
                                          st.session_state.full_pdf_text, 
                                          uploaded_pdf_file.name):
                        st.write(f"Document content saved for future chat sessions.")
                else:
                        st.warning(f"Failed to save document content for future chat.")
                
                # We'll save machines after user confirmation
                load_crm_data() # Refresh CRM data in session state after all saves
            else: 
                st.warning(f"Failed to save main client info for quote '{client_info_payload['quote_ref']}'. Priced items not saved.")
            
            status_bar.update(label="Processing Complete!", state="complete", expanded=False)
        
        st.session_state.processing_done = True
    except Exception as e:
        st.session_state.error_message = f"Initial processing error: {e}"; st.text(traceback.format_exc())
        if 'status_bar' in locals() and status_bar is not None : status_bar.update(label="Error!", state="error", expanded=True)
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)

def process_machine_specific_data(machine_data, template_file_path):
    """Process a specific machine to generate its GOA document"""
    try:
        if not configure_gemini_client():
            st.session_state.error_message = "Failed to configure LLM client. Check API key."
            return False
            
        # Extract common items from the machine data
        common_items = machine_data.get("common_items", [])
        
        # Get machine-specific data from LLM
        with st.spinner(f"Processing machine: {machine_data.get('machine_name')}..."):
            machine_filled_data = get_machine_specific_fields_via_llm(
                machine_data,
                common_items,
                st.session_state.template_contexts,
                st.session_state.full_pdf_text
            )
            
            # Store the machine-specific data
            st.session_state.machine_specific_filled_data = machine_filled_data
            
            # Generate the machine-specific document
            machine_specific_output_path = f"output_{machine_data.get('machine_name', 'machine').replace(' ', '_')}.docx"
            fill_word_document_from_llm_data(template_file_path, machine_filled_data, machine_specific_output_path)
            st.session_state.machine_docx_path = machine_specific_output_path
            
            # If machine has an ID (from database), save the template data
            if "id" in machine_data:
                save_machine_template_data(
                    machine_data["id"], 
                    "GOA", 
                    machine_filled_data,
                    machine_specific_output_path
                )
            
            return True
    except Exception as e:
        st.session_state.error_message = f"Machine processing error: {e}"
        st.text(traceback.format_exc())
        return False

# --- Function to load CRM data --- 
def load_crm_data():
    """Load CRM data and update session state"""
    st.session_state.all_crm_clients = load_all_clients()
    st.session_state.crm_data_loaded = True

def load_previous_document(client_id):
    """
    Load a previously processed document from the database
    """
    try:
        # Get client data
        client_data = get_client_by_id(client_id)
        if not client_data:
            st.error(f"Client data not found for ID: {client_id}")
            return False
            
        quote_ref = client_data.get("quote_ref")
        
        # Load document content
        document_content = load_document_content(quote_ref)
        if not document_content:
            st.error(f"Document content not found for quote: {quote_ref}")
            return False
            
        # Load machines and templates
        machines = load_machines_for_quote(quote_ref)
        if not machines:
            st.warning(f"No machine data found for quote: {quote_ref}")
            # We can still proceed with chat functionality
        
        # Set session state for the loaded document
        st.session_state.full_pdf_text = document_content["full_pdf_text"]
        
        # Load priced items for the items_for_confirmation
        priced_items = load_priced_items_for_quote(quote_ref)
        st.session_state.selected_pdf_items_structured = priced_items
        st.session_state.items_for_confirmation = priced_items
        
        # Extract descriptions for LLM
        st.session_state.selected_pdf_descs = [item.get("description", "") for item in priced_items if item.get("description")]
        
        # If machines exist, set the identified_machines_data
        if machines:
            # Extract machine data from JSON
            machine_list = []
            common_items = []
            
            for machine in machines:
                machine_data = machine.get("machine_data", {})
                if machine_data:
                    machine_list.append(machine_data)
                    # We only need to get common items once as they're the same for all machines
                    if not common_items and "common_items" in machine_data:
                        common_items = machine_data.get("common_items", [])
            
            st.session_state.identified_machines_data = {
                "machines": machine_list,
                "common_items": common_items
            }
            
            # Set confirmation flags to skip to machine selection
            st.session_state.machine_confirmation_done = True
            st.session_state.common_options_confirmation_done = True
        else:
            # Reset these in case a previous document was loaded
            st.session_state.identified_machines_data = {}
            st.session_state.machine_confirmation_done = False
            st.session_state.common_options_confirmation_done = False
        
        # Set processing done flag to show the document processing UI
        st.session_state.processing_done = True
        
        return True
        
    except Exception as e:
        st.error(f"Error loading previous document: {e}")
        st.text(traceback.format_exc())
        return False

def calculate_machine_price(machine_data):
    """
    Calculate the total price for a machine including its add-ons
    """
    total_price = 0.0
    
    # Add main machine price
    main_item = machine_data.get("main_item", {})
    main_price = main_item.get("item_price_numeric", 0)
    if main_price is not None:
        total_price += main_price
    
    # Add prices of add-ons
    add_ons = machine_data.get("add_ons", [])
    for item in add_ons:
        addon_price = item.get("item_price_numeric", 0)
        if addon_price is not None:
            total_price += addon_price
    
    return total_price

def calculate_common_items_price(common_items):
    """
    Calculate the total price for common items
    """
    total_price = 0.0
    
    for item in common_items:
        item_price = item.get("item_price_numeric", 0)
        if item_price is not None:
            total_price += item_price
    
    return total_price

def generate_export_document(document_type, selected_machines, include_common_items, template_file_path, client_data):
    """
    Generate a packing slip or commercial invoice for selected machines
    
    Args:
        document_type: "packing_slip" or "commercial_invoice"
        selected_machines: List of selected machine data dictionaries
        include_common_items: Whether to include common items
        template_file_path: Path to the document template
        client_data: Client information from database
        
    Returns:
        Path to generated document
    """
    try:
        # Get common items if requested
        common_items = []
        if include_common_items and "identified_machines_data" in st.session_state:
            common_items = st.session_state.identified_machines_data.get("common_items", [])
        
        # Calculate total price
        total_price = sum(calculate_machine_price(machine) for machine in selected_machines)
        if include_common_items:
            total_price += calculate_common_items_price(common_items)
        
        # Create a list of all items to include in the document
        all_items = []
        
        # Add main machines and their add-ons
        for machine in selected_machines:
            # Add main machine
            main_item = machine.get("main_item", {})
            if main_item:
                all_items.append(main_item)
            
            # Add this machine's add-ons
            add_ons = machine.get("add_ons", [])
            all_items.extend(add_ons)
        
        # Add common items if requested
        if include_common_items:
            all_items.extend(common_items)
        
        # Create a filename for the generated document
        machine_names = "_".join([m.get("machine_name", "").replace(" ", "") for m in selected_machines])
        if len(machine_names) > 30:  # Avoid extremely long filenames
            machine_names = machine_names[:30] + "..."
        
        output_filename = f"{document_type}_{machine_names}_{st.session_state.run_key}.docx"
        
        # Prepare data for the document based on its type
        if document_type == "packing_slip":
            # Import packing slip generator if not already available
            from document_generators import generate_packing_slip_data
            
            document_data = generate_packing_slip_data(client_data, all_items)
            
            # Add additional calculated fields
            document_data["total_price"] = f"{total_price:.2f}"
            document_data["packing_slip_no"] = f"PS-{client_data.get('quote_ref', '')}"
            document_data["selected_machines"] = ", ".join([m.get("machine_name", "") for m in selected_machines])
            
        elif document_type == "commercial_invoice":
            # Import commercial invoice generator
            # You may need to implement this function in document_generators.py
            from document_generators import generate_commercial_invoice_data
            
            document_data = generate_commercial_invoice_data(client_data, all_items)
            
            # Add additional calculated fields
            document_data["total_price"] = f"{total_price:.2f}"
            document_data["invoice_no"] = f"INV-{client_data.get('quote_ref', '')}"
            document_data["selected_machines"] = ", ".join([m.get("machine_name", "") for m in selected_machines])
            
        else:
            raise ValueError(f"Unknown document type: {document_type}")
        
        # Fill the document with the prepared data
        fill_word_document_from_llm_data(template_file_path, document_data, output_filename)
        
        return output_filename
        
    except Exception as e:
        st.error(f"Error generating {document_type}: {e}")
        st.text(traceback.format_exc())
        return None

# --- New Context-Aware Chat Functions ---
def get_current_context():
    """
    Determines the current context for the chat based on user's location in the app
    Returns a tuple of (context_type, context_data)
    """
    if st.session_state.current_page == "Welcome":
        return ("general", None)
    elif st.session_state.current_page == "Quote Processing":
        if st.session_state.full_pdf_text:
            return ("quote", {
                "full_pdf_text": st.session_state.full_pdf_text,
                "selected_pdf_descs": st.session_state.selected_pdf_descs,
                "template_contexts": st.session_state.template_contexts
            })
        return ("general", None)
    elif st.session_state.current_page == "Export Documents":
        # Context based on selected client/machines
        if st.session_state.selected_client_for_detail_edit:
            return ("client", st.session_state.selected_client_for_detail_edit)
        return ("general", None)
    elif st.session_state.current_page == "CRM Management":
        if st.session_state.selected_client_for_detail_edit:
            return ("client", st.session_state.selected_client_for_detail_edit)
        return ("crm", None)
    return ("general", None)

def process_chat_query(query, context_type, context_data=None):
    """
    Process chat query based on the current context
    """
    if not query:
        return "Please enter a question."
    
    if context_type == "quote" and context_data:
        # Answer questions about the current quote
        return answer_pdf_question(
            query, 
            context_data.get("selected_pdf_descs", []),
            context_data.get("full_pdf_text", ""),
            context_data.get("template_contexts", {})
        )
    elif context_type == "client" and context_data:
        # Answer questions about the selected client
        client_info = f"Client: {context_data.get('customer_name', '')}\n"
        client_info += f"Quote: {context_data.get('quote_ref', '')}\n"
        
        # Get additional info if needed
        quote_ref = context_data.get('quote_ref')
        if quote_ref:
            doc_content = load_document_content(quote_ref)
            if doc_content and doc_content.get("full_pdf_text"):
                return answer_pdf_question(
                    query,
                    [],  # No specific descriptions needed
                    doc_content.get("full_pdf_text", ""),
                    {}  # No template contexts needed
                )
        
        # Fallback if no document content
        return f"I can help with questions about {context_data.get('customer_name', 'the client')}, but I don't have detailed quote information available."
    
    # Default general responses
    if "what can you do" in query.lower():
        return "I can help you process quotes, identify machines, generate documents, and answer questions about your data."
    elif "how do i" in query.lower():
        return "To get started, upload a quote PDF in the Quote Processing section. I'll guide you through the rest of the process."
    
    return "I'm not sure how to answer that question with the current context. Try asking about a specific quote or client if one is selected."

# --- Page Display Functions ---
def show_welcome_page():
    st.title("Welcome to the GOA Document Assistant")
    
    st.markdown("""
    ## What This Application Does
    
    This tool helps you process machine quotes to generate:
    - General Order Agreements (GOA)
    - Packing Slips
    - Commercial Invoices
    
    ## Data Storage
    
    The following data will be stored in the database:
    - Client information (name, address, etc.)
    - Quote details and line items
    - Machine specifications and groupings
    - Generated documents
    
    ## Getting Started
    
    1. Start by uploading a quote PDF in the Quote Processing section
    2. Identify machines and their add-ons
    3. Generate GOA documents for specific machines
    4. Create export documents as needed
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Go to Quote Processing", type="primary"):
            st.session_state.current_page = "Quote Processing"
            st.rerun()
    with col2:
        if st.button("View CRM Data"):
            st.session_state.current_page = "CRM Management"
            st.rerun()

def show_quote_processing():
    st.title("📄 Quote Processing")
    
    # Wizard-style interface with progress bar
    processing_steps = [
        "Upload Quote", 
        "Identify Main Machines", 
        "Select Common Options", 
        "Process Machine"
    ]
    current_step = st.session_state.processing_step
    
    # Progress bar
    progress_percentage = current_step / (len(processing_steps) - 1)
    st.progress(progress_percentage)
    st.subheader(f"Step {current_step + 1}: {processing_steps[current_step]}")
    
    # Step 1: Upload Quote
    if current_step == 0:
        st.markdown("Upload a PDF quote to begin processing.")
        
        # File uploader in main content area instead of sidebar
        uploaded_pdf = st.file_uploader("Choose PDF", type="pdf", key=f"pdf_uploader_main_{st.session_state.run_key}")

        if uploaded_pdf:
            st.markdown(f"**Uploaded:** `{uploaded_pdf.name}`")
            
            # Create two columns for processing options
            col1, col2 = st.columns(2)
            
            # Option 1: Full GOA Processing
            with col1:
                if st.button("🚀 Process for GOA", type="primary", key=f"process_btn_main_{st.session_state.run_key}"):
                    # Reset processing step to ensure we start fresh
                    st.session_state.processing_step = 0
                    # Process the document
                    TEMPLATE_FILE = "template.docx"
                    if not os.path.exists(TEMPLATE_FILE): 
                        st.error(f"Template '{TEMPLATE_FILE}' not found.")
                    else:
                        perform_initial_processing(uploaded_pdf, TEMPLATE_FILE)
                        # Move to next step if processing is done
                        if st.session_state.processing_done:
                            st.session_state.processing_step = 1
                            st.rerun()
            
            # Option 2: Quick Catalog
            with col2:
                if st.button("📊 Just Catalog Data", key="quick_catalog_btn"):
                    # Quick extraction and cataloging
                    result = quick_extract_and_catalog(uploaded_pdf)
                    if result:
                        st.success(f"Quote {result['quote_ref']} successfully cataloged with {len(result['items'])} items.")
                        
                        # Display extracted data
                        with st.expander("View Extracted Items", expanded=True):
                            if result['items']:
                                df = pd.DataFrame(result['items'])
                                # Clean up columns for display
                                display_cols = ['description', 'quantity_text', 'selection_text']
                                display_df = df[[c for c in display_cols if c in df.columns]]
                                st.dataframe(display_df, use_container_width=True)
                        
                        # Add option to go directly to CRM
                        if st.button("Go to CRM Management"):
                            st.session_state.current_page = "CRM Management"
                            st.rerun()
                    else:
                        st.error("Failed to catalog data.")
    
    # Step 2: Identify Main Machines
    elif current_step == 1:
        if not st.session_state.machine_confirmation_done:
            st.markdown("Select all items that are **main machines** in the quote. These are the primary equipment items.")
            
            items = st.session_state.items_for_confirmation
            if items:
                # Use checkboxes for better visibility
                st.markdown("### Select main machines:")
                
                selected_indices = []
                
                with st.container():
                    for i, item in enumerate(items):
                        desc = item.get('description', 'No description')
                        # Show first line of description plus price if available
                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                        price_str = item.get('item_price_str', '')
                        display_text = f"{first_line} {price_str}"
                        
                        # Check if this item was pre-selected
                        is_preselected = i in st.session_state.selected_main_machines
                        
                        # Create a checkbox for each item
                        is_selected = st.checkbox(
                            display_text,
                            value=is_preselected,
                            key=f"machine_checkbox_{i}"
                        )
                        
                        if is_selected:
                            selected_indices.append(i)
                
                # Store selected indices
                st.session_state.selected_main_machines = selected_indices
                
        col1, col2 = st.columns(2)
        with col1:
                    if st.button("⬅️ Back", key="back_to_upload"):
                        st.session_state.processing_step = 0
                        st.rerun()
                
        with col2:
                    if st.button("Next ➡️", key="confirm_machines_btn", type="primary"):
                        if not selected_indices:
                            st.warning("Please select at least one main machine.")
                        else:
                            st.session_state.machine_confirmation_done = True
                            st.session_state.processing_step = 2
                            st.rerun()
            else:
                st.warning("No items found for confirmation. Please process the document again.")
                if st.button("⬅️ Back to Upload", key="back_to_upload_no_items"):
                    st.session_state.processing_step = 0
                    st.rerun()
        else:
            # If machines already confirmed, move to next step
            st.session_state.processing_step = 2
            st.rerun()
    
    # Step 3: Select Common Options
    elif current_step == 2:
        if not st.session_state.common_options_confirmation_done:
            st.markdown("Select items that are **common options** applying to all machines (warranty, training, etc.)")
            
            items = st.session_state.items_for_confirmation
            if items:
                main_machine_indices = st.session_state.selected_main_machines
                
                # Create a list of options excluding main machines (which can't be common options)
                available_indices = []
                available_options = []
                for i, item in enumerate(items):
                    if i not in main_machine_indices:
                        desc = item.get('description', 'No description')
                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                        price_str = item.get('item_price_str', '')
                        display_text = f"{first_line} {price_str}"
                        available_indices.append(i)
                        available_options.append(display_text)
                
                # Use checkboxes instead of multiselect
                st.markdown("### Select common options (applying to all machines):")
                
                selected_positions = []
                with st.container():
                    for pos, i in enumerate(available_indices):
                        display_text = available_options[pos]
                        
                        # Check if this item was pre-selected
                        is_preselected = i in st.session_state.selected_common_options
                        
                        # Create a checkbox for each item
                        is_selected = st.checkbox(
                            display_text,
                            value=is_preselected,
                            key=f"common_checkbox_{i}"
                        )
                        
                        if is_selected:
                            selected_positions.append(pos)
                
                # Map selected positions back to original indices
                selected_indices = [available_indices[pos] for pos in selected_positions]
                
                # Store selected indices
                st.session_state.selected_common_options = selected_indices
                
                # Show current assignments
                with st.expander("Current Machine Assignments", expanded=False):
                    st.markdown("**Main Machines:**")
                    for i in main_machine_indices:
                        desc = items[i].get('description', 'No description')
                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                        st.markdown(f"- {first_line}")
                    
                    st.markdown("**Common Options:**")
                    for i in selected_indices:
                        desc = items[i].get('description', 'No description')
                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                        st.markdown(f"- {first_line}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Back", key="back_to_machines"):
                        st.session_state.machine_confirmation_done = False
                        st.session_state.processing_step = 1
                        st.rerun()
                
                with col2:
                    if st.button("Next ➡️", key="confirm_common_btn", type="primary"):
                        # Group items based on confirmed machines and common options
                        grouped_data = group_items_by_confirmed_machines(
                            items, 
                            st.session_state.selected_main_machines,
                            st.session_state.selected_common_options
                        )
                        
                        # Store the grouped data
                        st.session_state.identified_machines_data = grouped_data
                        
                        # Save the machines to the database
                        if st.session_state.selected_pdf_items_structured:
                            quote_ref = items[0].get('client_quote_ref') if items and items[0].get('client_quote_ref') else "unknown"
                            if save_machines_data(quote_ref, grouped_data):
                                st.success(f"Machine groupings saved to database.")
                            else:
                                st.warning(f"Failed to save machine groupings to database.")
                        
                        st.session_state.common_options_confirmation_done = True
                        st.session_state.processing_step = 3
                        st.rerun()
            else:
                st.warning("No items found for confirmation. Please process the document again.")
                if st.button("⬅️ Back to Upload", key="back_to_upload_no_common_items"):
                    st.session_state.processing_step = 0
                    st.rerun()
        else:
            # If common options already confirmed, move to next step
            st.session_state.processing_step = 3
            st.rerun()
    
    # Step 4: Process Machine
    elif current_step == 3:
        # Machine selection and processing
        st.subheader("🔍 Select Machine to Process")
        
        if st.session_state.identified_machines_data and "machines" in st.session_state.identified_machines_data:
            machines = st.session_state.identified_machines_data["machines"]
            if machines:
                # Create list of machine options for selection
                machine_options = [f"{m.get('machine_name', 'Unknown Machine')}" for m in machines]
                
                # Show selection dropdown
                selected_machine_idx = st.selectbox(
                    "Choose a machine to process:",
                    range(len(machine_options)),
                    format_func=lambda i: machine_options[i],
                    key=f"machine_select_{st.session_state.run_key}"
                )
                
                # Store selected machine index
                st.session_state.selected_machine_index = selected_machine_idx
                
                # Show machine details
                selected_machine = machines[selected_machine_idx]
                with st.expander(f"Machine Details: {selected_machine.get('machine_name')}", expanded=True):
                    st.markdown("**Main Machine Description:**")
                    st.markdown(f"```\n{selected_machine.get('main_item', {}).get('description', 'No description')}\n```")
                    
                    st.markdown("**Add-on Items:**")
                    add_ons = selected_machine.get('add_ons', [])
                    if add_ons:
                        for i, addon in enumerate(add_ons):
                            st.markdown(f"{i+1}. {addon.get('description', 'No description')}")
                    else:
                        st.markdown("No add-on items for this machine.")
                
                # Common items apply to all machines
                common_items = st.session_state.identified_machines_data.get("common_items", [])
                with st.expander("Common Items (apply to all machines)", expanded=False):
                    if common_items:
                        for i, item in enumerate(common_items):
                            st.markdown(f"{i+1}. {item.get('description', 'No description')}")
                    else:
                        st.markdown("No common items identified.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Back", key="back_to_common_options"):
                        st.session_state.common_options_confirmation_done = False
                        st.session_state.processing_step = 2
                        st.rerun()
                
                with col2:
                    if st.button("🔨 Process Selected Machine", key=f"process_machine_btn_{st.session_state.run_key}", type="primary"):
                        TEMPLATE_FILE = "template.docx"
                        if not os.path.exists(TEMPLATE_FILE): 
                            st.error(f"Template '{TEMPLATE_FILE}' not found.")
                        else:
                            success = process_machine_specific_data(selected_machine, TEMPLATE_FILE)
                            if success:
                                st.success(f"Machine '{selected_machine.get('machine_name')}' processed successfully!")
                                
                                # Show download for machine-specific document if available
                                if hasattr(st.session_state, 'machine_docx_path') and os.path.exists(st.session_state.machine_docx_path):
                                    st.subheader("📂 Machine-Specific Document")
                                    with open(st.session_state.machine_docx_path, "rb") as fp:
                                        st.download_button(
                                            "Download Machine-Specific Document",
                                            fp,
                                            os.path.basename(st.session_state.machine_docx_path),
                                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key=f"dl_machine_{st.session_state.run_key}",
                                            type="primary"
                                        )
            else:
                st.warning("No machines identified in the document.")
                if st.button("⬅️ Start Over", key="restart_no_machines"):
                    st.session_state.processing_step = 0
                    st.rerun()
        else:
            st.warning("Machine data not available. Please process the document first.")
            if st.button("⬅️ Start Over", key="restart_no_machine_data"):
                st.session_state.processing_step = 0
                st.rerun()
                
        # Option to go to export documents
        st.markdown("---")
        if st.button("Go to Export Documents", key="goto_export_docs"):
            st.session_state.current_page = "Export Documents"
            st.rerun()

def show_export_documents():
    st.title("📄 Export Documents")
    
    # Client selection
    st.subheader("Select Client")
    
    client_options_display = ["Select a Client..."] + \
                             [f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')} (ID: {c.get('id')})" 
                              for c in st.session_state.all_crm_clients]
    
    selected_client_option_str = st.selectbox(
        "Choose a client to generate documents for:", 
        client_options_display, 
        key=f"export_client_select_{st.session_state.run_key}", 
        index=0
    )
    
    if selected_client_option_str != "Select a Client...":
        try:
            selected_id = int(selected_client_option_str.split("(ID: ")[-1][:-1])
            client_data = get_client_by_id(selected_id)
            
            if client_data:
                st.session_state.selected_client_for_detail_edit = client_data
                
                # Load machines for this client
                quote_ref = client_data.get('quote_ref')
                machines_data = load_machines_for_quote(quote_ref)
                
                if machines_data:
                    # Show the list of identified machines for this client
                    st.subheader("Generate Export Documents")
                    
                    # Extract and process machine data
                    processed_machines = []
                    for machine in machines_data:
                        # Parse machine_data_json
                        try:
                            machine_data = machine.get("machine_data", {})
                            # Store the machine record ID for later use
                            machine_data["id"] = machine.get("id")
                            processed_machines.append(machine_data)
                        except Exception as e:
                            st.error(f"Error processing machine data: {e}")
                    
                    # Find common items (they should be the same in all machines)
                    common_items = []
                    if processed_machines:
                        common_items = processed_machines[0].get("common_items", [])
                    
                    # Let user select machines to include in export documents
                    selected_machine_indices = []
                    with st.form(key=f"export_docs_form_{client_data.get('id')}"):
                        st.markdown("Select machines to include in export documents:")
                        
                        # Machine selection
                        for i, machine in enumerate(processed_machines):
                            machine_name = machine.get("machine_name", f"Machine {i+1}")
                            # Calculate price for display
                            machine_price = calculate_machine_price(machine)
                            if st.checkbox(f"{machine_name} (${machine_price:.2f})", 
                                           value=True, 
                                           key=f"export_machine_{client_data.get('id')}_{i}"):
                                selected_machine_indices.append(i)
                        
                        # Option to include common items
                        include_common = st.checkbox("Include common items (warranty, shipping, etc.)", 
                                                    value=True,
                                                    key=f"include_common_{client_data.get('id')}")
                        
                        # Template selection
                        template_options = ["Packing Slip", "Commercial Invoice", "Certificate of Origin"]
                        available_templates = []
                        
                        if os.path.exists("packing_slip_template.docx"):
                            available_templates.append("Packing Slip")
                        if os.path.exists("commercial_invoice_template.docx"):
                            available_templates.append("Commercial Invoice")
                        if os.path.exists("certificate_of_origin_template.docx"):
                            available_templates.append("Certificate of Origin")
                        
                        if not available_templates:
                            st.warning("No document templates found. Please create template files.")
                            template_type = None
                        else: 
                            template_type = st.radio("Select document type:", available_templates)
                        
                        # Submit button
                        submit_button = st.form_submit_button("Generate Selected Document")
                    
                    # Process form submission (outside the form to avoid state issues)
                    if submit_button:
                        if not selected_machine_indices:
                            st.warning("Please select at least one machine to generate documents.")
                        elif template_type:
                            # Get selected machines data
                            selected_machines = [processed_machines[i] for i in selected_machine_indices]
                            
                            # Map template selection to document type and file path
                            document_type = ""
                            template_path = ""
                            if template_type == "Packing Slip":
                                document_type = "packing_slip"
                                template_path = "packing_slip_template.docx"
                            elif template_type == "Commercial Invoice":
                                document_type = "commercial_invoice"
                                template_path = "commercial_invoice_template.docx"
                            elif template_type == "Certificate of Origin":
                                document_type = "certificate_of_origin"
                                template_path = "certificate_of_origin_template.docx"
                            
                            with st.spinner(f"Generating {template_type}..."):
                                output_path = generate_export_document(
                                    document_type, 
                                    selected_machines, 
                                    include_common,
                                    template_path,
                                    client_data
                                )
                                
                                if output_path and os.path.exists(output_path):
                                    st.success(f"{template_type} generated: {output_path}")
                                    # Provide download button
                                    with open(output_path, "rb") as f:
                                        st.download_button(
                                            f"Download {template_type}",
                                            f,
                                            file_name=output_path,
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                        )
                                else:
                                    st.error(f"Failed to generate {template_type}.")
                        else:
                            st.error("Please select a document type.")
                else:
                    st.warning("No machines identified for this client.")
                    
                    # Provide option to process PDF to identify machines
                    st.markdown("### Process Quote to Identify Machines")
                    st.markdown("To generate export documents, you need to first process the quote to identify machines.")
                    
                    uploaded_file = st.file_uploader(
                        "Upload the quote PDF to process:", 
                        type="pdf", 
                        key=f"export_pdf_upload_{client_data.get('id')}"
                    )
                    
                    if uploaded_file:
                        # Allow user to adjust machine detection sensitivity
                        detection_sensitivity = st.select_slider(
                            "Machine Detection Sensitivity:",
                            options=["Conservative", "Moderate", "Aggressive"],
                            value="Moderate",
                            key=f"export_detection_sensitivity_{client_data.get('id')}"
                        )
                        
                        st.info("📌 Conservative: Only items with clear machine keywords or high prices\n"
                               "📌 Moderate: Balance between keywords and price indicators\n"
                               "📌 Aggressive: Include more potential machines based on weaker signals")
                    
                        if st.button("Process Quote", key=f"process_export_quote_{client_data.get('id')}"):
                            # Store the uploaded file temporarily
                            temp_pdf_path = os.path.join(".", uploaded_file.name)
                            try:
                                with open(temp_pdf_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                                
                                # Process the PDF to extract line items and full text
                                with st.spinner("Processing PDF..."):
                                    items = extract_line_item_details(temp_pdf_path)
                                    full_text = extract_full_pdf_text(temp_pdf_path)
                                    
                                    if items:
                                        # Save the items to the database
                                        save_priced_items(quote_ref, items)
                                        
                                        # Save the full text for chat and processing
                                        save_document_content(quote_ref, full_text, uploaded_file.name)
                                        
                                        # Set price threshold based on sensitivity
                                        price_threshold = 10000  # Default moderate threshold
                                        if detection_sensitivity == "Conservative":
                                            price_threshold = 15000  # Higher threshold = fewer machines detected
                                        elif detection_sensitivity == "Aggressive":
                                            price_threshold = 5000   # Lower threshold = more machines detected
                                        
                                        # Auto-identify machines with the improved algorithm
                                        machine_list = identify_machines_from_items(items, price_threshold)
                                        
                                        # Convert to expected format
                                        machine_data = {"machines": [], "common_items": []}
                                        
                                        for machine in machine_list:
                                            if machine.get("is_main_machine", True):
                                                # For main machines, create the expected structure
                                                main_item = machine.get("items", [])[0] if machine.get("items") else {}
                                                add_ons = machine.get("items", [])[1:] if len(machine.get("items", [])) > 1 else []
                                                
                                                machine_data["machines"].append({
                                                    "machine_name": machine.get("name", "Unknown Machine"),
                                                    "main_item": main_item,
                                                    "add_ons": add_ons
                                                })
                                            else:
                                                # For common items (non-machines), add all items to common_items list
                                                machine_data["common_items"].extend(machine.get("items", []))
                                        
                                        # Save the machines to the database
                                        if save_machines_data(quote_ref, machine_data):
                                            st.success("Quote processed successfully.")
                                            
                                            # Display the identified machines
                                            if machine_data["machines"]:
                                                st.write(f"**Identified {len(machine_data['machines'])} machine(s):**")
                                                for i, machine in enumerate(machine_data["machines"]):
                                                    with st.expander(f"{i+1}. {machine.get('machine_name', 'Unknown')}"):
                                                        st.write("**Main item:**")
                                                        st.write(machine.get('main_item', {}).get('description', 'No description'))
                                                        
                                                        st.write("**Add-ons:**")
                                                        add_ons = machine.get('add_ons', [])
                                                        if add_ons:
                                                            for j, addon in enumerate(add_ons):
                                                                st.write(f"- {addon.get('description', 'No description')}")
                                                        else:
                                                            st.write("No add-ons")
                                            
                                            # Show common items too
                                            if machine_data["common_items"]:
                                                with st.expander(f"Common Items ({len(machine_data['common_items'])})"):
                                                    for i, item in enumerate(machine_data["common_items"]):
                                                        st.write(f"- {item.get('description', 'No description')}")
                                            
                                            st.rerun() # Refresh to show the identified machines
                                        else:
                                            st.error("Failed to save machine data.")
                                    else:
                                        st.error("No items found in the PDF to process.")
                            except Exception as e:
                                st.error(f"Error processing quote: {e}")
                                st.text(traceback.format_exc())
                            finally:
                                # Clean up
                                if os.path.exists(temp_pdf_path):
                                    os.remove(temp_pdf_path)
                                    
                        # Add option for manual machine selection
                        st.markdown("### Or Manually Select Machines")
                        if st.button("Manual Machine Selection", key=f"manual_machine_selection_btn_{client_data.get('id')}"):
                            st.session_state[f"show_manual_export_selection_{client_data.get('id')}"] = True
                        st.rerun()
                        
                        # Show manual selection UI if requested
                        if st.session_state.get(f"show_manual_export_selection_{client_data.get('id')}", False):
                            # Load existing items if available
                            items = load_priced_items_for_quote(quote_ref)
                            
                            if not items:
                                st.error("No items found for this quote. Please upload a PDF first.")
                            else:
                                st.markdown("---")
                                st.subheader("Manual Machine Selection")
                                st.markdown("Select which items are main machines:")
                                
                                # Use form for selection
                                with st.form(key=f"manual_export_machine_selection_{client_data.get('id')}"):
                                    # Machine selection
                                    selected_machine_indices = []
                                    for i, item in enumerate(items):
                                        desc = item.get('description', 'No description')
                                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                                        price_str = item.get('selection_text', '')
                                        display_text = f"{first_line} ({price_str})"
                                        
                                        if st.checkbox(display_text, key=f"export_machine_check_{client_data.get('id')}_{i}"):
                                            selected_machine_indices.append(i)
                                    
                                    st.markdown("---")
                                    st.markdown("Select which items are common to all machines:")
                                    
                                    # Common item selection
                                    selected_common_indices = []
                                    for i, item in enumerate(items):
                                        # Skip if already selected as a machine
                                        if i in selected_machine_indices:
                                            continue
                                            
                                        desc = item.get('description', 'No description')
                                        first_line = desc.split('\n')[0] if '\n' in desc else desc
                                        price_str = item.get('selection_text', '')
                                        display_text = f"{first_line} ({price_str})"
                                        
                                        if st.checkbox(display_text, key=f"export_common_check_{client_data.get('id')}_{i}"):
                                            selected_common_indices.append(i)
                                    
                                    # Submit button
                                    submit_btn = st.form_submit_button("Save Machine Groupings")
                                
                                # Process form submission
                                if submit_btn:
                                    try:
                                        # Group items based on manual selection
                                        machine_data = {"machines": [], "common_items": []}
                                        
                                        # Add common items
                                        for idx in selected_common_indices:
                                            machine_data["common_items"].append(items[idx])
                                        
                                        # Create machine entries
                                        for idx in selected_machine_indices:
                                            main_machine = items[idx]
                                            machine_name = main_machine.get('description', 'Unknown Machine').split('\n')[0]
                                            
                                            # Find all add-ons that should be associated with this machine
                                            add_ons = []
                                            for i, item in enumerate(items):
                                                # Skip if it's a main machine or common item
                                                if i in selected_machine_indices or i in selected_common_indices:
                                                    continue
                                                
                                                # For simplicity, assign remaining items to the closest preceding machine
                                                if i > idx and (i < next((x for x in selected_machine_indices if x > idx), len(items))):
                                                    add_ons.append(item)
                                            
                                            # Create the machine entry
                                            machine_data["machines"].append({
                                                "machine_name": machine_name,
                                                "main_item": main_machine,
                                                "add_ons": add_ons
                                            })
                                        
                                        # Save the manually grouped data
                                        if save_machines_data(quote_ref, machine_data):
                                            st.success("Manual machine groupings saved successfully!")
                                            
                                            # Clear the manual selection state
                                            st.session_state.pop(f"show_manual_export_selection_{client_data.get('id')}", None)
                                            st.rerun()
                                        else:
                                            st.error("Failed to save manual machine groupings.")
                    except Exception as e:
                                        st.error(f"Error saving manual machine groupings: {e}")
                                        st.text(traceback.format_exc())
    else:
                st.error(f"Could not load client data for ID: {selected_id}")
        except Exception as e:
            st.error(f"Error loading client data: {e}")
            st.text(traceback.format_exc())
    else:
        st.info("Select a client to generate export documents.")

def show_crm_management():
    st.title("📒 CRM Management")
    if st.button("Refresh CRM List", key=f"refresh_crm_main_tab_{st.session_state.run_key}"):
        load_crm_data()
        st.success("CRM data refreshed.")

    # Option to add new client with PDF upload directly
    with st.expander("Quick Catalog New Quote", expanded=False):
        st.markdown("### Upload and Catalog a New Quote")
        st.markdown("This will extract data from a PDF quote and create a new client record.")
        
        uploaded_pdf = st.file_uploader("Choose PDF", type="pdf", key=f"crm_quick_upload_{st.session_state.run_key}")
        
        if uploaded_pdf:
            st.markdown(f"**Uploaded:** `{uploaded_pdf.name}`")
            if st.button("Catalog This Quote", type="primary", key="crm_quick_catalog_btn"):
                result = quick_extract_and_catalog(uploaded_pdf)
                if result:
                    st.success(f"Quote {result['quote_ref']} successfully cataloged with {len(result['items'])} items.")
                else:
                    st.error("Failed to catalog data.")

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

    # Create tabs for different client views
    if selected_client_option_str_for_view != "Select a Client Record...":
        try:
            selected_id_for_view = int(selected_client_option_str_for_view.split("(ID: ")[-1][:-1])
            if st.session_state.selected_client_for_detail_edit is None or st.session_state.selected_client_for_detail_edit.get('id') != selected_id_for_view:
                st.session_state.selected_client_for_detail_edit = get_client_by_id(selected_id_for_view)
                st.session_state.editing_client_id = selected_id_for_view
                st.session_state.confirming_delete_client_id = None # Reset delete confirmation if client changes
            
            client_to_display_and_edit = st.session_state.selected_client_for_detail_edit

            if client_to_display_and_edit:
                # Create tabs for client details, priced items, and export documents
                client_tab1, client_tab2, client_tab3, client_tab4 = st.tabs(["📋 Client Details", "💲 Priced Items", "📄 Export Documents", "📤 Upload PDF"])
                
                # Tab 1: Client Details
                with client_tab1:
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
                
                # Tab 2: Priced Items
                with client_tab2:
                    quote_ref_for_items = client_to_display_and_edit.get('quote_ref')
                    st.subheader(f"Priced Items for Quote: {quote_ref_for_items}")
                    
                    # Load or use already loaded items for editing
                    priced_items_for_quote = load_priced_items_for_quote(quote_ref_for_items)
                    st.session_state.current_priced_items_for_editing = priced_items_for_quote # Store original

                    if priced_items_for_quote:
                        df_priced_items = pd.DataFrame(priced_items_for_quote)
                        editable_df = df_priced_items[['id', 'item_description', 'item_quantity', 'item_price_str']].copy()
                        
                        st.markdown("**Edit Priced Items:**")
                        edited_df = st.data_editor(
                            editable_df, 
                            key=f"data_editor_priced_items_{st.session_state.editing_client_id}",
                            num_rows="dynamic", # Allow adding/deleting rows
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
                                            str(original_item.get('item_quantity', '')) != str(edited_row.get('item_quantity', '')) or
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

                            if changes_applied > 0:
                                st.success(f"{changes_applied} priced item(s) updated successfully!")
                                load_crm_data() # Reload all clients to reflect potential changes
                                st.rerun() # Rerun to refresh the data_editor with fresh data from DB
                            else:
                                st.info("No changes detected in priced items to save.")
                    else:
                        st.info("No priced items recorded for this quote to edit.")
                
                # Tab 3: Export Documents - New Tab
                with client_tab3:
                    st.subheader("📄 Generate Export Documents")
                    
                    # Load machines for this client
                    quote_ref = client_to_display_and_edit.get('quote_ref')
                    machines_data = load_machines_for_quote(quote_ref)
                    
                    if machines_data:
                        # Show the list of identified machines for this client
                        st.markdown("### Machines identified for this client:")
                        
                        # Extract and process machine data
                        processed_machines = []
                        for machine in machines_data:
                            # Parse machine_data_json
                            try:
                                machine_data = machine.get("machine_data", {})
                                # Store the machine record ID for later use
                                machine_data["id"] = machine.get("id")
                                processed_machines.append(machine_data)
                            except Exception as e:
                                st.error(f"Error processing machine data: {e}")
                        
                        # Find common items (they should be the same in all machines)
                        common_items = []
                        if processed_machines:
                            common_items = processed_machines[0].get("common_items", [])
                        
                        # Let user select machines to include in export documents
                        selected_machine_indices = []
                        with st.form(key=f"export_docs_form_{client_to_display_and_edit.get('id')}"):
                            st.markdown("Select machines to include in export documents:")
                            
                            # Machine selection
                            for i, machine in enumerate(processed_machines):
                                machine_name = machine.get("machine_name", f"Machine {i+1}")
                                # Calculate price for display
                                machine_price = calculate_machine_price(machine)
                                if st.checkbox(f"{machine_name} (${machine_price:.2f})", 
                                               value=True, 
                                               key=f"export_machine_{client_to_display_and_edit.get('id')}_{i}"):
                                    selected_machine_indices.append(i)
                        
                            # Option to include common items
                            include_common = st.checkbox("Include common items (warranty, shipping, etc.)", 
                                                        value=True,
                                                        key=f"include_common_{client_to_display_and_edit.get('id')}")
                            
                            # Template selection
                            template_options = []
                            if os.path.exists("packing_slip_template.docx"):
                                template_options.append("Packing Slip")
                            if os.path.exists("commercial_invoice_template.docx"):
                                template_options.append("Commercial Invoice")
                            
                            if not template_options:
                                st.warning("No document templates found. Please create template files.")
                                template_type = None
                            else:
                                template_type = st.radio("Select document type:", template_options)
                            
                            # Submit button
                            submit_button = st.form_submit_button("Generate Selected Document")
                        
                        # Process form submission (outside the form to avoid state issues)
                        if submit_button:
                            if not selected_machine_indices:
                                st.warning("Please select at least one machine to generate documents.")
                            elif template_type:
                                # Get selected machines data
                                selected_machines = [processed_machines[i] for i in selected_machine_indices]
                                
                                # Map template selection to document type and file path
                                document_type = ""
                                template_path = ""
                                if template_type == "Packing Slip":
                                    document_type = "packing_slip"
                                    template_path = "packing_slip_template.docx"
                                elif template_type == "Commercial Invoice":
                                    document_type = "commercial_invoice"
                                    template_path = "commercial_invoice_template.docx"
                                
                                with st.spinner(f"Generating {template_type}..."):
                                    output_path = generate_export_document(
                                        document_type, 
                                        selected_machines, 
                                        include_common,
                                        template_path,
                                        client_to_display_and_edit
                                    )
                                    
                                    if output_path and os.path.exists(output_path):
                                        st.success(f"{template_type} generated: {output_path}")
                                        # Provide download button
                                        with open(output_path, "rb") as f:
                                            st.download_button(
                                                f"Download {template_type}",
                                                f,
                                                file_name=output_path,
                                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                            )
                                    else:
                                        st.error(f"Failed to generate {template_type}.")
                            else:
                                st.error("Please select a document type.")
                    else:
                        st.warning("No machines identified for this client.")
                        
                        # Provide option to process PDF to identify machines
                        st.markdown("### Process Quote to Identify Machines")
                        st.markdown("To generate export documents, you need to first process the quote to identify machines.")
                        
                        uploaded_file = st.file_uploader(
                            "Upload the quote PDF to process:", 
                            type="pdf", 
                            key=f"crm_pdf_upload_{client_to_display_and_edit.get('id')}"
                        )
                        
                        if uploaded_file and st.button("Process Quote", key=f"process_crm_quote_{client_to_display_and_edit.get('id')}"):
                            # Store the uploaded file temporarily
                            temp_pdf_path = os.path.join(".", uploaded_file.name)
                            try:
                                with open(temp_pdf_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                                
                                # Process the PDF to extract line items and full text
                                with st.spinner("Processing PDF..."):
                                    items = extract_line_item_details(temp_pdf_path)
                                    full_text = extract_full_pdf_text(temp_pdf_path)
                                    
                                    if items:
                                        # Save the items to the database
                                        save_priced_items(quote_ref, items)
                                        
                                        # Save the full text for chat and processing
                                        save_document_content(quote_ref, full_text, uploaded_file.name)
                                        
                                        # Auto-identify machines (this won't be confirmed by user, but provides initial grouping)
                                        identified_machines = identify_machines_from_items(items)
                                        
                                        # Save the machines to the database
                                        if save_machines_data(quote_ref, identified_machines):
                                            st.success("Quote processed successfully. Machines identified and saved.")
                                            st.rerun() # Refresh to show the identified machines
                                        else:
                                            st.error("Failed to save machine data.")
                                    else:
                                        st.error("No items found in the PDF to process.")
                            except Exception as e:
                                st.error(f"Error processing quote: {e}")
                                st.text(traceback.format_exc())
                            finally:
                                # Clean up
                                if os.path.exists(temp_pdf_path):
                                    os.remove(temp_pdf_path)

                # New tab for direct PDF upload to client
                with client_tab4:
                    st.subheader(f"Upload PDF for {client_to_display_and_edit.get('customer_name', '')}")
                    st.markdown("Upload a PDF quote to extract data and add to this client record.")
                    
                    quote_ref = client_to_display_and_edit.get('quote_ref')
                    
                    uploaded_pdf = st.file_uploader("Choose PDF", type="pdf", key=f"client_pdf_upload_{quote_ref}")
                    
                    if uploaded_pdf:
                        st.markdown(f"**Uploaded:** `{uploaded_pdf.name}`")
                        
                        upload_options = st.radio(
                            "Processing Option:",
                            ["Extract items only", "Extract items and identify machines", "Extract items and manually select machines"],
                            key=f"client_upload_option_{quote_ref}"
                        )

                        # Additional options for machine detection sensitivity
                        if upload_options in ["Extract items and identify machines"]:
                            detection_sensitivity = st.select_slider(
                                "Machine Detection Sensitivity:",
                                options=["Conservative", "Moderate", "Aggressive"],
                                value="Moderate",
                                key=f"detection_sensitivity_{quote_ref}"
                            )
                            
                            st.info("📌 Conservative: Only items with clear machine keywords or very high prices\n"
                                   "📌 Moderate: Balance between keywords and price indicators\n"
                                   "📌 Aggressive: Include more potential machines based on weaker signals")
                        
                        if st.button("Process PDF", type="primary", key=f"client_process_pdf_{quote_ref}"):
                            temp_pdf_path = None
                            try:
                                temp_pdf_path = os.path.join(".", uploaded_pdf.name)
                                with open(temp_pdf_path, "wb") as f: f.write(uploaded_pdf.getbuffer())
                                
                                with st.spinner("Processing PDF..."):
                                    # Extract items and full text
                                    items = extract_line_item_details(temp_pdf_path)
                                    full_text = extract_full_pdf_text(temp_pdf_path)
                                    
                                    if items:
                                        # Save items to database
                                        if save_priced_items(quote_ref, items):
                                            st.success(f"Saved {len(items)} items to database.")
                                        else:
                                            st.error("Failed to save items.")
                                        
                                        # Save full text
                                        save_document_content(quote_ref, full_text, uploaded_pdf.name)
                                        
                                        # For manual machine selection
                                        if upload_options == "Extract items and manually select machines":
                                            st.session_state[f"manual_items_{quote_ref}"] = items
                                            st.session_state[f"show_manual_selection_{quote_ref}"] = True
                                            st.rerun()  # Force refresh to show the selection UI
                                        
                                        # For automatic machine identification
                                        elif upload_options == "Extract items and identify machines":
                                            # Apply the selected sensitivity for machine detection
                                            price_threshold = 10000  # Default moderate threshold
                                            if detection_sensitivity == "Conservative":
                                                price_threshold = 15000  # Higher threshold = fewer machines detected
                                            elif detection_sensitivity == "Aggressive":
                                                price_threshold = 5000   # Lower threshold = more machines detected
                                            
                                            # Pass the threshold to the identification function
                                            identified_machines = identify_machines_from_items(items, price_threshold)
                                            
                                            # Convert machine list to expected format
                                            machine_data = {"machines": [], "common_items": []}
                                            
                                            for machine in identified_machines:
                                                if machine.get("is_main_machine", True):
                                                    # For main machines, create the expected structure
                                                    main_item = machine.get("items", [])[0] if machine.get("items") else {}
                                                    add_ons = machine.get("items", [])[1:] if len(machine.get("items", [])) > 1 else []
                                                    
                                                    machine_data["machines"].append({
                                                        "machine_name": machine.get("name", "Unknown Machine"),
                                                        "main_item": main_item,
                                                        "add_ons": add_ons
                                                    })
                                                else:
                                                    # For common items (non-machines), add all items to common_items list
                                                    machine_data["common_items"].extend(machine.get("items", []))
                                            
                                            if save_machines_data(quote_ref, machine_data):
                                                st.success("Machine groupings saved.")
                                                
                                                # Display the identified machines
                                                if machine_data["machines"]:
                                                    st.write(f"**Identified {len(machine_data['machines'])} machine(s):**")
                                                    for i, machine in enumerate(machine_data["machines"]):
                                                        with st.expander(f"{i+1}. {machine.get('machine_name', 'Unknown')}"):
                                                            st.write("**Main item:**")
                                                            st.write(machine.get('main_item', {}).get('description', 'No description'))
                                                            
                                                            st.write("**Add-ons:**")
                                                            add_ons = machine.get('add_ons', [])
                                                            if add_ons:
                                                                for j, addon in enumerate(add_ons):
                                                                    st.write(f"- {addon.get('description', 'No description')}")
                                                            else:
                                                                st.write("No add-ons")
                                            
                                            # Show common items too
                                            if machine_data["common_items"]:
                                                with st.expander(f"Common Items ({len(machine_data['common_items'])})"):
                                                    for i, item in enumerate(machine_data["common_items"]):
                                                        st.write(f"- {item.get('description', 'No description')}")
                                    else:
                                        st.error("No items found in the PDF to process.")
                            except Exception as e:
                                st.error(f"Error processing PDF: {e}")
                                st.text(traceback.format_exc())
                            finally:
                                if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
                    
                    # Display the manual machine selection UI if needed
                    if uploaded_pdf and st.session_state.get(f"show_manual_selection_{quote_ref}", False):
                        items = st.session_state.get(f"manual_items_{quote_ref}", [])
                        
                        st.markdown("---")
                        st.subheader("Manual Machine Selection")
                        st.markdown("Select which items are main machines:")
                        
                        # Use checkboxes to select main machines
                        selected_machine_indices = []
                        with st.form(key=f"manual_machine_selection_{quote_ref}"):
                            for i, item in enumerate(items):
                                desc = item.get('description', 'No description')
                                first_line = desc.split('\n')[0] if '\n' in desc else desc
                                price_str = item.get('selection_text', '')
                                display_text = f"{first_line} ({price_str})"
                                
                                if st.checkbox(display_text, key=f"machine_check_{quote_ref}_{i}"):
                                    selected_machine_indices.append(i)
                            
                            st.markdown("---")
                            st.markdown("Select which items are common to all machines:")
                            
                            # Use checkboxes to select common items
                            selected_common_indices = []
                            for i, item in enumerate(items):
                                # Skip if already selected as a machine
                                if i in selected_machine_indices:
                                    continue
                                
                                desc = item.get('description', 'No description')
                                first_line = desc.split('\n')[0] if '\n' in desc else desc
                                price_str = item.get('selection_text', '')
                                display_text = f"{first_line} ({price_str})"
                                
                                if st.checkbox(display_text, key=f"common_check_{quote_ref}_{i}"):
                                    selected_common_indices.append(i)
                            
                            # Submit button for manual selection
                            submit_btn = st.form_submit_button("Save Machine Groupings")
                        
                        # Process the manual selection after form submission
                        if submit_btn:
                            try:
                                # Group items based on manual selection
                                machine_data = {"machines": [], "common_items": []}
                                
                                # Add common items first
                                for idx in selected_common_indices:
                                    machine_data["common_items"].append(items[idx])
                                
                                # Create machine entries
                                for idx in selected_machine_indices:
                                    main_machine = items[idx]
                                    machine_name = main_machine.get('description', 'Unknown Machine').split('\n')[0]
                                    
                                    # Find all add-ons that should be associated with this machine
                                    add_ons = []
                                    for i, item in enumerate(items):
                                        # Skip if it's a main machine or common item
                                        if i in selected_machine_indices or i in selected_common_indices:
                                            continue
                                        
                                        # For simplicity, assign remaining items to the closest preceding machine
                                        if i > idx and (i < next((x for x in selected_machine_indices if x > idx), len(items))):
                                            add_ons.append(item)
                                    
                                    # Create the machine entry
                                    machine_data["machines"].append({
                                        "machine_name": machine_name,
                                        "main_item": main_machine,
                                        "add_ons": add_ons
                                    })
                                
                                # Save the manually grouped data
                                if save_machines_data(quote_ref, machine_data):
                                    st.success("Manual machine groupings saved successfully!")
                                    
                                    # Clear the manual selection state
                                    st.session_state.pop(f"manual_items_{quote_ref}", None)
                                    st.session_state.pop(f"show_manual_selection_{quote_ref}", None)
                                    st.rerun()
                                else:
                                    st.error("Failed to save manual machine groupings.")
                            except Exception as e:
                                st.error(f"Error saving manual machine groupings: {e}")
                                st.text(traceback.format_exc())
        except Exception as e:
            st.error(f"Error in CRM client display/edit/delete section: {e}"); traceback.print_exc()
    else: # Nothing selected in the main client dropdown
        client_detail_editor_placeholder.empty()
        save_button_placeholder.empty()
        delete_section_placeholder.empty()
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

# --- Chat Component ---
def render_chat_ui():
    with st.sidebar.expander("💬 Chat Assistant", expanded=False):
        # Get current context for the chat
        context_type, context_data = get_current_context()
        
        # Display current context to the user
        if context_type == "quote":
            st.markdown("**Current context:** Quote processing")
        elif context_type == "client" and context_data:
            st.markdown(f"**Current context:** Client {context_data.get('customer_name', '')}")
        elif context_type == "crm":
            st.markdown("**Current context:** CRM management")
        else:
            st.markdown("**Current context:** General assistance")
        
        # Chat input
        user_query = st.text_input("Ask a question:", key="sidebar_chat_query")
        if st.button("Send", key="send_chat_query"):
            if user_query:
                # Add query to chat history
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                
                # Process the query based on current context
                response = process_chat_query(user_query, context_type, context_data)
                
                # Add response to chat history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                
                # Clear the input box (need to rerun)
                st.session_state.sidebar_chat_query = ""
                st.rerun()
        
        # Display chat history (last 5 exchanges)
        if st.session_state.chat_history:
            st.markdown("### Chat History")
            max_display = min(5, len(st.session_state.chat_history))
            for msg in st.session_state.chat_history[-max_display:]:
                if msg["role"] == "user":
                    st.markdown(f"**You:** {msg['content']}")
                else:
                    st.markdown(f"**Assistant:** {msg['content']}")
            
            if st.button("Clear History", key="clear_chat_history"):
                st.session_state.chat_history = []
                st.rerun()

# --- Main App ---
def main():
    # Set page config
    st.set_page_config(layout="wide", page_title="GOA LLM Assistant")
    
    # Initialize state
    initialize_session_state()
    init_db() # Initialize CRM database at app startup
    
    # Load CRM data once on first load if not already loaded
    if not st.session_state.crm_data_loaded:
        load_crm_data()
    
    # Error message display if needed
    if st.session_state.error_message: 
        st.error(st.session_state.error_message)
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page_options = ["Welcome", "Quote Processing", "Export Documents", "CRM Management"]
    selected_page = st.sidebar.radio("Go to", page_options, index=page_options.index(st.session_state.current_page))
    
    # Update current page in session state
    if selected_page != st.session_state.current_page:
        st.session_state.current_page = selected_page
        # Reset processing step when navigating to Quote Processing
        if selected_page == "Quote Processing":
            st.session_state.processing_step = 0
        st.rerun()
    
    # Render the chat UI in the sidebar
    render_chat_ui()
    
    # Display the selected page
    if st.session_state.current_page == "Welcome":
        show_welcome_page()
    elif st.session_state.current_page == "Quote Processing":
        show_quote_processing()
    elif st.session_state.current_page == "Export Documents":
        show_export_documents()
    elif st.session_state.current_page == "CRM Management":
        show_crm_management()

if __name__ == "__main__":
    main()
