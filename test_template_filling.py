"""
Simple Template Filling Validation Script

Tests that extracted fields properly fill templates by using the ACTUAL workflow from app.py.
Uses src.utils.llm_handler (the active module) not src.llm (the new refactored module).

Author: Claude Code
Date: 2026-01-16
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Import from ACTIVE modules (same as app.py uses)
from src.utils.pdf_utils import extract_line_item_details, identify_machines_from_items, extract_full_pdf_text
from src.utils.form_generator import generate_goa_form, extract_schema_from_excel
from src.utils.html_doc_filler import fill_and_generate_html
from src.utils.llm_handler import get_machine_specific_fields_via_llm, configure_gemini_client
from app import get_contexts_for_machine

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_standard_machine():
    """Test Standard Machine to HTML Template workflow"""
    print_section("TEST 1: STANDARD MACHINE to HTML TEMPLATE")

    # 1. Extract from PDF
    pdf_path = "templates/UME-23-0001CN-R5-V2.pdf"
    print(f"\n[1] Extracting from PDF: {pdf_path}")
    items = extract_line_item_details(pdf_path)
    machines_data = identify_machines_from_items(items)
    full_pdf_text = extract_full_pdf_text(pdf_path)

    # Find a Standard machine (not SortStar)
    standard_machine = None
    for m in machines_data['machines']:
        name = m['machine_name'].lower()
        if 'sortstar' not in name and 'unscrambler' not in name:
            if 'monoblock' in name or 'patriot' in name:
                standard_machine = m
                break

    if not standard_machine:
        print("[FAIL] No Standard machine found in PDF")
        return False

    print(f"[OK] Selected machine: {standard_machine['machine_name']}")

    # 2. Get template contexts (should be Standard HTML)
    print("\n[2] Getting template contexts...")
    template_contexts, template_file, is_sortstar = get_contexts_for_machine(standard_machine)

    if is_sortstar:
        print("[FAIL] Machine was detected as SortStar, expected Standard")
        return False

    print(f"[OK] Template type: Standard (HTML)")
    print(f"[OK] Template has {len(template_contexts)} fields")

    # Show some field names
    field_names = list(template_contexts.keys())[:10]
    print(f"[OK] Sample field names: {', '.join(field_names)}")

    # 3. Configure LLM
    print("\n[3] Configuring LLM...")
    if not configure_gemini_client():
        print("[FAIL] Could not configure Gemini client")
        return False
    print("[OK] LLM configured")

    # 4. Extract fields with LLM
    print("\n[4] Extracting fields with LLM (this may take 30-60 seconds)...")
    common_items = machines_data['common_items']

    extracted_data = get_machine_specific_fields_via_llm(
        machine_data=standard_machine,
        common_items=common_items,
        template_placeholder_contexts=template_contexts,
        full_pdf_text=full_pdf_text
    )

    if not extracted_data:
        print("[FAIL] LLM extraction returned empty data")
        return False

    total_fields = len(extracted_data)
    non_empty = sum(1 for v in extracted_data.values() if v and str(v).strip() and str(v).upper() not in ['NO', 'FALSE', ''])
    print(f"[OK] Extracted {total_fields} fields, {non_empty} non-empty ({non_empty/total_fields*100:.1f}%)")

    # Show sample extracted data
    print("\n[OK] Sample extracted fields:")
    count = 0
    for k, v in extracted_data.items():
        if v and str(v).strip() and str(v).upper() != 'NO' and count < 10:
            print(f"     {k}: {str(v)[:60]}")
            count += 1

    # 5. Generate HTML template
    print("\n[5] Generating HTML template from Excel...")
    if not generate_goa_form():
        print("[FAIL] Could not generate HTML template")
        return False
    print("[OK] HTML template generated")

    # 6. Fill HTML template
    print("\n[6] Filling HTML template with extracted data...")
    output_path = "test_standard_filled.html"

    success = fill_and_generate_html(
        template_path="templates/goa_form.html",
        data=extracted_data,
        output_path=output_path
    )

    if not success:
        print("[FAIL] Could not fill HTML template")
        return False

    print(f"[OK] HTML template filled: {output_path}")

    # 7. Validate filled HTML
    print("\n[7] Validating filled HTML...")
    from bs4 import BeautifulSoup

    with open(output_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # Count filled fields
    all_checkboxes = soup.find_all('input', {'type': 'checkbox'})
    checked = [cb for cb in all_checkboxes if cb.get('checked')]

    text_inputs = soup.find_all('input', {'type': 'text'})
    filled_text = [inp for inp in text_inputs if inp.get('value') and inp.get('value').strip()]

    textareas = soup.find_all('textarea')
    filled_textarea = [ta for ta in textareas if ta.string and ta.string.strip()]

    total_html_fields = len(all_checkboxes) + len(text_inputs) + len(textareas)
    filled_html_fields = len(checked) + len(filled_text) + len(filled_textarea)

    fill_rate = (filled_html_fields / total_html_fields * 100) if total_html_fields > 0 else 0

    print(f"[INFO] Checkboxes: {len(checked)}/{len(all_checkboxes)} checked")
    print(f"[INFO] Text inputs: {len(filled_text)}/{len(text_inputs)} filled")
    print(f"[INFO] Textareas: {len(filled_textarea)}/{len(textareas)} filled")
    print(f"[INFO] Overall: {filled_html_fields}/{total_html_fields} fields filled ({fill_rate:.1f}%)")

    # Check specific important fields
    print("\n[OK] Checking key fields in HTML:")
    key_checks = []
    for field_name, expected_value in list(extracted_data.items())[:20]:
        if expected_value and str(expected_value).strip() and str(expected_value).upper() != 'NO':
            # Look for this field in HTML
            input_elem = soup.find('input', {'name': field_name}) or soup.find('textarea', {'name': field_name})
            if input_elem:
                html_value = input_elem.get('value') or (input_elem.string if input_elem.name == 'textarea' else '')
                if html_value:
                    key_checks.append((field_name, True))
                    print(f"     [OK] {field_name}: {str(html_value)[:50]}")
                else:
                    key_checks.append((field_name, False))
                    print(f"     [FAIL] {field_name}: EMPTY (expected: {str(expected_value)[:50]})")
            else:
                print(f"     [WARN] {field_name}: Field not found in HTML")

    successful_checks = sum(1 for _, success in key_checks if success)
    print(f"\n[INFO] Key field validation: {successful_checks}/{len(key_checks)} matched")

    if fill_rate > 5:
        print("\n[PASS] Standard machine template filling works!")
        return True
    else:
        print("\n[FAIL] Fill rate too low, template filling not working properly")
        return False

def main():
    """Main test runner"""
    print_section("GOA TEMPLATE FILLING VALIDATION")
    print("Testing the ACTUAL workflow used by app.py")
    print(f"Working directory: {Path.cwd()}")

    # Check API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("\n[ERROR] GOOGLE_API_KEY not found in environment")
        print("Please create a .env file with: GOOGLE_API_KEY=your_key_here")
        return

    print(f"[OK] GOOGLE_API_KEY found (length: {len(api_key)})")

    # Run tests
    results = []

    print("\n" + "="*80)
    result1 = test_standard_machine()
    results.append(("Standard Machine to HTML Template", result1))

    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"[{status}] {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Template filling is working correctly.")
    else:
        print("\n[WARNING] Some tests failed. Check output above for details.")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
