import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from html import escape
from typing import Any, Dict
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
        from weasyprint import HTML  # type: ignore
    WEASYPRINT_AVAILABLE = True
    WEASYPRINT_IMPORT_ERROR: str | None = None
except (ImportError, OSError) as exc:
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = str(exc)

try:
    with suppress_stderr():
        from playwright.sync_api import sync_playwright  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
    PLAYWRIGHT_IMPORT_ERROR: str | None = None
except (ImportError, OSError) as exc:
    PLAYWRIGHT_AVAILABLE = False
    PLAYWRIGHT_IMPORT_ERROR = str(exc)


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
    
    # Split into lines while preserving indentation (needed for nested bullets).
    lines = [line.rstrip() for line in text_val.splitlines() if line.strip()]
    
    if not lines:
        p = soup.new_tag('p')
        p.string = "No options or specifications selected for this machine."
        p['style'] = "font-style: italic; color: #666;"
        wrapper.append(p)
        return wrapper
    
    # Single line that doesn't look like a bullet
    if len(lines) == 1:
        line = lines[0].strip()
        # Check if it's a bullet point
        bullet_prefixes = ['-', '*', '•', '·', '–', '—', '►', '▸']
        line_without_indent = line.lstrip()
        is_bullet = any(line_without_indent.startswith(prefix) for prefix in bullet_prefixes)
        
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
    def _is_indented(raw_line: str) -> bool:
        return (len(raw_line) - len(raw_line.lstrip(' \t'))) > 0

    first_line_raw = lines[0]
    first_line = first_line_raw.strip()
    if first_line.upper().startswith('MACHINE:'):
        # Extract machine description (may span multiple lines with sub-bullets)
        machine_main_text = first_line[8:].strip()  # Remove "MACHINE:" prefix
        machine_lines.append(machine_main_text)

        # Check following lines for indented sub-bullets that belong to machine description
        i = 1
        while i < len(lines):
            line = lines[i]
            # Check if line is indented (sub-bullet of machine)
            if _is_indented(line) and line.strip():
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
        first_is_bullet = any(first_line.lstrip().startswith(c) for c in bullet_chars)
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
            is_indented = _is_indented(raw_line) and raw_line.strip()

            # Strip leading whitespace and bullet characters
            line = raw_line.lstrip(' \t').strip()
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


def _has_text_value(value: str | None) -> bool:
    return bool((value or "").strip())


def _slugify_identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return normalized or "section"


def _normalize_label_overrides(label_overrides: dict[str, str] | None) -> dict[str, str]:
    if not label_overrides:
        return {}

    normalized: dict[str, str] = {}
    for key, value in label_overrides.items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            normalized[clean_key] = clean_value
    return normalized


def _apply_section_identifiers(soup: BeautifulSoup) -> None:
    used_ids: dict[str, int] = {}
    for section in soup.select('section.section'):
        header = section.select_one('.section-header h2') or section.find('h2')
        title = header.get_text(strip=True) if header else ""
        base_id = _slugify_identifier(title)
        occurrence = used_ids.get(base_id, 0)
        section_id = base_id if occurrence == 0 else f"{base_id}_{occurrence + 1}"
        used_ids[base_id] = occurrence + 1
        section['data-section-id'] = section_id


def _apply_label_overrides(
    soup: BeautifulSoup,
    label_overrides: dict[str, str] | None,
) -> None:
    overrides = _normalize_label_overrides(label_overrides)
    if not overrides:
        return

    for section in soup.select('section.section'):
        header = section.select_one('.section-header h2') or section.find('h2')
        if header is None:
            continue

        current_title = header.get_text(strip=True)
        section_id = str(section.get('data-section-id', '')).strip()
        replacement = (
            overrides.get(section_id)
            or overrides.get(current_title)
            or overrides.get(_slugify_identifier(current_title))
        )
        if replacement:
            header.string = replacement

    for field in soup.select('label.field'):
        placeholder = str(field.get('data-placeholder', '')).strip()
        if not placeholder:
            continue
        field_key = placeholder.replace('{{', '').replace('}}', '').strip()
        replacement = overrides.get(field_key) or overrides.get(placeholder)
        if not replacement:
            continue

        label_span = field.find('span', class_='label')
        if label_span is not None:
            label_span.string = replacement


