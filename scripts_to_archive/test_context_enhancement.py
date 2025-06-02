from src.utils.template_utils import extract_placeholder_context_hierarchical, enhance_placeholder_context_with_outline
import os

# Sample contexts that might come from the original extraction
sample_contexts = {
    # Basic fields
    'voltage': 'Basic Info',
    'psi': 'Utility Specs',
    'hz': 'Basic Info - Hz',
    
    # PLC related fields
    'plc_b&r_check': 'Controls',
    'plc_allen_bradley_check': 'Controls - PLC - Allen Bradley',
    'plc_other_check': 'Controls - PLC',
    
    # HMI related fields
    'hmi_10_check': 'HMI - Size',
    'hmi_15_check': 'HMI',
    
    # Reject system fields
    'cap_prs_check': 'Reject Reasons',
    'plug_prs_check': 'Reject System',
    
    # Other critical fields
    'explosion_proof_check': 'Explosion proof',
    'beacon_light_red_check': 'Beacon - Color',
    
    # Fields with no obvious match
    'custom_field_xyz': 'Custom Field',
    'special_feature_abc_check': 'Special Features'
}

# Run the enhancement
outline_path = 'full_fields_outline.md'
if os.path.exists(outline_path):
    print(f"Using outline file: {outline_path}")
    enhanced = enhance_placeholder_context_with_outline(sample_contexts, outline_path)
    
    print('\nBefore enhancement:')
    for k, v in sample_contexts.items():
        print(f'  {k}: {v}')
    
    print('\nAfter enhancement:')
    for k, v in enhanced.items():
        print(f'  {k}: {v}')
        
    # Add a comparison view
    print('\nComparison:')
    for k in sample_contexts:
        print(f'  {k}:')
        print(f'    Before: {sample_contexts[k]}')
        print(f'    After:  {enhanced[k]}')
        
    # Count how many fields were enhanced
    enhanced_count = sum(1 for k in sample_contexts if sample_contexts[k] != enhanced[k])
    print(f'\nEnhanced {enhanced_count} out of {len(sample_contexts)} fields')
else:
    print(f"Outline file not found: {outline_path}") 