"""
Client dashboard page module for QuoteFlow Document Assistant.

Displays the client dashboard interface for browsing and selecting clients.
Handles profile extraction workflow, client search/filtering, and action selection.
"""

import streamlit as st
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection,
    handle_selected_action, load_full_client_profile
)
from src.utils.db import load_document_content


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

            if st.button("Extract Full Profile", key="extract_profile_dash_btn", type="primary", width="stretch"):
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
                    if st.button("View Details", key=f"view_client_dash_{client_item.get('id')}", width="stretch"):
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
