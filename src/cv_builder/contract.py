from __future__ import annotations

import re
import sys

from cv_builder.render import RenderError


FRONTMATTER_KEY_PATTERN = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$")
PLAIN_EMAIL_PATTERN = re.compile(r"^[^\s@<>()[\]\\]+@[^\s@<>()[\]\\]+$")
SECTION_PATTERN = re.compile(r"^\s*##\s+(.+?)\s*$", re.MULTILINE)

REQUIRED_METADATA = ("name", "headline", "location", "email")
LAYOUT_BOOLEAN_FIELD = "layout_keep_headings_with_content"
LAYOUT_NEEDSPACE_FIELDS = (
    "layout_h2_needspace",
    "layout_h2_before_h3_needspace",
    "layout_h3_needspace",
)
MIN_NEEDSPACE = 1
MAX_NEEDSPACE = 30

SECTION_ALIASES: dict[str, set[str]] = {
    "profile": {"profile", "summary", "personal profile"},
    "experience": {"experience", "professional experience", "work experience", "employment history"},
    "skills": {"skills", "core skills", "core capabilities", "technical skills", "technical experience"},
    "education": {"education", "qualifications"},
}


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RenderError("Missing YAML frontmatter at the top of input.md")

    metadata: dict[str, str] = {}
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        if not line.strip():
            continue
        match = FRONTMATTER_KEY_PATTERN.match(line)
        if not match:
            raise RenderError(f"Invalid frontmatter line: {line}")
        metadata[match.group(1)] = match.group(2).strip().strip("'\"")

    if end_index is None:
        raise RenderError("Frontmatter is not closed with '---'")

    body = "\n".join(lines[end_index + 1 :]).lstrip()
    return metadata, body


def _normalise_heading(heading: str) -> str:
    return re.sub(r"\s+", " ", heading.strip().lower())


def _check_sections(body: str) -> None:
    sections = {match.group(1).strip() for match in SECTION_PATTERN.finditer(body)}
    normalised = {_normalise_heading(s) for s in sections}

    missing = [
        group
        for group, aliases in SECTION_ALIASES.items()
        if not normalised.intersection(aliases)
    ]

    if missing:
        hint = "; ".join(
            f"{group}: {', '.join(sorted(aliases))}"
            for group, aliases in SECTION_ALIASES.items()
            if group in missing
        )
        print(
            f"Warning: missing recommended section group(s): {', '.join(missing)}.\n"
            f"  Accepted headings — {hint}",
            file=sys.stderr,
        )


def _check_layout_metadata(metadata: dict[str, str]) -> None:
    enabled = metadata.get(LAYOUT_BOOLEAN_FIELD)
    if enabled is not None and enabled.lower() not in {"true", "false"}:
        raise RenderError(
            f"Invalid {LAYOUT_BOOLEAN_FIELD}: expected true or false"
        )

    for field in LAYOUT_NEEDSPACE_FIELDS:
        value = metadata.get(field)
        if value is None:
            continue
        if not re.fullmatch(r"[0-9]+", value):
            raise RenderError(
                f"Invalid {field}: expected an integer from "
                f"{MIN_NEEDSPACE} to {MAX_NEEDSPACE}"
            )
        parsed = int(value)
        if not MIN_NEEDSPACE <= parsed <= MAX_NEEDSPACE:
            raise RenderError(
                f"Invalid {field}: expected an integer from "
                f"{MIN_NEEDSPACE} to {MAX_NEEDSPACE}"
            )


def validate_markdown_contract(markdown: str) -> dict[str, str]:
    metadata, body = parse_frontmatter(markdown)

    missing = [field for field in REQUIRED_METADATA if not metadata.get(field)]
    if missing:
        raise RenderError(f"Missing required frontmatter field(s): {', '.join(missing)}")

    if not PLAIN_EMAIL_PATTERN.fullmatch(metadata["email"]):
        raise RenderError(
            "Invalid email frontmatter: use a plain email address, not a Markdown or mailto link"
        )

    if not body.strip():
        raise RenderError("CV body is empty after frontmatter")

    _check_layout_metadata(metadata)
    _check_sections(body)

    return metadata
