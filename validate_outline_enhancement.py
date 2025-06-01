import os
import sys
from src.utils.template_utils import extract_placeholder_context_hierarchical, enhance_placeholder_context_with_outline

def analyze_outline_enhancement():
    """
    Analyze why the outline enhancement isn't working effectively
    """
    template_path = "templates/template.docx"
    outline_path = "full_fields_outline.md"
    
    print(f"Analyzing outline enhancement with template: {template_path}")
    print(f"Using outline file: {outline_path}")
    
    # Make sure both files exist
    if not os.path.exists(template_path):
        print(f"Error: Template file {template_path} not found")
        return
    
    if not os.path.exists(outline_path):
        print(f"Error: Outline file {outline_path} not found")
        return
    
    # Extract original context
    print("\nExtracting original hierarchical context...")
    original_context = extract_placeholder_context_hierarchical(template_path, enhance_with_outline=False)
    print(f"Found {len(original_context)} placeholders with context")
    
    # Now enhance with outline
    print("\nEnhancing context with outline file...")
    enhanced_context = enhance_placeholder_context_with_outline(original_context, outline_path)
    print(f"Enhanced context has {len(enhanced_context)} entries")
    
    # Count how many were actually improved
    improved_count = 0
    for key in original_context:
        if original_context[key] != enhanced_context[key]:
            improved_count += 1
    
    print(f"\nNumber of placeholders with improved context: {improved_count} out of {len(original_context)}")
    
    # Sample some improvements
    if improved_count > 0:
        print("\nSample improvements:")
        count = 0
        for key in original_context:
            if original_context[key] != enhanced_context[key]:
                print(f"\nKey: {key}")
                print(f"  Original: {original_context[key]}")
                print(f"  Enhanced: {enhanced_context[key]}")
                count += 1
                if count >= 5:  # Show just 5 examples
                    break
    
    # Check for specific placeholders that should be enhanced
    important_placeholders = [
        "plc_b&r_check", 
        "plc_allen_bradley_check", 
        "plc_compactlogix_check", 
        "hmi_size10_check", 
        "hmi_size15_check", 
        "explosion_proof_check",
        "voltage",
        "hz",
        "psi"
    ]
    
    print("\nChecking specific important placeholders:")
    for key in important_placeholders:
        if key in original_context:
            print(f"\nKey: {key}")
            original = original_context.get(key, "Not found")
            enhanced = enhanced_context.get(key, "Not found")
            print(f"  Original: {original}")
            print(f"  Enhanced: {enhanced}")
            if original == enhanced:
                print("  Status: NOT ENHANCED")
            else:
                print("  Status: ENHANCED")
        else:
            print(f"\nKey: {key} not found in context")
    
    # Try direct enhancement of keys using normalized versions
    print("\nAttempting direct enhancement with manual normalization:")
    for key in important_placeholders:
        if key in original_context:
            print(f"\nKey: {key}")
            # Try different normalizations of the key
            clean_key = key.replace("_check", "")
            normalized_keys = [
                key,
                clean_key,
                clean_key.replace("_", ""),
                clean_key.lower()
            ]
            
            # See if any of these match in the outline directly
            with open(outline_path, 'r', encoding='utf-8') as f:
                outline_lines = f.readlines()
            
            found_match = False
            for line in outline_lines:
                line = line.strip().lower()
                for norm_key in normalized_keys:
                    if norm_key.lower() in line:
                        print(f"  Found match in outline: {line}")
                        found_match = True
                        break
                if found_match:
                    break
            
            if not found_match:
                print("  No direct match found in outline file")

if __name__ == "__main__":
    analyze_outline_enhancement() 