def _filter_included_sections(
    soup: BeautifulSoup,
    included_sections: list[str] | None,
) -> None:
    if not included_sections:
        return

    included_keys = {
        _slugify_identifier(str(section_key))
        for section_key in included_sections
        if str(section_key).strip()
    }
    if not included_keys:
        return

    for section in list(soup.select('section.section')):
        header = section.select_one('.section-header h2') or section.find('h2')
        section_title = header.get_text(strip=True) if header else ""
        section_id = str(section.get('data-section-id', '')).strip()
        section_keys = {
            _slugify_identifier(section_id),
            _slugify_identifier(section_title),
        }
        if not section_keys.intersection(included_keys):
            section.decompose()


def _field_is_populated(label_element) -> bool:
    formatted_element = label_element.find(class_='formatted-list')
    if formatted_element is not None:
        if formatted_element.has_attr('data-field-value'):
            return _has_text_value(str(formatted_element.get('data-field-value', '')))
        return _has_text_value(formatted_element.get_text(" ", strip=True))

    checkbox = label_element.find('input', attrs={'type': 'checkbox'})
    if checkbox is not None:
        return checkbox.has_attr('checked')

    input_elem = label_element.find('input')
    if input_elem is not None:
        return _has_text_value(str(input_elem.get('value', '')))

    textarea = label_element.find('textarea')
    if textarea is not None:
        return _has_text_value(textarea.get_text())

    return False


def _toggle_class(element: Any, class_name: str, enabled: bool) -> None:
    if element is None:
        return
    classes = list(element.get('class', []))
    if enabled and class_name not in classes:
        classes.append(class_name)
    if not enabled:
        classes = [name for name in classes if name != class_name]
    if classes:
        element['class'] = classes
    else:
        element.attrs.pop('class', None)


def _ensure_group_blocks(soup: BeautifulSoup) -> None:
    for group in soup.select('.group'):
        direct_children = [child for child in group.children if getattr(child, 'name', None)]
        if not direct_children:
            continue
        if any('group-block' in (child.get('class') or []) for child in direct_children):
            continue

        blocks: list[Any] = []
        current_block = None
        for child in direct_children:
            child_classes = child.get('class', [])
            if 'group-title' in child_classes or current_block is None:
                current_block = soup.new_tag('div')
                current_block['class'] = ['group-block']
                blocks.append(current_block)
            current_block.append(child.extract())

        for block in blocks:
            group.append(block)


def _ensure_print_value_node(soup: BeautifulSoup, label_element: Any) -> Any | None:
    if label_element is None:
        return None
    if 'checkbox' in label_element.get('class', []):
        return None
    if label_element.find(class_='formatted-list') is not None:
        return None

    existing = label_element.find(class_='field-value-print')
    if existing is not None:
        return existing

    mirror = soup.new_tag('div')
    mirror['class'] = ['field-value-print']
    token = label_element.find(class_='token')
    if token is not None:
        token.insert_before(mirror)
    else:
        label_element.append(mirror)
    return mirror


def _sync_layout_state(soup: BeautifulSoup) -> None:
    _ensure_group_blocks(soup)

    for label_element in soup.select('label.field'):
        checkbox = label_element.find('input', attrs={'type': 'checkbox'})
        formatted = label_element.find(class_='formatted-list')

        if checkbox is not None:
            _toggle_class(label_element, 'is-checked', checkbox.has_attr('checked'))
            _toggle_class(label_element, 'has-value', False)
            continue

        field_value = ""
        if formatted is not None:
            field_value = str(formatted.get('data-field-value', '')) or formatted.get_text("\n", strip=True)
        else:
            input_elem = label_element.find('input')
            textarea = label_element.find('textarea')
            if input_elem is not None:
                field_value = str(input_elem.get('value', ''))
            elif textarea is not None:
                field_value = textarea.get_text()

        has_value = _has_text_value(field_value)
        _toggle_class(label_element, 'has-value', has_value)
        _toggle_class(label_element, 'is-checked', False)

        mirror = _ensure_print_value_node(soup, label_element)
        if mirror is not None:
            mirror.clear()
            if field_value:
                mirror.append(field_value)

    for group in soup.select('.group'):
        has_content = any(_field_is_populated(field) for field in group.select('label.field'))
        _toggle_class(group, 'has-content', has_content)


