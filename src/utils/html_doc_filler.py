import os
import sys
from typing import Dict
from bs4 import BeautifulSoup
from contextlib import contextmanager


@contextmanager
def suppress_stderr():
    """Context manager to suppress standard output and error."""
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        old_stdout = sys.stdout
        sys.stderr = devnull
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr
            sys.stdout = old_stdout


try:
    with suppress_stderr():
        from weasyprint import HTML, CSS  # type: ignore
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False


def format_options_listing(soup: BeautifulSoup, text_val: str) -> BeautifulSoup:
    """
    Robustly format options_listing field content into structured HTML.
    Handles various input formats:
    - Empty/whitespace only -> "No options or specifications selected"
    - Single line of text -> Display as paragraph
    - "No options..." message -> Display as-is
    - Header + bullet lines -> Format with header and <ul> list
    - Just bullet lines (no header) -> Add default header and format
    
    Args:
        soup: BeautifulSoup instance for creating new tags
        text_val: The raw text value for options_listing
        
    Returns:
        BeautifulSoup element (wrapper div) with formatted content
    """
    wrapper = soup.new_tag('div')
    wrapper['class'] = ['formatted-list', 'options-listing']
    
    # Handle empty/whitespace
    if not text_val or not text_val.strip():
        p = soup.new_tag('p')
        p.string = "No options or specifications selected for this machine."
        p['style'] = "font-style: italic; color: #666;"
        wrapper.append(p)
        return wrapper
    
    text_val = text_val.strip()
    
    # Check for "no options" message variants
    no_opts_patterns = [
        'no options or specifications selected',
        'no options selected',
        'no specifications selected',
        'none selected',
        'n/a',
    ]
    text_lower = text_val.lower()
    if any(pattern in text_lower for pattern in no_opts_patterns):
        p = soup.new_tag('p')
        p.string = text_val
        p['style'] = "font-style: italic; color: #666;"
        wrapper.append(p)
        return wrapper
    
    # Split into lines
    lines = text_val.splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        p = soup.new_tag('p')
        p.string = "No options or specifications selected for this machine."
        p['style'] = "font-style: italic; color: #666;"
        wrapper.append(p)
        return wrapper
    
    # Single line that doesn't look like a bullet
    if len(lines) == 1:
        line = lines[0]
        # Check if it's a bullet point
        bullet_prefixes = ['-', '*', '•', '·', '–', '—', '►', '▸']
        is_bullet = any(line.startswith(prefix) for prefix in bullet_prefixes)
        
        if not is_bullet:
            # Single non-bullet line - display as paragraph
            p = soup.new_tag('p')
            p.string = line
            wrapper.append(p)
            return wrapper
    
    # Multiple lines or single bullet line - check for machine description and header
    machine_lines = []  # Will hold main machine desc + any sub-bullets
    body_lines = []

    # Check if first line is MACHINE: description (special formatting)
    first_line = lines[0]
    if first_line.upper().startswith('MACHINE:'):
        # Extract machine description (may span multiple lines with sub-bullets)
        machine_main_text = first_line[8:].strip()  # Remove "MACHINE:" prefix
        machine_lines.append(machine_main_text)

        # Check following lines for indented sub-bullets that belong to machine description
        i = 1
        while i < len(lines):
            line = lines[i]
            # Check if line is indented (sub-bullet of machine)
            if line.startswith('  ') and line.strip():
                machine_lines.append(line)
                i += 1
            elif not line.strip():
                # Skip blank line and continue
                i += 1
            else:
                # Non-indented line - this starts the body_lines
                break

        # Remaining lines are body_lines
        body_lines = lines[i:]
    else:
        # Check for other header patterns
        header_patterns = [
            'selected options',
            'options and specifications',
            'machine specifications',
            'specifications:',
            'options:',
            'features:',
            'included:',
        ]

        bullet_chars = ['-', '*', '•', '·', '–', '—', '►', '▸']
        first_is_bullet = any(first_line.startswith(c) for c in bullet_chars)
        first_is_header = (
            not first_is_bullet and
            (first_line.endswith(':') or any(pat in first_line.lower() for pat in header_patterns))
        )

        if first_is_header:
            # Regular header found
            header = soup.new_tag('p')
            header.string = first_line
            header['style'] = "font-weight: 700; margin: 0 0 6px;"
            wrapper.append(header)
            body_lines = lines[1:]
        else:
            # No header, just bullets
            body_lines = lines

    # Create machine description section if present (more prominent than regular header)
    if machine_lines:
        machine_section = soup.new_tag('div')
        machine_section['style'] = "font-weight: 700; font-size: 1.05em; margin: 0 0 10px; padding: 6px; background-color: #f0f4f8; border-left: 3px solid #4a90e2;"

        # First line is the main machine description
        if machine_lines:
            main_p = soup.new_tag('p')
            main_p['style'] = "margin: 0;"
            main_p.string = machine_lines[0]
            machine_section.append(main_p)

        # If there are sub-bullets for the machine, render them as nested list
        if len(machine_lines) > 1:
            machine_ul = soup.new_tag('ul')
            machine_ul['style'] = "list-style-type: circle; margin: 6px 0 0 20px; padding: 0; font-weight: 400; font-size: 0.92em; line-height: 1.3;"

            bullet_chars = ['-', '*', '•', '·', '–', '—', '►', '▸']
            for sub_line in machine_lines[1:]:
                # Strip indentation and bullet characters
                cleaned = sub_line.strip()
                for char in bullet_chars:
                    if cleaned.startswith(char):
                        cleaned = cleaned[1:].strip()
                        break

                if cleaned:
                    sub_li = soup.new_tag('li')
                    sub_li.string = cleaned
                    sub_li['style'] = "margin-bottom: 2px;"
                    machine_ul.append(sub_li)

            if machine_ul.contents:
                machine_section.append(machine_ul)

        wrapper.append(machine_section)
    
    # Create bullet list if there are body lines, supporting nested bullets
    if body_lines:
        ul = soup.new_tag('ul')
        ul['style'] = "list-style-type: disc; margin-left: 18px; padding-left: 4px; margin-top: 4px; line-height: 1.4;"

        bullet_chars = ['-', '*', '•', '·', '–', '—', '►', '▸']
        current_li = None
        nested_ul = None

        for raw_line in body_lines:
            # Check if line is indented (sub-bullet)
            is_indented = raw_line.startswith('  ') and raw_line.strip()

            # Strip leading whitespace and bullet characters
            line = raw_line.strip()
            for char in bullet_chars:
                if line.startswith(char):
                    line = line[1:].strip()
                    break

            if not line:
                continue

            if is_indented:
                # This is a sub-bullet - add to nested list
                if current_li is not None:
                    # Create nested ul if it doesn't exist
                    if nested_ul is None:
                        nested_ul = soup.new_tag('ul')
                        nested_ul['style'] = "list-style-type: circle; margin-left: 20px; margin-top: 3px; margin-bottom: 3px; line-height: 1.3;"
                        current_li.append(nested_ul)

                    # Add sub-item to nested list
                    sub_li = soup.new_tag('li')
                    sub_li.string = line
                    sub_li['style'] = "margin-bottom: 2px; font-size: 0.95em;"
                    nested_ul.append(sub_li)
            else:
                # This is a main bullet - create new li
                current_li = soup.new_tag('li')
                current_li.append(line)  # Use append instead of .string to allow nested elements
                current_li['style'] = "margin-bottom: 3px;"
                ul.append(current_li)
                nested_ul = None  # Reset nested list for next main bullet

        if ul.contents:
            wrapper.append(ul)
    
    return wrapper


