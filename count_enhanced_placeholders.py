import os

def count_placeholders():
    # Check if the file exists
    file_path = "template_hierarchical_context_improved.txt"
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii', 'utf-16']
    lines = []
    
    for encoding in encodings:
        try:
            # Read all lines from the file
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            print(f"Successfully read file with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            print(f"Failed to read with encoding: {encoding}")
            continue
    
    if not lines:
        print("Error: Could not read file with any of the attempted encodings")
        return
    
    total_placeholders = len(lines)
    
    # Define the sections we consider enhanced
    enhanced_sections = [
        "Control & Programming Specifications",
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
    
    # Count enhanced placeholders
    enhanced_count = 0
    unenhanced_placeholders = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        is_enhanced = False
        for section in enhanced_sections:
            if section in line:
                enhanced_count += 1
                is_enhanced = True
                break
        
        if not is_enhanced:
            # Extract the placeholder key from the line
            try:
                parts = line.split(': ', 1)
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    unenhanced_placeholders.append((key, value))
                else:
                    print(f"Warning: Line doesn't contain expected format: {line}")
            except Exception as e:
                print(f"Error parsing line: {line}, Error: {str(e)}")
    
    # Print the results
    print(f"Total placeholders: {total_placeholders}")
    print(f"Enhanced placeholders: {enhanced_count}")
    print(f"Unenhanced placeholders: {total_placeholders - enhanced_count}")
    
    # Print a sample of unenhanced placeholders
    if unenhanced_placeholders:
        print("\nSample of unenhanced placeholders:")
        for key, value in unenhanced_placeholders[:20]:  # Show first 20
            print(f"  {key}: {value}")

if __name__ == "__main__":
    count_placeholders() 