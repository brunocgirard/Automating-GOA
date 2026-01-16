"""
Simple Field Editor - Emergency Fallback

This is a simplified version that just renders all fields without complex organization.
Use this if the main template_preview_editor is having issues.
"""

import streamlit as st
from typing import Dict, Any


def render_simple_field_editor(
    template_data: Dict[str, Any],
    widget_key_prefix: str = "simple"
) -> Dict[str, Any]:
    """
    Renders fields in a simple flat list without section organization.

    Args:
        template_data: Dictionary of field values {field_key: value}
        widget_key_prefix: Prefix for widget keys

    Returns:
        Dictionary of edited field values
    """
    st.info(f"Rendering {len(template_data)} fields in simple mode")

    edited_data = {}

    # Count fields for progress
    total_fields = len(template_data)
    rendered_count = 0

    for field_key, current_value in template_data.items():
        # Determine if checkbox
        is_checkbox = (
            field_key.endswith("_check") or
            str(current_value).upper() in ["YES", "NO", "TRUE", "FALSE"]
        )

        widget_key = f"{widget_key_prefix}_{field_key}"

        try:
            if is_checkbox:
                checked = str(current_value).upper() in ["YES", "TRUE"]
                new_val = st.checkbox(
                    field_key,
                    value=checked,
                    key=widget_key
                )
                edited_data[field_key] = "YES" if new_val else "NO"
            else:
                height = 150 if field_key == "options_listing" else 60
                new_val = st.text_area(
                    field_key,
                    value=current_value if current_value else "",
                    height=height,
                    key=widget_key
                )
                edited_data[field_key] = new_val

            rendered_count += 1

        except Exception as e:
            st.error(f"Error rendering {field_key}: {e}")
            edited_data[field_key] = current_value

    st.success(f"Rendered {rendered_count}/{total_fields} fields")

    return edited_data
