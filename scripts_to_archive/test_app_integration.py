"""
Demo script showing how to use the enhanced features in the context of the app.
This simulates a workflow similar to what happens in app.py, but in a simplified form.
"""
import os
import json
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical
from src.utils.llm_handler import apply_post_processing_rules, get_all_fields_via_llm

def demonstrate_enhanced_workflow():
    """
    Demonstrate how the enhanced features would be used in the app workflow
    """
    print("=== GOA Template Processing with Enhanced Features ===")
    
    # 1. Check if template file exists
    template_path = "templates/template.docx"
    outline_path = "full_fields_outline.md"
    
    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return
    
    if not os.path.exists(outline_path):
        print(f"Outline file not found: {outline_path}")
        return
    
    # 2. Extract placeholders and context (with enhancement)
    print("\nExtracting context with enhancement...")
    enhanced_contexts = extract_placeholder_context_hierarchical(
        template_path, 
        enhance_with_outline=True,
        outline_path=outline_path
    )
    
    # 3. Create sample data
    print("\nCreating sample data as if it came from the LLM...")
    sample_data = {
        # Customer information
        "customer_name": "Acme Pharmaceuticals",
        "machine_model": "AutoFill 3000",
        "production_speed": "60",  # Missing units
        
        # Checkboxes with mixed casing (will be normalized)
        "explosion_proof_check": "yes",  # Lowercase
        "hmi_10_check": "YES",
        "hmi_15_check": "YES",  # Multiple HMI sizes (conflict)
        "plc_b&r_check": "YES",
        "plc_allen_bradley_check": "YES",  # Multiple PLC types (conflict)
        
        # Utility specifications
        "voltage": "220",  # Missing V
        "hz": "50",        # Missing Hz
        "psi": "80",       # Missing PSI
        
        # Multi-color beacon indicators
        "beacon_tri_color_check": "YES",
        "beacon_red_check": "NO",
        "beacon_green_check": "NO",
        "beacon_amber_check": "NO"
    }
    
    # 4. Apply post-processing rules
    print("\nApplying post-processing rules...")
    corrected_data = apply_post_processing_rules(sample_data, enhanced_contexts)
    
    # 5. Display results
    print("\n=== Results of Enhanced Processing ===")
    
    # Show the corrections for customer information
    print("\nCustomer Information:")
    print(f"Customer Name: {corrected_data['customer_name']}")
    print(f"Machine Model: {corrected_data['machine_model']}")
    print(f"Production Speed: {corrected_data['production_speed']}")
    
    # Show HMI size conflict resolution
    print("\nHMI Size Conflict Resolution:")
    print(f"10\" HMI: {corrected_data['hmi_10_check']}")
    print(f"15\" HMI: {corrected_data['hmi_15_check']}")
    
    # Show PLC type conflict resolution
    print("\nPLC Type Conflict Resolution:")
    print(f"B&R PLC: {corrected_data['plc_b&r_check']}")
    print(f"Allen Bradley PLC: {corrected_data['plc_allen_bradley_check']}")
    
    # Show utility specifications formatting
    print("\nUtility Specifications Formatting:")
    print(f"Voltage: {corrected_data['voltage']}")
    print(f"Frequency: {corrected_data['hz']}")
    print(f"Air Pressure: {corrected_data['psi']}")
    
    # Show beacon light handling
    print("\nBeacon Light Handling:")
    print(f"Tri-color Beacon: {corrected_data['beacon_tri_color_check']}")
    print(f"Red Beacon: {corrected_data['beacon_red_check']}")
    print(f"Green Beacon: {corrected_data['beacon_green_check']}")
    print(f"Amber Beacon: {corrected_data['beacon_amber_check']}")
    
    # Show explosion-proof related changes
    print("\nExplosion-Proof Related Changes:")
    print(f"Explosion Proof: {corrected_data['explosion_proof_check']}")
    
    print("\n=== How These Enhancements Improve the App ===")
    print("1. Enhanced context extraction improves field recognition in complex templates")
    print("2. Comprehensive synonym detection helps match industry terminology in quotes")
    print("3. Post-processing rules ensure data consistency and correct common errors")
    print("4. Domain-specific section guidance helps the LLM understand template sections")
    print("5. Special rules handle industry-specific requirements like explosion-proof environments")

if __name__ == "__main__":
    demonstrate_enhanced_workflow() 