def _prune_empty_content(
    soup: BeautifulSoup,
    *,
    hide_empty_sections: bool,
    hide_empty_fields: bool,
) -> None:
    if not hide_empty_sections and not hide_empty_fields:
        return

    if hide_empty_fields:
        for label_element in list(soup.select('label.field')):
            if not _field_is_populated(label_element):
                label_element.decompose()

        for grid in list(soup.select('.field-grid, .checkbox-grid')):
            if not grid.select('label.field'):
                grid.decompose()

        for group in list(soup.select('.group')):
            if not group.select('label.field'):
                group.decompose()

    if hide_empty_sections:
        for section in list(soup.select('section.section')):
            fields = section.select('label.field')
            if hide_empty_fields:
                if not fields:
                    section.decompose()
                continue

            if not any(_field_is_populated(field) for field in fields):
                section.decompose()


def _strip_class_name(element: Any, class_name: str) -> None:
    if element is None:
        return
    classes = [name for name in element.get('class', []) if name != class_name]
    if classes:
        element['class'] = classes
    else:
        element.attrs.pop('class', None)


def _strip_interactive_ui(soup: BeautifulSoup) -> None:
    for script_tag in list(soup.find_all('script')):
        script_tag.decompose()

    for interactive_block in list(soup.select('.no-print, .delete-btn, .toggle-icon')):
        interactive_block.decompose()

    for token in list(soup.select('.token')):
        token.decompose()

    for shell in soup.select('.layout-shell'):
        has_toc_sidebar = shell.select_one('.toc-sidebar') is not None
        if not has_toc_sidebar:
            _strip_class_name(shell, 'layout-shell')
            existing_style = str(shell.get('style', '')).strip()
            shell['style'] = f"{existing_style}; display:block;" if existing_style else "display:block;"

    for section in soup.select('section.section'):
        _strip_class_name(section, 'collapsed')
        section.attrs.pop('data-collapsed', None)

    transient_classes = (
        'field-hidden-by-search',
        'group-hidden-by-search',
        'section-hidden-by-search',
        'field-match',
    )
    for class_name in transient_classes:
        for element in soup.select(f'.{class_name}'):
            _strip_class_name(element, class_name)

    for editable in soup.select('[contenteditable]'):
        editable.attrs.pop('contenteditable', None)
        editable.attrs.pop('title', None)

    for control in soup.select('input, textarea, select'):
        tag_name = control.name.lower()
        if tag_name == 'input' and str(control.get('type', '')).lower() in {'checkbox', 'radio'}:
            control['disabled'] = 'disabled'
            continue
        if tag_name == 'select':
            control['disabled'] = 'disabled'
            continue
        control['readonly'] = 'readonly'

    body = soup.body
    if body is not None:
        for class_name in ('edit-mode', 'readonly'):
            _strip_class_name(body, class_name)


def _strip_to_pure_output_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    _strip_interactive_ui(soup)
    return str(soup)


def _build_interactive_backup_path(output_path: str) -> str:
    if output_path.lower().endswith('.html'):
        return f"{output_path[:-5]}.interactive.backup.html"
    return f"{output_path}.interactive.backup.html"


def _compact_text(value: str | None, *, max_length: int = 120) -> str:
    compact_value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(compact_value) <= max_length:
        return compact_value
    return compact_value[: max_length - 3].rstrip() + "..."


def _extract_field_text(label_element: Any) -> str:
    if label_element is None:
        return ""

    formatted_element = label_element.find(class_='formatted-list')
    if formatted_element is not None:
        field_value = _compact_text(str(formatted_element.get('data-field-value', '')))
        if field_value:
            return field_value
        return _compact_text(formatted_element.get_text(" ", strip=True))

    input_element = label_element.find('input')
    if input_element is not None:
        input_type = str(input_element.get('type', '')).lower()
        if input_type == 'checkbox':
            return "Yes" if input_element.has_attr('checked') else ""
        return _compact_text(str(input_element.get('value', '')))

    textarea_element = label_element.find('textarea')
    if textarea_element is not None:
        return _compact_text(textarea_element.get_text(" ", strip=True))

    return _compact_text(label_element.get_text(" ", strip=True))


