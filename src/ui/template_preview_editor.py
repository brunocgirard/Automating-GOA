"""
Reusable template preview and editor component.

This module provides a reusable field editor with live HTML preview that can be used in:
1. Quote Processing workflow - Preview extracted fields before document generation
2. CRM Management - Edit existing saved templates

The editor organizes fields by section and subsection, supports both checkboxes and text fields,
and provides live HTML preview of changes.

New in Phase 2: Confidence indicators for each field showing extraction quality.
"""

import streamlit as st
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup

from src.utils.template_utils import SORTSTAR_EXPLICIT_MAPPINGS
from src.utils.form_generator import get_all_fields_from_excel, OUTPUT_HTML_PATH
from src.utils.html_doc_filler import fill_html_template
from src.llm import get_confidence_level, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW


# Confidence indicator display helpers
def get_confidence_indicator(confidence: float) -> str:
    """
    Returns an ASCII-based confidence indicator based on the score.

    Args:
        confidence: Float between 0.0 and 1.0

    Returns:
        str: ASCII indicator string (no Unicode emojis for Windows compatibility)
    """
    level = get_confidence_level(confidence)
    if level == 'high':
        return "[HIGH]"  # Green conceptually
    elif level == 'medium':
        return "[MED]"   # Yellow conceptually
    else:
        return "[LOW]"   # Red conceptually - needs review


def get_confidence_color(confidence: float) -> str:
    """
    Returns a color code for the confidence level.

    Args:
        confidence: Float between 0.0 and 1.0

    Returns:
        str: Color name for Streamlit styling
    """
    level = get_confidence_level(confidence)
    if level == 'high':
        return "green"
    elif level == 'medium':
        return "orange"
    else:
        return "red"


def is_sortstar_machine(machine_name: Optional[str]) -> bool:
    """
    Determines if a machine is a SortStar type based on its name.

    Args:
        machine_name: Name of the machine

    Returns:
        bool: True if machine is SortStar type
    """
    if not machine_name:
        return False
    sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
    return bool(re.search(sortstar_pattern, machine_name.lower()))


def is_field_suspicious(field_value: Any, field_key: str) -> bool:
    """
    Checks if a field value looks suspicious (likely LLM error or placeholder text).

    Args:
        field_value: The field value to check
        field_key: The field key for context

    Returns:
        bool: True if field value looks suspicious
    """
    if field_value is None or field_value == "":
        # Empty is OK - most fields should be empty
        return False

    if isinstance(field_value, str):
        value_lower = field_value.strip().lower()

        # Suspicious placeholder text that shouldn't remain in final output
        suspicious_phrases = [
            "n/a", "not applicable", "not specified", "not selected",
            "none selected", "to be determined", "tbd", "pending",
            "not available", "unknown", "not provided", "see quote",
            "refer to quote", "as per quote", "not mentioned"
        ]

        # Check if the ENTIRE value is just a suspicious phrase
        if value_lower in suspicious_phrases:
            return True

        # Check if value is suspiciously generic for non-checkbox fields
        if not field_key.endswith("_check"):
            if value_lower in ["yes", "no", "true", "false"]:
                # These are suspicious for text fields
                return True

    return False


