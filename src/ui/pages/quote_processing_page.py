"""
Quote Processing Workflow Page

This module contains the complete quote processing workflow with 5 main steps:
1. Load Quote - Select and load a previous quote from the database
2. Identify Main Machines - Select which items are main machines
3. Select Common Options - Select which items apply to all machines
4. Process Machine - Select a machine and run LLM extraction
5. Preview & Edit - Review extracted fields, edit if needed, and generate document

This is the most complex workflow in the application, handling the entire
pipeline from PDF upload to final GOA document generation.
"""

import streamlit as st
import base64
from typing import Dict, List, Optional, Any
from src.ui.template_preview_editor import render_field_editor, get_suspicious_fields_summary


def show_quote_processing():
    st.title("📄 Quote Processing")
    processing_steps = ["Load Quote", "Identify Main Machines", "Select Common Options", "Process Machine"]

    from app import (
        perform_initial_processing, process_machine_specific_data,
        run_llm_extraction_only, generate_and_save_document,
        load_previous_document, TEMPLATE_FILE,
        calculate_machine_price, calculate_common_items_price
    )

    current_step = st.session_state.processing_step

    # Account for preview step (Step 3.5) in progress calculation
    if current_step == 3 and st.session_state.get('preview_step_active', False):
        # Show intermediate progress during preview
        progress_percentage = 3.5 / len(processing_steps)
        step_label = "Step 3.5: Review & Edit Fields"
    else:
        progress_percentage = current_step / (len(processing_steps) - 1) if len(processing_steps) > 1 else 0
        step_label = f"Step {current_step + 1}: {processing_steps[current_step]}"

    st.progress(progress_percentage)
    st.subheader(step_label)

    if current_step == 0:
        st.subheader("🔄 Load Previous Quote")

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

                # Navigation buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Select Another Quote", key="select_another_quote"):
                        # Reset state
                        st.session_state.processing_step = 0
                        st.session_state.machine_confirmation_done = False
                        st.session_state.common_options_confirmation_done = False
                        st.session_state.items_for_confirmation = []
                        st.session_state.selected_main_machines = []
                        st.session_state.selected_common_options = []
                        st.session_state.identified_machines_data = None
                        st.rerun()
                with col2:
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
        # Check if preview is active - if so, show preview instead
        if st.session_state.get('preview_step_active', False):
            # Step 3.5: Preview & Edit Extracted Fields
            st.subheader("📋 Review & Edit Extracted Fields")

            machine_filled_data = st.session_state.get('machine_specific_filled_data', {})
            machine_name = st.session_state.get('selected_machine_name', 'machine')

            if not machine_filled_data:
                st.error("No extracted data found. Please run extraction again.")
                if st.button("← Back to Machine Selection"):
                    st.session_state.preview_step_active = False
                    st.rerun()
            else:
                # Show summary stats including confidence metrics
                summary = get_suspicious_fields_summary(machine_filled_data)

                # Get confidence scores from session state
                conf_scores = st.session_state.get('field_confidence_scores', {})
                high_conf = sum(1 for c in conf_scores.values() if c >= 0.8)
                med_conf = sum(1 for c in conf_scores.values() if 0.5 <= c < 0.8)
                low_conf = sum(1 for c in conf_scores.values() if c < 0.5)

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Fields", summary['total_fields'])
                with col2:
                    st.metric("Filled Fields", summary['filled_fields'])
                with col3:
                    st.metric("High Confidence", high_conf)
                with col4:
                    st.metric("Medium Confidence", med_conf)
                with col5:
                    st.metric("Low Confidence", low_conf)

                # Show warnings for issues
                if summary['suspicious_fields'] > 0:
                    st.warning(f"[WARN] {summary['suspicious_fields']} field(s) contain suspicious values (placeholder text like 'N/A' or 'Not specified').")

                if low_conf > 0:
                    st.info(f"[INFO] {low_conf} field(s) have low confidence and may need verification. Look for [LOW] indicators in field labels.")

                st.markdown("---")

                # Get confidence scores and suggestions from session state
                confidence_scores = st.session_state.get('field_confidence_scores', {})
                field_suggestions = st.session_state.get('field_dependency_suggestions', [])

                # Render the field editor with preview and confidence indicators
                edited_data = render_field_editor(
                    template_data=machine_filled_data,
                    template_type="GOA",
                    machine_name=machine_name,
                    widget_key_prefix="preview_edit",
                    highlight_empty=True,
                    show_preview=True,
                    confidence_scores=confidence_scores,
                    field_suggestions=field_suggestions
                )

                # Update session state with edited data (real-time)
                st.session_state.machine_specific_filled_data = edited_data

                st.markdown("---")

                # Action buttons
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    if st.button("← Back to Machine Selection", key="preview_back"):
                        st.session_state.preview_step_active = False
                        st.rerun()
                with col2:
                    if st.button("🔄 Re-run LLM Extraction", key="preview_rerun"):
                        # Get selected machine again and re-extract
                        machines = st.session_state.identified_machines_data.get("machines", [])
                        selected_machine_idx = st.session_state.selected_machine_index
                        selected_machine = machines[selected_machine_idx]

                        with st.spinner("Re-extracting data from PDF..."):
                            success = run_llm_extraction_only(selected_machine)
                            if success:
                                st.success("Data re-extracted successfully!")
                                st.rerun()
                            else:
                                st.error("Re-extraction failed. Check errors above.")
                with col3:
                    if st.button("✅ Approve & Generate Document", type="primary", key="preview_approve"):
                        with st.spinner("Generating document and saving to database..."):
                            success = generate_and_save_document()
                            if success:
                                st.success("Document generated and saved successfully!")
                                st.session_state.preview_step_active = False

                                # Note about template modifications
                                st.info("To view or modify the GOA template, go to CRM Management and select this client.")
                                st.rerun()
                            else:
                                st.error("Failed to generate document. Check errors above.")
        else:
            # Step 3: Select Machine and Extract Data
            if st.button("⬅️ Select Another Quote", key="select_another_quote_step4"):
                # Reset state
                st.session_state.processing_step = 0
                st.session_state.machine_confirmation_done = False
                st.session_state.common_options_confirmation_done = False
                st.session_state.items_for_confirmation = []
                st.session_state.selected_main_machines = []
                st.session_state.selected_common_options = []
                st.session_state.identified_machines_data = None
                st.session_state.preview_step_active = False
                st.rerun()
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
                    if st.button("⬅️ Back (GOA Common Options)", key="goa_back_common"):
                        st.session_state.common_options_confirmation_done = False
                        st.session_state.processing_step = 2
                        st.session_state.preview_step_active = False
                        st.rerun()
                with col2:
                    if st.button("Extract Data with LLM →", type="primary", key=f"extract_machine_btn_{st.session_state.run_key}"):
                        with st.spinner(f"Extracting data for {selected_machine.get('machine_name')}..."):
                            success = run_llm_extraction_only(selected_machine)
                            if success:
                                st.success(f"Extracted {len(st.session_state.machine_specific_filled_data)} fields successfully!")
                                st.session_state.preview_step_active = True
                                st.rerun()
                            else:
                                st.error(f"Failed to extract data. Check errors above.")
            else:
                st.warning("No machines identified. Go back to Step 1 to select main machines.")
                if st.button("⬅️ Back to Step 1", key="back_to_step1"):
                    st.session_state.processing_step = 1
                    st.session_state.machine_confirmation_done = False
                    st.session_state.common_options_confirmation_done = False
                    st.rerun()
