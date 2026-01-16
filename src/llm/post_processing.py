"""
Post-processing module for LLM-generated field values.

This module applies domain-specific correction rules to LLM outputs, ensuring:
- Consistent formatting of checkbox values (YES/NO)
- Mutual exclusivity constraints (e.g., only one HMI size, one PLC type)
- Standardized units and formats (voltage, frequency, pressure, speed)
- Cross-field validation and logical consistency
- Evidence-based verification to prevent false positives

The post-processing pipeline runs after LLM extraction to catch common errors
and enforce business rules that are difficult to capture in prompts alone.
"""

import re
from typing import Dict, List


def _zero_evidence_check(field_data: Dict[str, str], template_schema: Dict[str, Dict], full_pdf_text: str, selected_pdf_descriptions: List[str]) -> Dict[str, str]:
    """
    Verifies that for every 'YES' checkbox, there is at least one positive indicator in the text.
    If no evidence is found, it flips the value to 'NO'.

    Args:
        field_data: Dictionary of field names to values from LLM
        template_schema: Schema information about the fields, including positive indicators
        full_pdf_text: The full text of the PDF document
        selected_pdf_descriptions: Descriptions of selected PDF items

    Returns:
        Verified field data with unjustified YES values flipped to NO
    """
    print("Performing zero-evidence check on checkbox fields...")
    verified_data = field_data.copy()

    # Combine all text sources for efficient searching
    aggregated_text = full_pdf_text.lower() + " " + " ".join(desc.lower() for desc in selected_pdf_descriptions)

    for field_name, value in field_data.items():
        if value == "YES" and field_name in template_schema and template_schema[field_name].get("type") == "boolean":
            positive_indicators = template_schema[field_name].get("positive_indicators", [])

            # Check if any positive indicator is present in the aggregated text
            has_evidence = any(indicator in aggregated_text for indicator in positive_indicators)

            if not has_evidence:
                print(f"Flipping '{field_name}' to 'NO' due to lack of evidence.")
                verified_data[field_name] = "NO"

    return verified_data


