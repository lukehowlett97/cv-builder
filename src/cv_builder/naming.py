from __future__ import annotations

import re
import unicodedata
from datetime import date


H1_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$")
FRONTMATTER_KEY_PATTERN = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$")


def extract_frontmatter_value(markdown: str, key: str) -> str | None:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for line in lines[1:]:
        if line.strip() == "---":
            return None
        match = FRONTMATTER_KEY_PATTERN.match(line)
        if match and match.group(1) == key:
            value = match.group(2).strip().strip("'\"")
            return value or None
    return None


def extract_first_h1(markdown: str) -> str | None:
    for line in markdown.splitlines():
        match = H1_PATTERN.match(line)
        if match:
            title = match.group(1).strip()
            return title or None
    return None


def default_name(today: date | None = None) -> str:
    resolved = today or date.today()
    return f"cv-{resolved.isoformat()}"


def slugify_filename(value: str, fallback: str | None = None) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().strip()
    lowered = re.sub(r"[\s_]+", "-", lowered)
    lowered = re.sub(r"[^a-z0-9-]+", "", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    if lowered:
        return lowered
    if fallback:
        return slugify_filename(fallback)
    return default_name()


def suggested_name(markdown: str) -> str:
    title = extract_frontmatter_value(markdown, "name") or extract_first_h1(markdown)
    return slugify_filename(title or default_name(), fallback=default_name())
