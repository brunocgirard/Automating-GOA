import os
import json
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical, enhance_placeholder_context_with_outline
from src.utils.llm_handler import apply_post_processing_rules

def test_enhanced_synonyms():
    """Test the enhanced synonym detection for checkboxes"""
    print("\n=== Testing Enhanced Synonym Detection ===")
    # Create a mock schema entry for a checkbox field
    mock_schema = {
        "explosion_proof_check": {
            "type": "boolean",
            "section": "Control & Programming Specifications",
            "description": "Explosion Proof"
        }
    }
    
    # Create test data with a value that needs correction
    test_data = {"explosion_proof_check": "yes"}  # Lowercase 'yes' should be corrected to uppercase
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, mock_schema)
    
    # Print the result
    print(f"Original value: {test_data['explosion_proof_check']}")
    print(f"Corrected value: {corrected_data['explosion_proof_check']}")
    print(f"Test passed: {corrected_data['explosion_proof_check'] == 'YES'}")

def test_hmi_rule():
    """Test the rule that only one HMI size should be selected"""
    print("\n=== Testing HMI Size Rule ===")
    # Create test data with multiple HMI sizes selected
    test_data = {
        "hmi_10_check": "YES",
        "hmi_15_check": "YES",
        "hmi_5_7_check": "NO"
    }
    
    # Create a mock schema
    mock_schema = {
        "hmi_10_check": {"type": "boolean", "section": "HMI", "description": "10 inch HMI"},
        "hmi_15_check": {"type": "boolean", "section": "HMI", "description": "15 inch HMI"},
        "hmi_5_7_check": {"type": "boolean", "section": "HMI", "description": "5.7 inch HMI"}
    }
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, mock_schema)
    
    # Print the result
    print(f"Original values: 10\"={test_data['hmi_10_check']}, 15\"={test_data['hmi_15_check']}")
    print(f"Corrected values: 10\"={corrected_data['hmi_10_check']}, 15\"={corrected_data['hmi_15_check']}")
    
    # Check if only one HMI size is selected
    hmi_yes_count = sum(1 for k, v in corrected_data.items() if k.startswith('hmi_') and v == 'YES')
    print(f"Number of HMI sizes set to YES: {hmi_yes_count}")
    print(f"Test passed - Only one HMI size is YES: {hmi_yes_count == 1}")
    
    # Check if the larger size was preferred
    print(f"Test passed - Larger size preferred: {corrected_data['hmi_15_check'] == 'YES' and corrected_data['hmi_10_check'] == 'NO'}")
    
    # Try alternative HMI field patterns
    print("\nTesting alternative HMI field patterns:")
    alt_test_data = {
        "touch_screen_10inch_check": "YES",
        "touch_screen_15inch_check": "YES"
    }
    
    alt_corrected_data = apply_post_processing_rules(alt_test_data, {})
    print(f"Original values: 10inch={alt_test_data['touch_screen_10inch_check']}, 15inch={alt_test_data['touch_screen_15inch_check']}")
    print(f"Corrected values: 10inch={alt_corrected_data['touch_screen_10inch_check']}, 15inch={alt_corrected_data['touch_screen_15inch_check']}")
    
    alt_yes_count = sum(1 for k, v in alt_corrected_data.items() if ('touch' in k or 'screen' in k) and v == 'YES')
    print(f"Number of touch screen sizes set to YES: {alt_yes_count}")
    print(f"Test passed - Only one touch screen size is YES: {alt_yes_count == 1}")
    print(f"Test passed - Larger size preferred: {alt_corrected_data['touch_screen_15inch_check'] == 'YES' and alt_corrected_data['touch_screen_10inch_check'] == 'NO'}")

def test_voltage_formatting():
    """Test the voltage formatting rule"""
    print("\n=== Testing Voltage Formatting ===")
    # Create test data with voltage values that need formatting
    test_data = {
        "voltage": "220",  # Should be converted to a range
        "hz": "50",        # Should add Hz
        "psi": "80"        # Should add PSI
    }
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, {})
    
    # Print the result
    print(f"Original voltage: '{test_data['voltage']}'")
    print(f"Corrected voltage: '{corrected_data['voltage']}'")
    print(f"Original Hz: '{test_data['hz']}'")
    print(f"Corrected Hz: '{corrected_data['hz']}'")
    print(f"Original PSI: '{test_data['psi']}'")
    print(f"Corrected PSI: '{corrected_data['psi']}'")
    
    # Check if corrections were applied
    voltage_corrected = corrected_data['voltage'] != test_data['voltage'] and 'V' in corrected_data['voltage']
    hz_corrected = corrected_data['hz'] != test_data['hz'] and 'Hz' in corrected_data['hz']
    psi_corrected = corrected_data['psi'] != test_data['psi'] and 'PSI' in corrected_data['psi']
    
    print(f"Test passed: {voltage_corrected and hz_corrected and psi_corrected}")

