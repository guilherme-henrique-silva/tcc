#!/usr/bin/env python3
"""
Test script for docling markdown conversion from URL.

This script is isolated from the rest of the project and tests the ability
to fetch a document from a URL and convert it to markdown using docling.

Usage:
    python scripts/test_docling_markdown.py [URL] [--output OUTPUT_FILE]

Example:
    python scripts/test_docling_markdown.py https://example.com/document.pdf
    python scripts/test_docling_markdown.py https://example.com/doc.pdf --output output.md
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from docling.document_converter import DocumentConverter
from docling_core.types import InputFormat


def get_timestamp() -> str:
    """Get current timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def convert_url_to_markdown(url: str, output_file: str | None = None) -> str:
    """
    Convert a document from URL to markdown using docling.

    Args:
        url: URL of the document to convert
        output_file: Optional output file path. If not provided, will be auto-generated.

    Returns:
        The markdown content as string.

    Raises:
        Exception: If conversion fails
    """
    print(f"[{get_timestamp()}] Starting docling conversion from URL: {url}")

    try:
        # Initialize converter
        print(f"[{get_timestamp()}] Initializing DocumentConverter...")
        converter = DocumentConverter()

        # Convert document from URL
        print(f"[{get_timestamp()}] Fetching and converting document...")
        result = converter.convert(url)

        # Extract markdown
        markdown_content = result.document.export_to_markdown()

        print(f"[{get_timestamp()}] ✓ Conversion successful")
        print(f"[{get_timestamp()}] Document format detected: {result.input.format}")
        print(f"[{get_timestamp()}] Markdown size: {len(markdown_content)} characters")

        # Save to file if specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"[{get_timestamp()}] ✓ Markdown saved to: {output_path.absolute()}")
        else:
            # Auto-generate filename based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"docling_output_{timestamp}.md"
            output_path = Path(output_file)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"[{get_timestamp()}] ✓ Markdown saved to: {output_path.absolute()}")

        return markdown_content

    except Exception as e:
        print(f"[{get_timestamp()}] ✗ Error during conversion: {type(e).__name__}: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test docling markdown conversion from URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test_docling_markdown.py https://example.com/doc.pdf
  python scripts/test_docling_markdown.py https://example.com/doc.docx --output my_doc.md
        """,
    )

    parser.add_argument(
        "url",
        nargs="?",
        default="https://arxiv.org/pdf/2408.15169.pdf",
        help="URL of the document to convert (default: ArXiv example PDF)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output markdown file path (auto-generated if not specified)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    try:
        markdown = convert_url_to_markdown(args.url, args.output)

        if args.verbose:
            print(f"\n[{get_timestamp()}] First 500 characters of markdown:\n")
            print("=" * 80)
            print(markdown[:500])
            print("=" * 80)

        print(f"\n[{get_timestamp()}] Test completed successfully!")
        return 0

    except Exception as e:
        print(f"\n[{get_timestamp()}] Test failed with error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