def _extract_pdf_metadata_from_soup(soup: BeautifulSoup) -> dict[str, str]:
    labels = soup.select('label.field')

    def value_by_placeholder(placeholder_key: str) -> str:
        selector = f'label.field[data-placeholder="{{{{{placeholder_key}}}}}"]'
        return _extract_field_text(soup.select_one(selector))

    def value_by_label_keywords(*keywords: str) -> str:
        normalized_keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
        if not normalized_keywords:
            return ""

        for label in labels:
            label_span = label.select_one('.label')
            if label_span is None:
                continue
            label_text = label_span.get_text(" ", strip=True).lower()
            if any(keyword in label_text for keyword in normalized_keywords):
                candidate = _extract_field_text(label)
                if candidate:
                    return candidate
        return ""

    project_number = value_by_placeholder('f0001') or value_by_label_keywords('project', 'proj')
    customer_name = value_by_placeholder('f0002') or value_by_label_keywords('customer')
    machine_name = value_by_placeholder('f0003') or value_by_label_keywords('machine')
    report_date = value_by_label_keywords('date') or datetime.now().strftime("%b %d, %Y")

    return {
        "project_number": project_number or "N/A",
        "customer_name": customer_name or "N/A",
        "machine_name": machine_name or "N/A",
        "report_date": report_date,
    }


def _inject_pdf_cover_page(soup: BeautifulSoup, metadata: dict[str, str]) -> None:
    if soup.body is None or soup.select_one('.pdf-cover-page'):
        return

    cover_markup = f"""
    <section class="pdf-cover-page" aria-label="General Order Acknowledgement cover page">
        <p class="pdf-cover-kicker">General Order Acknowledgement</p>
        <h1 class="pdf-cover-title">Project Report</h1>
        <div class="pdf-cover-meta-grid">
            <div class="pdf-cover-meta-item">
                <span class="pdf-cover-label">Project #</span>
                <strong class="pdf-cover-value">{escape(metadata.get("project_number", "N/A"))}</strong>
            </div>
            <div class="pdf-cover-meta-item">
                <span class="pdf-cover-label">Customer</span>
                <strong class="pdf-cover-value">{escape(metadata.get("customer_name", "N/A"))}</strong>
            </div>
            <div class="pdf-cover-meta-item">
                <span class="pdf-cover-label">Machine</span>
                <strong class="pdf-cover-value">{escape(metadata.get("machine_name", "N/A"))}</strong>
            </div>
            <div class="pdf-cover-meta-item">
                <span class="pdf-cover-label">Date</span>
                <strong class="pdf-cover-value">{escape(metadata.get("report_date", "N/A"))}</strong>
            </div>
        </div>
    </section>
    """
    cover_section = BeautifulSoup(cover_markup, 'html.parser').select_one('.pdf-cover-page')
    if cover_section is not None:
        soup.body.insert(0, cover_section)


