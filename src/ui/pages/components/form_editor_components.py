"""
GOA Field Editing and Modification Utilities

This module provides comprehensive GOA (General Offer Arrangement) form editing
and modification capabilities for the QuoteFlow Document Assistant.

Key Components:
--------------
1. **show_goa_modifications_ui()**: Entry point for viewing/editing GOA template
   modifications for a specific machine. Provides tabbed interface for multiple
   templates.

2. **display_template_editor()**: Complex editor (826 lines) that handles:
   - HTML template parsing with BeautifulSoup
   - Field ordering based on Excel schema or SortStar mappings
   - Section and subsection management
   - Boolean and text field editing
   - Options listing auto-regeneration for SortStar machines
   - Bulk modification tracking and saves
   - Field validation and suspicious field detection
   - Few-shot learning feedback loop integration
   - Live HTML preview with edits applied

Architecture:
------------
- Dual template system: Standard (HTML from Excel) vs SortStar (Word)
- Section ordering preserved from GOA form HTML structure
- Subsection grouping extracted from div.group elements
- Field ranking based on HTML template order or Excel order
- Modification tracking with original/new value comparison

Related Files:
-------------
- src/utils/form_generator.py: Excel → HTML conversion
- src/utils/html_doc_filler.py: HTML template filling
- src/utils/template_utils.py: Field mappings (DEFAULT/SORTSTAR)
- src/ui/template_preview_editor.py: Preview and suspicious field detection
- src/utils/db.py: Database operations for modifications
- src/utils/few_shot_learning.py: Learning from user corrections
"""

import streamlit as st
import os
import json
import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

# Import utilities
from src.utils.form_generator import get_all_fields_from_excel, OUTPUT_HTML_PATH
from src.utils.html_doc_filler import fill_html_template, fill_and_generate_html
from src.ui.template_preview_editor import render_field_editor, get_suspicious_fields_summary
from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS, SORTSTAR_EXPLICIT_MAPPINGS
from src.utils.few_shot_learning import (
    save_successful_extraction_as_example,
    determine_machine_type
)

