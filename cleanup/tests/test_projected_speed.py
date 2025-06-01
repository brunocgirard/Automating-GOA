from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical, generate_synonyms_for_checkbox
from src.utils.llm_handler import apply_post_processing_rules

def test_projected_speed_handling():
    """Test that the system properly handles 'projected speed' as equivalent to 'production_speed'"""
    print("\n=== Testing Projected Speed Handling ===")
    
    # 1. Test the synonym dictionary
    print("Checking synonym dictionary...")
    synonyms = generate_synonyms_for_checkbox("production_speed", "Production Speed")
    has_projected_speed = "projected speed" in synonyms
    print(f"'projected speed' is in synonyms list: {has_projected_speed}")
    print(f"All synonyms for production_speed: {', '.join(synonyms)}")
    
    # 2. Test the post-processing handling
    print("\nTesting post-processing for production_speed...")
    
    # Create test data with bare numeric value
    test_data = {
        "production_speed": "75"  # Missing units
    }
    
    # Apply post-processing rules
    corrected_data = apply_post_processing_rules(test_data, {})
    
    # Print the result
    print(f"Original value: '{test_data['production_speed']}'")
    print(f"Corrected value: '{corrected_data['production_speed']}'")
    
    # Check if units were added
    has_units = any(unit in corrected_data['production_speed'].lower() for unit in ['units', 'bottles', 'per minute', '/min'])
    print(f"Test passed - Units added: {has_units}")
    
    # 3. Test with bottle reference
    print("\nTesting with bottle reference...")
    test_data_with_bottle = {
        "production_speed": "60",
        "bottle_size": "500ml"  # This should trigger bottles instead of units
    }
    
    corrected_data_with_bottle = apply_post_processing_rules(test_data_with_bottle, {})
    print(f"Original value: '{test_data_with_bottle['production_speed']}'")
    print(f"Corrected value: '{corrected_data_with_bottle['production_speed']}'")
    
    has_bottle_reference = "bottle" in corrected_data_with_bottle['production_speed'].lower()
    print(f"Test passed - Bottle reference added: {has_bottle_reference}")
    
    print("\nTest results summary:")
    print(f"1. 'projected speed' in synonym list: {has_projected_speed}")
    print(f"2. Basic units added to numeric value: {has_units}")
    print(f"3. Bottle-specific units added when relevant: {has_bottle_reference}")
    print(f"Overall test passed: {has_projected_speed and has_units}")

if __name__ == "__main__":
    test_projected_speed_handling() 