def _inject_pdf_quality_styles(soup: BeautifulSoup) -> None:
    if soup.head is None or soup.head.find('style', attrs={'data-pdf-quality': 'v2'}):
        return

    style_tag = soup.new_tag('style')
    style_tag['data-pdf-quality'] = 'v2'
    style_tag.string = """
        .pdf-cover-page {
            display: none;
        }
        @media print {
            .pdf-cover-page {
                display: flex !important;
                flex-direction: column;
                justify-content: center;
                gap: 16px;
                min-height: 250mm;
                padding: 24mm 18mm;
                border: 1px solid #d7dbe2;
                background: linear-gradient(160deg, #ffffff 0%, #f4f6f9 100%);
                break-after: page;
                page-break-after: always;
            }
            .pdf-cover-kicker {
                margin: 0;
                font-size: 15px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #4b5563;
                font-weight: 700;
            }
            .pdf-cover-title {
                margin: 0 0 8px;
                font-size: 32px;
                color: #c00000;
                line-height: 1.1;
            }
            .pdf-cover-meta-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px 16px;
            }
            .pdf-cover-meta-item {
                border: 1px solid #d7dbe2;
                border-radius: 8px;
                padding: 10px 12px;
                background: #ffffff;
            }
            .pdf-cover-label {
                display: block;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                color: #4b5563;
                margin-bottom: 5px;
            }
            .pdf-cover-value {
                display: block;
                font-size: 16px;
                color: #111827;
                line-height: 1.3;
                word-break: break-word;
            }
            .page .section {
                break-before: auto !important;
                page-break-before: auto !important;
                break-inside: auto !important;
                page-break-inside: auto !important;
                box-shadow: none !important;
            }
            .page .section-header {
                break-after: avoid !important;
                page-break-after: avoid !important;
                page-break-inside: avoid !important;
            }
            .page .group {
                break-inside: auto !important;
                page-break-inside: auto !important;
            }
            .page .group-block {
                break-inside: avoid-page !important;
                page-break-inside: avoid !important;
            }
            .page .group-title {
                break-after: avoid !important;
                page-break-after: avoid !important;
                background: #dce3ee !important;
                color: #1e2d3d !important;
            }
            .page .group.has-content .group-title {
                background: #ffe6d7 !important;
                color: #7f1d1d !important;
                border-left: 6px solid #c00000 !important;
                font-size: 12px !important;
                padding: 6px 12px !important;
                box-shadow: inset 0 0 0 1px #f3c3b0 !important;
            }
            .page .field-grid {
                grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)) !important;
                gap: 0 !important;
                border-top: 1px solid #ccc !important;
                border-left: 1px solid #ccc !important;
            }
            .page .checkbox-grid {
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)) !important;
                gap: 0 !important;
                border-top: 1px solid #ccc !important;
                border-left: 1px solid #ccc !important;
            }
            .page .field {
                display: grid !important;
                grid-template-columns: 130px 1fr !important;
                break-inside: avoid !important;
                page-break-inside: avoid !important;
                border-right: 1px solid #ccc !important;
                border-bottom: 1px solid #ccc !important;
            }
            .page .field .label {
                background: #edf0f5 !important;
                border-right: 1px solid #ccc !important;
            }
            .page .field.checkbox.is-checked {
                background: #fff3cd !important;
                border-left: 3px solid #c00000 !important;
                padding-left: 7px !important;
            }
            .page .field.has-value .label {
                color: #c00000 !important;
                font-weight: 700 !important;
            }
            .page .field-value-print {
                display: block !important;
                white-space: pre-wrap !important;
                overflow-wrap: anywhere !important;
            }
            .page .field .label {
                font-size: 11px !important;
                line-height: 1.25 !important;
            }
            .page input,
            .page textarea {
                font-size: 11px !important;
                line-height: 1.3 !important;
            }
            .page .field input[type="text"],
            .page .field input[type="number"],
            .page .field textarea {
                display: none !important;
            }
        }
    """
    soup.head.append(style_tag)


