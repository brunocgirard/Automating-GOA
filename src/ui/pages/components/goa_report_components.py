"""
GOA Report Generation Components

This module contains utilities for generating printable reports for GOA (General Offer Arrangement)
documents. These functions create HTML reports optimized for machine building teams with visual
organization and comprehensive specification listings.

Functions:
    - generate_printable_report: Creates detailed HTML report with full specifications
    - show_printable_report: Displays report in Streamlit with download option
    - show_printable_summary_report: Displays concise summary report in Streamlit
    - generate_machine_build_summary_html: Creates concise HTML summary report

All reports support both standard and SortStar machine types with appropriate formatting.
"""

import streamlit as st
import os
from datetime import datetime
from src.utils.template_utils import (
    DEFAULT_EXPLICIT_MAPPINGS,
    SORTSTAR_EXPLICIT_MAPPINGS,
    parse_full_fields_outline
)


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
        display_value = '<input type="checkbox">' if (is_checked_suffix and value_str.upper() in ["YES", "TRUE"]) or \
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