def test_beacon_light_rule():
    """Test the rule for multi-color beacon lights"""
    print("\n=== Testing Beacon Light Rule ===")
    # Create test data with a multi-color beacon indication
    test_data = {
        "beacon_tri_color_check": "YES",
        "beacon_red_check": "NO",
        "beacon_amber_check": "NO",
        "beacon_green_check": "NO"
    }
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, {})
    
    # Print the result
    print(f"Original values: Red={test_data['beacon_red_check']}, Amber={test_data['beacon_amber_check']}, Green={test_data['beacon_green_check']}")
    print(f"Corrected values: Red={corrected_data['beacon_red_check']}, Amber={corrected_data['beacon_amber_check']}, Green={corrected_data['beacon_green_check']}")
    all_lights_on = (corrected_data['beacon_red_check'] == 'YES' and 
                     corrected_data['beacon_amber_check'] == 'YES' and 
                     corrected_data['beacon_green_check'] == 'YES')
    print(f"Test passed: All beacon colors enabled = {all_lights_on}")

def test_production_speed_synonyms():
    """Test that projected speed is correctly recognized as production_speed"""
    print("\n=== Testing Production/Projected Speed Synonyms ===")
    
    # Create test data with 'projected speed' instead of 'production_speed'
    test_data = {
        "production_speed": "50"  # Missing units
    }
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, {})
    
    # Print the result
    print(f"Original value: '{test_data['production_speed']}'")
    print(f"Corrected value: '{corrected_data['production_speed']}'")
    
    # Check if units were added
    has_units = any(unit in corrected_data['production_speed'].lower() for unit in ['units', 'bottles', 'per minute', '/min'])
    print(f"Test passed - Units added: {has_units}")

def test_performance():
    """Test the performance of the post-processing rules function"""
    print("\n=== Testing Post-Processing Performance ===")
    
    # Create a larger test dataset to measure performance
    large_test_data = {}
    for i in range(1, 101):  # Create 100 fields
        if i % 3 == 0:  # Make every third field a checkbox
            large_test_data[f"test_field_{i}_check"] = "yes" if i % 2 == 0 else "no"
        else:
            large_test_data[f"test_field_{i}"] = f"Value {i}"
    
    # Add specific fields that trigger various rules
    large_test_data.update({
        "voltage": "220",
        "hz": "50",
        "psi": "75",
        "production_speed": "60",
        "hmi_10_check": "YES",
        "hmi_15_check": "YES",
        "plc_b&r_check": "YES",
        "plc_allen_bradley_check": "YES",
        "beacon_tri_color_check": "YES",
        "beacon_red_check": "NO",
        "beacon_green_check": "NO",
        "beacon_amber_check": "NO",
        "explosion_proof_check": "YES"
    })
    
    # Time the function execution
    import time
    start_time = time.time()
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(large_test_data, {})
    
    execution_time = time.time() - start_time
    print(f"Processed {len(large_test_data)} fields in {execution_time:.4f} seconds")
    print(f"Average time per field: {(execution_time * 1000) / len(large_test_data):.4f} ms")
    
    # Verify a few key corrections were made
    print("\nVerifying key corrections:")
    print(f"Voltage: '{corrected_data['voltage']}'")
    print(f"HMI 15 check: '{corrected_data['hmi_15_check']}', HMI 10 check: '{corrected_data['hmi_10_check']}'")
    print(f"Beacon lights all on: {corrected_data['beacon_red_check'] == 'YES' and corrected_data['beacon_green_check'] == 'YES' and corrected_data['beacon_amber_check'] == 'YES'}")

def test_context_enhancement():
    """Test the context enhancement using outline file"""
    print("\n=== Testing Context Enhancement ===")
    
    # Check if template file exists
    template_path = "templates/template.docx"
    outline_path = "full_fields_outline.md"
    
    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return
    
    if not os.path.exists(outline_path):
        print(f"Outline file not found: {outline_path}")
        return
    
    # Extract contexts without enhancement
    print("Extracting contexts without enhancement...")
    regular_contexts = extract_placeholder_context_hierarchical(template_path, enhance_with_outline=False)
    
    # Extract contexts with enhancement
    print("Extracting contexts with enhancement...")
    enhanced_contexts = extract_placeholder_context_hierarchical(template_path, enhance_with_outline=True, outline_path=outline_path)
    
    # Compare the results
    regular_count = len(regular_contexts)
    enhanced_count = len(enhanced_contexts)
    
    print(f"Regular context count: {regular_count}")
    print(f"Enhanced context count: {enhanced_count}")
    
    # Sample a few fields to compare
    sample_fields = []
    sample_count = 0
    
    for key in regular_contexts.keys():
        if key.endswith("_check") and sample_count < 5:
            sample_fields.append(key)
            sample_count += 1
    
    print("\nSample field comparison:")
    for field in sample_fields:
        print(f"Field: {field}")
        print(f"  Regular context: {regular_contexts.get(field, 'N/A')}")
        print(f"  Enhanced context: {enhanced_contexts.get(field, 'N/A')}")
        print("")

if __name__ == "__main__":
    print("Testing enhancement functionalities...")
    
    # Run tests
    test_enhanced_synonyms()
    test_hmi_rule()
    test_voltage_formatting()
    test_beacon_light_rule()
    test_production_speed_synonyms()
    test_performance()
    test_context_enhancement()
    
    print("\nAll tests completed!") 