import streamlit as st
import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
import traceback
import shutil
from datetime import datetime

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

def show_template_summary(template_data, template_contexts=None):
    """
    Displays a hierarchical summary of selected items in the template.
    
    Args:
        template_data: Dictionary of field keys to values from template
        template_contexts: Optional dictionary of field keys to their context/description
    """
    sections = generate_template_summary(template_data, template_contexts)
    
    if not sections:
        st.info("No items selected in this template.")
        return
        
    st.markdown("### Template Summary")
    
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

def show_goa_modifications_ui(machine_id: int):
    """
    Displays and manages GOA template modifications for a specific machine.
    
    Args:
        machine_id: ID of the machine to show modifications for
    """
    from src.utils.crm_utils import (
        load_machine_templates_with_modifications, save_goa_modification,
        update_template_after_modifications
    )
    from src.utils.doc_filler import fill_word_document_from_llm_data
    
    st.subheader("🔄 GOA Template Modifications")
    
    # Display machine ID for debugging
    st.info(f"Machine ID: {machine_id}")
    
    # Load all templates with modifications for this machine
    templates_data = load_machine_templates_with_modifications(machine_id)
    
    if not templates_data["templates"]:
        st.warning(f"No templates found for machine ID {machine_id}.")
        st.info("You need to process a GOA template for this machine first.")
        
        # Add helpful instructions
        st.markdown("""
        ### How to Process a Machine for GOA:
        1. Go to the "Machine Processing" tab
        2. Select the machine you want to process
        3. Click "Process Selected Machine for GOA"
        
        After processing the machine, you can return to this tab to modify the template.
        """)
        return
    
    # Display templates in tabs
    template_names = [t["template_type"] for t in templates_data["templates"]]
    if not template_names:
        st.warning("No template types found in the loaded data.")
        return
        
    template_tabs = st.tabs(template_names)
    
    for i, template in enumerate(templates_data["templates"]):
        with template_tabs[i]:
            template_id = template["id"]
            template_type = template["template_type"]
            
            # Check if template data exists and is valid
            if "template_data" not in template or not template["template_data"]:
                st.error(f"Template data missing or invalid for template ID {template_id}")
                continue
                
            template_data = template["template_data"]
            modifications = template["modifications"]
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Template ID:** {template_id}")
                st.markdown(f"**Type:** {template_type}")
                st.markdown(f"**Last Updated:** {template['processing_date']}")
            with col2:
                if template["generated_file_path"] and os.path.exists(template["generated_file_path"]):
                    with open(template["generated_file_path"], "rb") as fp:
                        st.download_button(
                            "Download Document", 
                            fp, 
                            os.path.basename(template["generated_file_path"]), 
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                            key=f"dl_template_{template_id}"
                        )
                else:
                    st.warning("Document file not found or path not specified")
            
            # Show template summary (hierarchical view of selected items)
            try:
                # Try to get template contexts from session state or elsewhere
                template_contexts = None
                if "template_contexts" in st.session_state:
                    template_contexts = st.session_state.template_contexts
                    
                # Show the hierarchical summary
                st.markdown("### Template Content Summary")
                show_template_summary(template_data, template_contexts)
            except Exception as e:
                st.error(f"Error displaying template summary: {str(e)}")
            
            # Add a function to get hierarchical display for a field
            def get_field_hierarchical_display(field_key):
                """
                Returns a formatted hierarchical display for a field based on template_contexts.
                
                Args:
                    field_key: The field key to get hierarchical display for
                
                Returns:
                    A dictionary with section, subsection, and field information
                """
                result = {
                    "section": "Unknown Section",
                    "subsection": "",
                    "field": field_key,
                    "display": field_key
                }
                
                if "template_contexts" in st.session_state and field_key in st.session_state.template_contexts:
                    context = st.session_state.template_contexts[field_key]
                    context_parts = context.split(' - ')
                    
                    if len(context_parts) >= 1:
                        result["section"] = context_parts[0]
                    if len(context_parts) >= 2:
                        result["subsection"] = context_parts[1]
                    if len(context_parts) >= 3:
                        result["field"] = context_parts[2]
                    elif len(context_parts) == 2:
                        result["field"] = context_parts[1]
                    
                    # Create a formatted display
                    if result["subsection"]:
                        result["display"] = f"{result['section']} → {result['subsection']} → {result['field']}"
                    else:
                        result["display"] = f"{result['section']} → {result['field']}"
                    
                return result
            
            # Display existing modifications
            if modifications:
                st.markdown("### Existing Modifications")
                
                # Create enhanced display data with hierarchical information
                enhanced_mods_data = []
                for mod in modifications:
                    field_key = mod.get("field_key", "")
                    hierarchy_info = get_field_hierarchical_display(field_key)
                    
                    enhanced_mod = {
                        "field_key": field_key,
                        "field_display": hierarchy_info["display"],
                        "section": hierarchy_info["section"],
                        "subsection": hierarchy_info["subsection"],
                        "field": hierarchy_info["field"],
                        "original_value": mod.get("original_value", ""),
                        "modified_value": mod.get("modified_value", ""),
                        "modification_reason": mod.get("modification_reason", ""),
                        "modified_by": mod.get("modified_by", ""),
                        "modification_date": mod.get("modification_date", "")
                    }
                    enhanced_mods_data.append(enhanced_mod)
                
                # Sort modifications by section, subsection and field
                enhanced_mods_data.sort(key=lambda x: (x["section"], x["subsection"], x["field"]))
                
                # Group modifications by section for organized display
                from itertools import groupby
                grouped_mods = {}
                for section, section_mods in groupby(enhanced_mods_data, key=lambda x: x["section"]):
                    if section not in grouped_mods:
                        grouped_mods[section] = list(section_mods)
                    else:
                        grouped_mods[section].extend(list(section_mods))
                
                # Display modifications by section in expandable containers
                for section, section_mods in grouped_mods.items():
                    with st.expander(f"Section: {section} ({len(section_mods)} modifications)", expanded=True):
                        # Convert to dataframe for display
                        df_data = []
                        for mod in section_mods:
                            display_row = {
                                "Section": mod["section"],
                                "Subsection": mod["subsection"],
                                "Field": mod["field"],
                                "Original Value": mod["original_value"],
                                "Modified Value": mod["modified_value"],
                                "Reason": mod["modification_reason"],
                                "Modified By": mod["modified_by"],
                                "Date": mod["modification_date"]
                            }
                            df_data.append(display_row)
                        
                        if df_data:
                            df = pd.DataFrame(df_data)
                            st.dataframe(df, use_container_width=True)
                
                # Also provide a traditional table view option
                with st.expander("Show All Modifications (Table View)", expanded=False):
                    mods_df = pd.DataFrame(modifications)
                    # Format the dataframe for display
                    display_cols = {
                        "field_key": "Field Key",
                        "original_value": "Original Value",
                        "modified_value": "Modified Value",
                        "modification_reason": "Reason",
                        "modified_by": "Modified By",
                        "modification_date": "Date"
                    }
                    mods_df = mods_df[[col for col in display_cols.keys() if col in mods_df.columns]]
                    mods_df.columns = [display_cols[col] for col in mods_df.columns if col in display_cols]
                    st.dataframe(mods_df, use_container_width=True)
            else:
                st.info("No modifications have been made to this template yet.")
            
            # Add new modification
            st.markdown("### Add New Modification")
            with st.form(key=f"add_mod_form_{template_id}"):
                # Get all field keys from template data
                field_keys = list(template_data.keys())
                field_keys.sort()
                
                if not field_keys:
                    st.error("No fields found in template data")
                    st.form_submit_button("Cannot modify (no fields)")
                    continue
                
                # Group fields by section and subsection
                field_hierarchy = {}
                field_display_lookup = {}
                
                for field_key in field_keys:
                    hierarchy_info = get_field_hierarchical_display(field_key)
                    section = hierarchy_info["section"]
                    subsection = hierarchy_info["subsection"]
                    field = hierarchy_info["field"]
                    
                    # Create hierarchical format for display
                    if subsection:
                        display_text = f"{section} - {subsection} - {field}"
                        if section not in field_hierarchy:
                            field_hierarchy[section] = {}
                        if subsection not in field_hierarchy[section]:
                            field_hierarchy[section][subsection] = []
                        field_hierarchy[section][subsection].append(field_key)
                    else:
                        display_text = f"{section} - {field}"
                        if section not in field_hierarchy:
                            field_hierarchy[section] = {}
                        if "General" not in field_hierarchy[section]:
                            field_hierarchy[section]["General"] = []
                        field_hierarchy[section]["General"].append(field_key)
                    
                    # Store the display text for this field key
                    field_display_lookup[field_key] = display_text
                
                # Add section browser
                st.markdown("#### Browse by Section")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Create a section selector
                    section_options = ["All Sections"] + sorted(field_hierarchy.keys())
                    selected_section = st.selectbox(
                        "Section",
                        options=section_options,
                        key=f"section_select_{template_id}"
                    )
                
                with col2:
                    # Create a subsection selector based on selected section
                    if selected_section != "All Sections":
                        subsection_options = ["All Subsections"] + sorted(field_hierarchy[selected_section].keys())
                        selected_subsection = st.selectbox(
                            "Subsection",
                            options=subsection_options,
                            key=f"subsection_select_{template_id}"
                        )
                    else:
                        selected_subsection = "All Subsections"
                        st.selectbox(
                            "Subsection",
                            options=["All Subsections"],
                            key=f"subsection_select_all_{template_id}",
                            disabled=True
                        )
                
                # Filter options based on section/subsection selection
                filtered_options = []
                filtered_keys = []
                
                if selected_section == "All Sections":
                    # Show all fields
                    for section_name in sorted(field_hierarchy.keys()):
                        for subsection_name in sorted(field_hierarchy[section_name].keys()):
                            for field_key in field_hierarchy[section_name][subsection_name]:
                                hierarchy_info = get_field_hierarchical_display(field_key)
                                if subsection_name == "General" or not subsection_name:
                                    display_text = f"{section_name} - {hierarchy_info['field']}"
                                else:
                                    display_text = f"{section_name} - {subsection_name} - {hierarchy_info['field']}"
                                filtered_options.append(display_text)
                                filtered_keys.append(field_key)
                else:
                    if selected_subsection == "All Subsections":
                        # Show all fields in the selected section
                        for subsection_name in sorted(field_hierarchy[selected_section].keys()):
                            for field_key in field_hierarchy[selected_section][subsection_name]:
                                hierarchy_info = get_field_hierarchical_display(field_key)
                                if subsection_name == "General" or not subsection_name:
                                    display_text = f"{selected_section} - {hierarchy_info['field']}"
                                else:
                                    display_text = f"{selected_section} - {subsection_name} - {hierarchy_info['field']}"
                                filtered_options.append(display_text)
                                filtered_keys.append(field_key)
                    else:
                        # Show only fields in the selected subsection
                        for field_key in field_hierarchy[selected_section][selected_subsection]:
                            hierarchy_info = get_field_hierarchical_display(field_key)
                            if selected_subsection == "General" or not selected_subsection:
                                display_text = f"{selected_section} - {hierarchy_info['field']}"
                            else:
                                display_text = f"{selected_section} - {selected_subsection} - {hierarchy_info['field']}"
                            filtered_options.append(display_text)
                            filtered_keys.append(field_key)
                
                # Create mapping between display text and field key
                display_to_key_map = {display: key for display, key in zip(filtered_options, filtered_keys)}
                
                # Create formatted dataframe for field selection
                field_selection_data = []
                for i, (display, key) in enumerate(zip(filtered_options, filtered_keys)):
                    parts = display.split(" - ")
                    section = parts[0] if len(parts) >= 1 else ""
                    subsection = parts[1] if len(parts) >= 3 else ""
                    field = parts[-1]  # Last part is always the field
                    
                    field_selection_data.append({
                        "Section": section,
                        "Subsection": subsection,
                        "Field": field,
                        "Key": key,
                        "Display": display
                    })
                
                # Sort by section, subsection, field
                field_selection_data.sort(key=lambda x: (x["Section"], x["Subsection"], x["Field"]))
                
                # Display a selection table
                st.markdown("#### Select Field to Modify")
                
                # Format selection table
                selection_df = pd.DataFrame(field_selection_data)
                
                # Show the selectable field table
                if not selection_df.empty:
                    selection = st.dataframe(
                        selection_df[["Section", "Subsection", "Field"]],
                        use_container_width=True,
                        hide_index=False,
                        column_config={
                            "Section": st.column_config.TextColumn("Section"),
                            "Subsection": st.column_config.TextColumn("Subsection"),
                            "Field": st.column_config.TextColumn("Field")
                        }
                    )
                    
                    # Get user selection
                    selection_index = st.number_input(
                        "Select a row number from the table above", 
                        min_value=0, 
                        max_value=len(field_selection_data)-1 if field_selection_data else 0,
                        value=0,
                        key=f"field_selection_index_{template_id}"
                    )
                    
                    # Get the selected field key
                    if field_selection_data:
                        selected_field = field_selection_data[selection_index]["Key"]
                    else:
                        st.error("No fields available to select")
                        selected_field = None
                else:
                    st.warning("No fields match the current filter criteria")
                    # Provide a fallback selection method
                    st.markdown("#### Alternative Selection Method")
                    selected_field = st.selectbox(
                        "Select a field directly",
                        options=field_keys,
                        key=f"field_select_fallback_{template_id}"
                    )
                
                # Only show field details and value editing if a field is selected
                if not selected_field:
                    st.error("No field selected. Please select a field to modify.")
                    # Add a dummy form submission button that does nothing
                    st.form_submit_button("Cannot modify (no field selected)", disabled=True)
                    # Skip the rest of the form
                    continue
                
                # Display hierarchical context for the selected field
                if "template_contexts" in st.session_state and selected_field in st.session_state.template_contexts:
                    context = st.session_state.template_contexts[selected_field]
                    
                    # Split the context into hierarchy parts
                    context_parts = context.split(' - ')
                    
                    # Extract hierarchical components
                    section = context_parts[0] if len(context_parts) >= 1 else "Unknown"
                    subsection = context_parts[1] if len(context_parts) >= 2 else ""
                    field = context_parts[2] if len(context_parts) >= 3 else (context_parts[1] if len(context_parts) >= 2 else selected_field)
                    
                    # Create field info table
                    field_info = [
                        {"Component": "Section", "Value": section},
                        {"Component": "Subsection", "Value": subsection},
                        {"Component": "Field", "Value": field},
                        {"Component": "Type", "Value": "Checkbox" if selected_field.endswith("_check") else "Text Field"},
                        {"Component": "Field Key", "Value": selected_field}
                    ]
                    
                    # Display as a clean table
                    st.markdown("#### Field Information")
                    field_info_df = pd.DataFrame(field_info)
                    st.dataframe(field_info_df, use_container_width=True, hide_index=True)
                    
                    # Add helpful explanation based on field type
                    if selected_field.endswith("_check"):
                        st.caption(f"This is a checkbox field. 'YES' means this option is selected/included.")
                
                # Show current value
                st.markdown("#### Current and New Values")
                current_value = template_data.get(selected_field, "")
                st.text_input("Current Value", value=current_value, disabled=True, key=f"current_val_{template_id}")
                
                # Input for new value
                is_checkbox = selected_field.endswith("_check")
                
                if is_checkbox:
                    # For checkbox fields (ending with _check), provide YES/NO radio buttons
                    st.markdown("**New Value:**")
                    new_value = st.radio(
                        "Select YES or NO",
                        options=["YES", "NO"],
                        index=0 if current_value.upper() == "YES" else 1,
                        key=f"new_val_radio_{template_id}",
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    
                    # Add hint about the checkbox meaning based on context
                    if "template_contexts" in st.session_state and selected_field in st.session_state.template_contexts:
                        context = st.session_state.template_contexts[selected_field]
                        field_parts = context.split(" - ")
                        field_desc = field_parts[-1] if len(field_parts) > 0 else selected_field
                        st.caption(f"'YES' means '{field_desc}' is selected/included in the template.")
                
                elif selected_field.lower().endswith(("_qty", "_count", "_amount", "_number", "_vol", "_capacity")):
                    # For quantity fields, provide a numeric input
                    try:
                        # Try to convert current value to a number
                        current_numeric = float(current_value) if current_value else 0
                        is_integer = current_numeric.is_integer()
                        
                        if is_integer:
                            new_value = str(st.number_input(
                                "New Value",
                                value=int(current_numeric),
                                step=1,
                                key=f"new_val_int_{template_id}"
                            ))
                        else:
                            new_value = str(st.number_input(
                                "New Value",
                                value=current_numeric,
                                step=0.1,
                                format="%.2f",
                                key=f"new_val_float_{template_id}"
                            ))
                    except ValueError:
                        # Fall back to text input if conversion fails
                        new_value = st.text_input(
                            "New Value", 
                            value=current_value,
                            key=f"new_val_text_{template_id}",
                            placeholder="Enter a numeric value"
                        )
                
                elif any(dimension in selected_field.lower() for dimension in ["_width", "_height", "_length", "_size", "_diameter"]):
                    # For dimension fields, provide numeric input with units hint
                    new_value = st.text_input(
                        "New Value", 
                        value=current_value,
                        key=f"new_val_text_{template_id}",
                        placeholder="Enter value with units (e.g., 10mm, 1.5in)"
                    )
                    
                    # Add hint about expected format
                    st.caption("Include units if applicable (mm, cm, in, etc.)")
                
                else:
                    # For text fields, provide a text input with context-based placeholder
                    placeholder_text = "Enter new value"
                    
                    # Generate placeholder based on field context
                    if "template_contexts" in st.session_state and selected_field in st.session_state.template_contexts:
                        context = st.session_state.template_contexts[selected_field]
                        if "model" in selected_field.lower() or "model" in context.lower():
                            placeholder_text = "Enter model number or name"
                        elif "voltage" in selected_field.lower() or "voltage" in context.lower():
                            placeholder_text = "Enter voltage (e.g., 110V, 220-240V)"
                        elif "date" in selected_field.lower() or "date" in context.lower():
                            placeholder_text = "Enter date (YYYY-MM-DD)"
                        elif "country" in selected_field.lower() or "country" in context.lower():
                            placeholder_text = "Enter country name"
                    
                    new_value = st.text_input(
                        "New Value", 
                        value=current_value,
                        key=f"new_val_text_{template_id}",
                        placeholder=placeholder_text
                    )
                
                # Input for reason and modified by
                st.markdown("#### Modification Details")
                reason = st.text_input("Reason for Change", key=f"reason_{template_id}", 
                                       placeholder="e.g., Kickoff meeting, Client request")
                modified_by = st.text_input("Modified By", key=f"modified_by_{template_id}", 
                                           placeholder="Your name")
                
                submitted = st.form_submit_button("Save Modification")
                if submitted:
                    if new_value != current_value:
                        with st.spinner("Saving modification..."):
                            if save_goa_modification(
                                template_id, 
                                selected_field, 
                                current_value, 
                                new_value,
                                reason,
                                modified_by
                            ):
                                st.success(f"Modification saved for field '{selected_field}'.")
                                # Reload page to show the new modification
                                st.rerun()
                            else:
                                st.error("Failed to save modification. Check the database connection.")
                    else:
                        st.warning("No changes detected. New value must be different from current value.")
            
            # Regenerate document with modifications
            st.markdown("### Regenerate Document with Modifications")
            if st.button("Regenerate Document", key=f"regenerate_btn_{template_id}"):
                # Ensure all modifications are applied to template data
                with st.spinner("Updating template with modifications..."):
                    if update_template_after_modifications(template_id):
                        # Get updated template data
                        templates_data = load_machine_templates_with_modifications(machine_id)
                        updated_template = next((t for t in templates_data["templates"] if t["id"] == template_id), None)
                        
                        if updated_template:
                            # Find a template file to use
                            template_file_path = "templates/template.docx"  # Default
                            
                            # Try to find a specific template file based on template_type
                            if template_type.lower() == "goa":
                                template_file_path = "templates/template.docx"  # Specific GOA template
                            elif template_type.lower() == "packing slip":
                                template_file_path = "templates/Packing Slip.docx"
                            elif template_type.lower() == "commercial invoice":
                                template_file_path = "templates/Commercial Invoice.docx"
                            elif template_type.lower() == "certificate of origin":
                                template_file_path = "templates/CERTIFICATION OF ORIGIN_NAFTA.docx"
                            
                            if not os.path.exists(template_file_path):
                                st.error(f"Template file not found: {template_file_path}")
                            else:
                                # Generate new file name
                                file_name = f"output_modified_{template_type.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                                
                                # Fill document with updated data
                                try:
                                    with st.spinner(f"Generating modified document: {file_name}"):
                                        fill_word_document_from_llm_data(
                                            template_file_path, 
                                            updated_template["template_data"], 
                                            file_name
                                        )
                                        
                                        if os.path.exists(file_name):
                                            # Update path in database
                                            from src.utils.crm_utils import save_machine_template_data
                                            save_machine_template_data(
                                                machine_id, 
                                                template_type, 
                                                updated_template["template_data"],
                                                file_name
                                            )
                                            
                                            st.success(f"Document regenerated successfully: {file_name}")
                                            with open(file_name, "rb") as fp:
                                                st.download_button(
                                                    "Download Regenerated Document", 
                                                    fp, 
                                                    file_name, 
                                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                                                    key=f"dl_regen_{template_id}"
                                                )
                                        else:
                                            st.error(f"Failed to generate document at path: {file_name}")
                                except Exception as e:
                                    st.error(f"Error regenerating document: {str(e)}")
                                    import traceback
                                    st.code(traceback.format_exc())
                        else:
                            st.error("Failed to get updated template data.")
                    else:
                        st.error("Failed to update template with modifications.")

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
                        success = process_machine_specific_data(selected_machine, TEMPLATE_FILE)
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
                    # Show template modifications for this client
                    show_client_template_modifications(client_to_display_and_edit.get('id'))
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

def show_client_template_modifications(client_id):
    """
    Shows template modifications for all machines belonging to a client.
    This provides a consolidated view of all GOA changes across machines.
    
    Args:
        client_id: ID of the client
    """
    from src.utils.crm_utils import (
        get_client_by_id, load_machines_for_quote, 
        load_machine_templates_with_modifications
    )
    from src.utils.template_utils import extract_placeholder_context_hierarchical
    import pandas as pd
    
    st.subheader("🔄 Client Template Modifications History")
    
    # Get client information
    client = get_client_by_id(client_id)
    if not client:
        st.error(f"Client with ID {client_id} not found.")
        return
        
    st.markdown(f"**Client:** {client.get('customer_name', 'Unknown')}")
    st.markdown(f"**Quote Reference:** {client.get('quote_ref', 'Unknown')}")
    
    # Load all machines for this client
    machines = load_machines_for_quote(client.get('quote_ref', ''))
    if not machines:
        st.warning(f"No machines found for client {client.get('customer_name', 'Unknown')}.")
        return
        
    st.markdown(f"Found {len(machines)} machines for this client.")
    
    # Function to get hierarchical display for a field
    def get_field_hierarchical_display(field_key, template_contexts=None):
        """
        Returns a formatted hierarchical display for a field based on template_contexts.
        
        Args:
            field_key: The field key to get hierarchical display for
            template_contexts: Optional dictionary of field keys to their context
            
        Returns:
            A dictionary with section, subsection, and field information
        """
        result = {
            "section": "Unknown Section",
            "subsection": "",
            "field": field_key,
            "display": field_key
        }
        
        # Try session state first
        if "template_contexts" in st.session_state and field_key in st.session_state.template_contexts:
            context = st.session_state.template_contexts[field_key]
            context_parts = context.split(' - ')
            
            if len(context_parts) >= 1:
                result["section"] = context_parts[0]
            if len(context_parts) >= 2:
                result["subsection"] = context_parts[1]
            if len(context_parts) >= 3:
                result["field"] = context_parts[2]
            elif len(context_parts) == 2:
                result["field"] = context_parts[1]
            
            # Create a formatted display
            if result["subsection"]:
                result["display"] = f"{result['section']} → {result['subsection']} → {result['field']}"
            else:
                result["display"] = f"{result['section']} → {result['field']}"
        
        # Try provided contexts if available and field not found in session state
        elif template_contexts and field_key in template_contexts:
            context = template_contexts[field_key]
            context_parts = context.split(' - ')
            
            if len(context_parts) >= 1:
                result["section"] = context_parts[0]
            if len(context_parts) >= 2:
                result["subsection"] = context_parts[1]
            if len(context_parts) >= 3:
                result["field"] = context_parts[2]
            elif len(context_parts) == 2:
                result["field"] = context_parts[1]
            
            # Create a formatted display
            if result["subsection"]:
                result["display"] = f"{result['section']} → {result['subsection']} → {result['field']}"
            else:
                result["display"] = f"{result['section']} → {result['field']}"
        
        return result
    
    # Create tabs for each machine
    machine_tabs = st.tabs([m.get('machine_name', f"Machine {i+1}") for i, m in enumerate(machines)])
    
    # For each machine, show its template modifications
    for i, machine in enumerate(machines):
        with machine_tabs[i]:
            machine_id = machine.get('id')
            st.markdown(f"**Machine ID:** {machine_id}")
            st.markdown(f"**Name:** {machine.get('machine_name', 'Unknown')}")
            
            # Get templates and modifications for this machine
            templates_data = load_machine_templates_with_modifications(machine_id)
            templates = templates_data.get('templates', [])
            
            if not templates:
                st.info(f"No templates found for machine {machine.get('machine_name', 'Unknown')}.")
                continue
                
            # Create sub-tabs for each template type
            template_types = [t.get('template_type', 'Unknown') for t in templates]
            template_subtabs = st.tabs(template_types)
            
            for j, template in enumerate(templates):
                with template_subtabs[j]:
                    template_id = template.get('id')
                    template_type = template.get('template_type', 'Unknown')
                    
                    st.markdown(f"**Template ID:** {template_id}")
                    st.markdown(f"**Last Updated:** {template.get('processing_date', 'Unknown')}")
                    
                    # Show document download if available
                    if template.get('generated_file_path') and os.path.exists(template.get('generated_file_path')):
                        with open(template.get('generated_file_path'), "rb") as fp:
                            st.download_button(
                                "Download Document", 
                                fp, 
                                os.path.basename(template.get('generated_file_path')), 
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                                key=f"dl_client_template_{template_id}"
                            )
                    
                    # Show template summary
                    if 'template_data' in template and template['template_data']:
                        # Get template contexts from session state if available
                        template_contexts = None
                        if "template_contexts" in st.session_state:
                            template_contexts = st.session_state.template_contexts
                        elif os.path.exists("templates/template.docx"):
                            # Try to extract contexts if not in session state
                            template_contexts = extract_placeholder_context_hierarchical("templates/template.docx")
                            
                        # Show hierarchical summary
                        st.markdown("### Template Content Summary")
                        show_template_summary(template['template_data'], template_contexts)
                    
                    # Show modifications
                    modifications = template.get('modifications', [])
                    if modifications:
                        st.markdown("### Modifications History")
                        
                        # Create enhanced display data with hierarchical information
                        enhanced_mods_data = []
                        for mod in modifications:
                            field_key = mod.get("field_key", "")
                            hierarchy_info = get_field_hierarchical_display(field_key, template_contexts)
                            
                            enhanced_mod = {
                                "field_key": field_key,
                                "field_display": hierarchy_info["display"],
                                "section": hierarchy_info["section"],
                                "subsection": hierarchy_info["subsection"],
                                "field": hierarchy_info["field"],
                                "original_value": mod.get("original_value", ""),
                                "modified_value": mod.get("modified_value", ""),
                                "modification_reason": mod.get("modification_reason", ""),
                                "modified_by": mod.get("modified_by", ""),
                                "modification_date": mod.get("modification_date", "")
                            }
                            enhanced_mods_data.append(enhanced_mod)
                        
                        # Sort modifications by section, subsection and field
                        enhanced_mods_data.sort(key=lambda x: (x["section"], x["subsection"], x["field"]))
                        
                        # Group modifications by section for organized display
                        from itertools import groupby
                        grouped_mods = {}
                        for section, section_items in groupby(enhanced_mods_data, key=lambda x: x["section"]):
                            section_items_list = list(section_items)
                            if section not in grouped_mods:
                                grouped_mods[section] = section_items_list
                            else:
                                grouped_mods[section].extend(section_items_list)
                        
                        # Display modifications by section in expandable containers
                        for section, section_mods in grouped_mods.items():
                            with st.expander(f"Section: {section} ({len(section_mods)} modifications)", expanded=True):
                                # Convert to dataframe for display
                                df_data = []
                                for mod in section_mods:
                                    display_row = {
                                        "Section": mod["section"],
                                        "Subsection": mod["subsection"],
                                        "Field": mod["field"],
                                        "Original Value": mod["original_value"],
                                        "Modified Value": mod["modified_value"],
                                        "Reason": mod["modification_reason"],
                                        "Modified By": mod["modified_by"],
                                        "Date": mod["modification_date"]
                                    }
                                    df_data.append(display_row)
                                
                                if df_data:
                                    df = pd.DataFrame(df_data)
                                    st.dataframe(df, use_container_width=True)
                        
                        # Also provide a traditional table view option
                        with st.expander("Show All Modifications (Table View)", expanded=False):
                            mods_df = pd.DataFrame(modifications)
                            # Format the dataframe for display
                            display_cols = {
                                "field_key": "Field Key",
                                "original_value": "Original Value",
                                "modified_value": "Modified Value",
                                "modification_reason": "Reason",
                                "modified_by": "Modified By",
                                "modification_date": "Date"
                            }
                            mods_df = mods_df[[col for col in display_cols.keys() if col in mods_df.columns]]
                            mods_df.columns = [display_cols[col] for col in mods_df.columns if col in display_cols]
                            st.dataframe(mods_df, use_container_width=True)
                    else:
                        st.info("No modifications have been made to this template yet.")
                        
    # Add a consolidated view of all modifications across machines
    st.markdown("### Consolidated Modifications View")
    st.markdown("#### All Template Modifications")
    
    # Collect all modifications from all machines and templates
    all_mods = []
    for machine in machines:
        machine_id = machine.get('id')
        machine_name = machine.get('machine_name', 'Unknown')
        
        templates_data = load_machine_templates_with_modifications(machine_id)
        for template in templates_data.get('templates', []):
            template_id = template.get('id')
            template_type = template.get('template_type', 'Unknown')
            
            for mod in template.get('modifications', []):
                field_key = mod.get("field_key", "")
                hierarchy_info = get_field_hierarchical_display(field_key)
                
                enhanced_mod = {
                    "machine_name": machine_name,
                    "template_type": template_type,
                    "field_key": field_key,
                    "field_display": hierarchy_info["display"],
                    "section": hierarchy_info["section"],
                    "subsection": hierarchy_info["subsection"],
                    "field": hierarchy_info["field"],
                    "original_value": mod.get("original_value", ""),
                    "modified_value": mod.get("modified_value", ""),
                    "modification_reason": mod.get("modification_reason", ""),
                    "modified_by": mod.get("modified_by", ""),
                    "modification_date": mod.get("modification_date", "")
                }
                all_mods.append(enhanced_mod)
    
    if all_mods:
        # Sort by section and date
        all_mods.sort(key=lambda x: (x["section"], x.get("modification_date", "")), reverse=True)
        
        # Group by section for display
        from itertools import groupby
        grouped_mods = {}
        for section, section_items in groupby(all_mods, key=lambda x: x["section"]):
            section_items_list = list(section_items)
            if section not in grouped_mods:
                grouped_mods[section] = section_items_list
            else:
                grouped_mods[section].extend(section_items_list)
        
        # Display modifications by section
        for section, section_mods in grouped_mods.items():
            with st.expander(f"Section: {section} ({len(section_mods)} modifications)", expanded=True):
                # Convert to dataframe for display
                df_data = []
                for mod in section_mods:
                    display_row = {
                        "Machine": mod["machine_name"],
                        "Template": mod["template_type"],
                        "Section": mod["section"],
                        "Subsection": mod["subsection"],
                        "Field": mod["field"],
                        "Original": mod["original_value"],
                        "Modified": mod["modified_value"],
                        "Reason": mod["modification_reason"],
                        "By": mod["modified_by"],
                        "Date": mod["modification_date"]
                    }
                    df_data.append(display_row)
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
        
        # Also provide a summary of modifications
        st.markdown("### Modification Summary")
        
        # Group by field
        field_mods = {}
        for mod in all_mods:
            field_key = mod["field_key"]
            if field_key not in field_mods:
                field_mods[field_key] = []
            field_mods[field_key].append(mod)
        
        # Display summary of most frequently modified fields
        field_counts = {field: len(mods) for field, mods in field_mods.items()}
        sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)
        
        top_modified_fields = []
        for field_key, count in sorted_fields[:10]:  # Top 10 most modified fields
            hierarchy_info = get_field_hierarchical_display(field_key)
            top_modified_fields.append({
                "Section": hierarchy_info["section"],
                "Subsection": hierarchy_info["subsection"],
                "Field": hierarchy_info["field"],
                "Modification Count": count,
                "Last Modified": max([mod.get("modification_date", "") for mod in field_mods[field_key]])
            })
        
        if top_modified_fields:
            st.markdown("#### Top Modified Fields")
            top_fields_df = pd.DataFrame(top_modified_fields)
            st.dataframe(top_fields_df, use_container_width=True)
    else:
        st.info("No modifications found across any machines for this client.") 