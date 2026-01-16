"""
GOA HTML Form Generation Pipeline Diagnostic Script

Tests the complete pipeline from PDF extraction to HTML generation
using templates/UME-23-0001CN-R5-V2.pdf as test data.

Run with: python test_pipeline_diagnosis.py
"""

import os
import sys
from pathlib import Path
import traceback
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def print_section(title: str):
    """Print a section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_step(step: str, status: str = ""):
    """Print a step with optional status."""
    if status:
        print(f"[{status}] {step}")
    else:
        print(f"\n>>> {step}")

def test_step1_pdf_extraction(pdf_path: Path) -> tuple:
    """Test Step 1: PDF Extraction"""
    print_section("STEP 1: PDF EXTRACTION")

    try:
        from utils.pdf_utils import extract_line_item_details, identify_machines_from_items
        print_step("Imports successful", "OK")

        # Extract line items
        print_step("Running extract_line_item_details()...")
        items = extract_line_item_details(str(pdf_path))
        print_step(f"Extracted {len(items)} line items", "OK")

        # Show sample items
        if items:
            print("\nSample items (first 3):")
            for i, item in enumerate(items[:3], 1):
                print(f"  {i}. {item.get('description', 'N/A')[:60]}... - ${item.get('unit_price', 0)}")

        # Identify machines
        print_step("Running identify_machines_from_items()...")
        machines_data = identify_machines_from_items(items)

        machines = machines_data.get('machines', [])
        common_items = machines_data.get('common_items', [])

        print_step(f"Identified {len(machines)} machines", "OK")
        print_step(f"Identified {len(common_items)} common items", "OK")

        if machines:
            print("\nMachines found:")
            for i, machine in enumerate(machines, 1):
                print(f"  {i}. {machine.get('machine_name', 'N/A')}")
                print(f"     Add-ons: {len(machine.get('add_ons', []))}")

        return machines_data, items, True

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return None, None, False

def test_step2_form_generator() -> tuple:
    """Test Step 2: Form Generator"""
    print_section("STEP 2: FORM GENERATOR")

    try:
        from utils.form_generator import extract_schema_from_excel, generate_goa_form
        print_step("Imports successful", "OK")

        excel_path = Path("templates/GOA_template.xlsx")
        if not excel_path.exists():
            print_step(f"Excel template not found: {excel_path}", "ERROR")
            return None, False

        # Extract schema
        print_step("Running extract_schema_from_excel()...")
        schema = extract_schema_from_excel(excel_path)  # Pass Path object, not string
        print_step(f"Extracted schema with {len(schema)} fields", "OK")

        # Show schema breakdown by section
        sections = {}
        for field_key, field_info in schema.items():
            section = field_info.get('section', 'Unknown')
            sections[section] = sections.get(section, 0) + 1

        print("\nFields by section:")
        for section, count in sorted(sections.items()):
            print(f"  {section}: {count} fields")

        # Show sample field names
        print("\nSample field names (first 5):")
        for i, (field_key, field_info) in enumerate(list(schema.items())[:5], 1):
            print(f"  {i}. {field_key}: {field_info.get('description', 'N/A')[:60]}")

        # Generate HTML form
        print_step("Running generate_goa_form()...")
        success = generate_goa_form()

        html_path = Path("templates/goa_form.html")
        if success and html_path.exists():
            size_kb = html_path.stat().st_size / 1024
            print_step(f"Generated HTML template ({size_kb:.1f} KB)", "OK")
        else:
            print_step("Failed to generate HTML template", "ERROR")
            return schema, False

        return schema, True

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return None, False

def test_step3_llm_setup() -> tuple:
    """Test Step 3: LLM Extraction Setup"""
    print_section("STEP 3: LLM EXTRACTION SETUP")

    try:
        from utils.llm_handler import configure_gemini_client
        from dotenv import load_dotenv
        print_step("Imports successful", "OK")

        # Try loading from .env
        load_dotenv()

        # Check API key
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print_step("GOOGLE_API_KEY not found in environment", "WARN")
            print("  NOTE: LLM extraction will be skipped")
            print("  To enable: Create .env file with GOOGLE_API_KEY=your_key_here")
            return False, "mock"

        print_step(f"GOOGLE_API_KEY found (length: {len(api_key)})", "OK")

        # Configure client
        print_step("Running configure_gemini_client()...")
        client = configure_gemini_client()

        if client:
            print_step("Gemini client configured successfully", "OK")
            return True, "real"
        else:
            print_step("Failed to configure Gemini client", "ERROR")
            return False, "real"

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return False, "real"

def get_pdf_full_text(pdf_path: Path) -> str:
    """Extract full text from PDF."""
    try:
        from utils.pdf_utils import extract_full_pdf_text
        print_step("Extracting full PDF text...")
        text = extract_full_pdf_text(str(pdf_path))
        print_step(f"Extracted {len(text)} characters", "OK")
        return text
    except Exception as e:
        print_step(f"Failed to extract PDF text: {e}", "WARN")
        return ""

def test_step4_llm_extraction(machines_data: Dict, items: List, pdf_path: Path) -> tuple:
    """Test Step 4: LLM Field Extraction"""
    print_section("STEP 4: LLM FIELD EXTRACTION")

    try:
        from utils.llm_handler import get_machine_specific_fields_via_llm
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from app import get_contexts_for_machine
        print_step("Imports successful", "OK")

        # Get first machine
        machines = machines_data.get('machines', [])
        if not machines:
            print_step("No machines found to process", "ERROR")
            return None, False

        machine = machines[0]
        machine_name = machine.get('machine_name', 'Unknown')
        print_step(f"Processing machine: {machine_name}")

        # Get full PDF text
        full_pdf_text = get_pdf_full_text(pdf_path)
        if not full_pdf_text:
            print_step("Warning: No PDF text extracted, using empty string", "WARN")

        # Get template contexts (pass full machine dict, not just name)
        print_step("Getting template contexts for machine...")
        template_contexts, template_file, is_sortstar = get_contexts_for_machine(machine)
        template_type = "SortStar" if is_sortstar else "Standard"
        print_step(f"Template type: {template_type}", "OK")

        # Get common items
        common_items = machines_data.get('common_items', [])

        # Call LLM extraction
        print_step("Running get_machine_specific_fields_via_llm()...")
        print("  (This may take 30-60 seconds...)")

        extracted_data = get_machine_specific_fields_via_llm(
            machine_data=machine,
            common_items=common_items,
            template_placeholder_contexts=template_contexts,
            full_pdf_text=full_pdf_text
        )

        if not extracted_data:
            print_step("LLM extraction returned empty data", "ERROR")
            return None, False

        # Analyze extracted data
        total_fields = len(extracted_data)
        non_empty_fields = sum(1 for v in extracted_data.values() if v and str(v).strip())
        empty_fields = total_fields - non_empty_fields

        print_step(f"Extracted {total_fields} total fields", "OK")
        print_step(f"  Non-empty: {non_empty_fields} ({non_empty_fields/total_fields*100:.1f}%)")
        print_step(f"  Empty: {empty_fields} ({empty_fields/total_fields*100:.1f}%)")

        # Show sample of extracted fields
        print("\nSample extracted fields (first 10 non-empty):")
        count = 0
        for field_name, value in extracted_data.items():
            if value and str(value).strip() and count < 10:
                value_str = str(value)[:60]
                if len(str(value)) > 60:
                    value_str += "..."
                print(f"  {field_name}: {value_str}")
                count += 1

        return extracted_data, True

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return None, False

def test_step5_html_filling(extracted_data: Dict) -> tuple:
    """Test Step 5: HTML Filling"""
    print_section("STEP 5: HTML FILLING")

    try:
        from utils.html_doc_filler import fill_and_generate_html
        print_step("Imports successful", "OK")

        template_path = Path("templates/goa_form.html")
        output_path = Path("test_output_goa.html")

        if not template_path.exists():
            print_step(f"Template not found: {template_path}", "ERROR")
            return None, False

        # Fill HTML
        print_step("Running fill_and_generate_html()...")
        success = fill_and_generate_html(
            template_path=str(template_path),
            data=extracted_data,
            output_path=str(output_path)
        )

        if not success:
            print_step("Failed to fill HTML template", "ERROR")
            return None, False

        if not output_path.exists():
            print_step(f"Output file not created: {output_path}", "ERROR")
            return None, False

        size_kb = output_path.stat().st_size / 1024
        print_step(f"Generated filled HTML ({size_kb:.1f} KB)", "OK")
        print_step(f"Output location: {output_path.absolute()}", "INFO")

        return output_path, True

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return None, False

def test_step6_validation(output_path: Path) -> bool:
    """Test Step 6: End-to-End Validation"""
    print_section("STEP 6: END-TO-END VALIDATION")

    try:
        from bs4 import BeautifulSoup
        print_step("Imports successful", "OK")

        # Read HTML
        print_step("Parsing generated HTML...")
        with open(output_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Count checkboxes
        all_checkboxes = soup.find_all('input', {'type': 'checkbox'})
        checked_checkboxes = [cb for cb in all_checkboxes if cb.get('checked')]

        print_step(f"Checkboxes: {len(checked_checkboxes)}/{len(all_checkboxes)} checked")

        # Count text inputs
        text_inputs = soup.find_all('input', {'type': 'text'})
        filled_text_inputs = [inp for inp in text_inputs if inp.get('value')]

        print_step(f"Text inputs: {len(filled_text_inputs)}/{len(text_inputs)} filled")

        # Count textareas
        textareas = soup.find_all('textarea')
        filled_textareas = [ta for ta in textareas if ta.string and ta.string.strip()]

        print_step(f"Textareas: {len(filled_textareas)}/{len(textareas)} filled")

        # Total fields
        total_fields = len(all_checkboxes) + len(text_inputs) + len(textareas)
        filled_fields = len(checked_checkboxes) + len(filled_text_inputs) + len(filled_textareas)

        if total_fields > 0:
            fill_percentage = (filled_fields / total_fields) * 100
            print_step(f"Overall: {filled_fields}/{total_fields} fields filled ({fill_percentage:.1f}%)", "OK")
        else:
            print_step("No fields found in HTML", "WARN")

        # Check for specific important fields
        print("\nChecking key fields:")
        key_fields = [
            'client_name',
            'machine_model',
            'production_speed',
            'voltage',
            'quote_reference'
        ]

        for field_name in key_fields:
            field_input = soup.find('input', {'name': field_name})
            if field_input:
                value = field_input.get('value', '')
                status = "OK" if value else "EMPTY"
                print_step(f"  {field_name}: {value[:50] if value else '(empty)'}", status)
            else:
                print_step(f"  {field_name}: Not found in HTML", "WARN")

        return True

    except Exception as e:
        print_step(f"FAILED: {str(e)}", "ERROR")
        traceback.print_exc()
        return False

def main():
    """Main diagnostic runner."""
    print_section("GOA HTML FORM GENERATION PIPELINE DIAGNOSTIC")
    print(f"Test PDF: templates/UME-23-0001CN-R5-V2.pdf")
    print(f"Working directory: {Path.cwd()}")

    # Check test PDF exists
    pdf_path = Path("templates/UME-23-0001CN-R5-V2.pdf")
    if not pdf_path.exists():
        print_step(f"Test PDF not found: {pdf_path}", "ERROR")
        print("Please ensure the file exists before running this test.")
        return

    # Track results
    results = {
        'step1_pdf_extraction': False,
        'step2_form_generator': False,
        'step3_llm_setup': False,
        'step4_llm_extraction': False,
        'step5_html_filling': False,
        'step6_validation': False
    }

    # Step 1: PDF Extraction
    machines_data, items, success = test_step1_pdf_extraction(pdf_path)
    results['step1_pdf_extraction'] = success

    # Step 2: Form Generator
    schema, success = test_step2_form_generator()
    results['step2_form_generator'] = success

    # Step 3: LLM Setup
    llm_success, llm_mode = test_step3_llm_setup()
    results['step3_llm_setup'] = llm_success

    # Step 4: LLM Extraction (only if we have machines and LLM is set up)
    extracted_data = None
    if results['step1_pdf_extraction'] and results['step3_llm_setup'] and machines_data:
        extracted_data, success = test_step4_llm_extraction(machines_data, items, pdf_path)
        results['step4_llm_extraction'] = success
    elif results['step1_pdf_extraction'] and llm_mode == "mock" and machines_data and schema:
        # Create mock data for testing HTML filling using actual field placeholders
        print_section("STEP 4: LLM FIELD EXTRACTION (MOCK MODE)")
        print_step("Creating mock extracted data for testing...", "INFO")
        machine = machines_data.get('machines', [])[0]

        # Use actual field placeholders from schema
        extracted_data = {}
        sample_values = {
            'client': 'Test Client Inc.',
            'machine': machine.get('machine_name', 'Unknown'),
            'speed': '100 BPM',
            'voltage': '380V 3Ph 60Hz',
            'quote': 'UME-23-0001CN-R5-V2',
            'container': 'PET Bottle',
            'size': '500ml',
        }

        # Map some common fields using schema keys
        for field_key, field_info in list(schema.items())[:20]:
            desc = field_info.get('description', '').lower()
            field_type = field_info.get('type', 'string')

            if field_type == 'boolean':
                # Set some checkboxes to true for testing
                if 'standard' in desc or 'include' in desc:
                    extracted_data[field_key] = True
            else:
                # Set text fields based on description keywords
                if 'client' in desc or 'customer' in desc:
                    extracted_data[field_key] = sample_values['client']
                elif 'machine' in desc or 'model' in desc:
                    extracted_data[field_key] = sample_values['machine']
                elif 'speed' in desc or 'production' in desc:
                    extracted_data[field_key] = sample_values['speed']
                elif 'voltage' in desc or 'electrical' in desc:
                    extracted_data[field_key] = sample_values['voltage']
                elif 'quote' in desc or 'reference' in desc:
                    extracted_data[field_key] = sample_values['quote']
                elif 'container' in desc:
                    extracted_data[field_key] = sample_values['container']

        print_step(f"Created {len(extracted_data)} mock fields from schema", "OK")
        results['step4_llm_extraction'] = True
    else:
        print_section("STEP 4: LLM FIELD EXTRACTION")
        print_step("Skipped (prerequisites not met)", "SKIP")

    # Step 5: HTML Filling (only if we have extracted data)
    output_path = None
    if results['step4_llm_extraction'] and extracted_data:
        output_path, success = test_step5_html_filling(extracted_data)
        results['step5_html_filling'] = success
    else:
        print_section("STEP 5: HTML FILLING")
        print_step("Skipped (prerequisites not met)", "SKIP")

    # Step 6: Validation (only if we have output)
    if results['step5_html_filling'] and output_path:
        success = test_step6_validation(output_path)
        results['step6_validation'] = success
    else:
        print_section("STEP 6: END-TO-END VALIDATION")
        print_step("Skipped (prerequisites not met)", "SKIP")

    # Final summary
    print_section("DIAGNOSTIC SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("\nTest Results:")
    for step, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {step}")

    print(f"\nOverall: {passed}/{total} steps passed ({passed/total*100:.1f}%)")

    if passed == total:
        print_step("All tests passed! Pipeline is working correctly.", "SUCCESS")
    else:
        print_step("Some tests failed. Check errors above for details.", "WARNING")

        # Identify first failure point
        for step, success in results.items():
            if not success:
                print(f"\nFirst failure at: {step}")
                print("This is where the pipeline is breaking.")
                break

    print("\n" + "="*80)
    print("Diagnostic complete.")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
