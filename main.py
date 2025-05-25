import argparse
import os
import json
from typing import Dict, List
import traceback

from src.utils.pdf_utils import extract_selected_item_descriptions, extract_full_pdf_text
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical
from src.utils.llm_handler import configure_gemini_client, get_all_fields_via_llm, get_llm_chat_update
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.crm_utils import init_db, save_client_info

def main():
    parser = argparse.ArgumentParser(description="Extract info from PDF, use LLM to map to template, and fill Word doc.")
    parser.add_argument("--pdf", required=True, help="Path to the input PDF file")
    parser.add_argument("--output", required=True, help="Path to save the output Word document")
    parser.add_argument("--template", default="template.docx", help="Path to the Word template (optional)")
    args = parser.parse_args()

    # --- Input Validation & DB Init ---
    if not os.path.exists(args.pdf):
        print(f"Error: Input PDF file not found at {args.pdf}")
        return
    if not os.path.exists(args.template):
        print(f"Error: Template file not found at {args.template}")
        return

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as e:
            print(f"Error creating output directory {output_dir}: {e}")
            return
            
    init_db()

    # --- Processing Steps ---
    try:
        # 0. Configure LLM Client
        if not configure_gemini_client(): return

        # 1. Extract data from PDF
        print(f"Processing PDF: {args.pdf}...")
        selected_descriptions = extract_selected_item_descriptions(args.pdf)
        full_text_data = extract_full_pdf_text(args.pdf)
        if not selected_descriptions:
            print("Warning: No selected item descriptions were extracted from PDF tables.")
        if not full_text_data:
             print("Error: Could not extract full text from PDF. This is required for LLM processing.")
             return

        # 2. Get placeholder information from the template
        print(f"\nAnalyzing template: {args.template}...")
        all_template_placeholders = extract_placeholders(args.template)
        placeholder_contexts_from_template = extract_placeholder_context_hierarchical(args.template)
        if not placeholder_contexts_from_template:
             print("Error: Could not extract placeholder contexts from the template.")
             return
        
        # 3. Get LLM completions for ALL fields
        print("\nQuerying LLM for all template field values...")
        # Initialize final_data with all placeholders defaulted
        final_data = {ph: ("NO" if ph.endswith("_check") else "") for ph in all_template_placeholders}
        
        llm_extracted_data = get_all_fields_via_llm(
            selected_descriptions,
            placeholder_contexts_from_template,
            full_text_data
        )
        final_data.update(llm_extracted_data)

        print("\nFinal Data to be filled (after LLM processing):")
        print(json.dumps(final_data, indent=2))

        # 4. Fill the Word document
        print(f"\nFilling Word document: {args.output}...")
        fill_word_document_from_llm_data(args.template, final_data, args.output)
        print(f"Successfully created filled document: {args.output}")

        # --- Save to CRM ---
        print("\nSaving extracted information to CRM...")
        # Prepare data for CRM. Ensure keys match what save_client_info expects
        # and what is actually present in final_data from LLM output.
        crm_data_to_save = {
            "quote_ref": final_data.get("quote", ""), # Assuming 'quote' is the placeholder for quote_ref
            "customer_name": final_data.get("customer", ""),
            "machine_model": final_data.get("machine", ""),
            "country_destination": final_data.get("country", "")
            # Add other direct fields if the LLM is expected to extract them
        }
        if not crm_data_to_save["quote_ref"]:
            print("Warning: Quote Reference (quote_ref) is missing. Cannot save to CRM without it.")
        else:
            selected_descs_json = json.dumps(selected_descriptions)
            llm_data_json = json.dumps(final_data) # Save the entire filled data
            if save_client_info(crm_data_to_save, selected_descs_json, llm_data_json):
                print(f"CRM data for quote '{crm_data_to_save['quote_ref']}' saved/updated.")
            else:
                print(f"Failed to save CRM data for quote '{crm_data_to_save['quote_ref']}'.")
        # ---------------------

    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 