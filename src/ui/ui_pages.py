import streamlit as st
import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
import traceback
import shutil
from datetime import datetime
import uuid
import re
import numpy as np
import time
import random
from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS, SORTSTAR_EXPLICIT_MAPPINGS, parse_full_fields_outline


# Import from other modules
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection, 
    handle_selected_action, load_full_client_profile
)

# Import from utility modules
from src.utils.pdf_utils import extract_line_item_details, extract_full_pdf_text, identify_machines_from_items
from src.utils.llm_handler import configure_gemini_client, get_machine_specific_fields_via_llm, answer_pdf_question
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.crm_utils import (
    init_db, save_client_info, load_all_clients, get_client_by_id, 
    update_client_record, save_priced_items, load_priced_items_for_quote, 
    update_single_priced_item, delete_client_record, save_machines_data, 
    load_machines_for_quote, save_machine_template_data, load_machine_template_data, 
    save_document_content, load_document_content,
    load_machine_templates_with_modifications, save_goa_modification,
    update_template_after_modifications, find_machines_by_name, load_all_processed_machines
)
from src.generators.document_generators import generate_packing_slip_data, generate_commercial_invoice_data, generate_certificate_of_origin_data

# Moved from app.py
def show_welcome_page():
    """
    Displays the welcome page interface with quote upload and client dashboard access
    """
    st.title("QuoteFlow Document Assistant")
    
    # MODAL: Profile extraction workflow - confirmation step should be first
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "confirmation":
        if "extracted_profile" in st.session_state and st.session_state.extracted_profile:
            # Show confirmation UI and stop rendering the rest of the page
            st.session_state.confirmed_profile = confirm_client_profile(st.session_state.extracted_profile)
            if st.session_state.confirmed_profile:
                st.session_state.profile_extraction_step = "action_selection"
                st.rerun()
            return # Stop rendering the rest of the page
    
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
        
        if st.button("Extract Full Profile", key="extract_profile_btn", type="primary", use_container_width=True):
            st.session_state.extracted_profile = extract_client_profile(uploaded_file)
            if st.session_state.extracted_profile:
                st.session_state.profile_extraction_step = "confirmation"
                st.rerun()
            else:
                st.error("Failed to extract profile from the uploaded PDF.")
    
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
    st.title("🎯 Client Dashboard")
    
    # MODAL: Profile extraction workflow - confirmation step should be first
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "confirmation":
        if "extracted_profile" in st.session_state and st.session_state.extracted_profile:
            # Show confirmation UI and stop rendering the rest of the page
            st.session_state.confirmed_profile = confirm_client_profile(st.session_state.extracted_profile)
            if st.session_state.confirmed_profile:
                st.session_state.profile_extraction_step = "action_selection"
                st.rerun()
            return # Stop rendering the rest of the page
    
    # Status check for existing client profiles
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "action_selection":
        if "confirmed_profile" in st.session_state and st.session_state.confirmed_profile:
            profile = st.session_state.confirmed_profile
            action = show_action_selection(profile)

            # --- Explicitly handle chat navigation ---
            if action and "chat" in action.lower():
                # Correctly get client_info from the profile's "client_info" key
                client_info = profile.get("client_info", {})
                quote_ref = client_info.get("quote_ref")

                if not quote_ref:
                    st.error("Cannot start chat. Client profile is missing a quote reference.")
                    return

                # The full profile should already contain the document content
                doc_content = profile.get("document_content", {})
                full_text = doc_content.get("full_pdf_text", "")

                # If for some reason it's missing, try to load it directly as a fallback
                if not full_text:
                    from src.utils.crm_utils import load_document_content
                    loaded_doc = load_document_content(quote_ref)
                    full_text = loaded_doc.get("full_pdf_text", "") if loaded_doc else ""

                st.session_state.chat_context = {
                    "client_data": client_info,
                    "quote_ref": quote_ref,
                    "full_pdf_text": full_text
                }
                
                # Verify that the necessary data is present before switching pages
                if st.session_state.chat_context.get("full_pdf_text"):
                    st.session_state.current_page = "Chat"
                    st.session_state.profile_extraction_step = None 
                    st.rerun()
                else:
                    st.error(f"Cannot start chat. The document content for quote '{quote_ref}' is missing.")

            elif action:
                # Handle other actions using the existing workflow
                handle_selected_action(action, profile)
                st.rerun()
            return
    
    # Upload section
    with st.expander("Upload New Quote", expanded=False):
        uploaded_file = st.file_uploader("Choose a PDF quote to process", type=["pdf"], key="pdf_uploader_dashboard")
        
        if uploaded_file is not None:
            st.markdown(f"Uploaded: **{uploaded_file.name}**")
            
            if st.button("Extract Full Profile", key="extract_profile_dash_btn", type="primary", use_container_width=True):
                st.session_state.extracted_profile = extract_client_profile(uploaded_file)
                if st.session_state.extracted_profile:
                    st.session_state.profile_extraction_step = "confirmation"
                    st.rerun()
                else:
                    st.error("Failed to extract profile from the uploaded PDF.")
    
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

def generate_template_summary(template_data, template_contexts=None):
    """
    Generates a hierarchical summary of selected items in a template.
    
    Args:
        template_data: Dictionary of field keys to values from template
        template_contexts: Optional dictionary of field keys to their context/description
        
    Returns:
        Dictionary mapping section names to lists of selected items
    """
    # Initialize sections dictionary
    sections = {
        "Control & Programming Specifications": [],
        "Mechanical Specifications": [],
        "Documentation & Validation": [],
        "General Information": [],
        "Other Specifications": []
    }
    
    # Process each field in the template data
    for field_key, value in template_data.items():
        # Skip empty values
        if not value:
            continue
            
        # Skip non-selected checkboxes
        if field_key.endswith("_check") and value.upper() != "YES":
            continue
            
        # Determine the section based on the field key or context
        section = "Other Specifications"
        
        # Check field key for section hints
        if field_key.startswith(("plc_", "hmi_", "cps_", "vfd_", "etr_")):
            section = "Control & Programming Specifications"
        elif field_key.startswith(("ms_", "mech_", "ss_", "pp_")):
            section = "Mechanical Specifications"
        elif field_key.startswith(("doc_", "val_", "faq_", "dq_", "iq_", "oq_", "pq_")):
            section = "Documentation & Validation"
        elif field_key.startswith(("gn_", "gi_", "info_")):
            section = "General Information"
            
        # Extract hierarchical context components for this field
        context_section = ""
        context_subsection = ""
        context_field = ""
        full_context = ""
        
        if template_contexts and field_key in template_contexts:
            context = template_contexts[field_key]
            
            # If context is a string, parse the hierarchical components
            if isinstance(context, str):
                full_context = context
                
                # Split by delimiter to extract hierarchical components
                parts = context.split(' - ')
                if len(parts) >= 1:
                    context_section = parts[0]
                if len(parts) >= 2:
                    context_subsection = parts[1]
                if len(parts) >= 3:
                    context_field = parts[2]
                elif len(parts) == 2:
                    context_field = parts[1]  # If only 2 parts, the second is the field
                
                # Use the context to determine the section if possible
                context_lower = context.lower()
                if any(term in context_lower for term in ["control", "plc", "hmi", "programming", "software"]):
                    section = "Control & Programming Specifications"
                elif any(term in context_lower for term in ["mechanical", "material", "machine", "hardware"]):
                    section = "Mechanical Specifications"
                elif any(term in context_lower for term in ["document", "validation", "qualification", "protocol"]):
                    section = "Documentation & Validation"
                elif any(term in context_lower for term in ["general", "information", "client", "customer"]):
                    section = "General Information"
            
            # If context is a dictionary (from schema format), extract context from it
            elif isinstance(context, dict):
                # Combine title and description for context
                title = context.get("title", "")
                description = context.get("description", "")
                section_hint = context.get("section", "")
                
                # Build the full context string
                if title and description:
                    full_context = f"{title} - {description}"
                    context_field = description
                elif title:
                    full_context = title
                    context_field = title
                elif description:
                    full_context = description
                    context_field = description
                
                # Also determine section from context if available
                if section_hint:
                    context_section = section_hint
                    section_hint_lower = section_hint.lower()
                    if "control" in section_hint_lower or "programming" in section_hint_lower:
                        section = "Control & Programming Specifications"
                    elif "mechanical" in section_hint_lower:
                        section = "Mechanical Specifications"
                    elif "document" in section_hint_lower or "validation" in section_hint_lower:
                        section = "Documentation & Validation"
                    elif "general" in section_hint_lower or "information" in section_hint_lower:
                        section = "General Information"
                
        # Prepare a friendly name for the field
        friendly_name = field_key
        
        # For checkbox fields, remove the _check suffix and format nicely
        if field_key.endswith("_check"):
            friendly_name = field_key[:-6].replace("_", " ").title()
            
        # If we have context, use it to improve the friendly name
        if template_contexts and field_key in template_contexts:
            context = template_contexts[field_key]
            if isinstance(context, str) and context:
                # Extract a short name from the context
                lines = context.splitlines()
                if lines:
                    first_line = lines[0].strip()
                    if first_line:
                        friendly_name = first_line
            elif isinstance(context, dict) and "title" in context:
                friendly_name = context["title"]
                
        # Add to the appropriate section
        sections[section].append({
            "key": field_key,
            "name": friendly_name,
            "value": value,
            "context": full_context,
            "section": context_section or section,
            "subsection": context_subsection,
            "field": context_field or friendly_name
        })
        
    # Remove empty sections
    sections = {k: v for k, v in sections.items() if v}
    
    return sections

def show_template_items_table(template_data, template_contexts=None):
    """
    Displays template items in a simple tabular format showing Item, Value, and Section Path,
    grouped by section as shown in the screenshot, using explicit_placeholder_mappings from template_utils.py.
    
    Args:
        template_data: Dictionary of field keys to values from template
        template_contexts: Optional dictionary of field keys to their context/description
    """
    from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS
    
    if not template_data:
        st.info("No items selected in this template.")
        return
    
    # Group items by section based on explicit_placeholder_mappings
    sections = {}
    
    for field_key, value in template_data.items():
        # Skip empty values
        if not value:
            continue
            
        # Skip non-selected checkboxes
        if field_key.endswith("_check") and value.upper() != "YES":
            continue
        
        # Get section and subsection from explicit_placeholder_mappings if available
        section = "Other Specifications"
        subsection = ""
        full_path = ""
        
        if field_key in DEFAULT_EXPLICIT_MAPPINGS:
            mapping = DEFAULT_EXPLICIT_MAPPINGS[field_key]
            full_path = mapping
            
            # Extract section and subsection from the mapping
            if " - " in mapping:
                parts = mapping.split(" - ")
                section = parts[0].strip()
                
                # If there are multiple parts, everything between the first and last part is the subsection
                if len(parts) > 2:
                    subsection = " - ".join(parts[1:-1]).strip()
                elif len(parts) == 2:
                    subsection = ""  # No subsection in this case
        
        # Prepare a friendly name for the field
        friendly_name = field_key
        
        # For checkbox fields, remove the _check suffix and format nicely
        if field_key.endswith("_check"):
            friendly_name = field_key[:-6].replace("_", " ").title()
            
        # If we have explicit mapping, use it for the friendly name
        if field_key in DEFAULT_EXPLICIT_MAPPINGS:
            mapping_parts = DEFAULT_EXPLICIT_MAPPINGS[field_key].split(" - ")
            if len(mapping_parts) > 0:
                # Use the last part as the friendly name
                friendly_name = mapping_parts[-1]
        # Or if we have context, use it to improve the friendly name
        elif template_contexts and field_key in template_contexts:
            context = template_contexts[field_key]
            if isinstance(context, str) and context:
                # Extract a short name from the context
                lines = context.splitlines()
                if lines:
                    first_line = lines[0].strip()
                    if first_line:
                        friendly_name = first_line
            elif isinstance(context, dict) and "title" in context:
                friendly_name = context["title"]
        
        # Initialize section if not already in sections
        if section not in sections:
            sections[section] = []
            
        # Add to the appropriate section with full hierarchical information
        sections[section].append({
            "Item": friendly_name,
            "Section Path": full_path,  # Full hierarchical path from mapping
            "Value": value,
            # Field Key removed as requested
        })
    
    # Remove empty sections
    sections = {k: v for k, v in sections.items() if v}
    
    # Display each section separately
    for section_name, items in sections.items():
        if items:
            st.subheader(section_name)
            df = pd.DataFrame(items)
            # Add row numbers (starting from 0)
            df.insert(0, '', range(len(df)))
            st.dataframe(df, use_container_width=True, hide_index=True)

