"""
Welcome page module for QuoteFlow Document Assistant.

Displays the welcome page interface with quote upload and client dashboard access.
Handles profile extraction workflow including confirmation step and recent client profiles.
"""

import streamlit as st
from src.workflows.profile_workflow import (
    extract_client_profile, confirm_client_profile, show_action_selection,
    load_full_client_profile
)


def show_welcome_page():
    """
    Displays the welcome page interface with quote upload and client dashboard access
    """
    st.title("QuoteFlow Document Assistant")

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
                        if st.button("View Details", key=f"view_client_{client_summary_item.get('id')}", width="stretch"):
                            full_profile_data = load_full_client_profile(client_summary_item.get('quote_ref'))
                            if full_profile_data:
                                st.session_state.confirmed_profile = full_profile_data
                                st.session_state.profile_extraction_step = "action_selection"
                                st.rerun()
                            else: st.error(f"Could not load full profile for {client_summary_item.get('quote_ref')}.")
            st.markdown("&nbsp;")
            if len(st.session_state.all_crm_clients) > 5:
                if st.button("View All Clients", width="stretch"):
                    st.session_state.current_page = "Client Dashboard"
                    st.rerun()
        else:
            st.info("No client profiles found. Upload a quote below to create a new profile.")

    st.markdown("---")
    st.subheader("📤 Upload New Quote")
    uploaded_file = st.file_uploader("Choose a PDF quote to process", type=["pdf"], key="pdf_uploader_welcome")

    if uploaded_file is not None:
        st.markdown(f"Uploaded: **{uploaded_file.name}**")

        if st.button("Extract Full Profile", key="extract_profile_btn", type="primary", width="stretch"):
            st.session_state.extracted_profile = extract_client_profile(uploaded_file)
            if st.session_state.extracted_profile:
                st.session_state.profile_extraction_step = "confirmation"
                st.rerun()
            else:
                st.error("Failed to extract profile from the uploaded PDF.")

    # Profile extraction workflow - confirmation step
    if "profile_extraction_step" in st.session_state and st.session_state.profile_extraction_step == "confirmation":
        if "extracted_profile" in st.session_state and st.session_state.extracted_profile:
            # Show confirmation UI
            st.session_state.confirmed_profile = confirm_client_profile(st.session_state.extracted_profile)
            if st.session_state.confirmed_profile:
                st.session_state.profile_extraction_step = "action_selection"
                st.rerun()