def _prepare_html_for_pdf(html_content: str) -> tuple[str, dict[str, str]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    metadata = _extract_pdf_metadata_from_soup(soup)
    _sync_layout_state(soup)
    _inject_pdf_cover_page(soup, metadata)
    _inject_pdf_quality_styles(soup)
    return str(soup), metadata


def _build_pdf_header_template(metadata: dict[str, str]) -> str:
    project_number = escape(_compact_text(metadata.get("project_number", "N/A"), max_length=80))
    report_date = escape(_compact_text(metadata.get("report_date", "N/A"), max_length=80))
    return (
        "<div style=\"width:100%; font-size:8px; color:#4b5563; padding:0 8mm; "
        "display:flex; justify-content:space-between; align-items:center;\">"
        f"<span>Project #: {project_number}</span>"
        f"<span>Date: {report_date}</span>"
        "</div>"
    )


def _build_pdf_footer_template(metadata: dict[str, str]) -> str:
    customer_name = _compact_text(metadata.get("customer_name", "N/A"), max_length=50)
    machine_name = _compact_text(metadata.get("machine_name", "N/A"), max_length=60)
    descriptor = escape(f"{customer_name} | {machine_name}")
    return (
        "<div style=\"width:100%; font-size:8px; color:#4b5563; padding:0 8mm; "
        "display:flex; justify-content:space-between; align-items:center;\">"
        f"<span>{descriptor}</span>"
        "<span>Page <span class=\"pageNumber\"></span> / "
        "<span class=\"totalPages\"></span></span>"
        "</div>"
    )


def fill_html_template(
    html_content: str,
    data: Dict[str, str],
    *,
    hide_empty_sections: bool = False,
    hide_empty_fields: bool = False,
    included_sections: list[str] | None = None,
    label_overrides: dict[str, str] | None = None,
    pure_output: bool = False,
) -> str:
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
                normalized_checkbox = str(value or "").strip().upper()
                if normalized_checkbox in ['YES', 'TRUE', '1', 'CHECKED', 'ON', 'Y']:
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
            formatted_element['data-field-key'] = key
            formatted_element['data-field-value'] = text_val
            # The placeholder is on the label, so the formatted element doesn't need it.
            # We are replacing the input/textarea inside the label.
            target_element.replace_with(formatted_element)
        elif target_element.name == 'input':
            target_element['value'] = text_val
        elif target_element.name == 'textarea':
            target_element.string = text_val

    _apply_section_identifiers(soup)
    _apply_label_overrides(soup, label_overrides)
    _filter_included_sections(soup, included_sections)
    _prune_empty_content(
        soup,
        hide_empty_sections=hide_empty_sections,
        hide_empty_fields=hide_empty_fields,
    )
    _sync_layout_state(soup)

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
        body.print-preview .section-header .toggle-icon {
            display: none !important;
        }
        body.print-preview .section.collapsed > .section-content {
            max-height: none !important;
            padding: 16px 14px !important;
        }
    """
    if soup.head and not soup.head.find('style', string=lambda s: 'options-listing' in str(s)):
        soup.head.append(style_tag)

    rendered_html = str(soup)
    if pure_output:
        return _strip_to_pure_output_html(rendered_html)
    return rendered_html


def _generate_pdf_with_wkhtmltopdf(html_content: str, output_path: str) -> None:
    wkhtmltopdf_path = _resolve_wkhtmltopdf_binary()
    if not wkhtmltopdf_path:
        raise RuntimeError("wkhtmltopdf binary not found.")

    html_temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(html_content)
            html_temp_path = tmp_file.name

        result = subprocess.run(
            [
                wkhtmltopdf_path,
                "--encoding",
                "utf-8",
                "--print-media-type",
                "--disable-smart-shrinking",
                "--page-size",
                "Letter",
                "--margin-top",
                "10mm",
                "--margin-right",
                "10mm",
                "--margin-bottom",
                "10mm",
                "--margin-left",
                "10mm",
                "--quiet",
                html_temp_path,
                output_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr_output = (result.stderr or "").strip()
            raise RuntimeError(
                f"wkhtmltopdf failed with exit code {result.returncode}: {stderr_output or 'unknown error'}"
            )
    finally:
        if html_temp_path and os.path.exists(html_temp_path):
            os.remove(html_temp_path)


def _generate_pdf_with_playwright(html_content: str, output_path: str) -> None:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright is not available.")

    metadata = _extract_pdf_metadata_from_soup(BeautifulSoup(html_content, 'html.parser'))
    header_template = _build_pdf_header_template(metadata)
    footer_template = _build_pdf_footer_template(metadata)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        page.set_content(html_content, wait_until="domcontentloaded")
        page.emulate_media(media="print")
        page.pdf(
            path=output_path,
            format="Letter",
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=True,
            header_template=header_template,
            footer_template=footer_template,
            margin={
                "top": "16mm",
                "right": "10mm",
                "bottom": "14mm",
                "left": "10mm",
            },
        )
        context.close()
        browser.close()


def generate_preview_pdf(html_content: str, output_path: str) -> None:
    """Render a preview HTML snapshot directly to PDF without extra print CSS injection."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright is not available.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            java_script_enabled=False,
            viewport={"width": 1480, "height": 2200},
        )
        page = context.new_page()
        page.set_content(html_content, wait_until="domcontentloaded")
        page.emulate_media(media="screen")
        page.pdf(
            path=output_path,
            format="Letter",
            print_background=True,
            prefer_css_page_size=True,
            margin={
                "top": "10mm",
                "right": "10mm",
                "bottom": "10mm",
                "left": "10mm",
            },
        )
        context.close()
        browser.close()