def show_template_summary(template_data, template_contexts=None):
    """
    Displays a summary of selected items in the template.
    
    Args:
        template_data: Dictionary of field keys to values from template
        template_contexts: Optional dictionary of field keys to their context/description
    """
    if not template_data:
        st.info("No items selected in this template.")
        return
        
    st.markdown("### Template Summary")
    
    # Use the tabular display format with sections
    show_template_items_table(template_data, template_contexts)
    
    # Make the tabular view the default and only view
    # The hierarchical view is removed since it's not working correctly
    # and the simple tabular view matches the preferred layout in the screenshot
    
    # If you want to re-enable the hierarchical view in the future,
    # you can uncomment the code below and fix the toggle functionality
    
    '''
    # Optional: Add a toggle to show the hierarchical view if needed
    # Generate a unique key using UUID
    import uuid
    # Create a unique identifier from the first few keys in template_data and a random component
    template_id = "-".join(list(template_data.keys())[:2]) if template_data else "empty"
    toggle_key = f"hierarchical_view_{template_id}_{str(uuid.uuid4())[:8]}"
    
    if st.toggle("Show Detailed Hierarchical View", value=False, key=toggle_key):
        sections = generate_template_summary(template_data, template_contexts)
        
        if not sections:
            st.info("No items selected for hierarchical view.")
            return
        
        # Display a combined view of all sections first for easy reference
        st.markdown("#### All Selected Fields (Combined View)")
        all_items = []
        for section_name, items in sections.items():
            for item in items:
                all_items.append({
                    "Section": item["section"],
                    "Subsection": item["subsection"],
                    "Field": item["field"],
                    "Value": item["value"],
                    "Field Key": item["key"]
                })
        
        if all_items:
            all_df = pd.DataFrame(all_items)
            st.dataframe(all_df, use_container_width=True)
        
        # Create a DataFrame for each section
        for section_name, items in sections.items():
            if items:
                st.markdown(f"#### {section_name}")
                
                # Convert to DataFrame for better display
                df_data = []
                for item in items:
                    df_data.append({
                        "Section": item["section"],
                        "Subsection": item["subsection"],
                        "Field": item["field"],
                        "Value": item["value"],
                        "Field Key": item["key"]
                    })
                    
                if df_data:
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
    '''

