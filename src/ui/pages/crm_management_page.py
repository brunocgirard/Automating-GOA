"""
CRM Management Page Module

This module handles the CRM management interface, including:
- Client record viewing and editing
- Priced items management
- Client deletion and creation
- Template modifications for machines
"""

import streamlit as st
import pandas as pd
from typing import Optional


def show_crm_management_page():
    """
    Displays the CRM management interface for viewing, editing, and managing client records,
    priced items, and template modifications.
    """
    st.title("📒 CRM Management")
    from app import load_crm_data, quick_extract_and_catalog, update_single_priced_item # Ensure update_single_priced_item is imported

    if st.button("Refresh CRM List", key=f"refresh_crm_main_tab_{st.session_state.run_key}"):
        load_crm_data(); st.success("CRM data refreshed.")

    st.subheader("Client Records")
    client_options_display = ["Select a Client Record..."] + [f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')} (ID: {c.get('id')})" for c in st.session_state.all_crm_clients]
    selected_client_option_str_for_view = st.selectbox("Select Client to View/Edit Details:", client_options_display, key=f"crm_select_for_view_main_tab_{st.session_state.run_key}", index=0)

    client_detail_editor_placeholder = st.empty()
    save_button_placeholder = st.empty()
    delete_section_placeholder = st.empty()

    if selected_client_option_str_for_view != "Select a Client Record...":
        try:
            from src.utils.db import get_client_by_id, load_machines_for_quote

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

                        client_data = client_to_display_and_edit

                        # Split addresses into 3 parts, padding with empty strings if needed
                        sold_addr_parts = (client_data.get('sold_to_address', '') or '').split('\n')
                        ship_addr_parts = (client_data.get('ship_to_address', '') or '').split('\n')
                        sold_addr_parts += [''] * (3 - len(sold_addr_parts))
                        ship_addr_parts += [''] * (3 - len(ship_addr_parts))

                        client_detail_for_df = {
                            'id': client_data.get('id'),
                            'Ax': client_data.get('ax', ''),
                            'Company': client_data.get('company', ''),
                            'Customer': client_data.get('customer_name', ''),
                            'Machine': client_data.get('machine_model', ''),
                            'Quote No': client_data.get('quote_ref', ''),
                            'Serial Number': client_data.get('serial_number', ''),
                            'Sold to/Address 1': sold_addr_parts[0],
                            'Sold to/Address 2': sold_addr_parts[1],
                            'Sold to/Address 3': sold_addr_parts[2],
                            'Ship to/Address 1': ship_addr_parts[0],
                            'Ship to/Address 2': ship_addr_parts[1],
                            'Ship to/Address 3': ship_addr_parts[2],
                            'Telefone': client_data.get('telephone', ''),
                            'Customer PO': client_data.get('customer_po', ''),
                            'Order date': client_data.get('order_date', ''),
                            'Ox': client_data.get('ox', ''),
                            'Via': client_data.get('via', ''),
                            'Incoterm': client_data.get('incoterm', ''),
                            'Tax ID': client_data.get('tax_id', ''),
                            'H.S': client_data.get('hs_code', ''),
                            'Customer Number': client_data.get('customer_number', ''),
                            'Customer contact': client_data.get('customer_contact_person', ''),
                        }

                        df_for_editor = pd.DataFrame([client_detail_for_df])

                        column_order = [
                            'Ax', 'Company', 'Customer', 'Machine', 'Quote No', 'Serial Number',
                            'Sold to/Address 1', 'Sold to/Address 2', 'Sold to/Address 3',
                            'Ship to/Address 1', 'Ship to/Address 2', 'Ship to/Address 3',
                            'Telefone', 'Customer PO', 'Order date', 'Ox', 'Via', 'Incoterm',
                            'Tax ID', 'H.S', 'Customer Number', 'Customer contact'
                        ]

                        edited_df_output = st.data_editor(
                            df_for_editor,
                            key=f"client_detail_editor_{client_to_display_and_edit.get('id', 'new')}",
                            num_rows="fixed",
                            hide_index=True,
                            width="stretch",
                            column_order=column_order,
                            column_config={
                                "id": None,  # Hide ID column
                                "Quote No": st.column_config.TextColumn(required=True),
                            }
                        )

                        st.session_state.edited_client_details_df = edited_df_output

                    with save_button_placeholder.container():
                        if st.button("💾 Save Client Detail Changes", key=f"save_details_btn_{client_to_display_and_edit.get('id', 'new')}"):
                            if not st.session_state.edited_client_details_df.empty:
                                updated_row = st.session_state.edited_client_details_df.iloc[0].to_dict()

                                # Combine address parts back into single fields
                                sold_to_address = "\n".join([
                                    str(updated_row.get('Sold to/Address 1', '')),
                                    str(updated_row.get('Sold to/Address 2', '')),
                                    str(updated_row.get('Sold to/Address 3', ''))
                                ]).strip()

                                ship_to_address = "\n".join([
                                    str(updated_row.get('Ship to/Address 1', '')),
                                    str(updated_row.get('Ship to/Address 2', '')),
                                    str(updated_row.get('Ship to/Address 3', ''))
                                ]).strip()

                                client_id_to_update = client_to_display_and_edit.get('id')
                                update_payload = {
                                    'ax': updated_row.get('Ax'),
                                    'company': updated_row.get('Company'),
                                    'customer_name': updated_row.get('Customer'),
                                    'machine_model': updated_row.get('Machine'),
                                    'quote_ref': updated_row.get('Quote No'),
                                    'serial_number': updated_row.get('Serial Number'),
                                    'sold_to_address': sold_to_address,
                                    'ship_to_address': ship_to_address,
                                    'telephone': updated_row.get('Telefone'),
                                    'customer_po': updated_row.get('Customer PO'),
                                    'order_date': updated_row.get('Order date'),
                                    'ox': updated_row.get('Ox'),
                                    'via': updated_row.get('Via'),
                                    'incoterm': updated_row.get('Incoterm'),
                                    'tax_id': updated_row.get('Tax ID'),
                                    'hs_code': updated_row.get('H.S'),
                                    'customer_number': updated_row.get('Customer Number'),
                                    'customer_contact_person': updated_row.get('Customer contact'),
                                }

                                if not update_payload.get('quote_ref'):
                                    st.error("Quote No is required!")
                                elif update_client_record(client_id_to_update, update_payload):
                                    st.success("Client details updated!")
                                    load_crm_data()
                                    st.session_state.selected_client_for_detail_edit = get_client_by_id(client_id_to_update)
                                    st.rerun()
                                else:
                                    st.error("Failed to update client details.")
                            else:
                                st.warning("No client data in editor to save.")
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
                    from src.utils.db import load_priced_items_for_quote

                    quote_ref_for_items = client_to_display_and_edit.get('quote_ref'); st.subheader(f"Priced Items for Quote: {quote_ref_for_items}")
                    priced_items_for_quote = load_priced_items_for_quote(quote_ref_for_items); st.session_state.current_priced_items_for_editing = priced_items_for_quote
                    if priced_items_for_quote:
                        df_priced_items = pd.DataFrame(priced_items_for_quote); editable_df = df_priced_items[['id', 'item_description', 'item_quantity', 'item_price_str']].copy()
                        st.markdown("**Edit Priced Items:**")
                        edited_df = st.data_editor(editable_df, key=f"data_editor_priced_items_{st.session_state.editing_client_id}", num_rows="dynamic", hide_index=True, width="stretch", column_config={"id": None, "item_description": st.column_config.TextColumn("Description", width="large", required=True), "item_quantity": st.column_config.TextColumn("Qty"), "item_price_str": st.column_config.TextColumn("Price (Text)")})
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
                            from src.ui.ui_pages import show_goa_modifications_ui
                            show_goa_modifications_ui(selected_machine_id, machine_name=selected_machine_name) # Pass machine_name
        except Exception as e: st.error(f"Error in CRM client display: {e}"); import traceback; traceback.print_exc()
    else: st.info("Select a client to view/edit details.")

    st.markdown("---"); st.subheader("All Client Records Table")
    if st.session_state.all_crm_clients:
        df_all_clients = pd.DataFrame(st.session_state.all_crm_clients)
        all_clients_cols = [
            'id', 'ax', 'company', 'customer_name', 'machine_model', 'quote_ref', 'serial_number',
            'sold_to_address', 'ship_to_address', 'telephone', 'customer_po', 'order_date',
            'ox', 'via', 'incoterm', 'tax_id', 'hs_code', 'customer_number',
            'customer_contact_person', 'processing_date'
        ]
        df_all_clients_final = df_all_clients[[c for c in all_clients_cols if c in df_all_clients.columns]]
        st.dataframe(df_all_clients_final, width="stretch", hide_index=True)
    else: st.info("No client records found.")

    with st.expander("Manually Add New Client Record"):
        with st.form(key=f"crm_add_new_form_{st.session_state.run_key}"):
            st.markdown("**Enter New Client Details:**")

            # Using columns for a better layout
            col1, col2, col3 = st.columns(3)

            with col1:
                new_quote_ref = st.text_input("Quote No (Required)", key=f"new_qr_{st.session_state.run_key}")
                new_cust_name = st.text_input("Customer", key=f"new_cn_{st.session_state.run_key}")
                new_company = st.text_input("Company", key=f"new_comp_{st.session_state.run_key}")
                new_machine_model = st.text_input("Machine", key=f"new_mm_{st.session_state.run_key}")
                new_serial_number = st.text_input("Serial Number", key=f"new_sn_{st.session_state.run_key}")
                new_customer_number = st.text_input("Customer Number", key=f"new_cnum_{st.session_state.run_key}")
                new_contact = st.text_input("Customer contact", key=f"new_ccp_{st.session_state.run_key}")
                new_tel = st.text_input("Telefone", key=f"new_tel_{st.session_state.run_key}")

            with col2:
                new_po = st.text_input("Customer PO", key=f"new_cpo_{st.session_state.run_key}")
                new_order_date = st.text_input("Order date", key=f"new_od_{st.session_state.run_key}")
                new_via = st.text_input("Via", key=f"new_via_{st.session_state.run_key}")
                new_incoterm = st.text_input("Incoterm", key=f"new_inco_{st.session_state.run_key}")
                new_tax_id = st.text_input("Tax ID", key=f"new_tax_{st.session_state.run_key}")
                new_hs_code = st.text_input("H.S", key=f"new_hs_{st.session_state.run_key}")
                new_ax = st.text_input("Ax", key=f"new_ax_{st.session_state.run_key}")
                new_ox = st.text_input("Ox", key=f"new_ox_{st.session_state.run_key}")

            with col3:
                new_sold_addr = st.text_area("Sold to Address", key=f"new_sta_{st.session_state.run_key}", placeholder="Line 1\nLine 2\nLine 3")
                new_ship_addr = st.text_area("Ship to Address", key=f"new_shipta_{st.session_state.run_key}", placeholder="Line 1\nLine 2\nLine 3")

            if st.form_submit_button("➕ Add New Client"):
                if not new_quote_ref:
                    st.error("Quote No is required.")
                else:
                    from src.utils.db import save_client_info

                    new_client_data = {
                        'quote_ref': new_quote_ref,
                        'customer_name': new_cust_name,
                        'company': new_company,
                        'machine_model': new_machine_model,
                        'serial_number': new_serial_number,
                        'customer_number': new_customer_number,
                        'customer_contact_person': new_contact,
                        'telephone': new_tel,
                        'customer_po': new_po,
                        'order_date': new_order_date,
                        'via': new_via,
                        'incoterm': new_incoterm,
                        'tax_id': new_tax_id,
                        'hs_code': new_hs_code,
                        'ax': new_ax,
                        'ox': new_ox,
                        'sold_to_address': new_sold_addr,
                        'ship_to_address': new_ship_addr,
                    }
                    if save_client_info(new_client_data):
                        st.success("New client added!")
                        load_crm_data()
                        st.rerun()
                    else:
                        st.error("Failed to add new client.")


def update_client_record(client_id: int, update_payload: dict) -> bool:
    """
    Updates a client record in the database.

    Args:
        client_id: ID of the client to update
        update_payload: Dictionary containing fields to update

    Returns:
        True if successful, False otherwise
    """
    from src.utils.db import update_client_record as db_update_client_record
    return db_update_client_record(client_id, update_payload)


def delete_client_record(client_id: int) -> bool:
    """
    Deletes a client record from the database.

    Args:
        client_id: ID of the client to delete

    Returns:
        True if successful, False otherwise
    """
    from src.utils.db import delete_client_record as db_delete_client_record
    return db_delete_client_record(client_id)
