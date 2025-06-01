"""
This script tests the optimization in extract_placeholder_context_hierarchical
"""

import os
from src.utils.template_utils import extract_placeholders, extract_placeholder_context_hierarchical, explicit_placeholder_mappings

def test_optimization():
    print("Testing the optimization in extract_placeholder_context_hierarchical")
    
    # Path to the template
    template_path = 'templates/template.docx'
    
    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return
    
    # First, get all placeholders from the template
    placeholders = extract_placeholders(template_path)
    print(f"Found {len(placeholders)} placeholders in the template")
    
    # Check how many are in explicit_placeholder_mappings
    mapped_placeholders = [ph for ph in placeholders if ph in explicit_placeholder_mappings]
    print(f"{len(mapped_placeholders)} of {len(placeholders)} placeholders are explicitly mapped")
    
    # Check the first few unmapped placeholders
    unmapped_placeholders = [ph for ph in placeholders if ph not in explicit_placeholder_mappings]
    if unmapped_placeholders:
        print(f"First 5 unmapped placeholders: {', '.join(unmapped_placeholders[:5])}")
    
    # Test with optimization on
    print("\nTesting with optimization ON")
    context_map_optimized = extract_placeholder_context_hierarchical(
        template_path, enhance_with_outline=True, check_if_all_mapped=True
    )
    print(f"Got {len(context_map_optimized)} placeholder contexts with optimization ON")
    
    # Test with optimization off
    print("\nTesting with optimization OFF")
    context_map_unoptimized = extract_placeholder_context_hierarchical(
        template_path, enhance_with_outline=True, check_if_all_mapped=False
    )
    print(f"Got {len(context_map_unoptimized)} placeholder contexts with optimization OFF")
    
    # Compare results
    if len(context_map_optimized) == len(context_map_unoptimized):
        print("\nBoth methods returned the same number of context entries")
    else:
        print(f"\nDifferent number of context entries: optimized={len(context_map_optimized)}, unoptimized={len(context_map_unoptimized)}")
    
    # Check a few sample values to make sure they match
    if placeholders:
        sample_ph = placeholders[0]
        if sample_ph in context_map_optimized and sample_ph in context_map_unoptimized:
            if context_map_optimized[sample_ph] == context_map_unoptimized[sample_ph]:
                print(f"Sample placeholder '{sample_ph}' has matching context in both maps")
            else:
                print(f"Sample placeholder '{sample_ph}' has different context:")
                print(f"  Optimized: {context_map_optimized[sample_ph]}")
                print(f"  Unoptimized: {context_map_unoptimized[sample_ph]}")

if __name__ == "__main__":
    test_optimization() 