import re
import os
from collections import defaultdict, Counter

def analyze_missing_sections():
    # Check if the file exists
    file_path = "template_context_final.txt"
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return
    
    # Read the file with utf-8 encoding
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.readlines()
    except UnicodeDecodeError:
        # Try with a different encoding
        with open(file_path, 'r', encoding='cp1252') as f:
            content = f.readlines()
    
    # Dictionary to track section counts
    section_counts = Counter()
    total_placeholders = 0
    enhanced_placeholders = 0
    
    # Standard GOA sections from the outline
    standard_sections = [
        "Control & Programming Specifications",
        "Utility Specifications",
        "Bottle Handling System Specifications",
        "Reject / Inspection System",
        "Material Specifications",
        "Capping System Specifications",
        "Labeling System Specifications",
        "Coding and Inspection System Specifications",
        "Induction Specifications",
        "Conveyor Specifications",
        "Gas Purge",
        "Desiccant",
        "Cottoner",
        "Plugging System Specifications",
        "Warranty & Install & Spares",
        "Validation Documents",
        "Manual Specifications",
        "Order Identification",
        "Basic Information",
        "Euro Guarding",
        "Packaging & Transport",
        "Change Part Quantities and Construction Materials",
        "Liquid Filling System Specifications",
        "BeltStar System Specifications",
        "Shrink Sleeve Specifications",
        "Street Fighter Tablet Counter"
    ]
    
    # Extract data for each placeholder
    current_section = "Unknown"
    unenhanced_placeholders = []
    
    for line in content:
        line = line.strip()
        if not line:
            continue
            
        # Check for section headers
        if line.startswith("== ") and line.endswith(" =="):
            current_section = line[3:-3].strip()
            continue
            
        # Check for placeholder lines
        if ":" in line:
            total_placeholders += 1
            placeholder, context = line.split(":", 1)
            placeholder = placeholder.strip()
            context = context.strip()
            
            # Determine if this is an enhanced context
            is_enhanced = False
            primary_section = context.split(" - ")[0] if " - " in context else context
            for std_section in standard_sections:
                if std_section in primary_section:
                    is_enhanced = True
                    section_counts[std_section] += 1
                    enhanced_placeholders += 1
                    break
            
            if not is_enhanced:
                section_counts[current_section] += 1
                unenhanced_placeholders.append((placeholder, context, current_section))
    
    # Calculate unenhanced placeholders
    unenhanced_count = total_placeholders - enhanced_placeholders
    
    # Print statistics
    print(f"Total placeholders: {total_placeholders}")
    print(f"Enhanced placeholders: {enhanced_placeholders}")
    print(f"Unenhanced placeholders: {unenhanced_count}")
    
    # Print enhanced section counts
    print("\nEnhanced Sections:")
    for section in standard_sections:
        if section_counts[section] > 0:
            print(f"  {section}: {section_counts[section]} placeholders")
    
    # Print unenhanced section counts
    print("\nUnenhanced Sections:")
    for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        if section not in standard_sections and count > 0:
            print(f"  {section}: {count} placeholders")
    
    # Print unenhanced placeholders
    if unenhanced_placeholders:
        print("\nUnenhanced Placeholders:")
        for placeholder, context, section in sorted(unenhanced_placeholders):
            print(f"  {placeholder}: {context} (Section: {section})")
    
    # Identify missing sections and placeholders
    print("\nTo improve enhancement, add these section mappings to the section_mapping dictionary:")
    for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        if section not in standard_sections and count > 0:
            print(f'    # {section} section mappings')
            section_key = section.lower().replace(" ", "_").replace("/", "_").replace("-", "_").replace("&", "and")
            for std_section in standard_sections:
                # Try to suggest an appropriate mapping based on section names
                if any(keyword in section.lower() for keyword in std_section.lower().split()):
                    print(f'    "{section_key}": "{std_section}",')
                    break
            else:
                # No match found, suggest mapping to Other
                print(f'    "{section_key}": "Other",  # Needs manual review')
            print()

if __name__ == "__main__":
    analyze_missing_sections() 