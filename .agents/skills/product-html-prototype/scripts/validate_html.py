#!/usr/bin/env python3
"""Validate a self-contained HTML product prototype."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CDN_PATTERNS = (
    "cdn.jsdelivr",
    "unpkg",
    "cdnjs",
    "fonts.googleapis",
    "bootstrapcdn",
)


def has(pattern: str, text: str, flags: int = re.IGNORECASE | re.DOTALL) -> bool:
    return re.search(pattern, text, flags) is not None


def result(kind: str, message: str) -> None:
    print(f"{kind}: {message}")


def validate(path: Path) -> int:
    failures: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        failures.append(f"File not found: {path}")
        for message in failures:
            result("FAIL", message)
        return 1

    text = path.read_text(encoding="utf-8")
    lower = text.lower()

    if "<!doctype html" not in lower and "<html" not in lower:
        failures.append("Missing <!doctype html> or <html.")

    if not has(r"<title\b[^>]*>.*?</title>", text):
        failures.append("Missing <title>.")

    if not has(r"<meta\b[^>]*name=[\"']viewport[\"'][^>]*>", text):
        failures.append("Missing viewport meta.")

    if not has(r"<style\b[^>]*>.*?</style>", text):
        failures.append("Missing embedded <style>.")

    has_script = has(r"<script\b[^>]*>.*?</script>", text)
    interactive_markup = any(
        token in lower
        for token in (
            "<button",
            "<form",
            "onclick=",
            "data-page=",
            "role=\"dialog\"",
            "role='dialog'",
            "<select",
            "<input",
        )
    )
    if interactive_markup and not has_script:
        failures.append("Interactive markup exists but no embedded <script> was found.")

    for pattern in CDN_PATTERNS:
        if pattern in lower:
            failures.append(f"External CDN detected: {pattern}.")

    if "<button" not in lower:
        warnings.append("No <button> found; clickable prototype may be too static.")

    if "<main" not in lower and 'role="main"' not in lower and "role='main'" not in lower:
        warnings.append("No <main> or role=\"main\" landmark found.")

    for message in failures:
        result("FAIL", message)
    for message in warnings:
        result("WARN", message)

    if failures:
        return 1

    result("PASS", f"{path} passed HTML prototype checks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a self-contained HTML prototype.")
    parser.add_argument("html_file", nargs="?", default="prototype.html")
    args = parser.parse_args()
    return validate(Path(args.html_file))


if __name__ == "__main__":
    sys.exit(main())
