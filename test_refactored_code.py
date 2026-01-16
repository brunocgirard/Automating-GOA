"""
Test script for refactored src/llm module.

This tests the same workflow as test_template_filling.py but using the refactored code.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Import from REFACTORED modules
from src.utils.pdf_utils import extract_line_item_details, identify_machines_from_items, extract_full_pdf_text
from src.utils.form_generator import generate_goa_form
from src.utils.html_doc_filler import fill_and_generate_html
from src.llm import get_machine_specific_fields_via_llm, configure_gemini_client
from app import get_contexts_for_machine

def test_refactored():
    """Test that the refactored code works end-to-end"""
    print("\n" + "="*80)
    print("  TESTING REFACTORED src/llm MODULE")
    print("="*80)

    # 1. Extract from PDF
    pdf_path = "templates/UME-23-0001CN-R5-V2.pdf"
    print(f"\n[1] Extracting from PDF: {pdf_path}")
    items = extract_line_item_details(pdf_path)
    machines_data = identify_machines_from_items(items)
    full_pdf_text = extract_full_pdf_text(pdf_path)

    # Find Standard machine
    standard_machine = None
    for m in machines_data['machines']:
        name = m['machine_name'].lower()
        if 'sortstar' not in name and 'unscrambler' not in name:
            if 'monoblock' in name or 'patriot' in name:
                standard_machine = m
                break

    if not standard_machine:
        print("[FAIL] No Standard machine found")
        return False

    print(f"[OK] Selected: {standard_machine['machine_name']}")

    # 2. Get template contexts
    print("\n[2] Getting template contexts...")
    template_contexts, template_file, is_sortstar = get_contexts_for_machine(standard_machine)
    print(f"[OK] Template type: {'SortStar' if is_sortstar else 'Standard'} ({len(template_contexts)} fields)")

    # 3. Configure LLM
    print("\n[3] Configuring LLM...")
    if not configure_gemini_client():
        print("[FAIL] Could not configure Gemini")
        return False
    print("[OK] LLM configured")

    # 4. Extract with refactored code
    print("\n[4] Extracting with REFACTORED src/llm module...")
    common_items = machines_data['common_items']

    extracted_data = get_machine_specific_fields_via_llm(
        machine_data=standard_machine,
        common_items=common_items,
        template_placeholder_contexts=template_contexts,
        full_pdf_text=full_pdf_text
    )

    if not extracted_data:
        print("[FAIL] Extraction returned empty")
        return False

    total = len(extracted_data)
    non_empty = sum(1 for v in extracted_data.values() if v and str(v).strip() and str(v).upper() != 'NO')
    print(f"[OK] Extracted {total} fields, {non_empty} non-empty ({non_empty/total*100:.1f}%)")

    # 5. Generate and fill HTML
    print("\n[5] Generating HTML template...")
    if not generate_goa_form():
        print("[FAIL] Could not generate HTML")
        return False
    print("[OK] HTML generated")

    print("\n[6] Filling HTML template...")
    output_path = "test_refactored_output.html"
    success = fill_and_generate_html(
        template_path="templates/goa_form.html",
        data=extracted_data,
        output_path=output_path
    )

    if not success:
        print("[FAIL] Could not fill HTML")
        return False

    print(f"[OK] HTML filled: {output_path}")

    # 7. Validate
    print("\n[7] Validating...")
    from bs4 import BeautifulSoup

    with open(output_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    all_checkboxes = soup.find_all('input', {'type': 'checkbox'})
    checked = [cb for cb in all_checkboxes if cb.get('checked')]

    text_inputs = soup.find_all('input', {'type': 'text'})
    filled_text = [inp for inp in text_inputs if inp.get('value') and inp.get('value').strip()]

    total_fields = len(all_checkboxes) + len(text_inputs)
    filled_fields = len(checked) + len(filled_text)

    fill_rate = (filled_fields / total_fields * 100) if total_fields > 0 else 0

    print(f"[INFO] Checkboxes: {len(checked)}/{len(all_checkboxes)} checked")
    print(f"[INFO] Text inputs: {len(filled_text)}/{len(text_inputs)} filled")
    print(f"[INFO] Overall: {filled_fields}/{total_fields} fields filled ({fill_rate:.1f}%)")

    if fill_rate > 5:
        print("\n[SUCCESS] Refactored code works correctly!")
        return True
    else:
        print("\n[FAIL] Fill rate too low")
        return False

if __name__ == "__main__":
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY not found in .env")
        sys.exit(1)

    print(f"[OK] GOOGLE_API_KEY found (length: {len(api_key)})")

    result = test_refactored()
    sys.exit(0 if result else 1)
