"""
Template display utilities for rendering template-related information.

This module provides helper functions for displaying template data in various formats:
- generate_template_summary: Creates a hierarchical summary of selected template items
- show_template_items_table: Displays template items in tabular format grouped by section
- show_template_summary: Renders the main template summary interface

These functions handle field organization, context mapping, and friendly name generation
for both standard and SortStar machine templates.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Any
from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS


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
            st.dataframe(df, width="stretch", hide_index=True)


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
