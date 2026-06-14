#!/usr/bin/env python3
"""
Standalone test script for docling markdown conversion.

This script tests docling markdown conversion capabilities.
Run this from the project root with the backend environment:

    python -m scripts.test_docling_markdown_standalone [URL]

Or from scripts directory:
    cd ..
    python -m scripts.test_docling_markdown_standalone https://example.com/document.pdf

Example PDF sources:
    - https://arxiv.org/pdf/2408.15169.pdf (ArXiv paper)
    - https://github.com/anthropics/anthropic-sdk-python/blob/main/README.md (rendered as PDF)
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime


def convert_url_to_markdown(url: str, output_file: str | None = None) -> str:
    """
    Convert a document from URL to markdown using docling.

    Args:
        url: URL of the document to convert
        output_file: Optional output file path. If not provided, will be auto-generated.

    Returns:
        The markdown content as string.

    Raises:
        ImportError: If docling is not installed
        Exception: If conversion fails
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        raise ImportError(
            "docling is not installed. Install backend dependencies with:\n"
            "  pip install -r backend/requirements.txt"
        )

    timestamp = _get_timestamp()
    print(f"[{timestamp}] Starting docling conversion from URL: {url}")

    try:
        # Initialize converter
        print(f"[{_get_timestamp()}] Initializing DocumentConverter...")
        converter = DocumentConverter()

        # Convert document from URL
        print(f"[{_get_timestamp()}] Fetching and converting document...")
        result = converter.convert(url)

        # Extract markdown
        markdown_content = result.document.export_to_markdown()

        print(f"[{_get_timestamp()}] ✓ Conversion successful")
        print(f"[{_get_timestamp()}] Document format detected: {result.input.format}")
        print(f"[{_get_timestamp()}] Markdown size: {len(markdown_content)} characters")

        # Save to file if specified
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"[{_get_timestamp()}] ✓ Markdown saved to: {output_path.absolute()}")
        else:
            # Auto-generate filename based on timestamp
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"docling_output_{ts}.md"
            output_path = Path(output_file)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"[{_get_timestamp()}] ✓ Markdown saved to: {output_path.absolute()}")

        return markdown_content

    except Exception as e:
        print(f"[{_get_timestamp()}] ✗ Error during conversion: {type(e).__name__}: {e}")
        raise


def _get_timestamp() -> str:
    """Get current timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test docling markdown conversion from URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.test_docling_markdown_standalone https://arxiv.org/pdf/2408.15169.pdf
  python -m scripts.test_docling_markdown_standalone https://example.com/doc.pdf --output my_doc.md
  python -m scripts.test_docling_markdown_standalone https://example.com/doc.pdf --verbose
        """,
    )

    parser.add_argument(
        "url",
        nargs="?",
        default="https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml",
        help="URL of the document to convert",
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
        help="Enable verbose output (show first 500 chars of markdown)",
    )

    args = parser.parse_args()

    try:
        markdown = convert_url_to_markdown(args.url, args.output)

        if args.verbose:
            print(f"\n[{_get_timestamp()}] First 500 characters of markdown:\n")
            print("=" * 80)
            print(markdown[:500])
            if len(markdown) > 500:
                print(f"\n... ({len(markdown) - 500} more characters)")
            print("=" * 80)

        print(f"\n[{_get_timestamp()}] ✓ Test completed successfully!")
        return 0

    except ImportError as e:
        print(f"\n[{_get_timestamp()}] ✗ Import error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[{_get_timestamp()}] ✗ Test failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
