from src.utils.form_generator import EXCEL_PATH, OUTPUT_HTML_PATH, generate_goa_form


def main() -> None:
    if not generate_goa_form(excel_path=EXCEL_PATH, output_path=OUTPUT_HTML_PATH):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
