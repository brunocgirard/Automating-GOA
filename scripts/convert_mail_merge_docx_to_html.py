"""Batch convert Mail_merge DOCX templates into classless HTML fragments."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
import shutil
import subprocess
import sys

DEFAULT_SOURCE_DIR = Path("Mail_merge")
DEFAULT_OUTPUT_DIR = DEFAULT_SOURCE_DIR / "html_fragments"
STYLESHEET_NAME = "mail-merge-content.css"

# Fixed output names for known Mail_merge templates.
OUTPUT_FILE_NAMES: dict[str, str] = {
    "Paking Slip.docx": "paking-slip.html",
    "Commercial Invoice.docx": "commercial-invoice.html",
    "CERTIFICATION OF ORIGIN_NAFTA.docx": "certification-of-origin-nafta.html",
    "Customer_Oxxxx_COR.docx": "customer-oxxxx-cor.html",
}

CLASS_ATTR_PATTERN = re.compile(r"""\sclass=(?:"[^"]*"|'[^']*')""", re.IGNORECASE)

STYLESHEET_CONTENT = """article {
  max-width: 795px;
  margin: 0 auto;
  padding: 0;
  color: #111111;
  background: #ffffff;
  font-family: "Times New Roman", Times, serif;
  font-size: 15px;
  line-height: 1.45;
}

article * {
  box-sizing: border-box;
}

article h1,
article h2,
article h3,
article h4,
article h5,
article h6 {
  margin: 1.1rem 0 0.55rem;
  line-height: 1.25;
}

article h1 {
  font-size: 2rem;
}

article h2 {
  font-size: 1.6rem;
}

article h3 {
  font-size: 1.35rem;
}

article h4 {
  font-size: 1.2rem;
}

article h5,
article h6 {
  font-size: 1rem;
}

article p {
  margin: 0 0 0.8rem;
}

article ul,
article ol {
  margin: 0 0 1rem 1.5rem;
  padding: 0;
}

article li {
  margin-bottom: 0.3rem;
}

article a {
  color: #0b4a8b;
  text-decoration: underline;
}

article blockquote {
  margin: 0.8rem 0;
  padding: 0.2rem 0.8rem;
  border-left: 3px solid #c9c9c9;
  color: #333333;
}

article table {
  width: 100%;
  margin: 1rem 0;
  border-collapse: collapse;
}

article th,
article td {
  border: 1px solid #bdbdbd;
  padding: 0.4rem 0.5rem;
  text-align: left;
  vertical-align: top;
}

article hr {
  border: 0;
  border-top: 1px solid #cdcdcd;
  margin: 1rem 0;
}

article img,
article svg {
  max-width: 100%;
  height: auto;
}

@media (max-width: 840px) {
  article {
    padding-left: 12px;
    padding-right: 12px;
  }
}
"""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "template"


def _resolve_output_name(docx_name: str) -> str:
    mapped_name = OUTPUT_FILE_NAMES.get(docx_name)
    if mapped_name:
        return mapped_name
    return f"{_slugify(Path(docx_name).stem)}.html"


def _build_pandoc_command(pandoc_binary: str, docx_path: Path) -> list[str]:
    return [
        pandoc_binary,
        str(docx_path),
        "-f",
        "docx",
        "-t",
        "html5",
        "--embed-resources",
        "--wrap=none",
    ]


def _strip_class_attributes(html_fragment: str) -> str:
    return CLASS_ATTR_PATTERN.sub("", html_fragment)


def _wrap_fragment(html_fragment: str, source_docx_name: str) -> str:
    fragment = html_fragment.strip()
    escaped_source = escape(source_docx_name, quote=True)
    return f"<article data-source-docx=\"{escaped_source}\">\n{fragment}\n</article>\n"


def _convert_single_template(docx_path: Path, output_path: Path, pandoc_binary: str) -> None:
    command = _build_pandoc_command(pandoc_binary, docx_path)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Pandoc conversion failed for '{docx_path}': {stderr or 'no stderr output'}"
        )

    cleaned_fragment = _strip_class_attributes(result.stdout or "")
    wrapped_fragment = _wrap_fragment(cleaned_fragment, docx_path.name)
    output_path.write_text(wrapped_fragment, encoding="utf-8")


def write_stylesheet(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stylesheet_path = output_dir / STYLESHEET_NAME
    stylesheet_path.write_text(STYLESHEET_CONTENT.strip() + "\n", encoding="utf-8")
    return stylesheet_path


def convert_templates(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    pandoc_binary: str = "pandoc",
    write_styles: bool = True,
) -> list[tuple[Path, Path]]:
    pandoc_path = shutil.which(pandoc_binary)
    if not pandoc_path:
        raise RuntimeError("Pandoc is required but was not found on PATH.")

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    docx_files = sorted(path for path in source_dir.glob("*.docx") if path.is_file())
    if not docx_files:
        raise RuntimeError(f"No DOCX files found in {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    converted: list[tuple[Path, Path]] = []
    for docx_path in docx_files:
        output_name = _resolve_output_name(docx_path.name)
        output_path = output_dir / output_name
        _convert_single_template(docx_path, output_path, pandoc_path)
        converted.append((docx_path, output_path))

    if write_styles:
        write_stylesheet(output_dir)

    return converted


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Mail_merge DOCX templates into classless HTML fragments."
    )
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Directory containing DOCX templates.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write HTML fragments and stylesheet.",
    )
    parser.add_argument(
        "--pandoc-binary",
        default="pandoc",
        help="Pandoc executable name or absolute path.",
    )
    parser.add_argument(
        "--skip-stylesheet",
        action="store_true",
        help=f"Skip writing {STYLESHEET_NAME}.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)

    try:
        converted = convert_templates(
            source_dir=source_dir,
            output_dir=output_dir,
            pandoc_binary=args.pandoc_binary,
            write_styles=not args.skip_stylesheet,
        )
    except Exception as exc:  # pragma: no cover - CLI error handling path
        print(str(exc), file=sys.stderr)
        return 1

    for src_path, dest_path in converted:
        print(f"Converted {src_path.name} -> {dest_path}")

    if not args.skip_stylesheet:
        print(f"Wrote stylesheet -> {output_dir / STYLESHEET_NAME}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
