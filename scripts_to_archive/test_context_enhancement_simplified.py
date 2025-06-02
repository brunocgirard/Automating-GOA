from src.utils.template_utils import extract_placeholder_context_hierarchical, enhance_placeholder_context_with_outline
import os

# Sample contexts that might come from the original extraction
sample_contexts = {
    # Critical PLC/HMI fields
    'plc_b&r_check': 'Controls',
    'hmi_10_check': 'HMI - Size',
    'explosion_proof_check': 'Explosion proof',
    'cap_prs_check': 'Reject Reasons',
    
    # Fields with no obvious match
    'custom_field_xyz': 'Custom Field'
}

# Run the enhancement
outline_path = 'full_fields_outline.md'
if os.path.exists(outline_path):
    print(f"Using outline file: {outline_path}")
    enhanced = enhance_placeholder_context_with_outline(sample_contexts, outline_path)
    
    print('\nResults (Before → After):')
    for k in sample_contexts:
        print(f'  {k}:')
        print(f'    Before: {sample_contexts[k]}')
        print(f'    After:  {enhanced[k]}')
        
    # Count how many fields were enhanced
    enhanced_count = sum(1 for k in sample_contexts if sample_contexts[k] != enhanced[k])
    print(f'\nEnhanced {enhanced_count} out of {len(sample_contexts)} fields')
else:
    print(f"Outline file not found: {outline_path}") 