"""
Machine Build Reports Page Module

This module contains the interface for viewing and printing template reports
for specific machines in the GOA document generation system. It allows users
to select a machine and generate a printable summary report, or batch process
reports for all machines in a client.
"""

import streamlit as st
import json
import re
import datetime
from typing import Dict, List, Optional, Any

# Import database functions
from src.utils.db import (
    load_all_processed_machines,
    get_client_by_id,
    load_machines_for_quote,
    load_machine_templates_with_modifications
)

# Import report generation functions from components
from src.ui.pages.components.goa_report_components import (
    show_printable_summary_report,
    generate_printable_report
)


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
        st.session_state.all_processed_machines = load_all_processed_machines() # from db

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
        from src.utils.db import get_client_by_id, load_machines_for_quote # Ensure imports are here
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
