"""
This script removes the duplicate explicit_placeholder_mappings dictionary from template_utils.py
"""

def fix_duplicates():
    filepath = 'src/utils/template_utils.py'
    
    # Read the file line by line
    with open(filepath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Initialize markers for finding the duplicate
    start_idx = -1
    end_idx = -1
    
    # Look for the start of the duplicate declaration
    for i, line in enumerate(lines):
        if "# Add explicit mappings for specific placeholders" in line and i < 2000:
            if i+1 < len(lines) and "explicit_placeholder_mappings =" in lines[i+1]:
                start_idx = i
                # Now that we found the start, look for the end
                brace_count = 0
                for j in range(i+1, len(lines)):
                    line_j = lines[j]
                    if "{" in line_j:
                        brace_count += line_j.count("{")
                    if "}" in line_j:
                        brace_count -= line_j.count("}")
                    
                    # Check if this is the end of the dictionary
                    if brace_count == 0 and "}" in line_j:
                        # Look for the "First pass" comment after this
                        if j+2 < len(lines) and "# First pass: Try direct key matches" in lines[j+2]:
                            end_idx = j
                            break
                break  # Exit after finding the first occurrence
    
    if start_idx != -1 and end_idx != -1:
        # Print some debug info
        print(f"Found start at line {start_idx+1}: {lines[start_idx].strip()}")
        print(f"Found end at line {end_idx+1}: {lines[end_idx].strip()}")
        
        # Remove the duplicate dictionary lines
        new_lines = lines[:start_idx] + ["        # First pass: Try direct key matches and known fields\n"] + lines[end_idx+3:]
        
        # Write the updated content
        with open(filepath, 'w', encoding='utf-8') as file:
            file.writelines(new_lines)
        print(f"Successfully removed duplicate explicit_placeholder_mappings from {filepath}")
        print(f"Removed lines {start_idx+1} to {end_idx+1}")
    else:
        print("Could not find the duplicate definition")
        print(f"Search results: start_idx={start_idx}, end_idx={end_idx}")

if __name__ == "__main__":
    fix_duplicates() 