def generate_printable_report(template_data, machine_name="", template_type="", is_sortstar_machine: bool = False):
    """
    Generates a clean, printable HTML report of selected template items,
    optimized for machine building teams with visual organization.
    
    Args:
        template_data: Dictionary of field keys to values from template
        machine_name: Name of the machine (optional)
        template_type: Type of template (e.g., "GOA") (optional)
        is_sortstar_machine: Boolean indicating if the machine is a SortStar machine.
        
    Returns:
        HTML string for the report
    """
    import datetime
    import os

    # Select the appropriate mappings and outline file based on machine type
    current_mappings = SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar_machine else DEFAULT_EXPLICIT_MAPPINGS
    outline_file_to_use = "sortstar_fields_outline.md" if is_sortstar_machine else "full_fields_outline.md"
    
    # Initialize outline structure
    outline_structure = {}
    
    # Function to convert SortStar mappings to proper outline structure
    def build_sortstar_outline_from_mappings(mappings):
        """Convert SortStar explicit mappings to a proper outline structure"""
        outline = {}
        for key, value_path in mappings.items():
            parts = [p.strip() for p in value_path.split(" > ")]
            if len(parts) >= 1:
                section = parts[0]
                if section not in outline:
                    outline[section] = {"_direct_fields_": [], "_subsections_": {}}
                
                # Handle subsections
                if len(parts) >= 3:  # Section > Subsection > Field
                    subsection = parts[1]
                    if subsection not in outline[section]["_subsections_"]:
                        outline[section]["_subsections_"][subsection] = []
                    # Add the field key to track later
                    outline[section]["_subsections_"][subsection].append(key)
                elif len(parts) == 2:  # Section > Field (no subsection)
                    outline[section]["_direct_fields_"].append(key)
        return outline
    
    # Read and parse the outline file if it exists
    if os.path.exists(outline_file_to_use):
        with open(outline_file_to_use, 'r', encoding='utf-8') as f:
            outline_content = f.read()
        
        # Use appropriate parsing function based on machine type
        if is_sortstar_machine:
            # For SortStar, build proper outline structure from mappings
            outline_structure = build_sortstar_outline_from_mappings(current_mappings)
        else:
            # For regular templates, use the standard outline parser
            outline_structure = parse_full_fields_outline(outline_content)
    else:
        # If outline file doesn't exist but we have SortStar machine
        if is_sortstar_machine:
            outline_structure = build_sortstar_outline_from_mappings(current_mappings)
        else:
            st.warning(f"Outline file not found: {outline_file_to_use}. Report structure may be less organized.")

    # Building categories remain the same
    building_categories = {
        "components": ["parts", "component", "assembly", "material", "hardware", "seal", "tubing", "slats"],
        "dimensions": ["dimension", "size", "width", "height", "length", "diameter", "qty", "quantities"],
        "electrical": ["voltage", "power", "electrical", "circuit", "wiring", "hz", "amps"],
        "programming": ["program", "software", "plc", "hmi", "interface", "control", "batch", "report"],
        "safety": ["safety", "guard", "protection", "emergency", "secure", "e-stop"],
        "utility": ["utility", "psi", "cfm", "conformity", "certification"],
        "handling": ["bottle handling", "conveyor", "puck", "index", "motion", "reject", "turntable", "elevator"],
        "processing": ["filling", "capping", "labeling", "coding", "induction", "torque", "purge", "desiccant", "cottoner", "plugging"],
        "documentation": ["documentation", "validation", "manual", "fat", "sat", "dq", "iq", "oq"],
        "general": ["general", "info", "order", "customer", "machine", "direction", "speed", "warranty", "install", "spares", "packaging", "transport"]
    }

    # --- Data Preparation --- 
    # report_data will store { section_name: { "_direct_fields_": [], "_subsections_": { subsection_name: [] } } }
    report_data_by_outline = {section_name: {"_direct_fields_": [], "_subsections_": {sub_name: [] for sub_name in details.get("_subsections_", [])}} 
                              for section_name, details in outline_structure.items()}
    
    # If outline_structure is empty, initialize with a default section for all fields
    if not report_data_by_outline:
        report_data_by_outline["All Specifications"] = {"_direct_fields_": [], "_subsections_": {}}

    unmapped_or_additional_fields = [] # Fields not fitting the outline or not in explicit_mappings

    # Sort template_data for consistent processing
    sorted_template_data_items = sorted(template_data.items(), key=lambda x: x[0])

    for field_key, value in sorted_template_data_items:
        if not value or (field_key.endswith("_check") and str(value).upper() != "YES"):
            continue

        field_info = {
            "key": field_key,
            "value": value,
            "label": field_key, # Default label
            "path": field_key,  # Default path
            "category": "general" # Default category
        }

        # Determine building category
        for cat, keywords in building_categories.items():
            # Check against key, explicit mapping path, and eventual label
            path_from_mapping = current_mappings.get(field_key, field_key).lower()
            if any(kw in field_key.lower() or kw in path_from_mapping for kw in keywords):
                field_info["category"] = cat
                break
        
        mapped_section_name = None
        mapped_subsection_name = None

        if field_key in current_mappings:
            full_path_string = current_mappings[field_key]
            field_info["path"] = full_path_string
            
            # Handle different delimiters based on machine type
            if is_sortstar_machine:
                parts = [p.strip() for p in full_path_string.split(" > ")]
            else:
                parts = [p.strip() for p in full_path_string.split(" - ")]

            if parts:
                field_info["label"] = parts[-1] # Last part is usually the most specific label
                potential_section = parts[0]
                potential_subsection = None
                
                if len(parts) > 2:
                    if is_sortstar_machine:
                        # For SortStar, use just the second part as subsection
                        potential_subsection = parts[1]
                    else:
                        # For regular templates, join everything between section and label
                        potential_subsection = " - ".join(parts[1:-1])
                elif len(parts) == 2: # Section - Field, no explicit subsection in mapping
                    potential_subsection = None
                
                # Try to match this field to the outline structure
                # First, check if potential_section matches a top-level outline section
                # Case-insensitive matching for robustness
                matched_outline_section_key = next((os_key for os_key in outline_structure 
                                                    if os_key.lower() == potential_section.lower()), None)

                if matched_outline_section_key:
                    mapped_section_name = matched_outline_section_key # Use the casing from outline_structure
                    # Now check for subsection match within this outline section
                    if potential_subsection:
                        available_subsections = outline_structure[mapped_section_name].get("_subsections_", [])
                        matched_outline_subsection_key = next((sub_key for sub_key in available_subsections 
                                                               if sub_key.lower() == potential_subsection.lower()), None)
                        if matched_outline_subsection_key:
                            mapped_subsection_name = matched_outline_subsection_key # Use casing from outline
                else: # Section from mapping not found in outline, treat as unmapped/additional
                    pass 
        
        # Place the field
        if mapped_section_name and mapped_section_name in report_data_by_outline:
            if mapped_subsection_name and mapped_subsection_name in report_data_by_outline[mapped_section_name]["_subsections_"]:
                report_data_by_outline[mapped_section_name]["_subsections_"][mapped_subsection_name].append(field_info)
            else:
                # Add to direct fields of the section if no subsection match or no subsection in mapping
                report_data_by_outline[mapped_section_name]["_direct_fields_"].append(field_info)
        else:
            # If no explicit mapping or section doesn't match outline, add to unmapped
            # Or, if the outline is empty, all fields go to the default section's direct_fields
            if not outline_structure and "All Specifications" in report_data_by_outline:
                 report_data_by_outline["All Specifications"]["_direct_fields_"].append(field_info)
            else:
                unmapped_or_additional_fields.append(field_info)

    # Sort fields within each section/subsection
    for section_name, section_content in report_data_by_outline.items():
        if "_direct_fields_" in section_content:
            section_content["_direct_fields_"] = sorted(section_content["_direct_fields_"], key=lambda x: (x["category"], x["label"]))
        if "_subsections_" in section_content:
            for sub_name, fields_list in section_content["_subsections_"].items():
                section_content["_subsections_"][sub_name] = sorted(fields_list, key=lambda x: (x["category"], x["label"]))
    
    sorted_unmapped_fields = sorted(unmapped_or_additional_fields, key=lambda x: (x["category"], x["path"]))

    # --- HTML Generation --- 
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Machine Build Specification: {machine_name or 'N/A'}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; line-height: 1.4; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #2980b9; margin-top: 35px; border-bottom: 1px solid #bdc3c7; padding-bottom: 8px; page-break-before: auto; page-break-after: avoid;}}
            h3 {{ color: #16a085; margin-top: 25px; font-size: 1.1em; background-color: #f0f9ff; padding: 8px; border-left: 4px solid #5dade2; page-break-after: avoid; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; box-shadow: 0 2px 3px rgba(0,0,0,0.1); page-break-inside: avoid; }}
            th {{ background-color: #eaf2f8; text-align: left; padding: 10px 12px; border-bottom: 2px solid #aed6f1; font-weight: bold; }}
            td {{ padding: 9px 12px; border-bottom: 1px solid #d6eaf8; }}
            tr:nth-child(even) td {{ background-color: #f8f9f9; }}
            /* tr:hover td {{ background-color: #e8f6fd; }} */
            .report-header {{ margin-bottom: 30px; display: flex; align-items: center; justify-content: space-between; }}
            .report-meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 5px; }}
            .section-count, .subsection-count {{ color: #7f8c8d; font-size: 0.85em; margin-left: 10px; font-weight: normal; }}
            
            .specs-container {{ display: flex; flex-wrap: wrap; gap: 15px; margin: 15px 0; }}
            .spec-box {{ border: 1px solid #d4e6f1; border-radius: 5px; padding: 12px; flex: 1 1 280px; background-color: #fdfefe; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .spec-box-title {{ font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid #d4e6f1; padding-bottom: 6px; color: #2e86c1; font-size: 1em;}}
            .spec-item {{ margin-bottom: 7px; font-size: 0.95em; }}
            .spec-label {{ font-weight: bold; color: #566573; }}
            .spec-value {{ color: #283747; margin-left: 5px; }}
            
            .toc {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 30px; border: 1px solid #e9ecef; }}
            .toc ul {{ list-style-type: none; padding-left: 0; }}
            .toc li a {{ text-decoration: none; color: #3498db; display: block; padding: 3px 0; }}
            .toc li a:hover {{ text-decoration: underline; }}
            .toc-section {{ font-weight: bold; margin-top: 8px; }}
            .toc-subsection {{ padding-left: 20px; font-size: 0.95em; }}

            .print-button {{ position: fixed; top: 20px; right: 20px; z-index: 1000; }}
            @media print {{
                body {{ font-size: 10pt; margin: 15mm; }}
                h1, h2, h3 {{ page-break-after: avoid; }}
                table, .specs-container, .spec-box {{ page-break-inside: avoid !important; }}
                .no-print {{ display: none !important; }}
                .print-header {{ display: block; text-align: center; margin-bottom: 20px; }}
                .toc {{ display: none; }}
                .report-header {{ justify-content: center; text-align: center; }}
            }}
            .build-summary {{ background-color: #fdfefe; padding: 15px; border-radius: 5px; margin-top: 20px; border: 1px solid #d4e6f1; }}
            .key-specs {{ display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }}
            .key-spec {{ flex: 1 1 200px; padding: 10px; background-color: #f8f9f9; border-radius: 5px; border: 1px solid #e0e0e0; }}
            .key-spec-title {{ font-weight: bold; margin-bottom: 5px; color: #2980b9; }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <div>
                <h1>Machine Build Specification</h1>
                <div class="report-meta">Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    """
    
    if machine_name: html += f'<div class="report-meta">Machine: {machine_name}</div>\n'
    if template_type: html += f'<div class="report-meta">Template Type: {template_type}</div>\n'
    
    html += """
            </div>
            <div class="print-button no-print">
                <button onclick="window.print()">Print Report</button>
            </div>
        </div>
        
        <div class="build-summary">
            <h2>Build Summary</h2>
    """
    
    # Key specifications summary (simplified - uses all fields for now, can be refined)
    key_specs_summary = {
        "Mechanical": [], "Electrical": [], "Control": [], "Safety": [], "Processing": [], "General": []
    }
    temp_all_fields_for_summary = []
    for sec_data in report_data_by_outline.values():
        temp_all_fields_for_summary.extend(sec_data.get("_direct_fields_", []))
        for sub_fields in sec_data.get("_subsections_", {}).values():
            temp_all_fields_for_summary.extend(sub_fields)
    temp_all_fields_for_summary.extend(sorted_unmapped_fields)

    for item in temp_all_fields_for_summary:
        cat = item["category"]
        if cat in ["components", "dimensions", "handling"]: target_cat = "Mechanical"
        elif cat == "electrical": target_cat = "Electrical"
        elif cat == "programming": target_cat = "Control"
        elif cat == "safety": target_cat = "Safety"
        elif cat == "processing": target_cat = "Processing"
        else: target_cat = "General"
        if len(key_specs_summary[target_cat]) < 5:  # Limit to 5 key specs per category
            key_specs_summary[target_cat].append((item["label"], item["value"]))
    
    html += '<div class="key-specs">'
    for spec_type, specs in key_specs_summary.items():
        if specs:
            html += f'''
            <div class="key-spec">
                <div class="key-spec-title">{spec_type}</div>
                <ul>
            '''
            for spec_item, spec_value in specs:
                html += f"<li><b>{spec_item}:</b> {spec_value}</li>\n"
            html += '</ul></div>'
    html += '</div></div>' # Close key-specs and build-summary
    
    # --- Table of Contents --- 
    html += '<div class="toc no-print"><h2>Table of Contents</h2><ul>'
    
    # Determine section order based on machine type
    if is_sortstar_machine:
        # Define SortStar section ordering
        sortstar_section_order = [
            "GENERAL ORDER ACKNOWLEDGEMENT", 
            "BASIC SYSTEMS", 
            "OPTIONAL SYSTEMS", 
            "Order Identification", 
            "Utility Specifications"
        ]
        
        # Create ordered list of sections based on SortStar priority
        toc_section_keys = []
        
        # First add sections in the predefined order if they exist
        for ordered_section in sortstar_section_order:
            if ordered_section in report_data_by_outline:
                toc_section_keys.append(ordered_section)
        
        # Then add any remaining sections from report_data_by_outline that weren't in the predefined order
        for section in report_data_by_outline.keys():
            if section not in toc_section_keys:
                toc_section_keys.append(section)
    else:
        # Use the order from outline_structure if available, otherwise sorted keys of report_data_by_outline
        toc_section_keys = list(outline_structure.keys()) if outline_structure else sorted(list(report_data_by_outline.keys()))

    for section_name in toc_section_keys:
        if section_name not in report_data_by_outline: continue # Skip if section from outline has no data
        section_content = report_data_by_outline[section_name]
        section_id = section_name.replace(" ", "_").replace("/", "_").replace("&", "and")
        has_content = section_content.get("_direct_fields_") or any(section_content.get("_subsections_", {}).values())
        if not has_content: continue

        html += f'<li class="toc-section"><a href="#{section_id}">{section_name}</a></li>'
        if "_subsections_" in section_content and section_content["_subsections_"]:
            # Sort subsections from outline for TOC consistency
            sorted_toc_subs = sorted(list(section_content["_subsections_"].keys()))
            for sub_name in sorted_toc_subs:
                if section_content["_subsections_"][sub_name]: # Only list if subsection has items
                    sub_id = f"{section_id}_{sub_name.replace(' ', '_').replace('/', '_').replace('&', 'and')}"
                    html += f'<li class="toc-subsection"><a href="#{sub_id}">{sub_name}</a></li>'
    if sorted_unmapped_fields:
        html += f'<li class="toc-section"><a href="#unmapped_additional_fields">Additional Specifications</a></li>'
    html += '</ul></div>'
    
    # --- Main Report Content --- 
    # Use the same section order as TOC
    report_section_keys = toc_section_keys

    for section_name in report_section_keys:
        if section_name not in report_data_by_outline: continue
        section_content = report_data_by_outline[section_name]
        section_id = section_name.replace(" ", "_").replace("/", "_").replace("&", "and")
        
        # Check if section has any content before rendering header
        direct_fields_exist = bool(section_content.get("_direct_fields_"))
        subsections_with_content = any(bool(fields) for fields in section_content.get("_subsections_", {}).values())
        if not direct_fields_exist and not subsections_with_content: continue

        total_items_in_section = len(section_content.get("_direct_fields_", [])) + sum(len(sub_list) for sub_list in section_content.get("_subsections_", {}).values())
        html += f'<h2 id="{section_id}">{section_name} <span class="section-count">({total_items_in_section} items)</span></h2>'

        # Render direct fields for the section
        if direct_fields_exist:
            html += '<div class="specs-container">'
            # Group direct fields by category
            direct_fields_by_cat = {}
            for item in section_content["_direct_fields_"]:
                cat = item["category"]
                if cat not in direct_fields_by_cat: direct_fields_by_cat[cat] = []
                direct_fields_by_cat[cat].append(item)
            
            for cat_name, cat_items in sorted(direct_fields_by_cat.items()):
                html += f'<div class="spec-box category-{cat_name}"><div class="spec-box-title">{cat_name.replace("_", " ").title()}</div>'
                for item in cat_items:
                    display_value = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
                    html += f'<div class="spec-item"><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></div>'
                html += '</div>' # Close spec-box
            html += '</div>' # Close specs-container

            html += "<table><thead><tr><th>Item</th><th>Specification Path</th><th>Value</th></tr></thead><tbody>"
            for item in section_content["_direct_fields_"]:
                display_value_table = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
                html += f'<tr><td>{item["label"]}</td><td>{item["path"]}</td><td>{display_value_table}</td></tr>'
            html += "</tbody></table>"

        # Render subsections
        if "_subsections_" in section_content and section_content["_subsections_"]:
            # Sort subsections for display (already sorted for TOC)
            sorted_display_subs = sorted(list(section_content["_subsections_"].keys()))
            for sub_name in sorted_display_subs:
                fields_list = section_content["_subsections_"][sub_name]
                if not fields_list: continue # Skip empty subsections

                sub_id = f"{section_id}_{sub_name.replace(' ', '_').replace('/', '_').replace('&', 'and')}"
                html += f'<h3 id="{sub_id}">{sub_name} <span class="subsection-count">({len(fields_list)} items)</span></h3>'
                html += '<div class="specs-container">'
                # Group subsection fields by category
                sub_fields_by_cat = {}
                for item in fields_list:
                    cat = item["category"]
                    if cat not in sub_fields_by_cat: sub_fields_by_cat[cat] = []
                    sub_fields_by_cat[cat].append(item)

                for cat_name, cat_items in sorted(sub_fields_by_cat.items()):
                    html += f'<div class="spec-box category-{cat_name}"><div class="spec-box-title">{cat_name.replace("_", " ").title()}</div>'
                    for item in cat_items:
                        display_value = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
                        html += f'<div class="spec-item"><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></div>'
                    html += '</div>' # Close spec-box
                html += '</div>' # Close specs-container

                html += "<table><thead><tr><th>Item</th><th>Specification Path</th><th>Value</th></tr></thead><tbody>"
                for item in fields_list:
                    display_value_table = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
                    html += f'<tr><td>{item["label"]}</td><td>{item["path"]}</td><td>{display_value_table}</td></tr>'
                html += "</tbody></table>"

    # Render unmapped/additional fields
    if sorted_unmapped_fields:
        html += f'<h2 id="unmapped_additional_fields">Additional Specifications <span class="section-count">({len(sorted_unmapped_fields)} items)</span></h2>'
        html += '<div class="specs-container">'
        unmapped_by_cat = {}
        for item in sorted_unmapped_fields:
            cat = item["category"]
            if cat not in unmapped_by_cat: unmapped_by_cat[cat] = []
            unmapped_by_cat[cat].append(item)
        
        for cat_name, cat_items in sorted(unmapped_by_cat.items()):
            html += f'<div class="spec-box category-{cat_name}"><div class="spec-box-title">{cat_name.replace("_", " ").title()}</div>'
            for item in cat_items:
                display_value = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
                html += f'<div class="spec-item"><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></div>'
            html += '</div>' # Close spec-box
        html += '</div>' # Close specs-container
        
        html += "<table><thead><tr><th>Item</th><th>Specification Path</th><th>Value</th></tr></thead><tbody>"
        for item in sorted_unmapped_fields:
            display_value_table = item["value"].replace("\n", "<br>") if item["key"] == "options_listing" else item["value"]
            html += f'<tr><td>{item["label"]}</td><td>{item["path"]}</td><td>{display_value_table}</td></tr>'
        html += "</tbody></table>"

    html += """
    <div class="print-header">
        <h2>Machine Build Specification</h2>
        <!-- Add machine name and other details if needed for print header -->
    </div>
    </body>
    </html>
    """
    return html

def show_printable_report(template_data, machine_name="", template_type=""):
    """
    Shows a printable report in a new tab using Streamlit components.
    
    Args:
        template_data: Dictionary of field keys to values from template
        machine_name: Name of the machine (optional)
        template_type: Type of template (e.g., "GOA") (optional)
    """
    # Generate HTML report
    html_report = generate_printable_report(template_data, machine_name, template_type)
    
    # Display with html component
    st.components.v1.html(html_report, height=600, scrolling=True)
    
    # Provide a download button for the HTML report
    st.download_button(
        "Download Report (HTML)",
        html_report,
        file_name=f"template_items_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
        mime="text/html",
        key="download_report_html"
    )

def show_goa_modifications_ui(machine_id: int = None, machine_name: Optional[str] = None):
    """
    Displays and manages GOA template modifications for a specific machine.
    Uses a simpler UI similar to client records.
    
    Args:
        machine_id: Optional ID of the machine to show modifications for
        machine_name: Optional name of the machine.
    """
    try:
        from src.utils.crm_utils import load_machine_templates_with_modifications, save_goa_modification
        
        st.subheader("🔄 Template Modifications")
        
        if machine_id is None:
            st.info("Please select a machine from the Client Dashboard to modify its templates.")
            return
            
        # Basic info about the selected machine
        st.info(f"Modifying templates for Machine ID: {machine_id}")
        
        # Load templates for this machine
        templates_data = load_machine_templates_with_modifications(machine_id)
        
        if not templates_data or not templates_data.get("templates"):
            st.warning(f"No templates found for machine ID {machine_id}.")
            st.info("You need to process this machine for templates first.")
            return
        
        # Display templates in tabs if there are multiple
        templates = templates_data["templates"]
        
        if len(templates) > 1:
            template_tabs = st.tabs([t["template_type"] for t in templates])
            for i, template in enumerate(templates):
                with template_tabs[i]:
                    display_template_editor(template, machine_id, machine_name)
        else:
            # Only one template, no need for tabs
            display_template_editor(templates[0], machine_id, machine_name)
    except Exception as e:
        st.error(f"Error displaying template modifications: {str(e)}")
        import traceback
        st.exception(e)
        
def display_template_editor(template, machine_id: Optional[int] = None, machine_name: Optional[str] = None):
    """Helper function to display and edit a single template"""
    try:
        from src.utils.crm_utils import save_goa_modification
        # Imports for explicit_placeholder_mappings are already at the top of the file
        import re
        
        is_sortstar_machine = False
        if machine_name:
            sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
            if re.search(sortstar_pattern, machine_name.lower()):
                is_sortstar_machine = True
                st.info(f"SortStar machine template editor active for: {machine_name}")
        
        current_explicit_mappings = SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar_machine else DEFAULT_EXPLICIT_MAPPINGS
        
        template_id = template["id"]
        template_type = template["template_type"]
        
        # Check if template data exists and is valid
        if "template_data" not in template or not template["template_data"]:
            st.error(f"Template data missing or invalid for template ID {template_id}")
            return
            
        template_data = template["template_data"]
        
        # Check if options_listing field exists and show its value
        if "options_listing" in template_data:
            options_value = template_data["options_listing"]
            with st.expander("Debug: Options Listing Field", expanded=False):
                st.markdown("**Current Options Listing Value:**")
                st.text(options_value)
                st.markdown("**Machine Type:** " + ("SortStar" if is_sortstar_machine else "Regular"))
                st.markdown(f"**Mapping for options_listing:** {current_explicit_mappings.get('options_listing', 'Not found in mappings')}")

        # Make sure options_listing is properly handled for SortStar machines
        if is_sortstar_machine and "options_listing" in template_data:
            # For SortStar machines, we always regenerate the options_listing
            # to ensure it shows the actual selections instead of placeholder structure
            selected_details = []
            
            # First try to find the machine record to get its add-ons
            machine_record = None
            machine_add_ons = []
            
            if machine_id:
                # Load machine data from the database to get add-ons
                from src.utils.crm_utils import load_machines_for_quote
                
                # First find the quote_ref for this machine
                for client in st.session_state.all_crm_clients:
                    machines = load_machines_for_quote(client.get('quote_ref', ''))
                    for m in machines:
                        if m.get('id') == machine_id:
                            machine_record = m
                            # Try to get add-ons from machine_data
                            machine_data_content = machine_record.get("machine_data")
                            if isinstance(machine_data_content, str):
                                try:
                                    import json
                                    machine_data_content = json.loads(machine_data_content)
                                    if "add_ons" in machine_data_content:
                                        machine_add_ons = machine_data_content["add_ons"]
                                except json.JSONDecodeError:
                                    st.warning(f"Could not parse machine_data JSON for add-ons")
                            elif isinstance(machine_data_content, dict) and "add_ons" in machine_data_content:
                                machine_add_ons = machine_data_content["add_ons"]
                            break
                    if machine_record:
                        break
            
            # Add actual add-ons from the machine data (like regular template)
            if machine_add_ons:
                for i, addon in enumerate(machine_add_ons, 1):
                    if "description" in addon and addon["description"]:
                        # Format description nicely
                        desc_lines = addon["description"].split('\n')
                        main_desc = desc_lines[0] if desc_lines else addon["description"]
                        selected_details.append(f"- Add-on {i}: {main_desc}")
            
            # If no add-ons were found, fall back to template fields
            if not selected_details:
                # Process each field in the template to generate selections list
                for field_key, value in template_data.items():
                    if field_key != "options_listing" and value:
                        is_checkbox = field_key.endswith("_check")
                        
                        # Skip fields with 'none', 'not selected', or similar values
                        if isinstance(value, str) and any(term in value.lower() for term in ["none", "not selected", "not specified"]):
                            continue
                            
                        # Get a user-friendly description for the field
                        if field_key in current_explicit_mappings:
                            field_path = current_explicit_mappings[field_key]
                            
                            # For SortStar, extract just the field name without the full hierarchy
                            if ">" in field_path:
                                parts = field_path.split(" > ")
                                if len(parts) > 1:
                                    # Use only the most specific part (last part) as the field description
                                    # This matches how regular templates display options
                                    field_description = parts[-1].strip()
                                else:
                                    field_description = field_path.strip()
                            else:
                                field_description = field_path.strip()
                        else:
                            field_description = field_key.replace("_", " ").capitalize()
                        
                        # Skip if the field description contains "none" or similar
                        if any(term in field_description.lower() for term in ["none", "not selected", "not specified"]):
                            continue
                        
                        # Add selected checkboxes and meaningful text fields
                        if is_checkbox and str(value).upper() == "YES":
                            selected_details.append(f"• {field_description}")
                        elif not is_checkbox and field_key not in ["customer", "machine", "quote"]:
                            # Only add non-checkbox fields if they have meaningful content
                            if isinstance(value, str) and value.strip() and value.lower() not in ["no", "false", "0"]:
                                selected_details.append(f"• {field_description}: {value}")
            
            # Create the new options_listing content
            if selected_details:
                new_options_listing = "Selected Options and Specifications:\n" + "\n".join(selected_details)
            else:
                new_options_listing = "No options or specifications selected for this machine."
            
            # Compare with current value to see if update needed
            current_options_listing = template_data["options_listing"]
            if current_options_listing != new_options_listing:
                # Content needs updating - save the change
                template_data["options_listing"] = new_options_listing
                try:
                    save_goa_modification(
                        template_id, "options_listing", 
                        current_options_listing, 
                        new_options_listing,
                        "Auto-regenerated for SortStar machine", "System"
                    )
                    st.success("Updated options_listing field with actual selections")
                    # Force reload to display the updated content
                    st.rerun()
                except Exception as e:
                    st.warning(f"Could not save regenerated options_listing: {e}")
        
        # Display template info
        st.markdown(f"**Template ID:** {template_id}")
        st.markdown(f"**Type:** {template_type}")
        st.markdown(f"**Last Updated:** {template['processing_date']}")
        
        # Download document button if available
        if template.get("generated_file_path") and os.path.exists(template["generated_file_path"]):
            with open(template["generated_file_path"], "rb") as fp:
                st.download_button(
                    "Download Document", 
                    fp, 
                    os.path.basename(template["generated_file_path"]), 
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                    key=f"dl_template_{template_id}"
                )
        
        # Create sections for editing vs adding fields
        edit_tab, add_tab = st.tabs(["Edit Existing Fields", "Add New Fields"])
        
        # Tab for editing existing fields
        with edit_tab:
            st.markdown("#### Edit Existing Template Fields")

            # Group fields by hierarchy from current_explicit_mappings
            structured_fields = {}
            other_fields = [] # For fields in template_data but not in current_explicit_mappings

            # Sort template_data items by key for consistent processing order
            sorted_template_data_items = sorted(template_data.items(), key=lambda item: item[0])

            for field_key, current_value in sorted_template_data_items:
                is_boolean = (field_key.endswith("_check") or 
                             (isinstance(current_value, str) and current_value.upper() in ["YES", "NO", "TRUE", "FALSE"]))
                
                if field_key in current_explicit_mappings: # Use current_explicit_mappings
                    path = current_explicit_mappings[field_key]
                    
                    # Handle the difference in delimiters: SortStar uses ">" while regular templates use "-"
                    if is_sortstar_machine:
                        parts = [p.strip() for p in path.split(" > ")]
                    else:
                        parts = [p.strip() for p in path.split(" - ")]
                    
                    section = parts[0]
                    subsection = None
                    field_label = parts[-1]

                    if len(parts) > 2: # Section > Subsection > Field
                        subsection = parts[1]  # For SortStar, use first subsection only
                    elif len(parts) == 2: # Section > Field
                        pass # subsection remains None, field_label is parts[1]

                    if not section: # Should not happen if mappings are correct
                        section = "Uncategorized"
                    if not field_label: # Should not happen
                        field_label = field_key

                    # Special handling for options_listing field to ensure it's in the correct section
                    if field_key == "options_listing":
                        if is_sortstar_machine:
                            section = "Option Listing"
                            subsection = None
                        else:
                            section = "Option Listing"
                            subsection = None

                    if section not in structured_fields:
                        structured_fields[section] = {}
                    
                    current_section_dict = structured_fields[section]
                    target_subsection_key = subsection if subsection else "_fields_" # Use a consistent key for direct fields

                    if target_subsection_key not in current_section_dict:
                        current_section_dict[target_subsection_key] = []
                    
                    current_section_dict[target_subsection_key].append({
                        "key": field_key, 
                        "label": field_label, 
                        "value": current_value, 
                        "is_boolean": is_boolean,
                        "path": path  # Store full path for reference
                    })
                else:
                    # Special handling for options_listing even if not in mappings
                    if field_key == "options_listing":
                        if "Option Listing" not in structured_fields:
                            structured_fields["Option Listing"] = {"_fields_": []}
                        
                        structured_fields["Option Listing"]["_fields_"].append({
                            "key": field_key,
                            "label": "Additional Quoted Options",
                            "value": current_value,
                            "is_boolean": False,
                            "path": "Option Listing > Additional Quoted Options" if is_sortstar_machine else "Option Listing - Additional Quoted Options"
                        })
                    else:
                        other_fields.append({
                            "key": field_key, 
                            "label": field_key, # Use key as label if not in mappings
                            "value": current_value, 
                            "is_boolean": is_boolean
                        })

            # For SortStar machines, use a specific order for main sections
            if is_sortstar_machine:
                # Define SortStar section ordering
                sortstar_section_order = [
                    "GENERAL ORDER ACKNOWLEDGEMENT", 
                    "BASIC SYSTEMS", 
                    "OPTIONAL SYSTEMS", 
                    "Order Identification", 
                    "Utility Specifications"
                ]
                
                # Create a sorting key function that respects this order
                def sortstar_section_sort_key(section_item):
                    section_name = section_item[0]
                    if section_name in sortstar_section_order:
                        return (sortstar_section_order.index(section_name), section_name)
                    return (len(sortstar_section_order), section_name)
                
                sorted_sections_list = sorted(structured_fields.items(), key=sortstar_section_sort_key)
            else:
                # For regular templates, just sort alphabetically
                sorted_sections_list = sorted(structured_fields.items(), key=lambda item: item[0])

            for section_name, subsections_dict in sorted_sections_list:
                # Determine if the expander should be open by default
                expanded_default = False
                if is_sortstar_machine and section_name in ["BASIC SYSTEMS", "GENERAL ORDER ACKNOWLEDGEMENT"]:
                    expanded_default = True
                # Also expand Option Listing section by default for both machine types
                if section_name == "Option Listing" or (is_sortstar_machine and section_name == "Option Listing"):
                    expanded_default = True
                
                with st.expander(f"**{section_name}**", expanded=expanded_default):
                    # Special sorting for SortStar subsections
                    if is_sortstar_machine:
                        # For SortStar, keep direct fields first, then sort subsections
                        sorted_subsections_list = []
                        if "_fields_" in subsections_dict:
                            sorted_subsections_list.append(("_fields_", subsections_dict["_fields_"]))
                        
                        # Add other subsections sorted alphabetically
                        other_subsections = [(k, v) for k, v in subsections_dict.items() if k != "_fields_"]
                        sorted_subsections_list.extend(sorted(other_subsections, key=lambda item: item[0]))
                    else:
                        # For regular templates, sort subsections normally
                        sorted_subsections_list = sorted(subsections_dict.items(), key=lambda item: item[0] if item[0] != "_fields_" else "")
                    
                    for subsection_name, fields_list in sorted_subsections_list:
                        if subsection_name != "_fields_":
                            st.markdown(f"##### {subsection_name}")
                        
                        # Sort fields within the subsection/section by position in mappings
                        if is_sortstar_machine:
                            # Sort fields based on priority for SortStar
                            def get_sortstar_field_priority(field_info):
                                # Give options_listing highest priority for SortStar
                                if field_info["key"] == "options_listing":
                                    return -1
                                # Otherwise use the mapping index as before
                                keys_list = list(current_explicit_mappings.keys())
                                try:
                                    return keys_list.index(field_info["key"])
                                except ValueError:
                                    return len(keys_list)
                            
                            sorted_fields_list = sorted(fields_list, key=get_sortstar_field_priority)
                        else:
                            # For regular templates, prioritize options_listing and then sort by label
                            def get_regular_field_priority(field_info):
                                if field_info["key"] == "options_listing":
                                    return -1
                                return 0
                                
                            sorted_fields_list = sorted(fields_list, key=lambda x: (get_regular_field_priority(x), x["label"]))

                        for field_info in sorted_fields_list:
                            field_key = field_info["key"]
                            field_display = field_info["label"]
                            current_value = field_info["value"]
                            is_boolean = field_info["is_boolean"]

                            col1, col2, col3 = st.columns([3, 4, 1.5]) 
                            with col1:
                                st.markdown(f"{field_display}")
                            with col2:
                                if is_boolean:
                                    cv_str = str(current_value) if current_value is not None else "NO"
                                    is_checked = cv_str.upper() in ["YES", "TRUE"]
                                    new_checked = st.checkbox(
                                        f"Enable {field_key}", 
                                        value=is_checked,
                                        key=f"edit_bool_{field_key}_{template_id}",
                                        label_visibility="collapsed"
                                    )
                                    new_value = "YES" if new_checked else "NO"
                                else:
                                    current_value_str = "" if current_value is None else str(current_value)
                                    if field_key == "options_listing":
                                        new_value = st.text_area(
                                            f"Value for {field_key}", 
                                            value=current_value_str,
                                            key=f"edit_text_{field_key}_{template_id}",
                                            label_visibility="collapsed",
                                            height=150 # Provide more space for options_listing
                                        )
                                    else:
                                        new_value = st.text_input(
                                            f"Value for {field_key}", 
                                            value=current_value_str,
                                            key=f"edit_text_{field_key}_{template_id}",
                                            label_visibility="collapsed"
                                        )
                            with col3:
                                current_compare_val = str(current_value).upper() if is_boolean and current_value is not None else str(current_value if current_value is not None else "")
                                new_compare_val = str(new_value).upper() if is_boolean else str(new_value)

                                if new_compare_val != current_compare_val:
                                    if st.button("Save", key=f"save_edit_{field_key}_{template_id}", use_container_width=True):
                                        try:
                                            save_goa_modification(
                                                template_id, field_key, 
                                                str(current_value if current_value is not None else ("NO" if is_boolean else "")), 
                                                new_value,
                                                "Manual edit", "User"
                                            )
                                            st.success(f"Updated: {field_display}")
                                            template_data[field_key] = new_value 
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error saving: {str(e)}")
            
            if other_fields:
                # Sort other_fields by label as well
                sorted_other_fields = sorted(other_fields, key=lambda x: x["label"])
                with st.expander("**Other Fields (Not in Standard Outline)**", expanded=False):
                    for field_info in sorted_other_fields:
                        field_key = field_info["key"]
                        field_display = field_info["label"]
                        current_value = field_info["value"]
                        is_boolean = field_info["is_boolean"]

                        col1, col2, col3 = st.columns([3, 4, 1.5])
                        with col1:
                            st.markdown(f"{field_display}")
                        with col2:
                            if is_boolean:
                                cv_str = str(current_value) if current_value is not None else "NO"
                                is_checked = cv_str.upper() in ["YES", "TRUE"]
                                new_checked = st.checkbox(
                                    f"Enable {field_key}", 
                                    value=is_checked,
                                    key=f"edit_bool_other_{field_key}_{template_id}",
                                    label_visibility="collapsed"
                                )
                                new_value = "YES" if new_checked else "NO"
                            else:
                                current_value_str = "" if current_value is None else str(current_value)
                                if field_key == "options_listing":
                                    new_value = st.text_area(
                                        f"Value for {field_key}", 
                                        value=current_value_str,
                                        key=f"edit_text_other_{field_key}_{template_id}",
                                        label_visibility="collapsed",
                                        height=150
                                    )
                                else:
                                    new_value = st.text_input(
                                        f"Value for {field_key}", 
                                        value=current_value_str,
                                        key=f"edit_text_other_{field_key}_{template_id}",
                                        label_visibility="collapsed"
                                    )
                            with col3:
                                current_compare_val = str(current_value).upper() if is_boolean and current_value is not None else str(current_value if current_value is not None else "")
                                new_compare_val = str(new_value).upper() if is_boolean else str(new_value)
                                if new_compare_val != current_compare_val:
                                    if st.button("Save", key=f"save_edit_other_{field_key}_{template_id}", use_container_width=True):
                                        try:
                                            save_goa_modification(
                                                template_id, field_key, 
                                                str(current_value if current_value is not None else ("NO" if is_boolean else "")), 
                                                new_value,
                                                "Manual edit", "User"
                                            )
                                            st.success(f"Updated: {field_display}")
                                            template_data[field_key] = new_value
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error saving: {str(e)}")
        
        # Tab for adding new fields
        with add_tab:
            st.subheader("Add New Fields")
            st.info("Use this section to add fields that weren't found by the LLM but should be included in the template.")
            
            try:
                # Filter out fields that are already in the template
                available_fields = {k: v for k, v in current_explicit_mappings.items() # Use current_explicit_mappings
                                   if k not in template_data}
                
                if not available_fields:
                    st.warning("All known fields are already in the template.")
                else:
                    # Create categories for easier selection
                    categories = {}
                    for key, value in available_fields.items():
                        if " - " in value:
                            category = value.split(" - ")[0]
                        else:
                            category = "Other"
                        
                        if category not in categories:
                            categories[category] = []
                        
                        categories[category].append((key, value))
                    
                    # Create a dropdown to select category
                    selected_category = st.selectbox(
                        "Select Category", 
                        options=sorted(categories.keys()),
                        key=f"category_select_{template_id}"
                    )
                    
                    if selected_category and selected_category in categories:
                        # Create a dropdown to select the field
                        field_options = [(key, value) for key, value in categories[selected_category]]
                        selected_field_index = st.selectbox(
                            "Select Field to Add",
                            options=range(len(field_options)),
                            format_func=lambda i: field_options[i][1], # Show only the descriptive value
                            key=f"field_select_{template_id}"
                        )
                        
                        if selected_field_index is not None:
                            selected_key, selected_value = field_options[selected_field_index]
                            
                            # Determine if it's a boolean field
                            is_boolean = selected_key.endswith("_check")
                            
                            # Input for the new value
                            st.markdown(f"**Adding Field:** {selected_key}")
                            st.markdown(f"**Description:** {selected_value}")
                            
                            if is_boolean:
                                new_value = "YES" if st.checkbox(
                                    "Set to YES", 
                                    key=f"new_bool_{selected_key}_{template_id}"
                                ) else "NO"
                            else:
                                new_value = st.text_input(
                                    f"Value for {selected_key}",
                                    key=f"new_text_{selected_key}_{template_id}"
                                )
                            
                            # Button to add the field
                            if st.button("Add Field", key=f"add_field_{template_id}"):
                                try:
                                    # Save the new field
                                    save_goa_modification(
                                        template_id, selected_key, "", new_value,
                                        "Manual addition", "User"
                                    )
                                    st.success(f"Added new field: {selected_key}")
                                    # Rerun to refresh UI
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error adding field: {str(e)}")
            except Exception as e:
                st.error(f"Error in Add New Fields section: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying template editor: {str(e)}")
        import traceback
        st.exception(e)

def show_template_report_page():
    """
    Displays a dedicated page for viewing and printing template reports.
    This page allows users to select any machine that has template data
    and generate a printable report.
    """
    st.title("📋 Template Reports")
    st.markdown("### Generate Printable Template Reports")
    
    # Load all clients
    # Ensure all_processed_machines is loaded if not already
    if "all_processed_machines" not in st.session_state or not st.session_state.all_processed_machines:
        st.session_state.all_processed_machines = load_all_processed_machines() # from crm_utils

    processed_machines = st.session_state.all_processed_machines
    
    if not processed_machines:
        st.warning("No machines with processed templates found. Please process a GOA for a machine first.")
        return
    
    # Create a mapping for easier lookup: client_name - quote_ref -> list of machines
    client_machine_map = {}
    for machine_info in processed_machines:
        client_key = f"{machine_info.get('client_name', 'N/A')} - {machine_info.get('quote_ref', 'N/A')}"
        if client_key not in client_machine_map:
            client_machine_map[client_key] = []
        client_machine_map[client_key].append(machine_info)

    client_options_display = ["Select a Client..."] + sorted(list(client_machine_map.keys()))
    selected_client_key = st.selectbox(
        "Select Client:",
        options=client_options_display,
        index=0,
        key="report_client_selector"
    )

    if selected_client_key != "Select a Client...":
        machines_for_client = client_machine_map[selected_client_key]
        machine_options = [(m.get('id'), m.get('machine_name', f"Machine ID {m.get('id')}")) for m in machines_for_client]
        
        selected_machine_id = st.selectbox(
            "Select Machine:",
            options=[m[0] for m in machine_options],
            format_func=lambda x: next((m[1] for m in machine_options if m[0] == x), "Unknown Machine"),
            key="report_machine_selector"
        )
        
        if selected_machine_id:
            templates_data = load_machine_templates_with_modifications(selected_machine_id)
            templates = templates_data.get('templates', [])
            
            if not templates:
                st.warning(f"No templates found for the selected machine. Process a GOA first.")
                return
            
            # --- Streamlined GOA Template Handling ---
            goa_template_data = None
            goa_template_type_name = "GOA"
            machine_name_for_report = next((m.get('machine_name', '') for m in machines_for_client if m.get('id') == selected_machine_id), "Unknown Machine")
            
            # Check if this is a SortStar machine based on the machine name
            is_sortstar_machine = False
            if machine_name_for_report:
                sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
                try:
                    if re.search(sortstar_pattern, machine_name_for_report.lower()):
                        is_sortstar_machine = True
                        st.info(f"SortStar machine detected: {machine_name_for_report}")
                except NameError:
                    import re
                    if re.search(sortstar_pattern, machine_name_for_report.lower()):
                        is_sortstar_machine = True
                        st.info(f"SortStar machine detected: {machine_name_for_report}")

            for t in templates:
                if str(t.get('template_type', '')).lower() == "goa":
                    if t.get('template_data') and isinstance(t.get('template_data'), dict):
                        goa_template_data = t['template_data']
                        goa_template_type_name = t.get('template_type', "GOA") # Use actual type name if available
                        break # Found valid GOA template data
                    elif t.get('template_data_json'): # Attempt to parse from JSON if direct data is bad
                        try:
                            import json
                            parsed_data = json.loads(t.get('template_data_json'))
                            if parsed_data and isinstance(parsed_data, dict):
                                goa_template_data = parsed_data
                                goa_template_type_name = t.get('template_type', "GOA")
                                st.info("Successfully recovered GOA template data from JSON.")
                                break
                        except Exception as e_parse:
                            st.warning(f"Could not parse GOA template JSON for machine {machine_name_for_report}: {e_parse}")
            
            if goa_template_data:
                st.markdown("---")
                st.markdown("### GOA Build Summary") 
                show_printable_summary_report(goa_template_data, machine_name_for_report, goa_template_type_name, is_sortstar_machine)
                st.info("To print this summary, use your browser's print function (CTRL+P or CMD+P) or download the HTML version and open it in a browser.")
            else:
                st.error(f"Valid GOA template data not found for machine: {machine_name_for_report}.")
                st.info("Please ensure a GOA has been processed for this machine and contains valid data.")
            # --- End of Streamlined GOA Template Handling (Old SelectBox removed) ---

    # Batch Report section (remains largely unchanged, but will use the detailed report generator)
    st.markdown("---")
    st.markdown("### Generate Batch Report for All Machines")
    
    unique_clients_for_batch_processing = {}
    if processed_machines: # processed_machines is defined at the top of show_template_report_page
        for machine_record in processed_machines:
            client_id = machine_record.get('client_id')
            if client_id and client_id not in unique_clients_for_batch_processing:
                # Storing client_id as key and display string as value
                unique_clients_for_batch_processing[client_id] = f"{machine_record.get('client_name', 'N/A')} - {machine_record.get('quote_ref', 'N/A')}"
    
    # Create options for the selectbox: (value_to_return, display_label)
    batch_client_options_for_selector = [("placeholder_batch", "Select Client for Batch Report...")] + \
                                        [(cid, name) for cid, name in sorted(unique_clients_for_batch_processing.items(), key=lambda item: item[1])]

    selected_client_id_batch = None
    if len(batch_client_options_for_selector) > 1: # Check if there are actual clients to select
        selected_client_id_batch = st.selectbox(
            "Select client for batch report:",
            options=[opt[0] for opt in batch_client_options_for_selector], # Pass only the IDs as options
            format_func=lambda x: dict(batch_client_options_for_selector).get(x, "Invalid client"), # Use the dict for display format
            index=0, # Default to placeholder
            key="template_report_client_select_batch"
        )
    else:
        st.info("No clients with processed machine templates available for batch reporting.")

    if selected_client_id_batch and selected_client_id_batch != "placeholder_batch":
        # selected_client_id_batch is now the actual client_id (integer)
        from src.utils.crm_utils import get_client_by_id, load_machines_for_quote # Ensure imports are here
        client_for_batch = get_client_by_id(selected_client_id_batch)
        
        if client_for_batch:
            # Load machines for this client using its primary quote_ref
            machines_for_batch = load_machines_for_quote(client_for_batch.get('quote_ref', ''))
            
            if not machines_for_batch:
                st.warning(f"No machines found for client {client_for_batch.get('customer_name', 'Unknown')} for batch processing.")
                # return # Optionally return if no machines, or allow to proceed if logic handles empty machines
            
            # Select template type for all machines
            template_type_options = ["GOA", "Packing Slip", "Commercial Invoice", "Certificate of Origin"]
            selected_template_type = st.selectbox(
                "Select template type for all machines:",
                options=template_type_options,
                key="template_report_type_select_batch"
            )
            
            # Generate batch report button
            if st.button("Generate Batch Report", key="generate_batch_report_btn"):
                st.markdown("---")
                st.markdown(f"### Batch Report: {selected_template_type} for {client_for_batch.get('customer_name', 'Unknown')}")
                
                import datetime # Ensure datetime is imported
                combined_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Batch Template Report - {client_for_batch.get('customer_name', 'Unknown')}</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            margin: 20px;
                            color: #333;
                        }}
                        h1 {{
                            color: #2c3e50;
                            border-bottom: 2px solid #3498db;
                            padding-bottom: 10px;
                        }}
                        h2 {{
                            color: #2980b9;
                            margin-top: 30px;
                            border-bottom: 1px solid #bdc3c7;
                            padding-bottom: 5px;
                        }}
                        h3 {{
                            color: #16a085;
                            margin-top: 25px;
                        }}
                        .machine-section {{
                            margin-bottom: 40px;
                            page-break-before: always;
                        }}
                        .report-meta {{
                            color: #7f8c8d;
                            font-size: 14px;
                            margin-bottom: 5px;
                        }}
                        .client-info {{
                            margin-bottom: 30px;
                        }}
                    </style>
                </head>
                <body>
                    <h1>Batch Template Report: {selected_template_type}</h1>
                    <div class="client-info">
                        <div class="report-meta">Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
                        <div class="report-meta">Client: {client_for_batch.get('customer_name', 'Unknown')}</div>
                        <div class="report-meta">Quote Reference: {client_for_batch.get('quote_ref', 'Unknown')}</div>
                    </div>
                """
                
                # Counter for machines with reports
                machines_with_reports = 0
                
                # Process each machine
                for machine in machines_for_batch:
                    machine_id = machine.get('id')
                    machine_name = machine.get('machine_name', f"Machine ID: {machine_id}")
                    
                    # Check if this is a SortStar machine
                    is_sortstar_machine = False
                    if machine_name:
                        sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
                        if re.search(sortstar_pattern, machine_name.lower()):
                            is_sortstar_machine = True
                    
                    # Load templates for this machine
                    templates_data = load_machine_templates_with_modifications(machine_id)
                    templates = templates_data.get('templates', [])
                    
                    # Find the template of the selected type
                    template = next((t for t in templates if t.get('template_type', '').lower() == selected_template_type.lower()), None)
                    
                    if template and 'template_data' in template and template['template_data']:
                        # Generate report for this machine
                        machine_report = generate_printable_report(
                            template['template_data'],
                            machine_name,
                            selected_template_type,
                            is_sortstar_machine
                        )
                        
                        # Extract the body content (between <body> and </body>)
                        import re
                        body_content = re.search(r'<body>(.*?)</body>', machine_report, re.DOTALL)
                        
                        if body_content:
                            # Add machine section to combined report
                            combined_html += f"""
                            <div class="machine-section">
                                <h2>{machine_name}</h2>
                            """
                            
                            # Add the report content for this machine (removing the outer structure)
                            content = body_content.group(1)
                            # Remove the main title and metadata since we have it in the combined report
                            content = re.sub(r'<h1>.*?</h1>', '', content)
                            content = re.sub(r'<div class="report-header">.*?</div>', '', content)
                            
                            combined_html += content
                            combined_html += "</div>"
                            machines_with_reports += 1
                
                # Close the HTML document
                combined_html += """
                </body>
                </html>
                """
                
                if machines_with_reports > 0:
                    # Display the combined report
                    st.components.v1.html(combined_html, height=600, scrolling=True)
                    
                    # Provide a download button for the combined report
                    st.download_button(
                        "Download Batch Report (HTML)",
                        combined_html,
                        file_name=f"batch_report_{selected_template_type.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.html",
                        mime="text/html",
                        key="download_batch_report_html"
                    )
                    
                    st.success(f"Generated reports for {machines_with_reports} machines.")
                else:
                    st.warning(f"No machines with {selected_template_type} templates found.")

def show_printable_summary_report(template_data, machine_name="", template_type="", is_sortstar_machine: bool = False):
    """
    Shows a printable summary report in a new tab using Streamlit components.
    
    Args:
        template_data: Dictionary of field keys to values from template
        machine_name: Name of the machine (optional)
        template_type: Type of template (e.g., "GOA") (optional)
        is_sortstar_machine: Boolean, True if it's a SortStar machine.
    """
    # Generate HTML summary report
    html_summary_report = generate_machine_build_summary_html(template_data, machine_name, template_type, is_sortstar_machine)
    
    # Display with html component
    st.components.v1.html(html_summary_report, height=600, scrolling=True)
    
    # Provide a download button for the HTML summary report
    st.download_button(
        "Download Summary Report (HTML)",
        html_summary_report,
        file_name=f"summary_template_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
        mime="text/html",
        key="download_summary_report_html"
    )

def show_quote_processing():
    st.title("📄 Quote Processing")
    processing_steps = ["Upload Quote", "Identify Main Machines", "Select Common Options", "Process Machine"]
    
    import base64
    from app import (
        perform_initial_processing, process_machine_specific_data, 
        load_previous_document, TEMPLATE_FILE, 
        calculate_machine_price, calculate_common_items_price
    )
    
    current_step = st.session_state.processing_step
    progress_percentage = current_step / (len(processing_steps) - 1) if len(processing_steps) > 1 else 0
    st.progress(progress_percentage)
    st.subheader(f"Step {current_step + 1}: {processing_steps[current_step]}")
    
    if current_step == 0:
        st.subheader("📄 Upload Quote PDF")
        uploaded_pdf = st.file_uploader("Choose PDF document to process", type="pdf", key=f"pdf_upload_{st.session_state.run_key}")
        
        # Add option to associate with existing client
        use_existing_client = st.checkbox("Associate with existing client?", key=f"goa_use_existing_client_{st.session_state.run_key}")
        existing_client_id = None
        
        if use_existing_client and "all_crm_clients" in st.session_state and st.session_state.all_crm_clients:
            client_options = [(c.get('id'), f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')}") for c in st.session_state.all_crm_clients]
            selected_client_id = st.selectbox(
                "Select existing client:", 
                options=[c[0] for c in client_options],
                format_func=lambda x: next((c[1] for c in client_options if c[0] == x), ""),
                key=f"goa_existing_client_select_{st.session_state.run_key}"
            )
            existing_client_id = selected_client_id
            st.info(f"Quote will be associated with selected client (ID: {existing_client_id})")
            
            # Store the client ID in session state to use in perform_initial_processing
            st.session_state.selected_existing_client_id = existing_client_id
        else:
            # Clear the selected client ID if checkbox is unchecked
            st.session_state.selected_existing_client_id = None
        
        if uploaded_pdf is not None:
            st.success(f"📄 PDF uploaded: {uploaded_pdf.name}")
            # Store file name for use in process_machine_specific_data
            st.session_state.pdf_filename = uploaded_pdf.name
            
            if st.button("Process PDF", key=f"process_pdf_{st.session_state.run_key}", type="primary"):
                if perform_initial_processing(uploaded_pdf, TEMPLATE_FILE):
                    st.session_state.processing_step = 1
                    st.rerun()
                else:
                    st.error("Failed to process PDF. Check errors above.")
        
        st.divider()
        st.subheader("🔄 Or Load Previous Quote")
        
        # Previous quote loading section
        if st.session_state.all_crm_clients:
            quotes = [(c['id'], f"{c.get('customer_name', 'Unknown')} - {c.get('quote_ref', 'Unknown')}") for c in st.session_state.all_crm_clients]
            if quotes:
                selected_quote_id = st.selectbox(
                    "Select a previous quote:", 
                    options=[q[0] for q in quotes], 
                    format_func=lambda x: next((q[1] for q in quotes if q[0] == x), ""), 
                    key="load_prev_quote"
                )
                if st.button("📥 Load Selected Quote", key="load_quote_btn"):
                    with st.spinner("Loading document..."): 
                        if load_previous_document(selected_quote_id): 
                            st.success("Document loaded!")
                            st.session_state.processing_step = 1
                            st.rerun()
            else: 
                st.info("No previous quotes to load.")
        
    elif current_step == 1:
        if not st.session_state.machine_confirmation_done:
            st.subheader("🔍 Identify Main Machines")
            
            # Display items for selection
            items = st.session_state.items_for_confirmation
            if items:
                # Create multiselect for main machines
                all_item_descs = [f"{i}: {item.get('description', '').split(chr(10))[0]}" for i, item in enumerate(items)]
                
                # Get current selections
                default_selections = st.session_state.selected_main_machines
                
                selected_indices = st.multiselect(
                    "Select main machine items:",
                    options=range(len(all_item_descs)),
                    default=default_selections,
                    format_func=lambda i: all_item_descs[i],
                    key=f"main_machines_select_{st.session_state.run_key}"
                )
                
                # Update selections in session state
                st.session_state.selected_main_machines = selected_indices
                
                # Show preview of selected items
                if selected_indices:
                    st.subheader("Selected Main Machines:")
                    for idx in selected_indices:
                        if idx < len(items):
                            item = items[idx]
                            st.markdown(f"**Item {idx}:** {item.get('description', '').split(chr(10))[0]}")
                            with st.expander("Full Description", expanded=False):
                                st.text(item.get('description', ''))
                
                # Continue button
                if st.button("Continue to Common Options ➡️", key="continue_to_common"):
                    st.session_state.machine_confirmation_done = True
                    st.rerun()
            else:
                st.warning("No items available for selection.")
        else:
            # Move to next step
            st.session_state.processing_step = 2
            st.rerun()
            
    elif current_step == 2:
        if not st.session_state.common_options_confirmation_done:
            st.subheader("🔧 Select Common Options")
            
            # Display items for selection, excluding already selected main machines
            items = st.session_state.items_for_confirmation
            main_machines = st.session_state.selected_main_machines
            
            if items:
                # Create multiselect for common options, excluding main machines
                all_item_descs = [f"{i}: {item.get('description', '').split(chr(10))[0]}" for i, item in enumerate(items)]
                available_indices = [i for i in range(len(items)) if i not in main_machines]
                
                # Get current selections
                default_selections = st.session_state.selected_common_options
                
                selected_indices = st.multiselect(
                    "Select common option items (apply to all machines):",
                    options=available_indices,
                    default=default_selections,
                    format_func=lambda i: all_item_descs[i] if i < len(all_item_descs) else f"Item {i}",
                    key=f"common_options_select_{st.session_state.run_key}"
                )
                
                # Update selections in session state
                st.session_state.selected_common_options = selected_indices
                
                # Show preview of selected items
                if selected_indices:
                    st.subheader("Selected Common Options:")
                    for idx in selected_indices:
                        if idx < len(items):
                            item = items[idx]
                            st.markdown(f"**Item {idx}:** {item.get('description', '').split(chr(10))[0]}")
                            with st.expander("Full Description", expanded=False):
                                st.text(item.get('description', ''))
                
                # Navigation buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Back to Main Machines", key="back_to_machines"):
                        st.session_state.machine_confirmation_done = False
                        st.session_state.processing_step = 1
                        st.rerun()
                with col2:
                    if st.button("Continue to Machine Processing ➡️", key="continue_to_processing"):
                        # Group items by machine based on selections
                        machine_data = {"machines": [], "common_items": []}
                        
                        # Add selected main machines
                        for idx in main_machines:
                            if idx < len(items):
                                machine_name = items[idx].get('description', '').split(chr(10))[0]
                                machine_data["machines"].append({
                                    "machine_name": machine_name,
                                    "main_item": items[idx],
                                    "add_ons": []
                                })
                        
                        # Add selected common options
                        for idx in selected_indices:
                            if idx < len(items):
                                machine_data["common_items"].append(items[idx])
                        
                        # Store in session state
                        st.session_state.identified_machines_data = machine_data
                        st.session_state.common_options_confirmation_done = True
                        st.session_state.processing_step = 3
                        st.rerun()
            else:
                st.warning("No items available for selection.")
        else:
            # Move to next step
            st.session_state.processing_step = 3
            st.rerun()
            
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
                if st.button("Process This Machine for GOA", type="primary", key=f"process_machine_btn_{st.session_state.run_key}"):
                    with st.spinner(f"Processing {selected_machine.get('machine_name')} for GOA..."):
                        success = process_machine_specific_data(selected_machine)
                        if success:
                            st.success(f"Machine '{selected_machine.get('machine_name')}' processed successfully!")
                            st.session_state.selected_machine_id = selected_machine.get('id')
                            
                            # Note about template modifications
                            st.info("To view or modify the GOA template for this machine, go to CRM Management and select this client.")
                            
                            st.rerun()
                        else:
                            st.error(f"Failed to process machine for GOA. Check errors above.")
        else:
            st.warning("No machines identified. Go back to Step 1 to select main machines.")
            if st.button("⬅️ Back to Step 1", key="back_to_step1"): 
                st.session_state.processing_step = 1
                st.session_state.machine_confirmation_done = False
                st.session_state.common_options_confirmation_done = False
                st.rerun()

def show_crm_management_page():
    st.title("📒 CRM Management")
    from app import load_crm_data, quick_extract_and_catalog, update_single_priced_item # Ensure update_single_priced_item is imported

    if st.button("Refresh CRM List", key=f"refresh_crm_main_tab_{st.session_state.run_key}"):
        load_crm_data(); st.success("CRM data refreshed.")
    with st.expander("Quick Catalog New Quote", expanded=False):
        st.markdown("Upload PDF to extract data and create new client record or associate with existing client.")
        uploaded_pdf_crm = st.file_uploader("Choose PDF for CRM Quick Catalog", type="pdf", key=f"crm_quick_upload_{st.session_state.run_key}")
        
        # Add option to associate with existing client
        use_existing_client = st.checkbox("Associate with existing client?", key=f"use_existing_client_{st.session_state.run_key}")
        existing_client_id = None
        
        if use_existing_client and st.session_state.all_crm_clients:
            client_options = [(c.get('id'), f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')}") for c in st.session_state.all_crm_clients]
            selected_client_id = st.selectbox(
                "Select existing client:", 
                options=[c[0] for c in client_options],
                format_func=lambda x: next((c[1] for c in client_options if c[0] == x), ""),
                key=f"existing_client_select_{st.session_state.run_key}"
            )
            existing_client_id = selected_client_id
            st.info(f"Quote will be associated with selected client (ID: {existing_client_id})")
        
        if uploaded_pdf_crm and st.button("Catalog This Quote", type="primary", key="crm_quick_catalog_btn"):
            result = quick_extract_and_catalog(uploaded_pdf_crm, existing_client_id)
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
                client_tab1, client_tab2, client_tab3, client_tab4 = st.tabs(["📋 Client Details", "💲 Priced Items", "📤 Upload PDF (Client)", "🔄 Template Modifications"])
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
                with client_tab4:
                    # Find machines for this client
                    from src.utils.crm_utils import load_machines_for_quote
                    machines = load_machines_for_quote(client_to_display_and_edit.get('quote_ref', ''))
                    
                    if not machines:
                        st.warning("No machines found for this client.")
                    else:
                        st.subheader("Select Machine to Modify Templates")
                        machine_options = [(m.get('id'), m.get('machine_name', f"Machine ID {m.get('id')}")) for m in machines]
                        selected_machine_id = st.selectbox(
                            "Select Machine:", 
                            options=[m[0] for m in machine_options],
                            format_func=lambda x: next((m[1] for m in machine_options if m[0] == x), ""),
                            key="template_machine_select"
                        )
                        
                        if selected_machine_id:
                            # Get the machine name for the selected ID
                            selected_machine_name = next((m[1] for m in machine_options if m[0] == selected_machine_id), None)
                            # Show template modifications UI for the selected machine
                            show_goa_modifications_ui(selected_machine_id, machine_name=selected_machine_name) # Pass machine_name
        except Exception as e: st.error(f"Error in CRM client display: {e}"); import traceback; traceback.print_exc()
    else: st.info("Select a client to view/edit details.")
    
    st.markdown("---"); st.subheader("All Client Records Table")
    if st.session_state.all_crm_clients:
        df_all_clients = pd.DataFrame(st.session_state.all_crm_clients)
        all_clients_cols = ['id', 'quote_ref', 'customer_name', 'machine_model', 'country_destination', 'sold_to_address', 'ship_to_address', 'telephone', 'customer_contact_person', 'customer_po', 'processing_date']
        df_all_clients_final = df_all_clients[[c for c in all_clients_cols if c in df_all_clients.columns]]
        st.dataframe(df_all_clients_final, use_container_width=True, hide_index=True)
    else: st.info("No client records found.")
    
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

def show_chat_page():
    """Displays the chat interface page with robust state management."""
    st.title("💬 Chat with Document Assistant")

    # Initialize required state variables
    if "chat_context" not in st.session_state:
        st.session_state.chat_context = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_page_client_selector" not in st.session_state:
        st.session_state.chat_page_client_selector = "placeholder"

    # --- Document Selection UI (Always Visible) ---
    st.subheader("Select Document to Chat About")

    client_options = [("placeholder", "Select a client/quote...")]
    if "all_crm_clients" in st.session_state and st.session_state.all_crm_clients:
        client_options.extend([(c.get('id'), f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')}") for c in st.session_state.all_crm_clients])

    # Determine the current selection to display in the dropdown.
    # This ensures the dropdown is in sync with the actual context.
    current_context_id = "placeholder"
    if st.session_state.chat_context:
        current_context_id = st.session_state.chat_context.get("client_data", {}).get("id", "placeholder")

    st.selectbox(
        "Client/Quote:",
        options=[opt[0] for opt in client_options],
        format_func=lambda x: dict(client_options).get(x, ""),
        # Set the key and ensure the index reflects the current state
        key="chat_page_client_selector",
        index=[opt[0] for opt in client_options].index(current_context_id),
        on_change=handle_chat_context_switch,
    )

    # --- Main Chat Interface ---
    if st.session_state.chat_context:
        chat_ctx = st.session_state.chat_context
        client_name = chat_ctx.get("client_data", {}).get("customer_name", "N/A")
        quote_ref = chat_ctx.get("quote_ref", "N/A")
        st.info(f"Chatting about document: **{client_name} - {quote_ref}**")

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask a question about the selected document..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    from app import process_chat_query
                    # This context is now guaranteed to be the correct one
                    context_data = {
                        "full_pdf_text": chat_ctx.get("full_pdf_text", ""),
                        "selected_pdf_descs": [],
                        "template_contexts": {}
                    }
                    response = process_chat_query(prompt, "quote", context_data)
                    st.markdown(response)
            
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    else:
        # This message shows when no context is loaded
        st.info("Please select a document from the dropdown to begin.")

def handle_chat_context_switch():
    """Callback triggered when the user selects a new document from the dropdown."""
    # The new client ID is in the widget's session state key
    selected_id = st.session_state.get("chat_page_client_selector")

    # Always clear the history when the selection changes.
    st.session_state.chat_history = []

    if selected_id and selected_id != "placeholder":
        from src.utils.crm_utils import get_client_by_id, load_document_content
        client_data = get_client_by_id(selected_id)
        if client_data:
            quote_ref = client_data.get('quote_ref')
            doc_content = load_document_content(quote_ref)
            if doc_content and doc_content.get("full_pdf_text"):
                # Load the new context
                st.session_state.chat_context = {
                    "client_data": client_data,
                    "quote_ref": quote_ref,
                    "full_pdf_text": doc_content.get("full_pdf_text", "")
                }
            else:
                # If the selected document has no content, clear the context
                st.session_state.chat_context = None
                st.warning(f"No document content found for quote '{quote_ref}'.")
        else:
            # If client ID is invalid, clear context
            st.session_state.chat_context = None
            st.error(f"Could not load client data for ID {selected_id}.")
    else:
        # If the user selects the placeholder, clear the context
        st.session_state.chat_context = None

    # If no valid context was loaded, reset the dropdown selection
    if st.session_state.chat_context is None:
        st.session_state.chat_page_client_selector = "placeholder"

def render_chat_ui():
    """
    This function previously rendered a quick chat component on all pages.
    It has been disabled as requested to remove the quick chat option
    while keeping the main Chat page intact.
    """
    # Function intentionally left empty to disable quick chat
    pass

def generate_machine_build_summary_html(template_data, machine_name="", template_type="", is_sortstar_machine: bool = False):
    """
    Generates a concise, printable HTML summary of selected template items,
    optimized for a quick overview for machine building teams.
    
    Args:
        template_data: Dictionary of field keys to values from template
        machine_name: Name of the machine (optional)
        template_type: Type of template (e.g., "GOA") (optional)
        is_sortstar_machine: Boolean indicating if the machine is a SortStar machine.
        
    Returns:
        HTML string for the summary report
    """
    # Imports are at the top of the file
    import datetime
    import os

    # print(f"DEBUG: generate_machine_build_summary_html called. Machine: {machine_name}, Type: {template_type}, IsSortStar: {is_sortstar_machine}") 
    if not template_data:
        # print("DEBUG: template_data is None or empty.")
        return "<p>No template data provided to generate the report.</p>"

    current_mappings = SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar_machine else DEFAULT_EXPLICIT_MAPPINGS
    outline_file_to_use = "sortstar_fields_outline.md" if is_sortstar_machine else "full_fields_outline.md"

    outline_structure = {}
    
    # Function to convert SortStar mappings to proper outline structure
    def build_sortstar_outline_from_mappings(mappings):
        """Convert SortStar explicit mappings to a proper outline structure"""
        outline = {}
        for key, value_path in mappings.items():
            parts = [p.strip() for p in value_path.split(" > ")]
            if len(parts) >= 1:
                section = parts[0]
                if section not in outline:
                    outline[section] = {"_direct_fields_": [], "_subsections_": {}}
                
                # Handle subsections
                if len(parts) >= 3:  # Section > Subsection > Field
                    subsection = parts[1]
                    if subsection not in outline[section]["_subsections_"]:
                        outline[section]["_subsections_"][subsection] = []
                    # Add the field key to track later
                    outline[section]["_subsections_"][subsection].append(key)
                elif len(parts) == 2:  # Section > Field (no subsection)
                    outline[section]["_direct_fields_"].append(key)
        return outline
    
    # Read and parse the outline file if it exists
    if os.path.exists(outline_file_to_use):
        with open(outline_file_to_use, 'r', encoding='utf-8') as f:
            outline_content = f.read()
        
        # Use appropriate parsing function based on machine type
        if is_sortstar_machine:
            # For SortStar, build proper outline structure from mappings
            outline_structure = build_sortstar_outline_from_mappings(current_mappings)
        else:
            # For regular templates, use the standard outline parser
            outline_structure = parse_full_fields_outline(outline_content)
    else:
        # If outline file doesn't exist but we have SortStar machine
        if is_sortstar_machine:
            outline_structure = build_sortstar_outline_from_mappings(current_mappings)
        else:
            # print(f"DEBUG: Outline file not found: {outline_file_to_use}. Report will list all items under 'Additional Specifications'.")
            pass # Keep outline_structure as empty dict

    # Initialize report_data_by_outline based on the structure of outline_structure
    report_data_by_outline = {}
    for section_name_from_outline, section_details_from_outline in outline_structure.items():
        subs_data_for_report = {}
        # Assuming section_details_from_outline.get("_subsections_") is a list of subsection names or a dict {name: fields}
        subsection_config = section_details_from_outline.get("_subsections_", [])
        if isinstance(subsection_config, list): # list of names
            for sub_name_str_key in subsection_config:
                if isinstance(sub_name_str_key, str):
                    subs_data_for_report[sub_name_str_key] = []
        elif isinstance(subsection_config, dict): # dict of {name: field_keys_list}
            for sub_name_key in subsection_config.keys():
                subs_data_for_report[sub_name_key] = []
        
        report_data_by_outline[section_name_from_outline] = {
            "_direct_fields_": [],
            "_subsections_": subs_data_for_report
        }
    
    if not outline_structure: 
        report_data_by_outline["All Specifications"] = {"_direct_fields_": [], "_subsections_": {}}
        print("DEBUG: Using fallback 'All Specifications' section due to no outline.")

    unmapped_or_additional_fields = []
    # field_keys_from_template_data_processed_by_outline = set()

    # New Strategy: Iterate through template_data and map to outline_structure
    print(f"DEBUG: Starting NEW STRATEGY: Iterating template_data ({len(template_data)} items) to map to outline.")
    for actual_field_key, value in template_data.items():
        value_str = str(value).strip()
        is_checked_suffix = actual_field_key.endswith("_check")

        # --- Re-activating and Refining Filters ---
        # Basic Filter 1: Skip if key is literally "none" or value implies negation/emptiness
        if actual_field_key.lower() == "none":
            # print(f"DEBUG: FILTERED (key is none): Key '{actual_field_key}', Value: '{value_str}'")
            continue
        if not value_str or value_str.lower() in ["no", "none", "false", "0"]: # Allow "0" if it means quantity 0 but is affirmative, but for now, filter out as per initial request for concise summary
            # if value_str == "0" and not is_checked_suffix: # Example: allow if it's a quantity like "0 pcs"
            #     pass # Potentially allow "0" for non-boolean fields if meaningful
            # else:
            # print(f"DEBUG: FILTERED (basic value): Key '{actual_field_key}', Value: '{value_str}'")
            continue
        
        # Basic Filter 2: For _check fields, value must be YES or TRUE
        if is_checked_suffix and not (value_str.upper() == "YES" or value_str.upper() == "TRUE"):
            # print(f"DEBUG: FILTERED (_check not YES/TRUE): Key '{actual_field_key}', Value: '{value_str}'")
            continue
        # --- End of Basic Filters ---

        # Determine display_value (checkmark or original string)
        display_value = "✔" if (is_checked_suffix and value_str.upper() in ["YES", "TRUE"]) or \
                                 (not is_checked_suffix and isinstance(value, str) and value_str.upper() == "YES") else value_str
        
        # Get descriptive path and final label
        descriptive_path = current_mappings.get(actual_field_key, actual_field_key)
        
        # Handle different delimiters based on machine type
        if is_sortstar_machine:
            path_parts = [p.strip() for p in descriptive_path.split(" > ")]
        else:
            path_parts = [p.strip() for p in descriptive_path.split(" - ")]
            
        final_label_for_item = path_parts[-1]

        # --- Stricter "None Option" Filter (applied AFTER display_value and label are determined) ---
        # This is critical: if the item is a "None" option, even if its value was "YES" (making display_value "✔"), skip it.
        current_item_label_lower = final_label_for_item.lower().strip()
        descriptive_path_lower = descriptive_path.lower()

        # Check for "None" options considering different delimiters based on machine type
        if current_item_label_lower == "none":
            # print(f"DEBUG: FILTERED (is None option - label): Key '{actual_field_key}', Label: '{final_label_for_item}'")
            continue
            
        # Check path endings with the correct delimiter
        if is_sortstar_machine:
            if descriptive_path_lower.endswith(" > none") or descriptive_path_lower.endswith(" > none (checkbox)"):
                # print(f"DEBUG: FILTERED (is None option - SortStar path): Key '{actual_field_key}', Path: '{descriptive_path}'")
                continue
        else:
            if descriptive_path_lower.endswith(" - none") or descriptive_path_lower.endswith(" - none (checkbox)"):
                # print(f"DEBUG: FILTERED (is None option - regular path): Key '{actual_field_key}', Path: '{descriptive_path}'")
                continue
        # --- End of "None Option" Filter ---
        
        # If after all this, display_value became empty (e.g. a boolean False not caught above, or a YES that was a None option)
        # This check should be mostly redundant if above filters are comprehensive
        if not display_value:
            # print(f"DEBUG: FILTERED (empty display_value post-processing): Key '{actual_field_key}', Label: '{final_label_for_item}', Value: '{value_str}'")
            continue
            
        field_info = {
            "key": actual_field_key,
            "value": display_value, 
            "label": final_label_for_item, 
            "full_path_label": descriptive_path 
        }

        # Try to map to outline_structure
        mapped_to_outline = False
        if outline_structure and path_parts:
            potential_section_name = path_parts[0]
            target_section_name_in_outline = None
            for outline_sec_name in outline_structure.keys():
                if outline_sec_name.lower() == potential_section_name.lower():
                    target_section_name_in_outline = outline_sec_name
                    break
            
            if target_section_name_in_outline:
                # Revised Subsection Mapping Logic
                if len(path_parts) > 1: # Path has at least a section and a field/first-level-subsection
                    first_level_item_name_from_path = path_parts[1] # Could be a field or first subsection
                    
                    # Check if this first_level_item_name_from_path matches a defined subsection in the outline for this section
                    target_first_level_subsection_in_outline = None
                    if target_section_name_in_outline in report_data_by_outline and \
                       isinstance(report_data_by_outline[target_section_name_in_outline].get("_subsections_"), dict):
                        for outline_sub_name_key in report_data_by_outline[target_section_name_in_outline]["_subsections_"].keys():
                            if outline_sub_name_key.lower() == first_level_item_name_from_path.lower():
                                target_first_level_subsection_in_outline = outline_sub_name_key
                                break
                    
                    if target_first_level_subsection_in_outline:
                        # Item belongs to this identified first-level subsection
                        # The label for the item should be the rest of its path parts
                        if is_sortstar_machine and len(path_parts) > 2:
                            # For SortStar, join with " > " as that's the delimiter used
                            field_info["label"] = " > ".join(path_parts[2:]) if len(path_parts) > 2 else final_label_for_item
                        else:
                            # For regular templates, join with " - "
                            field_info["label"] = " - ".join(path_parts[2:]) if len(path_parts) > 2 else final_label_for_item
                            
                        if not field_info["label"]: field_info["label"] = final_label_for_item # safety for cases like "Sec - Sub" (no further parts)
                        
                        # print(f"DEBUG: Mapping to Outline SUBN: Key '{actual_field_key}' -> Sec '{target_section_name_in_outline}' -> Sub '{target_first_level_subsection_in_outline}' (Label: {field_info[\"label\"]})")
                        report_data_by_outline[target_section_name_in_outline]["_subsections_"][target_first_level_subsection_in_outline].append(field_info)
                        mapped_to_outline = True
                    elif len(path_parts) >= 2: # Path looked like it had a field/sub-identifier after section, but it didn't match a known subsection
                        # Treat as a direct field under the section. Label is parts[1:]
                        if is_sortstar_machine:
                            # For SortStar, join with " > "
                            field_info["label"] = " > ".join(path_parts[1:]) if len(path_parts) > 1 else final_label_for_item
                        else:
                            # For regular templates, join with " - "
                            field_info["label"] = " - ".join(path_parts[1:]) if len(path_parts) > 1 else final_label_for_item
                            
                        if not field_info["label"]: field_info["label"] = final_label_for_item
                        # print(f"DEBUG: Mapping to Outline DIRECT (path >= 2, no sub match): Key '{actual_field_key}' -> Sec '{target_section_name_in_outline}' (Label: {field_info[\"label\"]})")
                        report_data_by_outline[target_section_name_in_outline]["_direct_fields_"].append(field_info)
                        mapped_to_outline = True
                    # If len(path_parts) == 1, it would mean only section name was in path_parts, which is unusual if actual_field_key comes from explicit_mappings
                    # This case is implicitly handled by falling through to unmapped if not otherwise caught.

                # else: # len(path_parts) <= 1, meaning path was just Section or less.
                    # This usually implies the descriptive_path was just the actual_field_key itself and didn't match a section.
                    # This case will be handled by mapped_to_outline remaining False and falling to unmapped_or_additional_fields.
                    # However, if target_section_name_in_outline was found, and len(path_parts) == 1, it means the key IS the section name? Unlikely.
                    # For safety, if it was somehow len(path_parts) == 1 AND target_section_name_in_outline matched, it's a direct field.
                    # This edge case is less critical path than subsection mapping.
                    # The more common case if only section matched is len(path_parts) == 2 (Section - Field)
                    # which is covered by the elif len(path_parts) >= 2 above if it doesn't match a subsection.
            
        if not mapped_to_outline:
            # print(f"DEBUG: Adding to unmapped: Key '{actual_field_key}' (Path: {descriptive_path}, Label: {final_label_for_item})")
            if not outline_structure:
                report_data_by_outline["All Specifications"]["_direct_fields_"].append(field_info)
            else:
                unmapped_or_additional_fields.append(field_info)

    # --- The old iteration logic based on outline_structure first is now removed/replaced by the above --- 

    total_direct_fields = sum(len(s_data.get('_direct_fields_', [])) for s_data in report_data_by_outline.values())
    total_subsection_fields = sum(sum(len(sublist) for sublist in s_data.get('_subsections_', {}).values()) for s_data in report_data_by_outline.values())
    print(f"DEBUG: (New Strategy) Total direct fields mapped to outline: {total_direct_fields}") 
    print(f"DEBUG: (New Strategy) Total subsection fields mapped to outline: {total_subsection_fields}") 
    print(f"DEBUG: (New Strategy) Total unmapped_or_additional_fields: {len(unmapped_or_additional_fields)}")

    # HTML Generation - Order of sections will come from iterating report_data_by_outline.keys()
    # To ensure outline order for sections, we should iterate list(outline_structure.keys()) if outline_structure exists
    # And for fields within sections/subsections, they are appended in the order template_data was iterated.
    # For true outline order of fields, explicit_placeholder_mappings would need to be sorted by outline, or a post-sort applied.

    # For now, let's preserve the order of how sections were defined in report_data_by_outline (from outline_structure)
    # And for items within sections/subsections, they are as they came from template_data, grouped by mapping.
    # A final sort by 'full_path_label' within each list can ensure consistent display if template_data order varies.
    for section_name_render in report_data_by_outline.keys(): # Iterate based on initialized sections
        section_content = report_data_by_outline[section_name_render]
        if section_content.get("_direct_fields_"):
            section_content["_direct_fields_"] = sorted(section_content["_direct_fields_"], key=lambda x: x["full_path_label"])
        if section_content.get("_subsections_"):
            for sub_name_render in section_content["_subsections_"]:
                if section_content["_subsections_"][sub_name_render]:
                    section_content["_subsections_"][sub_name_render] = sorted(section_content["_subsections_"][sub_name_render], key=lambda x: x["full_path_label"])
    
    unmapped_or_additional_fields = sorted(unmapped_or_additional_fields, key=lambda x: x["full_path_label"])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Machine Build Summary: {machine_name or 'N/A'}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 15px; color: #333; line-height: 1.3; font-size: 10pt; }}
            .report-header {{ margin-bottom: 20px; text-align: center; }}
            h1 {{ color: #2c3e50; font-size: 1.5em; margin-bottom: 5px; }}
            .report-meta {{ color: #7f8c8d; font-size: 0.85em; margin-bottom: 15px; }}
            h2 {{ color: #2980b9; font-size: 1.2em; margin-top: 20px; border-bottom: 1px solid #bdc3c7; padding-bottom: 6px; page-break-before: auto; page-break-after: avoid; }}
            h3 {{ color: #16a085; font-size: 1.05em; margin-top: 15px; margin-bottom: 5px; font-weight: bold; page-break-after: avoid; }}
            ul.spec-list {{ list-style-type: none; padding-left: 0; margin-left: 5px; page-break-inside: avoid; }}
            ul.spec-list li {{ margin-bottom: 4px; font-size: 0.95em; }}
            .spec-label {{ font-weight: normal; color: #283747; }}
            .spec-value {{ color: #000; margin-left: 8px; font-weight: bold; }}
            .section-block {{ margin-bottom: 15px; page-break-inside: avoid; }}
            .print-button {{ position: fixed; top: 10px; right: 10px; z-index: 1000; }}
            @media print {{
                body {{ margin: 10mm; font-size: 9pt; }}
                .print-button {{ display: none !important; }}
                h1, h2, h3, ul.spec-list li {{ page-break-after: avoid; page-break-inside: avoid !important; }}
            }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>Machine Build Summary</h1>
            <div class="report-meta">
                Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
                {f" | Machine: {machine_name}" if machine_name else ""}
                {f" | Template: {template_type}" if template_type else ""}
            </div>
        </div>
        <div class="print-button no-print">
            <button onclick="window.print()">Print Summary</button>
        </div>
    """
    
    # Iterate through sections in the order defined by outline_structure keys for rendering
    # This ensures the report follows the outline's section sequence.
    if is_sortstar_machine:
        # Define SortStar section ordering
        sortstar_section_order = [
            "GENERAL ORDER ACKNOWLEDGEMENT", 
            "BASIC SYSTEMS", 
            "OPTIONAL SYSTEMS", 
            "Order Identification", 
            "Utility Specifications"
        ]
        
        # Create ordered list of sections based on SortStar priority
        rendered_section_names = []
        
        # First add sections in the predefined order if they exist
        for ordered_section in sortstar_section_order:
            if ordered_section in report_data_by_outline:
                rendered_section_names.append(ordered_section)
        
        # Then add any remaining sections from report_data_by_outline that weren't in the predefined order
        for section in report_data_by_outline.keys():
            if section not in rendered_section_names:
                rendered_section_names.append(section)
    else:
        # For regular templates, use outline structure order or alphabetical
        rendered_section_names = list(outline_structure.keys()) if outline_structure else list(report_data_by_outline.keys())
    
    has_any_content = False

    for section_name_to_render in rendered_section_names:
        if section_name_to_render not in report_data_by_outline: continue # Should not happen if initialized from outline
        
        section_content = report_data_by_outline[section_name_to_render]
        direct_fields = section_content.get("_direct_fields_", [])
        subsections_data_map = section_content.get("_subsections_", {}) # This is e.g. {"HMI": [items], "PLC": [items]}
        
        # Check if this section has any content to display
        section_has_direct_items = bool(direct_fields)
        section_has_subsection_items = any(bool(fields_list) for fields_list in subsections_data_map.values())
        
        if not section_has_direct_items and not section_has_subsection_items:
            continue
        
        has_any_content = True
        # Use section_name_to_render for headers and IDs
        html += f'<div class="section-block"><h2 id="{section_name_to_render.replace(" ", "_").replace("/", "_")}">{section_name_to_render}</h2>'

        if section_has_direct_items:
            html += '<ul class="spec-list">'
            # Items are already sorted by full_path_label before this HTML generation part
            for item in direct_fields:
                display_value = item["value"]
                # Special handling for options_listing - show as bullet points
                if item["key"] == "options_listing":
                    # Remove "Selected Options and Specifications:" header if present
                    cleaned_value = display_value
                    if isinstance(cleaned_value, str) and "Selected Options and Specifications:" in cleaned_value:
                        cleaned_value = cleaned_value.replace("Selected Options and Specifications:", "").strip()
                    
                    # Format as nested bullet list instead of truncating
                    html += f'<li><span class="spec-label">{item["label"]}:</span></li>'
                    html += '<li><ul style="list-style-type: disc; margin-left: 30px;">'
                    
                    # Split by lines and create bullet points
                    if isinstance(cleaned_value, str):
                        lines = cleaned_value.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line:  # Skip empty lines
                                html += f'<li>{line}</li>'
                    else:
                        html += f'<li>{cleaned_value}</li>'
                        
                    html += '</ul></li>'
                else:
                    # Normal field handling
                    html += f'<li><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></li>'
            html += '</ul>'

        if section_has_subsection_items:
            # Get the original order of subsection names for this section from outline_structure
            original_subsection_name_order = []
            if outline_structure and section_name_to_render in outline_structure:
                subsection_config_from_outline = outline_structure[section_name_to_render].get("_subsections_", [])
                if isinstance(subsection_config_from_outline, list):
                    original_subsection_name_order = [name for name in subsection_config_from_outline if isinstance(name, str)]
                elif isinstance(subsection_config_from_outline, dict):
                    original_subsection_name_order = list(subsection_config_from_outline.keys())
            
            # Fallback if original order couldn't be determined or for subsections not strictly in outline's list
            if not original_subsection_name_order:
                original_subsection_name_order = sorted(list(subsections_data_map.keys())) # Sort by name as fallback

            for sub_name_to_render in original_subsection_name_order:
                if sub_name_to_render in subsections_data_map:
                    fields_list_for_subsection = subsections_data_map[sub_name_to_render]
                    if not fields_list_for_subsection: continue

                    # Use section_name_to_render and sub_name_to_render for IDs
                    html += f'<h3 id="{section_name_to_render.replace(" ", "_").replace("/", "_")}_{sub_name_to_render.replace(" ", "_").replace("/", "_")}">{sub_name_to_render}</h3>'
                    html += '<ul class="spec-list">'
                    # Items are already sorted by full_path_label
                    for item in fields_list_for_subsection:
                        display_value = item["value"]
                        # Special handling for options_listing - show as bullet points
                        if item["key"] == "options_listing":
                            # Remove "Selected Options and Specifications:" header if present
                            cleaned_value = display_value
                            if isinstance(cleaned_value, str) and "Selected Options and Specifications:" in cleaned_value:
                                cleaned_value = cleaned_value.replace("Selected Options and Specifications:", "").strip()
                            
                            # Format as nested bullet list instead of truncating
                            html += f'<li><span class="spec-label">{item["label"]}:</span></li>'
                            html += '<li><ul style="list-style-type: disc; margin-left: 30px;">'
                            
                            # Split by lines and create bullet points
                            if isinstance(cleaned_value, str):
                                lines = cleaned_value.split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:  # Skip empty lines
                                        html += f'<li>{line}</li>'
                            else:
                                html += f'<li>{cleaned_value}</li>'
                                
                            html += '</ul></li>'
                        else:
                            # Normal field handling
                            html += f'<li><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></li>'
                    html += '</ul>'
        html += '</div>' 

    # Render unmapped fields if any
    if unmapped_or_additional_fields: 
        has_any_content = True
        html += f'<div class="section-block"><h2 id="unmapped_additional_fields">Additional Specifications</h2>'
        html += '<ul class="spec-list">'
        # Items are already sorted by full_path_label
        for item in unmapped_or_additional_fields: 
            display_value = item["value"]
            # Special handling for options_listing - show as bullet points
            if item["key"] == "options_listing":
                # Remove "Selected Options and Specifications:" header if present
                cleaned_value = display_value
                if isinstance(cleaned_value, str) and "Selected Options and Specifications:" in cleaned_value:
                    cleaned_value = cleaned_value.replace("Selected Options and Specifications:", "").strip()
                
                # Format as nested bullet list instead of truncating
                html += f'<li><span class="spec-label">{item["label"]}:</span></li>'
                html += '<li><ul style="list-style-type: disc; margin-left: 30px;">'
                
                # Split by lines and create bullet points
                if isinstance(cleaned_value, str):
                    lines = cleaned_value.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:  # Skip empty lines
                            html += f'<li>{line}</li>'
                else:
                    html += f'<li>{cleaned_value}</li>'
                    
                html += '</ul></li>'
            else:
                # Normal field handling
                html += f'<li><span class="spec-label">{item["label"]}:</span> <span class="spec-value">{display_value}</span></li>'
        html += '</ul></div>'
    
    if not has_any_content:
        html += "<p>No items were processed for this summary report based on current criteria (filters are currently off for debugging).</p>"

    html += """
    </body>
    </html>
    """
    return html