# Import database operations
from src.utils.db import (
    load_machine_templates_with_modifications,
    save_goa_modification,
    save_bulk_goa_modifications,
    save_machine_template_data,
    load_machines_for_quote,
    load_document_content
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
        # Imports for explicit_placeholder_mappings are already at the top of the file

        is_sortstar_machine = False
        if machine_name:
            sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
            if re.search(sortstar_pattern, machine_name.lower()):
                is_sortstar_machine = True
                st.info(f"SortStar machine template editor active for: {machine_name}")

        current_explicit_mappings = SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar_machine else get_all_fields_from_excel()

        # Create rank maps to preserve source order (Excel or SortStar mappings)
        field_rank = {key: i for i, key in enumerate(current_explicit_mappings.keys())}
        section_rank = {}
        subsection_rank = {}

        sec_idx = 0
        sub_idx = 0
        for key, path in current_explicit_mappings.items():
            # Parse path to get section/subsection
            if is_sortstar_machine:
                parts = [p.strip() for p in path.split(" > ")]
            else:
                parts = [p.strip() for p in path.split(" - ")]

            if parts:
                sec = parts[0]
                if sec not in section_rank:
                    section_rank[sec] = sec_idx
                    sec_idx += 1

                if len(parts) > 2:
                    sub = parts[1]
                    # Compound key for subsection to avoid collision between sections
                    sub_key = (sec, sub)
                    if sub_key not in subsection_rank:
                        subsection_rank[sub_key] = sub_idx
                        sub_idx += 1

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
            file_path = template["generated_file_path"]
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if file_path.endswith('.html'):
                mime_type = "text/html"
            elif file_path.endswith('.pdf'):
                mime_type = "application/pdf"

            with open(file_path, "rb") as fp:
                st.download_button(
                    "Download Document",
                    fp,
                    os.path.basename(file_path),
                    mime_type,
                    key=f"dl_template_{template_id}"
                )

        # Create sections for editing vs adding fields
        edit_tab, add_tab = st.tabs(["Edit Existing Fields", "Add New Fields"])

        # List to hold info about every field displayed in the editor
        all_displayed_fields = []

        # Tab for editing existing fields
        with edit_tab:
            st.markdown("#### Edit Existing Template Fields")

            # Build section-based editor with friendly labels
            section_fields: Dict[str, List[Dict[str, Any]]] = {}
            for k, v in template_data.items():
                mapping = current_explicit_mappings.get(k, k)
                section_name = "Uncategorized"
                friendly_label = k
                if mapping and (" > " in mapping or " - " in mapping):
                    parts = [p.strip() for p in mapping.replace(">", "-").split("-") if p.strip()]
                    if parts:
                        section_name = parts[0]
                        friendly_label = parts[-1]
                is_boolean = (str(v).upper() in ["YES", "NO", "TRUE", "FALSE"] or k.endswith("_check"))
                section_fields.setdefault(section_name, []).append(
                    {"key": k, "label": friendly_label, "value": v, "is_boolean": is_boolean}
                )

            # Order sections AND fields within sections to match GOA form (HTML) order
            # Also extract subsection groupings from div.group > div.group-title
            section_order = []
            # Maps section_name -> list of field keys in HTML order
            section_field_order: Dict[str, List[str]] = {}
            # Maps field_key -> subsection_name (or None if no subsection)
            field_to_subsection: Dict[str, Optional[str]] = {}
            # Maps section_name -> list of (subsection_name, list_of_field_keys) in HTML order
            section_subsection_order: Dict[str, List[tuple]] = {}
            try:
                if os.path.exists(OUTPUT_HTML_PATH):
                    with open(OUTPUT_HTML_PATH, "r", encoding="utf-8") as f:
                        soup = BeautifulSoup(f.read(), "html.parser")
                    # Iterate through all sections to get section order, subsection order, and field order
                    for section_elem in soup.select("section.section"):
                        hdr = section_elem.select_one("div.section-header > h2")
                        if hdr:
                            section_name = hdr.get_text(strip=True)
                            if section_name and section_name not in section_order:
                                section_order.append(section_name)
                                field_keys_in_section = []
                                subsection_list = []  # List of (subsection_name, [field_keys])

                                # Extract groups (subsections) within this section
                                for group_elem in section_elem.select("div.group"):
                                    group_title_elem = group_elem.select_one("div.group-title")
                                    subsection_name = group_title_elem.get_text(strip=True) if group_title_elem else None

                                    # Get fields within this group
                                    group_field_keys = []
                                    for field_elem in group_elem.select("label.field"):
                                        input_elem = field_elem.select_one("input[name], textarea[name]")
                                        if input_elem and input_elem.get("name"):
                                            field_key = input_elem.get("name")
                                            field_keys_in_section.append(field_key)
                                            group_field_keys.append(field_key)
                                            field_to_subsection[field_key] = subsection_name

                                    if group_field_keys:
                                        subsection_list.append((subsection_name, group_field_keys))

                                section_field_order[section_name] = field_keys_in_section
                                section_subsection_order[section_name] = subsection_list
            except Exception as e:
                print(f"Warning: could not parse section/field order from goa_form.html: {e}")

            def section_rank_func(name: str) -> int:
                return section_order.index(name) if name in section_order else len(section_order) + sorted(section_fields.keys()).index(name)

            def field_rank_func(field_info: Dict[str, Any], section_name: str) -> int:
                """Return field position based on HTML template order, falling back to alphabetical."""
                field_key = field_info["key"]
                if section_name in section_field_order:
                    field_order_list = section_field_order[section_name]
                    if field_key in field_order_list:
                        return field_order_list.index(field_key)
                # Fallback: fields not in HTML order go at end, sorted alphabetically
                return 10000 + ord(field_info["label"][0].lower()) if field_info["label"] else 10000

            section_options = sorted(section_fields.keys(), key=section_rank_func)
            selected_section = st.selectbox(
                "Select section to edit",
                section_options,
                key=f"section_select_{template_id}"
            )

            edited_data = dict(template_data)
            if selected_section:
                st.markdown(f"##### Fields in {selected_section}")

                # Build a lookup from field_key to field_info for this section
                section_field_lookup = {f["key"]: f for f in section_fields[selected_section]}

                # Get the subsection order for this section (if available)
                subsection_groups = section_subsection_order.get(selected_section, [])

                # Track which fields we have rendered to avoid duplicates
                rendered_fields = set()

                if subsection_groups:
                    # Render fields grouped by subsection with headers
                    for subsection_name, group_field_keys in subsection_groups:
                        # Display subsection header if it exists
                        if subsection_name:
                            st.markdown(f"###### {subsection_name}")

                        # Render fields in this subsection (in HTML order)
                        for field_key in group_field_keys:
                            if field_key in section_field_lookup and field_key not in rendered_fields:
                                field_info = section_field_lookup[field_key]
                                field_label = field_info["label"]
                                current_value = field_info["value"]
                                is_boolean = field_info["is_boolean"]
                                widget_key = f"edit_{template_id}_{field_key}"

                                if is_boolean:
                                    checked = str(current_value).upper() in ["YES", "TRUE"]
                                    new_val = st.checkbox(field_label, value=checked, key=widget_key)
                                    edited_data[field_key] = "YES" if new_val else "NO"
                                else:
                                    height = 150 if field_key == "options_listing" else 60
                                    new_val = st.text_area(
                                        field_label,
                                        value=current_value if current_value is not None else "",
                                        height=height,
                                        key=widget_key
                                    )
                                    edited_data[field_key] = new_val

                                rendered_fields.add(field_key)

                    # Render any remaining fields not in the HTML structure (fallback)
                    remaining_fields = [f for f in section_fields[selected_section] if f["key"] not in rendered_fields]
                    if remaining_fields:
                        st.markdown("###### Other Fields")
                        for field_info in sorted(remaining_fields, key=lambda x: field_rank_func(x, selected_section)):
                            field_key = field_info["key"]
                            field_label = field_info["label"]
                            current_value = field_info["value"]
                            is_boolean = field_info["is_boolean"]
                            widget_key = f"edit_{template_id}_{field_key}"

                            if is_boolean:
                                checked = str(current_value).upper() in ["YES", "TRUE"]
                                new_val = st.checkbox(field_label, value=checked, key=widget_key)
                                edited_data[field_key] = "YES" if new_val else "NO"
                            else:
                                height = 150 if field_key == "options_listing" else 60
                                new_val = st.text_area(
                                    field_label,
                                    value=current_value if current_value is not None else "",
                                    height=height,
                                    key=widget_key
                                )
                                edited_data[field_key] = new_val
                else:
                    # Fallback: no subsection info, render all fields in order
                    for field_info in sorted(section_fields[selected_section], key=lambda x: field_rank_func(x, selected_section)):
                        field_key = field_info["key"]
                        field_label = field_info["label"]
                        current_value = field_info["value"]
                        is_boolean = field_info["is_boolean"]
                        widget_key = f"edit_{template_id}_{field_key}"
                        if is_boolean:
                            checked = str(current_value).upper() in ["YES", "TRUE"]
                            new_val = st.checkbox(field_label, value=checked, key=widget_key)
                            edited_data[field_key] = "YES" if new_val else "NO"
                        else:
                            height = 150 if field_key == "options_listing" else 60
                            new_val = st.text_area(
                                field_label,
                                value=current_value if current_value is not None else "",
                                height=height,
                                key=widget_key
                            )
                            edited_data[field_key] = new_val

            # Live preview with edits applied using base GOA form (no highlights)
            try:
                base_template_path = OUTPUT_HTML_PATH
                if os.path.exists(base_template_path):
                    with open(base_template_path, "r", encoding="utf-8") as f:
                        raw_html = f.read()
                    plain_html = fill_html_template(raw_html, edited_data)
                    st.markdown("Preview (base GOA form, no highlights):")
                    st.components.v1.html(plain_html, height=900, scrolling=True)
                else:
                    st.info(f"Base GOA form not found at {base_template_path}.")
            except Exception as e:
                st.warning(f"Could not render HTML preview: {e}")

            if st.button("Save template changes", type="primary", key=f"save_template_{template_id}"):
                try:
                    save_machine_template_data(
                        machine_id,
                        template_type,
                        edited_data,
                        template.get("generated_file_path", "")
                    )
                    gen_path = template.get("generated_file_path", "")
                    if gen_path and gen_path.lower().endswith(".html") and os.path.exists(OUTPUT_HTML_PATH):
                        fill_and_generate_html(str(OUTPUT_HTML_PATH), edited_data, gen_path)
                    st.success("Template updated and saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save template: {e}")
            return

            # Optional field editor (legacy UI); hide by default
            show_field_editor = st.toggle("Show field editor (sections)", value=False)
            if not show_field_editor:
                return

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

            # Sort sections using section_rank to preserve Excel/Source order
            # Fallback to high number (9999) for unknown sections (like Option Listing) to put them at the end
            sorted_sections_list = sorted(structured_fields.items(), key=lambda item: section_rank.get(item[0], 9999))

            for section_name, subsections_dict in sorted_sections_list:
                # Determine if the expander should be open by default
                expanded_default = False
                if is_sortstar_machine and section_name in ["BASIC SYSTEMS", "GENERAL ORDER ACKNOWLEDGEMENT"]:
                    expanded_default = True
                # Also expand Option Listing section by default for both machine types
                if section_name == "Option Listing" or (is_sortstar_machine and section_name == "Option Listing"):
                    expanded_default = True

                with st.expander(f"**{section_name}**", expanded=expanded_default):
                    # Separate direct fields from subsections
                    direct_fields = []
                    if "_fields_" in subsections_dict:
                        direct_fields = subsections_dict["_fields_"]

                    other_subsections = [(k, v) for k, v in subsections_dict.items() if k != "_fields_"]

                    # Sort subsections using subsection_rank
                    sorted_subsections_list = sorted(other_subsections, key=lambda item: subsection_rank.get((section_name, item[0]), 9999))

                    # Combine: direct fields first (usually), then sorted subsections
                    # We wrap direct_fields in a tuple to match the list structure
                    final_subsections_list = []
                    if direct_fields:
                         final_subsections_list.append(("_fields_", direct_fields))
                    final_subsections_list.extend(sorted_subsections_list)

                    for subsection_name, fields_list in final_subsections_list:
                        if subsection_name != "_fields_":
                            st.markdown(f"##### {subsection_name}")

                        # Sort fields using field_rank
                        # Give options_listing highest priority (-1)
                        def get_field_priority(field_info):
                            if field_info["key"] == "options_listing":
                                return -1
                            return field_rank.get(field_info["key"], 9999)

                        sorted_fields_list = sorted(fields_list, key=get_field_priority)

                        for field_info in sorted_fields_list:
                            all_displayed_fields.append((field_info, "structured"))
                            field_key = field_info["key"]
                            field_display = field_info["label"]
                            current_value = field_info["value"]
                            is_boolean = field_info["is_boolean"]

                            col1, col2 = st.columns([3, 5.5])
                            with col1:
                                st.markdown(f"{field_display}")
                            with col2:
                                if is_boolean:
                                    cv_str = str(current_value) if current_value is not None else "NO"
                                    is_checked = cv_str.upper() in ["YES", "TRUE"]
                                    st.checkbox(
                                        f"Enable {field_key}",
                                        value=is_checked,
                                        key=f"edit_structured_bool_{field_key}_{template_id}",
                                        label_visibility="collapsed"
                                    )
                                else:
                                    current_value_str = "" if current_value is None else str(current_value)
                                    if field_key == "options_listing":
                                        st.text_area(
                                            f"Value for {field_key}",
                                            value=current_value_str,
                                            key=f"edit_structured_text_{field_key}_{template_id}",
                                            label_visibility="collapsed",
                                            height=150 # Provide more space for options_listing
                                        )
                                    else:
                                        st.text_input(
                                            f"Value for {field_key}",
                                            value=current_value_str,
                                            key=f"edit_structured_text_{field_key}_{template_id}",
                                            label_visibility="collapsed"
                                        )

            if other_fields:
                # Sort other_fields by label as well
                sorted_other_fields = sorted(other_fields, key=lambda x: x["label"])
                with st.expander("**Other Fields (Not in Standard Outline)**", expanded=False):
                    for field_info in sorted_other_fields:
                        all_displayed_fields.append((field_info, "other"))
                        field_key = field_info["key"]
                        field_display = field_info["label"]
                        current_value = field_info["value"]
                        is_boolean = field_info["is_boolean"]

                        col1, col2 = st.columns([3, 5.5])
                        with col1:
                            st.markdown(f"{field_display}")
                        with col2:
                            if is_boolean:
                                cv_str = str(current_value) if current_value is not None else "NO"
                                is_checked = cv_str.upper() in ["YES", "TRUE"]
                                st.checkbox(
                                    f"Enable {field_key}",
                                    value=is_checked,
                                    key=f"edit_other_bool_{field_key}_{template_id}",
                                    label_visibility="collapsed"
                                )
                            else:
                                current_value_str = "" if current_value is None else str(current_value)
                                if field_key == "options_listing":
                                    st.text_area(
                                        f"Value for {field_key}",
                                        value=current_value_str,
                                        key=f"edit_other_text_{field_key}_{template_id}",
                                        label_visibility="collapsed",
                                        height=150
                                    )
                                else:
                                    st.text_input(
                                        f"Value for {field_key}",
                                        value=current_value_str,
                                        key=f"edit_other_text_{field_key}_{template_id}",
                                        label_visibility="collapsed"
                                    )

            st.markdown("---")
            if st.button("Save All Changes", key=f"save_all_mods_{template_id}", type="primary", width="stretch"):
                changes_to_save = {}
                for field_info, field_type in all_displayed_fields:
                    field_key = field_info["key"]
                    original_value = field_info["value"]
                    is_boolean = field_info["is_boolean"]

                    if is_boolean:
                        widget_key = f"edit_{field_type}_bool_{field_key}_{template_id}"
                        new_checked = st.session_state.get(widget_key, False)
                        new_value = "YES" if new_checked else "NO"
                    else:
                        widget_key = f"edit_{field_type}_text_{field_key}_{template_id}"
                        new_value = st.session_state.get(widget_key, "")

                    original_compare_val = str(original_value if original_value is not None else ("NO" if is_boolean else ""))
                    new_compare_val = str(new_value)

                    if original_compare_val != new_compare_val:
                        changes_to_save[field_key] = {
                            "new_value": new_value,
                            "original_value": original_compare_val
                        }

                if changes_to_save:
                    with st.spinner(f"Saving {len(changes_to_save)} modifications..."):
                        success = save_bulk_goa_modifications(template_id, changes_to_save)
                        if success:
                            # --- FEW-SHOT LEARNING FEEDBACK LOOP ---
                            try:
                                # 1. Gather Context
                                feedback_machine_type = "general"
                                if machine_name:
                                    feedback_machine_type = determine_machine_type(machine_name)

                                feedback_template_type = template_type if template_type else "default"
                                if is_sortstar_machine:
                                    feedback_template_type = "sortstar"

                                # Attempt to get full text and machine data for context
                                feedback_full_text = ""
                                feedback_machine_data = {}
                                feedback_common_items = []

                                # Try to find the machine record and quote ref
                                if machine_id and st.session_state.all_crm_clients:
                                    found_machine = False
                                    for client in st.session_state.all_crm_clients:
                                        c_quote_ref = client.get('quote_ref', '')
                                        machines = load_machines_for_quote(c_quote_ref)
                                        for m in machines:
                                            if m.get('id') == machine_id:
                                                # Found our machine!
                                                found_machine = True

                                                # Get full text
                                                doc_content = load_document_content(c_quote_ref)
                                                if doc_content:
                                                    feedback_full_text = doc_content.get("full_pdf_text", "")

                                                # Get machine data and common items
                                                machine_data_content = m.get("machine_data")
                                                if isinstance(machine_data_content, str):
                                                    try:
                                                        feedback_machine_data = json.loads(machine_data_content)
                                                    except:
                                                        feedback_machine_data = {"machine_name": m.get("machine_name", "")}
                                                elif isinstance(machine_data_content, dict):
                                                    feedback_machine_data = machine_data_content

                                                if "common_items" in feedback_machine_data:
                                                    feedback_common_items = feedback_machine_data["common_items"]
                                                break
                                        if found_machine:
                                            break

                                # 2. Save Corrections as Examples
                                examples_saved = 0
                                for field_key, change_info in changes_to_save.items():
                                    new_val = change_info.get("new_value")

                                    # Skip if value is empty or just "NO" (unless we want to teach negatives, but positives are stronger)
                                    if not new_val: continue
                                    if isinstance(new_val, str) and new_val.upper() == "NO" and field_key.endswith("_check"):
                                        # Optional: could save "NO" examples if needed, but usually we focus on extraction
                                        continue

                                    save_successful_extraction_as_example(
                                        field_name=field_key,
                                        field_value=str(new_val),
                                        machine_data=feedback_machine_data,
                                        common_items=feedback_common_items,
                                        full_pdf_text=feedback_full_text,
                                        machine_type=feedback_machine_type,
                                        template_type=feedback_template_type,
                                        source_machine_id=machine_id,
                                        confidence_score=1.0 # High confidence because it's a human correction
                                    )
                                    examples_saved += 1

                                if examples_saved > 0:
                                    st.toast(f"🧠 Learned from {examples_saved} correction(s) for future use!", icon="🎓")

                            except Exception as e:
                                print(f"Error in few-shot feedback loop: {e}")
                                # Don't block the user flow if learning fails
                            # --- END FEEDBACK LOOP ---

                            st.success(f"Saved {len(changes_to_save)} modifications successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to save modifications. Please check the logs.")
                else:
                    st.info("No changes were detected to save.")

        # Tab for adding new fields
        with add_tab:
            st.subheader("Add New Fields")
            st.info("Use this section to add fields that weren't found by the LLM but should be included in the template.")

            try:
                if is_sortstar_machine:
                    all_possible_fields = current_explicit_mappings
                else:
                    # Use Excel source of truth for GOA
                    all_possible_fields = get_all_fields_from_excel()

                # Filter out fields that are already in the template
                available_fields = {k: v for k, v in all_possible_fields.items()
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
