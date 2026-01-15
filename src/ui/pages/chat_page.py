"""
Chat Page Module

This module handles the chat interface for interacting with document content.
Provides functions for:
- Displaying the chat interface
- Managing chat context and document selection
- Handling chat state management
"""

import streamlit as st
from typing import Optional


def show_chat_page():
    """
    Displays the chat interface page with robust state management.
    Allows users to select a document and ask questions about it.
    """
    st.title("💬 Chat with Document Assistant")

    # Initialize required state variables
    if "chat_context" not in st.session_state:
        st.session_state.chat_context = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_page_client_selector" not in st.session_state:
        st.session_state.chat_page_client_selector = "placeholder"

    # --- Document Selection UI (Always Visible) ---
    st.subheader("Select Document to Chat About")

    client_options = [("placeholder", "Select a client/quote...")]
    if "all_crm_clients" in st.session_state and st.session_state.all_crm_clients:
        client_options.extend([(c.get('id'), f"{c.get('customer_name', 'N/A')} - {c.get('quote_ref', 'N/A')}") for c in st.session_state.all_crm_clients])

    # Determine the current selection to display in the dropdown.
    # This ensures the dropdown is in sync with the actual context.
    current_context_id = "placeholder"
    if st.session_state.chat_context:
        current_context_id = st.session_state.chat_context.get("client_data", {}).get("id", "placeholder")

    st.selectbox(
        "Client/Quote:",
        options=[opt[0] for opt in client_options],
        format_func=lambda x: dict(client_options).get(x, ""),
        # Set the key and ensure the index reflects the current state
        key="chat_page_client_selector",
        index=[opt[0] for opt in client_options].index(current_context_id),
        on_change=handle_chat_context_switch,
    )

    # --- Main Chat Interface ---
    if st.session_state.chat_context:
        chat_ctx = st.session_state.chat_context
        client_name = chat_ctx.get("client_data", {}).get("customer_name", "N/A")
        quote_ref = chat_ctx.get("quote_ref", "N/A")
        st.info(f"Chatting about document: **{client_name} - {quote_ref}**")

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask a question about the selected document..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    from app import process_chat_query
                    # This context is now guaranteed to be the correct one
                    context_data = {
                        "full_pdf_text": chat_ctx.get("full_pdf_text", ""),
                        "selected_pdf_descs": [],
                        "template_contexts": {}
                    }
                    response = process_chat_query(prompt, "quote", context_data)
                    st.markdown(response)

            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()
    else:
        # This message shows when no context is loaded
        st.info("Please select a document from the dropdown to begin.")


def handle_chat_context_switch():
    """
    Callback triggered when the user selects a new document from the dropdown.
    Manages context switching and history clearing when documents change.
    """
    # The new client ID is in the widget's session state key
    selected_id = st.session_state.get("chat_page_client_selector")

    # Always clear the history when the selection changes.
    st.session_state.chat_history = []

    if selected_id and selected_id != "placeholder":
        from src.utils.db import get_client_by_id, load_document_content

        client_data = get_client_by_id(selected_id)
        if client_data:
            quote_ref = client_data.get('quote_ref')
            doc_content = load_document_content(quote_ref)
            if doc_content and doc_content.get("full_pdf_text"):
                # Load the new context
                st.session_state.chat_context = {
                    "client_data": client_data,
                    "quote_ref": quote_ref,
                    "full_pdf_text": doc_content.get("full_pdf_text", "")
                }
            else:
                # If the selected document has no content, clear the context
                st.session_state.chat_context = None
                st.warning(f"No document content found for quote '{quote_ref}'.")
        else:
            # If client ID is invalid, clear context
            st.session_state.chat_context = None
            st.error(f"Could not load client data for ID {selected_id}.")
    else:
        # If the user selects the placeholder, clear the context
        st.session_state.chat_context = None

    # If no valid context was loaded, reset the dropdown selection
    if st.session_state.chat_context is None:
        st.session_state.chat_page_client_selector = "placeholder"


def render_chat_ui():
    """
    This function previously rendered a quick chat component on all pages.
    It has been disabled as requested to remove the quick chat option
    while keeping the main Chat page intact.
    """
    # Function intentionally left empty to disable quick chat
    pass
