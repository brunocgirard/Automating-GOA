import os
import json
import argparse
from pprint import pprint
from typing import Dict, List, Optional, Any
import sqlite3

from src.utils.template_utils import extract_placeholder_context_hierarchical
from src.utils.crm_utils import load_machine_template_data, load_machine_templates_with_modifications


def display_machine_context(machine_id: str, db_path: str = "database.db", output_file: Optional[str] = None):
    """
    Displays the hierarchical context for a specific machine from the database.
    
    Args:
        machine_id: The machine ID to display context for
        db_path: Path to the SQLite database
        output_file: Optional path to save the output to a file
    """
    print(f"Retrieving hierarchical context for machine ID: {machine_id}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the machine exists
        cursor.execute("SELECT * FROM machines WHERE id = ?", (machine_id,))
        machine = cursor.fetchone()
        
        if not machine:
            print(f"Error: Machine with ID {machine_id} not found in the database")
            conn.close()
            return
        
        # Get the template data for this machine
        template_data = load_machine_template_data(machine_id, db_path)
        
        if not template_data:
            print(f"Error: No template data found for machine {machine_id}")
            conn.close()
            return
        
        # Process the output
        output_lines = []
        output_lines.append(f"Machine ID: {machine_id}")
        output_lines.append(f"Machine Name: {machine[1]}")  # Assuming name is in the second column
        output_lines.append("")
        output_lines.append("Placeholder Hierarchical Context:")
        output_lines.append("")
        
        # Group by sections for better readability
        sections = {}
        
        for key, value in template_data.items():
            # Skip complex values like lists or dicts
            if isinstance(value, (dict, list)):
                continue
                
            # Extract section from context if available
            context = ""
            if key in template_data.get("_context", {}):
                context = template_data["_context"][key]
                
                # Determine the section
                section = "Other"
                if " - " in context:
                    section = context.split(" - ")[0]
                
                if section not in sections:
                    sections[section] = []
                    
                sections[section].append(f"{key}: {context}")
            else:
                if "Other" not in sections:
                    sections["Other"] = []
                sections["Other"].append(f"{key}: {key}")  # Use key as context if none exists
        
        # Output by section
        for section, entries in sorted(sections.items()):
            output_lines.append(f"== {section} ==")
            output_lines.append("")
            
            for entry in sorted(entries):
                output_lines.append(entry)
                output_lines.append("-" * 40)  # Separator
            
            output_lines.append("")
        
        # Write or print the output
        output_text = "\n".join(output_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(f"Output written to {output_file}")
        else:
            print(output_text)
            
        conn.close()
    
    except Exception as e:
        print(f"Error displaying machine context: {e}")
        import traceback
        traceback.print_exc()


def display_placeholder_hierarchy(template_path: str = "templates/template.docx", output_file: Optional[str] = None):
    """
    Extracts and displays the hierarchical context of placeholders from a template.
    
    Args:
        template_path: Path to the template file
        output_file: Optional path to save the output to a file
    """
    print(f"Extracting hierarchical context from template: {template_path}")
    
    # Extract hierarchical context
    context_map = extract_placeholder_context_hierarchical(template_path)
    
    if not context_map:
        print("Error: Failed to extract placeholder context")
        return
    
    # Count placeholders and get list
    placeholders = sorted(context_map.keys())
    print(f"Found {len(placeholders)} placeholders with context")
    
    # Process the output
    output_lines = []
    output_lines.append(f"Found {len(placeholders)} placeholders in template: {template_path}")
    output_lines.append("")
    
    # Group by sections for better readability
    sections = {}
    
    for placeholder, context in context_map.items():
        # Determine the section
        section = "Other"
        if " - " in context:
            section = context.split(" - ")[0]
        
        if section not in sections:
            sections[section] = []
            
        sections[section].append(f"{placeholder}: {context}")
    
    # Output by section
    for section, entries in sorted(sections.items()):
        output_lines.append(f"== {section} ==")
        output_lines.append("")
        
        for entry in sorted(entries):
            output_lines.append(entry)
        
        output_lines.append("")
    
    # Write or print the output
    output_text = "\n".join(output_lines)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Output written to {output_file}")
    else:
        print(output_text)


def display_machine_template_data(machine_id: int, template_type: str = "GOA"):
    """
    Displays the template data for a specific machine.
    
    Args:
        machine_id: ID of the machine
        template_type: Type of template to display (default: "GOA")
    """
    print(f"Loading template data for machine ID: {machine_id}, template type: {template_type}")
    
    # Load template data
    template_data = load_machine_template_data(machine_id, template_type)
    
    if not template_data:
        print(f"No template data found for machine ID: {machine_id}, template type: {template_type}")
        return
    
    # Extract template data
    data = template_data.get("template_data", {})
    
    print(f"Found {len(data)} fields in template data")
    
    # Group by field type (checkbox vs text)
    checkboxes = {}
    text_fields = {}
    
    for key, value in data.items():
        if key.endswith("_check"):
            checkboxes[key] = value
        else:
            text_fields[key] = value
    
    # Print checkboxes
    print("\n== Checkboxes ==")
    for key, value in sorted(checkboxes.items()):
        print(f"{key}: {value}")
    
    # Print text fields
    print("\n== Text Fields ==")
    for key, value in sorted(text_fields.items()):
        if value and len(value) > 100:
            value = value[:100] + "..."
        print(f"{key}: {value}")


def display_all_machine_templates_for_client(quote_ref: str):
    """
    Displays all templates for all machines belonging to a specific client.
    
    Args:
        quote_ref: Quote reference for the client
    """
    # Connect to database
    db_path = os.path.join("data", "crm_data.db")
    conn = None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get client info
        cursor.execute("SELECT id, customer_name FROM clients WHERE quote_ref = ?", (quote_ref,))
        client = cursor.fetchone()
        
        if not client:
            print(f"No client found with quote reference: {quote_ref}")
            return
        
        client_id, client_name = client
        print(f"Client: {client_name} (ID: {client_id}, Quote: {quote_ref})")
        
        # Get machines for this client
        cursor.execute("""
        SELECT id, machine_name FROM machines 
        WHERE client_quote_ref = ? 
        ORDER BY id
        """, (quote_ref,))
        
        machines = cursor.fetchall()
        
        if not machines:
            print(f"No machines found for client with quote reference: {quote_ref}")
            return
        
        print(f"Found {len(machines)} machines for this client")
        
        # For each machine, display all templates
        for machine_id, machine_name in machines:
            print(f"\n{'=' * 80}")
            print(f"Machine: {machine_name} (ID: {machine_id})")
            
            templates_data = load_machine_templates_with_modifications(machine_id)
            templates = templates_data.get("templates", [])
            
            if not templates:
                print(f"  No templates found for this machine")
                continue
            
            print(f"  Found {len(templates)} templates for this machine")
            
            for template in templates:
                template_id = template.get("id")
                template_type = template.get("template_type", "Unknown")
                
                print(f"\n  Template: {template_type} (ID: {template_id})")
                
                # Get template data
                template_data = template.get("template_data", {})
                
                if not template_data:
                    print(f"    No data found for this template")
                    continue
                
                # Print selected checkboxes only (with YES values)
                checkboxes = {k: v for k, v in template_data.items() if k.endswith("_check") and v.upper() == "YES"}
                
                print(f"    Selected Checkboxes ({len(checkboxes)}):")
                for key, value in sorted(checkboxes.items()):
                    # Strip _check suffix for display
                    display_key = key[:-6] if key.endswith("_check") else key
                    print(f"      {display_key}")
                
                # Print filled text fields (non-empty)
                text_fields = {k: v for k, v in template_data.items() if not k.endswith("_check") and v}
                
                print(f"    Filled Text Fields ({len(text_fields)}):")
                for key, value in sorted(text_fields.items()):
                    if len(value) > 60:
                        value = value[:60] + "..."
                    print(f"      {key}: {value}")
                
                # Print modifications if any
                modifications = template.get("modifications", [])
                if modifications:
                    print(f"    Modifications ({len(modifications)}):")
                    for mod in modifications:
                        field_key = mod.get("field_key", "")
                        original = mod.get("original_value", "")
                        modified = mod.get("modified_value", "")
                        reason = mod.get("modification_reason", "")
                        
                        if len(original) > 30:
                            original = original[:30] + "..."
                        if len(modified) > 30:
                            modified = modified[:30] + "..."
                            
                        print(f"      {field_key}: {original} -> {modified} ({reason})")
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Check placeholder hierarchical context")
    parser.add_argument("--template", "-t", default="templates/template.docx", 
                        help="Path to template file (default: templates/template.docx)")
    parser.add_argument("--output", "-o", help="Path to output file (default: console output)")
    parser.add_argument("--machine", "-m", type=int, help="Machine ID to check template data")
    parser.add_argument("--quote", "-q", help="Quote reference to check all machines for a client")
    
    args = parser.parse_args()
    
    if args.quote:
        display_all_machine_templates_for_client(args.quote)
    elif args.machine:
        display_machine_template_data(args.machine)
    else:
        display_placeholder_hierarchy(args.template, args.output)


if __name__ == "__main__":
    main() 