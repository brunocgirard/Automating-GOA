import streamlit as st
import os
import json
import pandas as pd # For st.dataframe
from typing import Dict, List, Optional
import traceback # For detailed error logging
import shutil # For copying files

# Import your existing utility functions
from pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from template_utils import extract_placeholders, extract_placeholder_context_hierarchical
from llm_handler import configure_gemini_client, get_all_fields_via_llm, get_machine_specific_fields_via_llm, get_llm_chat_update, answer_pdf_question
from doc_filler import fill_word_document_from_llm_data
from crm_utils import init_db, save_client_info, load_all_clients, get_client_by_id, update_client_record, save_priced_items, load_priced_items_for_quote, update_single_priced_item, delete_client_record, save_machines_data, load_machines_for_quote, save_machine_template_data, load_machine_template_data, save_document_content, load_document_content

# --- App State Initialization (using st.session_state) ---
def initialize_session_state(is_new_processing_run=False):
    # Initialize navigation and pages
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Welcome"
    if "current_client_profile" not in st.session_state: # Added for dashboard context
        st.session_state.current_client_profile = None
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        
    # Initialize client profile workflow state
    if "profile_extraction_step" not in st.session_state:
        st.session_state.profile_extraction_step = None
    if "extracted_profile" not in st.session_state:
        st.session_state.extracted_profile = None
    if "confirmed_profile" not in st.session_state: # This will hold the active profile for actions
        st.session_state.confirmed_profile = None
    if "action_profile" not in st.session_state: # Potentially redundant if confirmed_profile is used
        st.session_state.action_profile = None
    if "chat_context" not in st.session_state:
        st.session_state.chat_context = None
    if "quote_chat_history" not in st.session_state:
        st.session_state.quote_chat_history = []
    if "current_action" not in st.session_state:
        st.session_state.current_action = None
    
    # Initialize processing step for wizard-style interface (GOA specific)
    if "processing_step" not in st.session_state:
        st.session_state.processing_step = 0
        
    # Initialize session state for machine confirmation during profile creation
    if "selected_main_machines_profile" not in st.session_state:
        st.session_state.selected_main_machines_profile = []
    if "selected_common_options_profile" not in st.session_state:
        st.session_state.selected_common_options_profile = []
    if "profile_machine_confirmation_step" not in st.session_state:
        st.session_state.profile_machine_confirmation_step = "main_machines"
        
    if is_new_processing_run or 'run_key' not in st.session_state: 
        st.session_state.run_key = st.session_state.get('run_key', 0) + (1 if is_new_processing_run else 0)

    keys_to_reset_on_new_pdf_processing_on_welcome_page = [
        'extracted_profile', 'confirmed_profile', 'profile_extraction_step',
        'selected_main_machines_profile', 'selected_common_options_profile',
        'profile_machine_confirmation_step'
    ]
    if is_new_processing_run: # Typically when a new PDF is uploaded on welcome page for profile extraction
        for key in keys_to_reset_on_new_pdf_processing_on_welcome_page:
            if key == "profile_machine_confirmation_step":
                st.session_state[key] = "main_machines"
            else:
                st.session_state[key] = None
        st.session_state.selected_main_machines_profile = []
        st.session_state.selected_common_options_profile = []

    # ... (rest of the original keys_to_reset and machine_keys_to_reset logic for GOA processing) ...
    # This part handles reset for the GOA-specific quote processing workflow
    goa_processing_keys_to_reset = [
        'full_pdf_text', 'processing_done', 'selected_pdf_descs', 'template_contexts',
        'llm_initial_filled_data', 'llm_corrected_filled_data', 'initial_docx_path',
        'corrected_docx_path', 'error_message', 'chat_log', 'correction_applied',
        'identified_machines_data', 'selected_machine_index', 'machine_specific_filled_data', 
        'machine_docx_path', 'selected_machine_id', 'machine_confirmation_done',
        'common_options_confirmation_done', 'items_for_confirmation', 'selected_main_machines',
        'selected_common_options', 'manual_machine_grouping',
        'processing_step' # Reset GOA wizard step
    ]
    goa_default_values = {
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
    # Reset these if is_new_processing_run is true OR if they are not in session_state
    # This logic needs to be careful not to reset profile workflow state if GOA processing is new
    # For now, let's assume is_new_processing_run is primarily for a fresh PDF upload on welcome page for profile extraction.
    # If GOA processing starts, it should have its own reset mechanism if needed.
    if is_new_processing_run: # This flag is now mainly for new profile extraction from welcome page
         for key in goa_processing_keys_to_reset:
            st.session_state[key] = goa_default_values[key]
    else: # Standard initialization for keys not yet in session state
        for key in goa_processing_keys_to_reset:
            if key not in st.session_state:
                 st.session_state[key] = goa_default_values[key]

    if 'all_crm_clients' not in st.session_state: # This is loaded from DB, not reset per run usually
        st.session_state.all_crm_clients = []
    if 'editing_client_id' not in st.session_state: # CRM specific
        st.session_state.editing_client_id = None

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

initialize_session_state() # Call it once at the start
init_db() # Initialize CRM database at app startup

# --- Helper Functions for App --- 

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
            from document_generators import generate_commercial_invoice_data
            
            document_data = generate_commercial_invoice_data(client_data, all_items)
            
            # Add additional calculated fields
            document_data["total_price"] = f"{total_price:.2f}"
            document_data["invoice_no"] = f"INV-{client_data.get('quote_ref', '')}"
            document_data["selected_machines"] = ", ".join([m.get("machine_name", "") for m in selected_machines])
            
        elif document_type == "certificate_of_origin":
            # Import certificate of origin generator
            from document_generators import generate_certificate_of_origin_data
            
            document_data = generate_certificate_of_origin_data(client_data, all_items)
            
            # Add additional calculated fields
            document_data["total_price"] = f"{total_price:.2f}"
            document_data["certificate_no"] = f"COO-{client_data.get('quote_ref', '')}"
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

def quick_extract_and_catalog(uploaded_pdf_file):
    """
    Quickly extract data from a PDF and catalog it in the database without full processing
    """
    temp_pdf_path = None
    try:
        temp_pdf_path = os.path.join(".", uploaded_pdf_file.name)
        with open(temp_pdf_path, "wb") as f:
            f.write(uploaded_pdf_file.getbuffer())
        
        # Extract items and full text
        items = extract_line_item_details(temp_pdf_path)
        full_text = extract_full_pdf_text(temp_pdf_path)
        
        if not items:
            return None
        
        # Create a client record using filename as quote reference
        quote_ref = uploaded_pdf_file.name.split('.')[0]
        client_info = {
            "quote_ref": quote_ref,
            "customer_name": "",  # These fields will be filled in later
            "machine_model": "",
            "country_destination": "",
            "sold_to_address": "",
            "ship_to_address": "",
            "telephone": "",
            "customer_contact_person": "",
            "customer_po": ""
        }
        
        # Save to database
        if save_client_info(client_info):
            if save_priced_items(quote_ref, items):
                if full_text:
                    save_document_content(quote_ref, full_text, uploaded_pdf_file.name)
                return {
                    "quote_ref": quote_ref,
                    "items": items
                }
        return None
    except Exception as e:
        print(f"Error in quick_extract_and_catalog: {e}")
        traceback.print_exc()
        return None
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

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
                
                # Save document content for later chat functionality
                if st.session_state.full_pdf_text:
                    if save_document_content(client_info_payload['quote_ref'], st.session_state.full_pdf_text, uploaded_pdf_file.name):
                        st.write(f"Document content saved for future chat functionality.")
                    else:
                        st.warning(f"Failed to save document content.")
                
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
    Load a previously processed document for chat functionality.
    
    Args:
        client_id: ID of the client record to load
    """
    try:
        # Reset to a clean state while preserving run key
        current_run_key = st.session_state.run_key
        initialize_session_state(is_new_processing_run=True)
        st.session_state.run_key = current_run_key
        
        # Get client data
        client_data = get_client_by_id(client_id)
        if not client_data:
            st.error(f"Client with ID {client_id} not found.")
            return False
        
        quote_ref = client_data.get("quote_ref")
        
        # Load document content
        document_content = load_document_content(quote_ref)
        if not document_content:
            st.error(f"Document content for quote {quote_ref} not found.")
            return False
        
        # Set full PDF text in session state
        st.session_state.full_pdf_text = document_content.get("full_pdf_text", "")
        
        # Load priced items
        priced_items = load_priced_items_for_quote(quote_ref)
        st.session_state.selected_pdf_items_structured = priced_items
        st.session_state.selected_pdf_descs = [item.get("item_description","") for item in priced_items if item.get("item_description")]
        
        # Load machines data
        machines_data = load_machines_for_quote(quote_ref)
        if machines_data:
            # Convert from database format to session state format
            machines_list = []
            common_items = []
            
            for machine in machines_data:
                machine_data = machine.get("machine_data", {})
                if machine_data:
                    machines_list.append(machine_data)
                    # Get common items from the first machine (they should be the same for all)
                    if not common_items and "common_items" in machine_data:
                        common_items = machine_data.get("common_items", [])
            
            st.session_state.identified_machines_data = {
                "machines": machines_list,
                "common_items": common_items
            }
        
        # Set processing state
        st.session_state.processing_done = True
        st.session_state.machine_confirmation_done = True
        st.session_state.common_options_confirmation_done = True
        
        return True
    except Exception as e:
        st.error(f"Error loading previous document: {e}")
        st.text(traceback.format_exc())
        return False

# --- Context-Aware Chat Functions ---
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
    st.title("Welcome to the QuoteFlow Document Assistant")
    
    # If a profile is loaded and action selection is pending, show Action Hub
    if st.session_state.get("profile_extraction_step") == "action_selection" and st.session_state.get("confirmed_profile"):
        action = show_action_selection(st.session_state.get("confirmed_profile"))
        if action:
            handle_selected_action(action, st.session_state.get("confirmed_profile"))
            # Keep profile_extraction_step as "action_selection" unless an action explicitly changes page
            # or resets the flow. Action hub should be sticky for the current profile.
            st.rerun() # Rerun to reflect any state changes from handle_selected_action
        return # Exit to prevent showing rest of welcome page

    st.markdown("""
    ## What This Application Does
    This tool helps you process machine quotes to generate various documents and manage client data.
    
    ## Getting Started
    Upload a quote PDF to extract client profile information or process it directly.
    """)
    
    uploaded_pdf = st.file_uploader("Choose PDF Quote", type="pdf", key="welcome_page_uploader")
    
    if uploaded_pdf:
        # When a new PDF is uploaded, reset relevant profile extraction states
        # initialize_session_state(is_new_processing_run=True) # This might be too broad, reset specific profile states instead
        st.session_state.extracted_profile = None
        st.session_state.confirmed_profile = None
        st.session_state.profile_extraction_step = "ready_to_extract" # Initial state before extraction
        st.session_state.selected_main_machines_profile = []
        st.session_state.selected_common_options_profile = []
        st.session_state.profile_machine_confirmation_step = "main_machines"

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Extract Client Profile", type="primary"):
                with st.spinner("Extracting client profile..."):
                    temp_pdf_path = os.path.join(".", uploaded_pdf.name)
                    try:
                        with open(temp_pdf_path, "wb") as f:
                            f.write(uploaded_pdf.getbuffer())
                        profile = extract_client_profile(temp_pdf_path)
                        if profile:
                            st.session_state.extracted_profile = profile
                            st.session_state.profile_extraction_step = "confirm" # Move to confirmation step
                            st.rerun()
                        else:
                            st.error("Failed to extract client profile. Please try again.")
                    finally:
                        if os.path.exists(temp_pdf_path):
                            os.remove(temp_pdf_path)
        
        with col2:
            if st.button("🚀 Process Document Directly (GOA)", key="direct_process_btn"):
                # This button should trigger the GOA-specific processing flow
                # It might need to pass the uploaded_pdf to perform_initial_processing
                # For now, it just navigates. Actual processing needs wiring.
                st.session_state.current_page = "Quote Processing" 
                # Perform initial processing directly for GOA workflow
                TEMPLATE_FILE = "template.docx"
                if not os.path.exists(TEMPLATE_FILE): 
                    st.error(f"Template '{TEMPLATE_FILE}' not found.")
                else:
                    # Pass the uploaded PDF to the initial processing function
                    # This assumes perform_initial_processing is adapted or can handle this
                    if perform_initial_processing(uploaded_pdf, TEMPLATE_FILE):
                        st.session_state.processing_step = 1 # Move to GOA machine confirmation
                    else:
                        st.error("Failed to start direct document processing.")
                st.rerun()
    
    if st.session_state.get("profile_extraction_step") == "confirm":
        if st.session_state.get("extracted_profile"):
            confirmed_profile = confirm_client_profile(st.session_state.get("extracted_profile"))
            if confirmed_profile:
                st.session_state.confirmed_profile = confirmed_profile
                st.session_state.current_client_profile = confirmed_profile 
                st.session_state.current_page = "Client Dashboard"
                st.session_state.profile_extraction_step = None # Reset this flow
                st.rerun()
        else:
            st.info("Upload a PDF to extract and confirm a client profile.")

    st.markdown("---")
    st.markdown("### Alternative Options")
    col_alt1, col_alt2, col_alt3 = st.columns(3)
    with col_alt1:
        if st.button("👤 Client Dashboard", key="goto_dashboard"):
            st.session_state.current_page = "Client Dashboard"
            st.rerun()
    with col_alt2:
        if st.button("⚙️ Process Quote for GOA", key="goto_processing"):
            st.session_state.current_page = "Quote Processing"
            st.rerun()
    with col_alt3:
        if st.button("📒 View CRM Data", key="goto_crm"):
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
        
        # Add option to load previous document
        st.subheader("📂 Load Previous Document")
        
        # Get list of quotes from database
        if st.session_state.all_crm_clients:
            quotes = [(c['id'], f"{c.get('customer_name', 'Unknown')} - {c.get('quote_ref', 'Unknown')}") 
                     for c in st.session_state.all_crm_clients]
            
            if quotes:
                selected_quote_id = st.selectbox(
                    "Select a previous quote:",
                    options=[q[0] for q in quotes],
                    format_func=lambda x: next((q[1] for q in quotes if q[0] == x), ""),
                    key="load_previous_quote"
                )
                
                if st.button("📥 Load Selected Quote", key="load_quote_btn"):
                    with st.spinner("Loading document..."):
                        if load_previous_document(selected_quote_id):
                            st.success("Document loaded successfully!")
                            st.session_state.processing_step = 1  # Go to machine selection step
                            st.rerun()
            else:
                st.info("No previous quotes found. Upload a new document to begin.")
    
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

# --- Helper Functions for Client Profile Workflow ---

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
            from llm_handler import gemini_client, genai
            generation_config = genai.types.GenerationConfig(
                temperature=0.2, # Lower temperature for more focused output
                top_p=0.95,
                max_output_tokens=2048
            )
            response = gemini_client.generate_content(
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
        machines_data = identify_machines_from_items(line_items)
        
        # Build the complete profile
        profile = {
            "client_info": mapped_client_info,
            "standard_fields": client_info,  # Keep original extraction for reference
            "line_items": line_items,
            "machines_data": machines_data,
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
    
    # Initialize session state for machine confirmation if not present
    if "selected_main_machines_profile" not in st.session_state:
        st.session_state.selected_main_machines_profile = []
    if "selected_common_options_profile" not in st.session_state:
        st.session_state.selected_common_options_profile = []
    if "profile_machine_confirmation_step" not in st.session_state:
        st.session_state.profile_machine_confirmation_step = "main_machines" # or "common_options"

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
                # Removed single machine model input from here
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
        
        with tab2:
            col1, col2 = st.columns(2)
            
            with col1:
                client_info["billing_address"] = st.text_area(
                    "Billing Address", 
                    value=client_info.get("billing_address", ""),
                    height=150
                )
                
                # Add more advanced fields
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
            # Placeholder or message indicating machine selection is pending
            st.form_submit_button("Next: Confirm Machines", disabled=True)
            submit_button = False # Ensure it doesn't trigger save yet
    
    # Update the profile with confirmed info (before machine selection)
    confirmed_profile["client_info"] = client_info
    confirmed_profile["standard_fields"] = standard_fields
    
    # --- Interactive Machine Selection --- 
    st.markdown("### 2. Confirm Identified Machines")
    items_for_machine_confirmation = confirmed_profile.get("line_items", [])
    
    if not items_for_machine_confirmation:
        st.info("No line items found in the quote to identify machines.")
        st.session_state.profile_machine_confirmation_step = "done" # Skip if no items
    
    elif st.session_state.profile_machine_confirmation_step == "main_machines":
        st.markdown("Select all items that are **main machines**.")
        selected_indices_main = []
        with st.container():
            for i, item in enumerate(items_for_machine_confirmation):
                desc = item.get('description', 'No description')
                first_line = desc.split('\n')[0] if '\n' in desc else desc
                price_str = item.get('selection_text', '') or item.get('item_price_str', '')
                display_text = f"{first_line} ({price_str})"
                
                # Check if pre-selected by initial LLM pass (optional)
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
                st.session_state.extracted_profile["machines_data"] = updated_machines_data # Update session state copy too
                st.session_state.profile_machine_confirmation_step = "done"
                st.success("Machines re-grouped based on your selection.")
                st.rerun()
                
    elif st.session_state.profile_machine_confirmation_step == "done":
        # Machine Information Summary (after confirmation)
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

    # Save to database if form submitted and machine confirmation is done
    if submit_button and st.session_state.profile_machine_confirmation_step == "done":
        if client_info.get("client_name") and client_info.get("quote_ref"):
            client_record = {
                "quote_ref": client_info.get("quote_ref"),
                "customer_name": client_info.get("client_name"),
                "machine_model": ", ".join([m.get("machine_name", "") for m in confirmed_profile.get("machines_data", {}).get("machines", [])]),
                "country_destination": client_info.get("country_destination", ""), # Added field from form
                "sold_to_address": client_info.get("billing_address"),
                "ship_to_address": client_info.get("shipping_address"),
                "telephone": client_info.get("phone"),
                "customer_contact_person": client_info.get("contact_person"),
                "customer_po": client_info.get("customer_po"),
                "incoterm": client_info.get("incoterm"),
                "quote_date": client_info.get("quote_date")
            }
            
            # Add standard fields that are not directly in client_info but are in standard_fields
            client_record["tax_id"] = standard_fields.get("Tax ID", "")
            client_record["hs_code"] = standard_fields.get("H.S", "")
            client_record["shipping_method"] = standard_fields.get("Via", "")
            client_record["serial_number"] = standard_fields.get("Serial Number", "")
            # Ensure all expected keys for save_client_info are present, even if empty
            
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
                load_crm_data()
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
    
    # Client profile summary
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"### {client_info.get('client_name', 'Unknown Client')}")
            st.markdown(f"**Quote:** {client_info.get('quote_ref', 'N/A')}")
            st.markdown(f"**Contact:** {client_info.get('contact_person', 'N/A')}")
            if client_info.get("phone"):
                st.markdown(f"**Phone:** {client_info.get('phone', 'N/A')}")
        
        with col2:
            # Display machine models from machines_data
            machines_list = client_profile.get("machines_data", {}).get("machines", [])
            if machines_list:
                models_str = ", ".join(
                    [m.get("machine_name", "Unknown") for m in machines_list[:3]] # Show first 3
                )
                if len(machines_list) > 3:
                    models_str += f" and {len(machines_list) - 3} more"
                st.markdown(f"**Machine Models:** {models_str}")
            else:
                st.markdown("**Machine Models:** Not Identified")
            
            if client_info.get("incoterm"):
                st.markdown(f"**Incoterm:** {client_info.get('incoterm', 'N/A')}")
            if client_info.get("quote_date"):
                st.markdown(f"**Date:** {client_info.get('quote_date', 'N/A')}")
            if client_info.get("customer_po"):
                st.markdown(f"**PO:** {client_info.get('customer_po', 'N/A')}")
        
        with col3:
            machines_count = len(client_profile.get("machines_data", {}).get("machines", []))
            items_count = len(client_profile.get("line_items", []))
            st.metric("Machines", machines_count)
            st.metric("Line Items", items_count)
    
    # Action cards
    st.markdown("### Available Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        goa_card = st.container(border=True)
        with goa_card:
            st.markdown("### 📄 Generate GOA Document")
            st.markdown("Create General Order Agreement documents for specific machines")
            if st.button("Generate GOA", key="action_goa", use_container_width=True):
                st.session_state.current_action = "goa_generation"
                st.session_state.action_profile = client_profile
                return "goa_generation"
    
    with col2:
        export_card = st.container(border=True)
        with export_card:
            st.markdown("### 📦 Export Documents")
            st.markdown("Create packing slips, commercial invoices and certificates")
            if st.button("Export Documents", key="action_export", use_container_width=True):
                st.session_state.current_action = "export_documents"
                st.session_state.action_profile = client_profile
                return "export_documents"
    
    col3, col4 = st.columns(2)
    
    with col3:
        edit_card = st.container(border=True)
        with edit_card:
            st.markdown("### ✏️ Edit Profile")
            st.markdown("Update client information and manage machines")
            if st.button("Edit Profile", key="action_edit", use_container_width=True):
                st.session_state.current_action = "edit_profile"
                st.session_state.action_profile = client_profile
                return "edit_profile"
    
    with col4:
        chat_card = st.container(border=True)
        with chat_card:
            st.markdown("### 💬 Chat with Quote")
            st.markdown("Ask questions about the quote and get answers")
            if st.button("Chat Interface", key="action_chat", use_container_width=True):
                st.session_state.current_action = "chat"
                st.session_state.action_profile = client_profile
                return "chat"
    
    # Profile details expander
    with st.expander("View Full Profile Details", expanded=False):
        tab1, tab2 = st.tabs(["Addresses", "Additional Fields"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Billing Address:**")
                st.text(client_info.get("billing_address", "Not provided"))
            with col2:
                st.markdown("**Shipping Address:**")
                st.text(client_info.get("shipping_address", "Not provided"))
        
        with tab2:
            # Display any additional standard fields that might be useful
            st.markdown("**Additional Information:**")
            extra_fields = []
            for key, value in standard_fields.items():
                if value and key not in ["Customer", "Company", "Quote No", "Machine"]:
                    extra_fields.append((key, value))
            
            if extra_fields:
                for key, value in extra_fields:
                    st.markdown(f"**{key}:** {value}")
            else:
                st.info("No additional information available")
    
    return None

def handle_selected_action(action, profile_data):
    """
    Route to the appropriate function based on selected action
    """
    if action == "goa_generation":
        # Set the current page and step for the wizard interface
        st.session_state.current_page = "Quote Processing"
        st.session_state.processing_step = 1  # Skip to machine selection step
        
        # Pre-populate session state with profile data
        st.session_state.full_pdf_text = profile_data.get("full_text", "")
        st.session_state.items_for_confirmation = profile_data.get("line_items", [])
        st.session_state.processing_done = True
        
        # Extract placeholder contexts
        TEMPLATE_FILE = "template.docx"
        if os.path.exists(TEMPLATE_FILE):
            st.session_state.template_contexts = extract_placeholder_context_hierarchical(TEMPLATE_FILE)
        
        # Pre-select machines
        machines_data = profile_data.get("machines_data", {})
        
        # Setup for machine confirmation
        st.session_state.selected_main_machines = []
        st.session_state.selected_common_options = []
        
        # Add pre-selection logic based on machines_data
        for i, item in enumerate(st.session_state.items_for_confirmation):
            # Check if this item is a main item in any machine
            is_main_machine = False
            for machine in machines_data.get("machines", []):
                if machine.get("main_item") == item:
                    is_main_machine = True
                    st.session_state.selected_main_machines.append(i)
                    break
            
            # Check if this item is in common items
            if not is_main_machine:
                for common_item in machines_data.get("common_items", []):
                    if common_item == item:
                        st.session_state.selected_common_options.append(i)
                        break
        
        return
    
    elif action == "export_documents":
        # Set the current page to export documents
        st.session_state.current_page = "Export Documents"
        
        # Pre-select the client in the export UI
        client_info = profile_data.get("client_info", {})
        quote_ref = client_info.get("quote_ref")
        
        # Find the client ID from the quote reference
        if st.session_state.all_crm_clients:
            for client in st.session_state.all_crm_clients:
                if client.get("quote_ref") == quote_ref:
                    st.session_state.selected_client_for_detail_edit = client
                    break
        
        return
    
    elif action == "edit_profile":
        # Set the current page to CRM management
        st.session_state.current_page = "CRM Management"
        
        # Pre-select the client in the CRM UI
        client_info = profile_data.get("client_info", {})
        quote_ref = client_info.get("quote_ref")
        
        # Find the client ID from the quote reference
        if st.session_state.all_crm_clients:
            for client in st.session_state.all_crm_clients:
                if client.get("quote_ref") == quote_ref:
                    st.session_state.selected_client_for_detail_edit = client
                    st.session_state.editing_client_id = client.get("id")
                    break
        
        return
    
    elif action == "chat":
        # Set up chat interface with the quote context
        st.session_state.current_page = "Chat"
        st.session_state.chat_context = {
            "full_pdf_text": profile_data.get("full_text", ""),
            "client_info": profile_data.get("client_info", {})
        }
        
        return
    
    return

def show_chat_page():
    """
    Display the chat interface for interacting with a specific quote
    """
    st.title("💬 Chat with Quote")
    
    # Check if we have chat context
    if not st.session_state.get("chat_context"):
        st.warning("No quote context available for chat. Please select a quote first.")
        
        if st.button("Return to Welcome Page"):
            st.session_state.current_page = "Welcome"
            st.rerun()
        return
    
    # Display client info
    client_info = st.session_state.chat_context.get("client_info", {})
    if client_info:
        st.markdown(f"**Client:** {client_info.get('client_name', 'Unknown')}")
        st.markdown(f"**Quote:** {client_info.get('quote_ref', 'Unknown')}")
    
    # Chat interface
    st.markdown("### Ask questions about this quote")
    
    # Initialize chat history if needed
    if "quote_chat_history" not in st.session_state:
        st.session_state.quote_chat_history = []
    
    # Display chat history
    for message in st.session_state.quote_chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Input for new messages
    if prompt := st.chat_input("Ask a question about this quote..."):
        # Add user message to history
        st.session_state.quote_chat_history.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate response
        with st.spinner("Thinking..."):
            try:
                # Get the full PDF text from context
                full_pdf_text = st.session_state.chat_context.get("full_pdf_text", "")
                
                # Use the answer_pdf_question function to get a response
                response = answer_pdf_question(
                    prompt, 
                    [],  # No specific descriptions needed
                    full_pdf_text,
                    {}   # No template contexts needed
                )
                
                # Add assistant response to history
                st.session_state.quote_chat_history.append({"role": "assistant", "content": response})
                
                # Display assistant response
                with st.chat_message("assistant"):
                    st.write(response)
            except Exception as e:
                st.error(f"Error generating response: {e}")
                traceback.print_exc()
    
    # Button to return to action selection
    st.markdown("---")
    if st.button("Return to Action Selection", key="return_to_actions"):
        # Reset the flow to action selection
        if st.session_state.get("confirmed_profile"):
            st.session_state.profile_extraction_step = "action_selection"
            st.session_state.chat_context = None
            st.session_state.current_page = "Welcome"
            st.rerun()
        else:
            st.session_state.current_page = "Welcome"
            st.rerun()

# --- Streamlit UI --- 
st.set_page_config(layout="wide", page_title="QuoteFlow Document Assistant")
st.title("📄 QuoteFlow Document Assistant")

# Load CRM data once on first load if not already loaded
if not st.session_state.crm_data_loaded:
    load_crm_data()

# Show error message if there is one
if st.session_state.error_message: 
    st.error(st.session_state.error_message)

def load_full_client_profile(quote_ref: str) -> Optional[Dict]:
    """Loads all data for a client to reconstruct the profile object."""
    client_info_db = None
    if st.session_state.all_crm_clients:
        client_summary = next((c for c in st.session_state.all_crm_clients if c.get("quote_ref") == quote_ref), None)
        if client_summary:
            client_info_db = get_client_by_id(client_summary.get("id"))
    
    if not client_info_db:
        st.error(f"Client with quote_ref {quote_ref} not found for full profile load.")
        return None

    client_info_app_structure = {
        "client_name": client_info_db.get("customer_name", ""),
        "quote_ref": client_info_db.get("quote_ref", ""),
        "contact_person": client_info_db.get("customer_contact_person", ""),
        "phone": client_info_db.get("telephone", ""),
        "billing_address": client_info_db.get("sold_to_address", ""),
        "shipping_address": client_info_db.get("ship_to_address", ""),
        "customer_po": client_info_db.get("customer_po", ""),
        "incoterm": client_info_db.get("incoterm", ""),
        "quote_date": client_info_db.get("quote_date", ""),
        "country_destination": client_info_db.get("country_destination", "")
    }
    line_items = load_priced_items_for_quote(quote_ref)
    machines_data_db = load_machines_for_quote(quote_ref)
    app_machines_list = []
    app_common_items = []
    if machines_data_db:
        if machines_data_db and isinstance(machines_data_db, list) and len(machines_data_db) > 0 and machines_data_db[0].get("machine_data"):
            first_machine_full_data = machines_data_db[0].get("machine_data", {})
            app_common_items = first_machine_full_data.get("common_items", [])
        for machine_record in machines_data_db:
            machine_detail = machine_record.get("machine_data", {})
            app_machines_list.append({
                "machine_name": machine_detail.get("machine_name"),
                "main_item": machine_detail.get("main_item"),
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
    }
    profile = {
        "client_info": client_info_app_structure, "standard_fields": standard_fields_reconstructed, 
        "line_items": line_items, "machines_data": machines_data_app_structure,
        "full_text": full_text, "pdf_filename": pdf_filename
    }
    return profile

def show_crm_management_page():
    st.title("📒 CRM Management")
    
    # Tabs for different CRM management functions
    tab1, tab2, tab3, tab4 = st.tabs(["View/Edit Clients", "Client Details", "Priced Items", "Delete Client"])
    
    # Tab 1: View/Edit Clients
    with tab1:
        st.subheader("Client Records")
        
        # Initialize client data if not loaded
        if not st.session_state.crm_data_loaded:
            load_crm_data()
        
        clients = st.session_state.all_crm_clients
        if not clients:
            st.info("No clients found in the database.")
        else:
            # Create a dataframe for display
            clients_df = pd.DataFrame(clients)
            # Select columns for display
            display_cols = ["id", "quote_ref", "customer_name", "machine_model", "customer_contact_person", "telephone", "incoterm", "quote_date"]
            display_df = clients_df[[c for c in display_cols if c in clients_df.columns]]
            
            # Format column names for display
            formatted_cols = {
                "id": "ID", 
                "quote_ref": "Quote Ref", 
                "customer_name": "Customer", 
                "machine_model": "Machine", 
                "customer_contact_person": "Contact Person", 
                "telephone": "Phone",
                "incoterm": "Incoterm",
                "quote_date": "Quote Date"
            }
            display_df = display_df.rename(columns={k: v for k, v in formatted_cols.items() if k in display_df.columns})
            
            # Display dataframe with row selection
            selection = st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "ID": st.column_config.NumberColumn(format="%d")
                },
                hide_index=True
            )
            
            # Selection for editing
            client_id_for_edit = st.selectbox(
                "Select a client to edit:",
                options=[c["id"] for c in clients],
                format_func=lambda x: next((f"{c['customer_name']} - {c['quote_ref']}" for c in clients if c["id"] == x), ""),
                key="crm_client_select"
            )
            
            if st.button("Edit Selected Client", key="edit_client_btn"):
                st.session_state.selected_client_for_detail_edit = next((c for c in clients if c["id"] == client_id_for_edit), None)
                st.session_state.editing_client_id = client_id_for_edit
                st.rerun()
    
    # Tab 2: Client Details (when a client is selected)
    with tab2:
        if st.session_state.selected_client_for_detail_edit:
            client = st.session_state.selected_client_for_detail_edit
            st.subheader(f"Editing Client: {client.get('customer_name', 'Unknown')}")
            
            with st.form("client_detail_edit_form"):
                # Basic fields
                col1, col2 = st.columns(2)
                
                with col1:
                    edited_quote_ref = st.text_input("Quote Reference", value=client.get("quote_ref", ""))
                    edited_customer_name = st.text_input("Customer Name", value=client.get("customer_name", ""))
                    edited_machine_model = st.text_input("Machine Model", value=client.get("machine_model", ""))
                    edited_customer_po = st.text_input("Customer PO", value=client.get("customer_po", ""))
                
                with col2:
                    edited_contact_person = st.text_input("Contact Person", value=client.get("customer_contact_person", ""))
                    edited_telephone = st.text_input("Telephone", value=client.get("telephone", ""))
                    edited_country = st.text_input("Country", value=client.get("country_destination", ""))
                    edited_incoterm = st.text_input("Incoterm", value=client.get("incoterm", ""))
                    edited_quote_date = st.text_input("Quote Date", value=client.get("quote_date", ""))
                
                # Address fields
                st.markdown("### Addresses")
                col3, col4 = st.columns(2)
                
                with col3:
                    edited_sold_to = st.text_area("Billing Address", value=client.get("sold_to_address", ""), height=150)
                
                with col4:
                    edited_ship_to = st.text_area("Shipping Address", value=client.get("ship_to_address", ""), height=150)
                
                # Submit button
                submit_edit = st.form_submit_button("Save Changes")
                
                if submit_edit:
                    # Prepare updated client record
                    updated_client = {
                        "id": client.get("id"),
                        "quote_ref": edited_quote_ref,
                        "customer_name": edited_customer_name,
                        "machine_model": edited_machine_model,
                        "country_destination": edited_country,
                        "sold_to_address": edited_sold_to,
                        "ship_to_address": edited_ship_to,
                        "telephone": edited_telephone,
                        "customer_contact_person": edited_contact_person,
                        "customer_po": edited_customer_po,
                        "incoterm": edited_incoterm,
                        "quote_date": edited_quote_date
                    }
                    
                    # Update the client record
                    if update_client_record(updated_client):
                        st.success("Client record updated successfully.")
                        # Refresh CRM data
                        load_crm_data()
                        # Reset selected client for edit to reflect changes
                        st.session_state.selected_client_for_detail_edit = next(
                            (c for c in st.session_state.all_crm_clients if c["id"] == client.get("id")),
                            None
                        )
                        st.rerun()
                    else:
                        st.error("Failed to update client record.")
        else:
            st.info("Select a client from the 'View/Edit Clients' tab to edit details.")
    
    # Tab 3: Priced Items
    with tab3:
        st.subheader("Priced Items")
        
        if st.session_state.selected_client_for_detail_edit:
            client = st.session_state.selected_client_for_detail_edit
            quote_ref = client.get("quote_ref")
            
            st.markdown(f"### Items for {client.get('customer_name', 'Unknown')} - {quote_ref}")
            
            # Load priced items for this quote
            priced_items = load_priced_items_for_quote(quote_ref)
            
            if priced_items:
                # Convert to DataFrame for display
                items_df = pd.DataFrame(priced_items)
                
                # Select columns to display
                display_columns = ["item_description", "quantity_text", "selection_text", "item_price_str"]
                if all(col in items_df.columns for col in display_columns):
                    display_df = items_df[display_columns]
                else:
                    # Fallback to available columns
                    display_df = items_df
                
                # Rename columns for better display
                column_rename = {
                    "item_description": "Description",
                    "quantity_text": "Quantity",
                    "selection_text": "Selection",
                    "item_price_str": "Price"
                }
                display_df = display_df.rename(columns=column_rename)
                
                # Display the dataframe
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    height=400
                )
                
                # Show total if price information is available
                if "item_price_numeric" in items_df.columns:
                    total_price = items_df["item_price_numeric"].sum()
                    st.markdown(f"**Total Price: ${total_price:,.2f}**")
                
                # Export button
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"priced_items_{quote_ref}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No priced items found for this client.")
        else:
            st.info("Select a client from the 'View/Edit Clients' tab to view their priced items.")
    
    # Tab 4: Delete Client
    with tab4:
        st.subheader("Delete Client Record")
        st.warning("Warning: Deleting a client record will permanently remove all associated data.")
        
        # Selection for deletion
        if st.session_state.all_crm_clients:
            client_id_for_delete = st.selectbox(
                "Select a client to delete:",
                options=[c["id"] for c in st.session_state.all_crm_clients],
                format_func=lambda x: next((f"{c['customer_name']} - {c['quote_ref']}" for c in st.session_state.all_crm_clients if c["id"] == x), ""),
                key="crm_client_delete_select"
            )
            
            if st.button("Delete Selected Client", key="delete_client_btn", type="primary"):
                st.session_state.confirming_delete_client_id = client_id_for_delete
                st.rerun()
            
            # Confirmation dialog
            if st.session_state.confirming_delete_client_id:
                client_to_delete = next((c for c in st.session_state.all_crm_clients if c["id"] == st.session_state.confirming_delete_client_id), None)
                if client_to_delete:
                    st.error(f"Are you sure you want to delete {client_to_delete.get('customer_name')} - {client_to_delete.get('quote_ref')}?")
                    
                    col_cancel, col_confirm = st.columns(2)
                    with col_cancel:
                        if st.button("Cancel", key="cancel_delete_btn"):
                            st.session_state.confirming_delete_client_id = None
                            st.rerun()
                    
                    with col_confirm:
                        if st.button("Confirm Delete", key="confirm_delete_btn", type="primary"):
                            if delete_client_record(st.session_state.confirming_delete_client_id):
                                st.success("Client record deleted successfully.")
                                # Reset state and refresh data
                                st.session_state.confirming_delete_client_id = None
                                st.session_state.selected_client_for_detail_edit = None
                                load_crm_data()
                                st.rerun()
                            else:
                                st.error("Failed to delete client record.")
        else:
            st.info("No clients available to delete.")

def show_client_dashboard_page():
    st.title("👤 Client Dashboard")
    st.markdown("Select a client to view their profile and available actions, or upload a new quote on the Welcome page.")
    if not st.session_state.crm_data_loaded:
        load_crm_data()
    clients = st.session_state.all_crm_clients
    if not clients:
        st.info("No clients found. Upload a quote on the Welcome page to create a client profile.")
        if st.button("Go to Welcome Page", key="dash_to_welcome_no_clients"):
            st.session_state.current_page = "Welcome"; st.rerun()
        return
    search_term = st.text_input("Search clients (by name or quote ref)", key="client_dashboard_search_input")
    filtered_clients = [c for c in clients if (search_term.lower() in c.get("customer_name", "").lower() or 
                                            search_term.lower() in c.get("quote_ref", "").lower())] if search_term else clients
    if not filtered_clients and search_term:
        st.warning(f"No clients found matching '{search_term}'.")
    for client_summary_item in filtered_clients:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.subheader(f"{client_summary_item.get('customer_name', 'N/A')}")
                st.caption(f"Quote Ref: {client_summary_item.get('quote_ref', 'N/A')}")
            with col2:
                processing_date_str = client_summary_item.get('processing_date', 'N/A')
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
                    else:
                        st.error(f"Could not load full profile for {client_summary_item.get('quote_ref')}.")
            st.markdown("&nbsp;") 

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
page_options = ["Welcome", "Client Dashboard", "Quote Processing", "Export Documents", "CRM Management", "Chat"]

default_page_index = 0
try:
    default_page_index = page_options.index(st.session_state.current_page)
except ValueError:
    st.session_state.current_page = "Welcome" 
    default_page_index = 0

selected_page = st.sidebar.radio("Go to", page_options, index=default_page_index)

if selected_page != st.session_state.current_page:
    st.session_state.current_page = selected_page
    if selected_page == "Quote Processing":
        st.session_state.processing_step = 0 
    if st.session_state.current_page != "Welcome" and st.session_state.get("profile_extraction_step") is not None:
        if st.session_state.current_page != "Client Dashboard": 
            st.session_state.profile_extraction_step = None
            st.session_state.confirmed_profile = None 
            st.session_state.extracted_profile = None
    st.rerun()

render_chat_ui() # General sidebar chat

# --- Display the selected page ---
if st.session_state.current_page == "Welcome":
    show_welcome_page()
elif st.session_state.current_page == "Client Dashboard":
    show_client_dashboard_page() # Ensuring this call is present
elif st.session_state.current_page == "Quote Processing":
    show_quote_processing()
elif st.session_state.current_page == "Export Documents":
    # Placeholder: Content for Export Documents page needs to be here
    # This section was previously overwritten; it needs its original UI code restored.
    # For now, let's just put a header to confirm navigation.
    st.header("📦 Export Documents")
    st.info("Content for Export Documents page to be restored here.")
elif st.session_state.current_page == "CRM Management":
    show_crm_management_page()
elif st.session_state.current_page == "Chat":
    show_chat_page()