def fill_html_template(html_content: str, data: Dict[str, str]) -> str:
    """
    Populate placeholders in HTML template while preserving layout and formatting multiline text.
    
    Args:
        html_content: The HTML template content
        data: Dictionary mapping placeholder keys to values
        
    Returns:
        Filled HTML content as string
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all field containers, which are the labels with class 'field'
    for label_element in soup.find_all('label', class_='field'):
        placeholder = label_element.get('data-placeholder')
        if not placeholder:
            continue
        
        key = placeholder.replace('{{', '').replace('}}', '').strip()
        value = data.get(key)
        text_val = str(value) if value is not None else ''

        # Handle Checkboxes
        if 'checkbox' in label_element.get('class', []):
            input_elem = label_element.find('input', type='checkbox')
            if input_elem:
                if value and str(value).upper() in ['YES', 'TRUE', '1', 'CHECKED']:
                    input_elem['checked'] = 'checked'
                else:
                    input_elem.attrs.pop('checked', None)
            continue

        # --- Handle all text-based fields (input, textarea) ---
        target_element = label_element.find('input') or label_element.find('textarea')
        
        if not target_element:
            continue

        # Determine if content is multiline
        multiline_chars = ['\n', '\r', '•', '–', '▪']
        has_multiline_content = (
            any(ch in text_val for ch in multiline_chars) or
            '- ' in text_val or
            '* ' in text_val or
            len(text_val.splitlines()) > 1
        )
        
        key_lower = key.lower()
        multiline_keywords = [
            'listing', 'note', 'comment', 'description', 'detail', 'remark',
            'spec', 'requirements', 'instruction', 'observation', 'options'
        ]
        multiline_hint = any(term in key_lower for term in multiline_keywords)
        
        should_format_as_list = (multiline_hint and text_val) or has_multiline_content

        if should_format_as_list:
            formatted_element = format_options_listing(soup, text_val)
            # The placeholder is on the label, so the formatted element doesn't need it.
            # We are replacing the input/textarea inside the label.
            target_element.replace_with(formatted_element)
        elif target_element.name == 'input':
            target_element['value'] = text_val
        elif target_element.name == 'textarea':
            target_element.string = text_val

    # Add consistent checkbox and list styling
    style_tag = soup.new_tag('style')
    style_tag.string = """
        .field.checkbox input[type="checkbox"] {
            -webkit-appearance: checkbox;
            appearance: checkbox;
            width: 18px;
            height: 18px;
            border: 1px solid var(--border);
            background: #fff;
            accent-color: var(--accent);
        }
        .field.checkbox input[type="checkbox"]:checked {
            background-color: var(--accent);
        }
        .formatted-list {
            padding: 6px 0;
        }
        .formatted-list ul {
            margin: 0;
        }
        .options-listing {
            background: #fafbfc;
            border-radius: 4px;
            padding: 8px 12px;
        }
    """
    if soup.head and not soup.head.find('style', string=lambda s: 'options-listing' in str(s)):
        soup.head.append(style_tag)

    return str(soup)


def generate_pdf(html_content: str, output_path: str):
    """Generates a PDF from HTML content using WeasyPrint."""
    if not WEASYPRINT_AVAILABLE:
        raise ImportError("WeasyPrint is not installed. Cannot generate PDF.")

    HTML(string=html_content).write_pdf(output_path)


def fill_and_generate_html(template_path: str, data: Dict[str, str], output_path: str) -> str:
    """
    Fills template and saves as HTML.
    
    Args:
        template_path: Path to the HTML template
        data: Dictionary mapping placeholder keys to values
        output_path: Path to save the filled HTML
        
    Returns:
        The filled HTML content as string
    """
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        filled_html = fill_html_template(html_content, data)

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(filled_html)

        print(f"Successfully generated HTML: {output_path}")
        return filled_html
    except Exception as e:
        print(f"Error generating HTML: {e}")
        import traceback
        traceback.print_exc()
        return ""


def fill_and_generate_pdf(template_path: str, data: Dict[str, str], output_path: str):
    """Generate HTML and optionally PDF."""
    html_output_path = output_path
    if output_path.endswith('.pdf') or output_path.endswith('.docx'):
        html_output_path = output_path.rsplit('.', 1)[0] + '.html'

    filled_html = fill_and_generate_html(template_path, data, html_output_path)

    if output_path.endswith('.pdf'):
        try:
            generate_pdf(filled_html, output_path)
            print(f"Successfully generated PDF: {output_path}")
        except Exception as e:
            print(f"Warning: Could not generate PDF ({e}). HTML available at {html_output_path}")
