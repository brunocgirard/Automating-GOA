from api.services.report_service import (
    generate_machine_report_html,
    generate_machine_summary_html,
)


def test_report_includes_only_selected_checkbox_items_and_ignores_text_fields() -> None:
    html = generate_machine_report_html(
        template_data={
            "eg_none_check": "YES",
            "ci_chs_check": "NO",
            "machine_speed": "120 bpm",
        },
        machine_name="Test Machine",
        template_type="GOA",
        is_sortstar_machine=False,
    )

    assert "Machine Build Checklist" in html
    assert "Euro Guarding" in html
    assert "None" in html
    assert "Coder - hot stamp" not in html
    assert "Selected GOA checklist items: <strong>1</strong>" in html
    assert "machine_speed" not in html
    assert "120 bpm" not in html
    assert html.count('aria-label="Mark completed:') == 1


def test_report_follows_goa_mapping_order() -> None:
    html = generate_machine_report_html(
        template_data={
            "ci_chs_check": "YES",
            "eg_none_check": "YES",
        },
        machine_name="Ordered Machine",
        template_type="GOA",
        is_sortstar_machine=False,
    )

    euro_index = html.find("Euro Guarding")
    coding_index = html.find("Coding and Inspection System Specifications")
    assert euro_index != -1
    assert coding_index != -1
    assert euro_index < coding_index


def test_summary_is_compact_checklist() -> None:
    html = generate_machine_summary_html(
        template_data={
            "eg_none_check": "YES",
            "ci_chs_check": "NO",
        },
        machine_name="Summary Machine",
        template_type="GOA",
        is_sortstar_machine=False,
    )

    assert "Machine Checklist Summary" in html
    assert "Selected GOA checklist items: <strong>1</strong>" in html
    assert "Euro Guarding" in html
    assert "Coding and Inspection System Specifications" not in html


def test_report_supports_goa_f_placeholder_checkboxes_in_goa_order() -> None:
    html = generate_machine_report_html(
        template_data={
            "f0037": "YES",  # Plug - SS 316
            "f0039": "NO",   # Cap - SS 304
            "f0040": "YES",  # Cap - SS 316
        },
        machine_name="Patriot",
        template_type="GOA",
        is_sortstar_machine=False,
    )

    assert "Selected GOA checklist items: <strong>2</strong>" in html
    assert "Change Part Quantities and Construction Materials" in html
    assert "Plug - SS 316" in html
    assert "Cap - SS 316" in html
    assert "Cap - SS 304" not in html
    assert html.count('aria-label="Mark completed:') == 2