def apply_post_processing_rules(field_data: Dict[str, str], template_schema: Dict[str, Dict], full_pdf_text: str, selected_pdf_descriptions: List[str]) -> Dict[str, str]:
    """
    Applies domain-specific rules and a zero-evidence check to correct and improve LLM-generated field values.

    This function implements 11 core correction rules:
    1. Checkbox value normalization (YES/NO casing)
    2. HMI size mutual exclusivity (only one size allowed)
    3. PLC type mutual exclusivity (only one type allowed)
    4. Voltage format standardization (ranges and V suffix)
    5. Frequency format standardization (Hz suffix)
    6. Pressure format standardization (PSI suffix)
    7. Multi-color beacon logic (tri-color enables all colors)
    8. Production speed unit formatting
    9. Cross-field validation (filling system implies filling type)
    10. Explosion proof consistency (pneumatic components)
    11. SortStar basic configuration mutual exclusivity

    After applying these rules, performs a zero-evidence check to verify all
    YES checkboxes have supporting evidence in the source text.

    Args:
        field_data: Dictionary of field names to values from LLM
        template_schema: Schema information about the fields
        full_pdf_text: The full text of the PDF document
        selected_pdf_descriptions: Descriptions of selected PDF items

    Returns:
        Corrected and improved field data
    """
    print("Applying post-processing rules to LLM output...")
    corrected_data = field_data.copy()

    # Quick early return if empty data
    if not corrected_data:
        return corrected_data

    # Create lookup maps for field types to avoid repetitive checks
    checkbox_fields = set()
    text_fields = set()

    # Pre-identify checkbox fields for faster processing
    for field_name in corrected_data.keys():
        # Determine if this is a checkbox field
        is_checkbox = False
        if field_name.endswith('_check'):
            is_checkbox = True
            checkbox_fields.add(field_name)
        elif field_name in template_schema and isinstance(template_schema[field_name], dict):
            is_checkbox = template_schema[field_name].get('type') == 'boolean'
            if is_checkbox:
                checkbox_fields.add(field_name)

        if not is_checkbox:
            text_fields.add(field_name)

    # Rule 1: Ensure all checkbox fields have correct YES/NO values (normalize casing)
    for field_name in checkbox_fields:
        value = corrected_data[field_name]
        if isinstance(value, str) and value.upper() in ["YES", "NO"]:
            corrected_data[field_name] = value.upper()
        else:
            # Default to NO for invalid values
            print(f"Correcting invalid checkbox value '{value}' to 'NO' for {field_name}")
            corrected_data[field_name] = "NO"

    # Extract field groups that we need for specific rules
    # This avoids repeated searches through all fields
    hmi_size_fields = [f for f in checkbox_fields if '_hmi_' in f.lower() and 'size' in f.lower()]
    alt_hmi_size_fields = [f for f in checkbox_fields
                          if ('hmi' in f.lower() or 'touch' in f.lower() or 'screen' in f.lower())
                          and any(s in f.lower() for s in ['15', '10', '5.7', '5_7', '15inch', '10inch'])]
    plc_type_fields = [f for f in checkbox_fields if 'plc_' in f.lower()]
    beacon_fields = [f for f in checkbox_fields if any(term in f.lower() for term in ['beacon', 'light', 'signal'])]

    # Rule 2: HMI size constraints - only one HMI size should be YES
    if hmi_size_fields:
        yes_hmi_sizes = [f for f in hmi_size_fields if corrected_data[f] == "YES"]
        if len(yes_hmi_sizes) > 1:
            print(f"Multiple HMI sizes selected ({yes_hmi_sizes}), keeping only the largest/first")
            # Prioritize based on size (larger screens are usually more expensive/premium)
            size_priority = {"15": 1, "10": 2, "5.7": 3, "5_7": 3}

            # Find the highest priority (lowest number) size
            best_field = yes_hmi_sizes[0]
            best_priority = 99

            for field in yes_hmi_sizes:
                for size, priority in size_priority.items():
                    if size in field and priority < best_priority:
                        best_priority = priority
                        best_field = field

            # Set only the best one to YES, others to NO
            for field in hmi_size_fields:
                corrected_data[field] = "YES" if field == best_field else "NO"

    # Also look for alternative HMI size field patterns
    if alt_hmi_size_fields and alt_hmi_size_fields != hmi_size_fields:  # Skip if same as already processed
        yes_alt_sizes = [f for f in alt_hmi_size_fields if corrected_data[f] == "YES"]
        if len(yes_alt_sizes) > 1:
            print(f"Multiple alternative HMI sizes selected ({yes_alt_sizes}), keeping only the largest")
            # Determine the largest size
            size_indicators = {"15": 15, "15inch": 15, "10": 10, "10inch": 10, "5.7": 5.7, "5_7": 5.7}
            best_field = yes_alt_sizes[0]
            best_size = 0

            for field in yes_alt_sizes:
                for indicator, size in size_indicators.items():
                    if indicator in field.lower() and size > best_size:
                        best_size = size
                        best_field = field

            # Set only the best one to YES, others to NO
            for field in alt_hmi_size_fields:
                corrected_data[field] = "YES" if field == best_field else "NO"

    # Rule 3: PLC type constraints - only one PLC type should be YES
    if plc_type_fields:
        yes_plc_types = [f for f in plc_type_fields if corrected_data[f] == "YES"]
        if len(yes_plc_types) > 1:
            print(f"Multiple PLC types selected ({yes_plc_types}), keeping only one")
            # Keep only the first one as YES
            for i, field in enumerate(plc_type_fields):
                corrected_data[field] = "YES" if field == yes_plc_types[0] else "NO"

    # Rule 4-6: Format utility specifications
    # Process these rules together for better performance
    has_voltage = 'voltage' in corrected_data
    has_hz = 'hz' in corrected_data
    has_psi = 'psi' in corrected_data

    if has_voltage or has_hz or has_psi:
        # Rule 4: Standardize voltage format
        if has_voltage:
            voltage_value = corrected_data['voltage']
            if voltage_value:
                # Detect if it's likely a voltage range
                if '-' not in voltage_value and '/' not in voltage_value:
                    try:
                        # If it's a single number, try to determine common range
                        voltage_num = int(''.join(c for c in voltage_value if c.isdigit()))
                        if voltage_num > 100 and voltage_num < 130:
                            corrected_data['voltage'] = "110-120V"
                        elif voltage_num > 200 and voltage_num < 250:
                            corrected_data['voltage'] = "208-240V"
                        elif voltage_num > 380 and voltage_num < 420:
                            corrected_data['voltage'] = "380-400V"
                        elif voltage_num > 460 and voltage_num < 490:
                            corrected_data['voltage'] = "460-480V"
                    except (ValueError, TypeError):
                        # Keep original if conversion fails
                        pass

                # Ensure V suffix if missing
                if voltage_value and not voltage_value.upper().endswith('V') and any(c.isdigit() for c in voltage_value):
                    corrected_data['voltage'] = voltage_value + 'V'

        # Rule 5: Ensure frequency has Hz suffix
        if has_hz:
            hz_value = corrected_data['hz']
            if hz_value and hz_value.isdigit():
                corrected_data['hz'] = hz_value + ' Hz'

        # Rule 6: PSI format standardization
        if has_psi:
            psi_value = corrected_data['psi']
            if psi_value and not 'psi' in psi_value.lower() and any(c.isdigit() for c in psi_value):
                corrected_data['psi'] = psi_value + ' PSI'

    # Rule 7: If 'tri-color beacon' is mentioned anywhere, enable all three color beacons
    if beacon_fields:
        # Check if any field mentions multi-color beacon
        has_multicolor = False
        for field in beacon_fields:
            if corrected_data[field] == "YES" and any(term in field.lower() for term in ['tri', 'three', 'multi']):
                has_multicolor = True
                break

        # Find individual color beacon fields
        color_beacon_fields = ['beacon_red_check', 'beacon_amber_check', 'beacon_green_check', 'beacon_yellow_check']
        color_beacon_fields = [f for f in color_beacon_fields if f in corrected_data]

        if color_beacon_fields:
            # If at least one beacon is set to YES, check if others should be too
            yes_beacon_count = sum(1 for f in color_beacon_fields if corrected_data[f] == "YES")
            if yes_beacon_count >= 2 or has_multicolor:
                # If multiple colors are already YES or we detected a multi-color beacon reference,
                # set all standard colors to YES
                print("Setting all standard beacon colors to YES based on multi-color beacon detection")
                for field in color_beacon_fields:
                    corrected_data[field] = "YES"

    # Rule 8: Production speed formatting
    if 'production_speed' in corrected_data:
        speed = corrected_data['production_speed']
        if speed:
            # Try to ensure speed has units
            if all(not c.isalpha() for c in speed) and any(c.isdigit() for c in speed):
                # No letters but has numbers - add units
                if any('bottle' in field_name.lower() for field_name in corrected_data.keys()):
                    corrected_data['production_speed'] = speed + ' bottles per minute'
                else:
                    corrected_data['production_speed'] = speed + ' units per minute'

    # Rule 9: Cross-field validation - if filling system is selected, ensure appropriate filling type
    filling_system_field = next((f for f in checkbox_fields if 'filling_system' in f.lower() and corrected_data[f] == "YES"), None)
    if filling_system_field:
        filling_type_fields = [f for f in checkbox_fields if any(typ in f.lower() for typ in ['volumetric', 'peristaltic', 'time_pressure', 'mass_flow'])]
        if filling_type_fields and not any(corrected_data.get(f) == "YES" for f in filling_type_fields):
            # Default to volumetric if available (most common)
            volumetric_field = next((f for f in filling_type_fields if 'volumetric' in f.lower()), None)
            if volumetric_field:
                print(f"Setting {volumetric_field} to YES as default filling type")
                corrected_data[volumetric_field] = "YES"

    # Rule 10: Explosion proof consistency
    if 'explosion_proof_check' in corrected_data and corrected_data['explosion_proof_check'] == "YES":
        print("Explosion proof selected - ensuring consistent related fields")
        # In explosion proof environments, typically pneumatic components are used instead of electric
        pneumatic_fields = [f for f in checkbox_fields if 'pneumatic' in f.lower()]
        for field in pneumatic_fields:
            corrected_data[field] = "YES"  # Set pneumatic options to YES

        # Disable certain electric components that would be replaced in explosion proof environments
        electric_fields_to_disable = [
            f for f in checkbox_fields
            if any(term in f.lower() for term in ['electric', 'servo', 'motor'])
            and 'explosion' not in f.lower()
        ]
        for field in electric_fields_to_disable:
            if corrected_data[field] == "YES":
                print(f"Setting {field} to NO due to explosion proof environment")
                corrected_data[field] = "NO"

    # Rule 11: SortStar Basic Machine Configuration - ensure only one is YES
    sortstar_basic_config_fields = [
        "bs_984_check", "bs_1230_check", "bs_985_check",
        "bs_1229_check", "bs_1264_check", "bs_1265_check"
    ]
    # Filter to only fields present in the current data
    active_sortstar_config_fields = [f for f in sortstar_basic_config_fields if f in corrected_data]

    if active_sortstar_config_fields: # Only run if any of these fields are actually in the data
        yes_sortstar_configs = [f for f in active_sortstar_config_fields if corrected_data.get(f) == "YES"]

        if len(yes_sortstar_configs) > 1:
            print(f"Warning: Multiple SortStar basic configurations selected: {yes_sortstar_configs}. Enforcing single selection.")
            # Keep the first one found as YES, set others to NO
            # A more sophisticated priority could be defined if needed, but for now, first encountered wins.
            first_yes_found = False
            for field_name in sortstar_basic_config_fields: # Iterate in defined order to ensure some consistency
                if field_name in corrected_data:
                    if corrected_data[field_name] == "YES":
                        if not first_yes_found:
                            first_yes_found = True
                            # This one stays YES
                        else:
                            corrected_data[field_name] = "NO" # Subsequent ones become NO
            print(f"Corrected SortStar basic configurations. Kept: {[f for f in active_sortstar_config_fields if corrected_data.get(f) == 'YES']}")
        elif not yes_sortstar_configs and any(f in corrected_data and corrected_data.get(f) is not None for f in active_sortstar_config_fields):
            # This case is tricky: if a sortstar machine is being processed, one of these *should* be yes.
            # However, this rule is for post-processing LLM output. If LLM says all are NO, this rule won't force one to YES.
            # That level of correction would require more context (knowing for sure it's a SortStar and which one).
            # For now, we just ensure there isn't *more than one* YES.
            pass

    # Final step: Perform a zero-evidence check to catch any remaining false positives
    final_verified_data = _zero_evidence_check(corrected_data, template_schema, full_pdf_text, selected_pdf_descriptions)

    return final_verified_data
