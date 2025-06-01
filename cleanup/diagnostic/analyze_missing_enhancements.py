import re
import os
from collections import defaultdict

def analyze_missing_contexts():
    # Check if the file exists
    file_path = "template_hierarchical_context_improved.txt"
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return
    
    # Read the file
    with open(file_path, 'r', encoding='cp1252') as f:
        content = f.read()
    
    # Extract the list of placeholders
    sections = content.split("==")
    
    # Count placeholders by section
    section_counts = defaultdict(int)
    missing_sections = []
    placeholder_counts = 0
    enhanced_counts = 0
    
    # Define the sections we want to check for
    target_sections = [
        "Control & Programming",
        "Utility Specifications",
        "Bottle Handling System",
        "Reject / Inspection",
        "Material Specifications",
        "Capping System",
        "Labeling System",
        "Coding and Inspection",
        "Induction Specifications",
        "Conveyor Specifications",
        "Gas Purge",
        "Desiccant",
        "Cottoner",
        "Plugging System",
        "Warranty & Install",
        "Validation Documents",
        "Manual Specifications",
        "Order Identification",
        "Basic Information",
        "Euro Guarding",
        "Packaging & Transport",
        "Change Part Quantities",
        "Liquid Filling",
        "BeltStar System",
        "Shrink Sleeve",
        "Street Fighter"
    ]
    
    # Analyze which placeholders have section headings
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Extract section title if it exists
        lines = section.split("\n")
        if not lines:
            continue
            
        section_title = lines[0].strip()
        
        # Count placeholders in this section
        placeholder_count = 0
        for line in lines[1:]:
            if line.strip() and "[" in line:
                placeholder_count += 1
                placeholder_counts += 1
        
        if section_title:
            print(f"Section: {section_title} - {placeholder_count} placeholders")
            
            # Check if this is an enhanced section
            is_enhanced = False
            for target in target_sections:
                if target in section_title:
                    is_enhanced = True
                    section_counts[target] += placeholder_count
                    enhanced_counts += placeholder_count
                    break
                    
            if not is_enhanced:
                missing_sections.append((section_title, placeholder_count))
        
    # Extract placeholders count from first line
    first_line = content.split("\n")[0]
    total_match = re.search(r"Found (\d+) placeholders", first_line)
    if total_match:
        total_placeholders = int(total_match.group(1))
        print(f"\nTotal placeholders according to file: {total_placeholders}")
    else:
        total_placeholders = placeholder_counts
    
    # Print statistics
    print(f"\nTotal placeholders found in sections: {placeholder_counts}")
    print(f"Enhanced placeholders: {enhanced_counts}")
    print(f"Missing enhancements: {placeholder_counts - enhanced_counts}")
    
    # Print enhanced section counts
    print("\nEnhanced Sections:")
    for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        print(f"  {section}: {count} placeholders")
    
    # Print missing sections
    print("\nMissing Sections:")
    for section, count in sorted(missing_sections, key=lambda x: -x[1]):
        print(f"  {section}: {count} placeholders")
        
    # Analyze what sections are missing from the outline
    print("\nSections needed to be added to the enhance_placeholder_context_with_outline function:")
    for section_title, count in missing_sections:
        if count > 0:
            normalized_key = section_title.lower().replace(' ', '_').replace('/', '_').replace('-', '_')
            print(f'    "{normalized_key}": "{section_title}",')

if __name__ == "__main__":
    analyze_missing_contexts() 