def organize_fields_by_section(
    template_data: Dict[str, Any],
    field_mappings: Dict[str, str],
    is_sortstar: bool
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Organizes template fields by section with friendly labels.

    Args:
        template_data: Dictionary of field values {placeholder_key: value}
        field_mappings: Dictionary mapping placeholder keys to full field paths
        is_sortstar: Whether this is a SortStar machine template

    Returns:
        Dictionary mapping section names to lists of field info dicts
    """
    section_fields: Dict[str, List[Dict[str, Any]]] = {}

    for key, value in template_data.items():
        mapping = field_mappings.get(key, key)
        section_name = "Uncategorized"
        friendly_label = key

        if mapping and (" > " in mapping or " - " in mapping):
            # Parse section/subsection from field path
            separator = " > " if is_sortstar else " - "
            parts = [p.strip() for p in mapping.split(separator) if p.strip()]

            if parts:
                section_name = parts[0]
                friendly_label = parts[-1]

        # Determine if field is boolean (checkbox)
        is_boolean = (
            str(value).upper() in ["YES", "NO", "TRUE", "FALSE"]
            or key.endswith("_check")
        )

        section_fields.setdefault(section_name, []).append({
            "key": key,
            "label": friendly_label,
            "value": value,
            "is_boolean": is_boolean
        })

    return section_fields


def parse_html_template_structure() -> Tuple[
    List[str],
    Dict[str, List[str]],
    Dict[str, Optional[str]],
    Dict[str, List[Tuple[Optional[str], List[str]]]]
]:
    """
    Parses the HTML template to extract section/subsection order.

    Returns:
        Tuple containing:
        - section_order: List of section names in order
        - section_field_order: Dict mapping section_name -> list of field keys
        - field_to_subsection: Dict mapping field_key -> subsection_name
        - section_subsection_order: Dict mapping section_name -> list of (subsection, fields) tuples
    """
    section_order = []
    section_field_order: Dict[str, List[str]] = {}
    field_to_subsection: Dict[str, Optional[str]] = {}
    section_subsection_order: Dict[str, List[Tuple[Optional[str], List[str]]]] = {}

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
        print(f"[WARN] Could not parse section/field order from goa_form.html: {e}")

    return section_order, section_field_order, field_to_subsection, section_subsection_order


def render_field_editor(
    template_data: Dict[str, Any],
    template_type: str,
    machine_name: str,
    widget_key_prefix: str,
    highlight_empty: bool = False,
    show_preview: bool = True,
    return_widget_values: bool = True,
    confidence_scores: Optional[Dict[str, float]] = None,
    field_suggestions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Renders a section-based field editor with optional live HTML preview.

    Args:
        template_data: Dictionary of field values {placeholder_key: value}
        template_type: Template type ("GOA" or other)
        machine_name: Name of the machine (for SortStar detection)
        widget_key_prefix: Unique prefix for Streamlit widget keys (avoid conflicts)
        highlight_empty: Whether to highlight empty or default-value fields
        show_preview: Whether to show live HTML preview below editor
        return_widget_values: Whether to return edited values from widgets
        confidence_scores: Optional dict of field_key -> confidence score (0.0-1.0)
        field_suggestions: Optional list of field dependency suggestions/warnings

    Returns:
        Dictionary of edited field values (same structure as template_data)
    """
    # Determine machine type and load appropriate field mappings
    is_sortstar = is_sortstar_machine(machine_name)

    if is_sortstar:
        st.info(f"SortStar machine template: {machine_name}")
        field_mappings = SORTSTAR_EXPLICIT_MAPPINGS
    else:
        field_mappings = get_all_fields_from_excel()

    # Organize fields by section
    section_fields = organize_fields_by_section(template_data, field_mappings, is_sortstar)

    # Parse HTML template structure for ordering
    section_order, section_field_order, field_to_subsection, section_subsection_order = parse_html_template_structure()

    # Helper functions for ranking
    def section_rank(name: str) -> int:
        return section_order.index(name) if name in section_order else len(section_order) + sorted(section_fields.keys()).index(name)

    def field_rank(field_info: Dict[str, Any], section_name: str) -> int:
        """Return field position based on HTML template order, falling back to alphabetical."""
        field_key = field_info["key"]
        if section_name in section_field_order:
            field_order_list = section_field_order[section_name]
            if field_key in field_order_list:
                return field_order_list.index(field_key)
        # Fallback: fields not in HTML order go at end, sorted alphabetically
        return 10000 + ord(field_info["label"][0].lower()) if field_info["label"] else 10000

    # Section selector
    section_options = sorted(section_fields.keys(), key=section_rank)
    selected_section = st.selectbox(
        "Select section to edit",
        section_options,
        key=f"{widget_key_prefix}_section_select"
    )

    # Build edited_data dict with current values
    edited_data = dict(template_data)

    # Display field dependency suggestions if available
    if field_suggestions:
        with st.expander("Field Dependency Suggestions", expanded=False):
            for suggestion in field_suggestions:
                sug_type = suggestion.get("type", "info")
                field = suggestion.get("field", "")
                reason = suggestion.get("reason", "")
                suggested = suggestion.get("suggested_value")

                if sug_type == "warning":
                    st.warning(f"**{field}**: {reason}")
                elif sug_type == "suggestion" and suggested:
                    st.info(f"**{field}**: {reason} (Suggested: {suggested})")
                else:
                    st.info(f"**{field}**: {reason}")

    if selected_section:
        st.markdown(f"##### Fields in {selected_section}")

        # Count suspicious fields and confidence statistics in this section
        section_field_keys = [f["key"] for f in section_fields[selected_section]]
        suspicious_count = 0
        low_conf_count = 0
        med_conf_count = 0
        high_conf_count = 0

        for field_info in section_fields[selected_section]:
            fk = field_info["key"]
            if highlight_empty and is_field_suspicious(field_info["value"], fk):
                suspicious_count += 1

            if confidence_scores and fk in confidence_scores:
                conf = confidence_scores[fk]
                if conf >= CONFIDENCE_HIGH:
                    high_conf_count += 1
                elif conf >= CONFIDENCE_MEDIUM:
                    med_conf_count += 1
                else:
                    low_conf_count += 1

        # Display confidence summary for this section
        if confidence_scores:
            conf_col1, conf_col2, conf_col3 = st.columns(3)
            with conf_col1:
                st.markdown(f":green[HIGH]: {high_conf_count}")
            with conf_col2:
                st.markdown(f":orange[MED]: {med_conf_count}")
            with conf_col3:
                st.markdown(f":red[LOW]: {low_conf_count}")

        if suspicious_count > 0:
            st.warning(f"[WARN] {suspicious_count} field(s) in this section have suspicious values (placeholder text or likely errors)")

        if low_conf_count > 0:
            st.info(f"[INFO] {low_conf_count} field(s) have low confidence and may need review")

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
                        field_confidence = confidence_scores.get(field_key) if confidence_scores else None
                        _render_single_field(
                            field_info,
                            edited_data,
                            widget_key_prefix,
                            highlight_empty,
                            field_confidence
                        )
                        rendered_fields.add(field_key)

            # Render any remaining fields not in the HTML structure (fallback)
            remaining_fields = [f for f in section_fields[selected_section] if f["key"] not in rendered_fields]
            if remaining_fields:
                st.markdown("###### Other Fields")
                for field_info in sorted(remaining_fields, key=lambda x: field_rank(x, selected_section)):
                    field_confidence = confidence_scores.get(field_info["key"]) if confidence_scores else None
                    _render_single_field(
                        field_info,
                        edited_data,
                        widget_key_prefix,
                        highlight_empty,
                        field_confidence
                    )
        else:
            # Fallback: no subsection info, render all fields in order
            for field_info in sorted(section_fields[selected_section], key=lambda x: field_rank(x, selected_section)):
                field_confidence = confidence_scores.get(field_info["key"]) if confidence_scores else None
                _render_single_field(
                    field_info,
                    edited_data,
                    widget_key_prefix,
                    highlight_empty,
                    field_confidence
                )

    # Live HTML preview
    if show_preview:
        st.markdown("---")
        st.markdown("#### Live Preview")
        try:
            if os.path.exists(OUTPUT_HTML_PATH):
                with open(OUTPUT_HTML_PATH, "r", encoding="utf-8") as f:
                    raw_html = f.read()
                plain_html = fill_html_template(raw_html, edited_data)
                st.components.v1.html(plain_html, height=900, scrolling=True)
            else:
                st.info(f"HTML template not found at {OUTPUT_HTML_PATH}")
        except Exception as e:
            st.warning(f"Could not render HTML preview: {e}")

    return edited_data


def _render_single_field(
    field_info: Dict[str, Any],
    edited_data: Dict[str, Any],
    widget_key_prefix: str,
    highlight_empty: bool,
    confidence: Optional[float] = None
) -> None:
    """
    Renders a single field widget (checkbox or text area) and updates edited_data.

    Args:
        field_info: Field information dict with keys: key, label, value, is_boolean
        edited_data: Dictionary to update with new values
        widget_key_prefix: Prefix for widget keys
        highlight_empty: Whether to show warnings for suspicious fields
        confidence: Optional confidence score (0.0-1.0) for this field
    """
    field_key = field_info["key"]
    field_label = field_info["label"]
    current_value = field_info["value"]
    is_boolean = field_info["is_boolean"]
    widget_key = f"{widget_key_prefix}_{field_key}"

    # Check if field has suspicious value that should be highlighted
    is_suspicious = highlight_empty and is_field_suspicious(current_value, field_key)

    # Build label with confidence indicator if available
    display_label = field_label
    help_text = None

    if confidence is not None:
        conf_indicator = get_confidence_indicator(confidence)
        conf_color = get_confidence_color(confidence)
        conf_pct = int(confidence * 100)

        # Add confidence indicator to label
        display_label = f"{field_label} {conf_indicator}"

        # Add help text with confidence explanation
        level = get_confidence_level(confidence)
        if level == 'high':
            help_text = f"Confidence: {conf_pct}% - High confidence extraction based on strong evidence in the document."
        elif level == 'medium':
            help_text = f"Confidence: {conf_pct}% - Medium confidence - value may need verification."
        else:
            help_text = f"Confidence: {conf_pct}% - LOW confidence - please review and verify this value."

    if is_suspicious:
        # Append suspicious warning to help text
        suspicious_help = f"[WARN] Suspicious value detected: '{current_value}'. This may be placeholder text or an LLM error."
        help_text = f"{help_text}\n{suspicious_help}" if help_text else suspicious_help

    # Determine if we need a special layout (low confidence or suspicious)
    needs_attention = is_suspicious or (confidence is not None and confidence < CONFIDENCE_MEDIUM)

    if needs_attention:
        # Show attention indicator for fields needing review
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            if is_suspicious:
                st.markdown("[!]")
            elif confidence is not None and confidence < CONFIDENCE_LOW:
                st.markdown(":red[[!]]")
            else:
                st.markdown(":orange[[?]]")
        with col2:
            if is_boolean:
                checked = str(current_value).upper() in ["YES", "TRUE"]
                new_val = st.checkbox(display_label, value=checked, key=widget_key, help=help_text)
                edited_data[field_key] = "YES" if new_val else "NO"
            else:
                height = 150 if field_key == "options_listing" else 60
                new_val = st.text_area(
                    display_label,
                    value=current_value if current_value is not None else "",
                    height=height,
                    key=widget_key,
                    help=help_text
                )
                edited_data[field_key] = new_val
    else:
        # Normal rendering
        if is_boolean:
            checked = str(current_value).upper() in ["YES", "TRUE"]
            new_val = st.checkbox(display_label, value=checked, key=widget_key, help=help_text)
            edited_data[field_key] = "YES" if new_val else "NO"
        else:
            height = 150 if field_key == "options_listing" else 60
            new_val = st.text_area(
                display_label,
                value=current_value if current_value is not None else "",
                height=height,
                key=widget_key,
                help=help_text
            )
            edited_data[field_key] = new_val


def get_suspicious_fields_summary(template_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Generates a summary of suspicious fields in the template data.

    Args:
        template_data: Dictionary of field values

    Returns:
        Dictionary with keys: 'total_fields', 'filled_fields', 'suspicious_fields'
    """
    total_fields = len(template_data)
    filled_fields = sum(1 for value in template_data.values() if value not in [None, ""])
    suspicious_fields = sum(1 for key, value in template_data.items() if is_field_suspicious(value, key))

    return {
        "total_fields": total_fields,
        "filled_fields": filled_fields,
        "suspicious_fields": suspicious_fields
    }