def _resolve_wkhtmltopdf_binary() -> str | None:
    explicit_path = os.getenv("WKHTMLTOPDF_PATH")
    candidates = [
        explicit_path,
        shutil.which("wkhtmltopdf"),
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def generate_pdf(html_content: str, output_path: str):
    """Generate PDF with Playwright (preferred), then WeasyPrint, then wkhtmltopdf."""
    generation_errors: list[str] = []
    prepared_html, _ = _prepare_html_for_pdf(html_content)

    if PLAYWRIGHT_AVAILABLE:
        try:
            _generate_pdf_with_playwright(prepared_html, output_path)
            return
        except Exception as exc:
            generation_errors.append(f"Playwright failed: {exc}")
    elif PLAYWRIGHT_IMPORT_ERROR:
        generation_errors.append(f"Playwright unavailable: {PLAYWRIGHT_IMPORT_ERROR}")

    if WEASYPRINT_AVAILABLE:
        try:
            HTML(string=prepared_html).write_pdf(output_path)
            return
        except Exception as exc:
            generation_errors.append(f"WeasyPrint failed: {exc}")
    elif WEASYPRINT_IMPORT_ERROR:
        generation_errors.append(f"WeasyPrint unavailable: {WEASYPRINT_IMPORT_ERROR}")

    if _resolve_wkhtmltopdf_binary():
        try:
            _generate_pdf_with_wkhtmltopdf(prepared_html, output_path)
            return
        except Exception as exc:
            generation_errors.append(f"wkhtmltopdf failed: {exc}")

    details = " | ".join(generation_errors) if generation_errors else "No PDF engine is available."
    raise RuntimeError(
        "Server-side PDF generation failed. Install Playwright Chromium via "
        "'python -m playwright install chromium' or configure a fallback PDF engine. "
        f"Details: {details}"
    )


def fill_and_generate_html(
    template_path: str,
    data: Dict[str, str],
    output_path: str,
    *,
    hide_empty_sections: bool = False,
    hide_empty_fields: bool = False,
    included_sections: list[str] | None = None,
    label_overrides: dict[str, str] | None = None,
    pure_output: bool = False,
) -> str:
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

        interactive_html = fill_html_template(
            html_content,
            data,
            hide_empty_sections=hide_empty_sections,
            hide_empty_fields=hide_empty_fields,
            included_sections=included_sections,
            label_overrides=label_overrides,
            pure_output=False,
        )

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if pure_output:
            backup_path = _build_interactive_backup_path(output_path)
            backup_dir = os.path.dirname(backup_path)
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                backup_file.write(interactive_html)
            filled_html = _strip_to_pure_output_html(interactive_html)
        else:
            filled_html = interactive_html

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(filled_html)

        print(f"Successfully generated HTML: {output_path}")
        return filled_html
    except Exception as e:
        print(f"Error generating HTML: {e}")
        import traceback
        traceback.print_exc()
        return ""


def fill_and_generate_pdf(
    template_path: str,
    data: Dict[str, str],
    output_path: str,
    *,
    hide_empty_sections: bool = False,
    hide_empty_fields: bool = False,
    included_sections: list[str] | None = None,
    label_overrides: dict[str, str] | None = None,
    pure_output: bool = False,
):
    """Generate HTML and optionally PDF."""
    html_output_path = output_path
    if output_path.endswith('.pdf') or output_path.endswith('.docx'):
        html_output_path = output_path.rsplit('.', 1)[0] + '.html'

    filled_html = fill_and_generate_html(
        template_path,
        data,
        html_output_path,
        hide_empty_sections=hide_empty_sections,
        hide_empty_fields=hide_empty_fields,
        included_sections=included_sections,
        label_overrides=label_overrides,
        pure_output=pure_output,
    )

    if output_path.endswith('.pdf'):
        try:
            generate_pdf(filled_html, output_path)
            print(f"Successfully generated PDF: {output_path}")
        except Exception as e:
            print(f"Warning: Could not generate PDF ({e}). HTML available at {html_output_path}")
