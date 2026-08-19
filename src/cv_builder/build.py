from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from cv_builder.contract import parse_frontmatter, validate_markdown_contract
from cv_builder.naming import slugify_filename, suggested_name
from cv_builder.render import (
    DocxRenderPaths,
    RenderError,
    RenderPaths,
    ensure_dependencies,
    ensure_docx_dependencies,
    render_docx,
    render_pdf,
)


@dataclass(frozen=True)
class BuildConfig:
    project_root: Path
    input_path: Path
    runs_dir: Path
    template_path: Path
    example_input_path: Path
    metadata_path: Path
    cover_input_path: Path


@dataclass(frozen=True)
class BuildResult:
    name: str
    run_dir: Path
    markdown_path: Path
    pdf_path: Path
    cover_docx_path: Path | None
    cleared_input: bool
    metadata: dict[str, str]


def default_config(project_root: Path) -> BuildConfig:
    return BuildConfig(
        project_root=project_root,
        input_path=project_root / "input.md",
        runs_dir=project_root / "runs",
        template_path=project_root / "tex" / "cv-template.tex",
        example_input_path=project_root / "example_input.md",
        metadata_path=project_root / "input" / "metadata.yml",
        cover_input_path=project_root / "cover_input.txt",
    )


def ensure_working_input(input_path: Path, example_input_path: Path) -> None:
    if input_path.is_file():
        return
    if not example_input_path.is_file():
        raise RenderError(
            f"Input file not found: {input_path} and example input file not found: {example_input_path}"
        )
    input_path.write_text(example_input_path.read_text(encoding="utf-8"), encoding="utf-8")


def read_input_markdown(input_path: Path, example_input_path: Path) -> str:
    ensure_working_input(input_path, example_input_path)
    content = input_path.read_text(encoding="utf-8")
    if not content.strip():
        raise RenderError(f"Input file is empty: {input_path}")
    return content


def has_frontmatter(markdown: str) -> bool:
    lines = markdown.lstrip().splitlines()
    return bool(lines and lines[0].strip() == "---")


def normalize_frontmatter(markdown: str) -> str:
    lines = markdown.lstrip().splitlines()
    if not lines or lines[0].strip() != "---":
        return markdown.lstrip()

    while len(lines) > 1 and not lines[1].strip():
        del lines[1]

    return "\n".join(lines) + "\n"


def read_metadata_frontmatter(metadata_path: Path) -> str:
    if not metadata_path.is_file():
        raise RenderError(
            "Missing YAML frontmatter at the top of input.md and fallback metadata file "
            f"not found: {metadata_path}"
        )

    content = metadata_path.read_text(encoding="utf-8").strip()
    if not content:
        raise RenderError(f"Fallback metadata file is empty: {metadata_path}")

    frontmatter = content if content.startswith("---") else f"---\n{content}\n---"
    parse_frontmatter(frontmatter)
    return frontmatter


def resolve_markdown_with_metadata(markdown: str, metadata_path: Path) -> str:
    if has_frontmatter(markdown):
        return normalize_frontmatter(markdown)
    frontmatter = read_metadata_frontmatter(metadata_path)
    return f"{frontmatter}\n\n{markdown.lstrip()}"


def resolve_output_name(markdown: str, provided_name: str | None) -> tuple[str, str]:
    suggestion = suggested_name(markdown)
    chosen = (provided_name or "").strip()
    return suggestion, slugify_filename(chosen or suggestion, fallback=suggestion)


def resolve_run_artifact_paths(runs_dir: Path, base_name: str) -> tuple[Path, Path, Path]:
    run_dir = runs_dir / base_name
    run_dir.mkdir(parents=True, exist_ok=True)

    markdown_output = run_dir / f"{base_name}.md"
    pdf_output = run_dir / f"{base_name}.pdf"
    if not markdown_output.exists() and not pdf_output.exists():
        return run_dir, markdown_output, pdf_output

    index = 1
    while True:
        indexed_name = f"{base_name}-{index}"
        markdown_output = run_dir / f"{indexed_name}.md"
        pdf_output = run_dir / f"{indexed_name}.pdf"
        if not markdown_output.exists() and not pdf_output.exists():
            return run_dir, markdown_output, pdf_output
        index += 1


def resolve_cover_docx_path(cover_input_path: Path, markdown_output: Path) -> Path | None:
    if not cover_input_path.is_file():
        return None
    return markdown_output.with_name(f"{markdown_output.stem}-cover.docx")


def resolve_cover_docx_path_from_text(cover_text: str | None, markdown_output: Path) -> Path | None:
    if not cover_text or not cover_text.strip():
        return None
    return markdown_output.with_name(f"{markdown_output.stem}-cover.docx")


def _render_cover_docx(config: BuildConfig, cover_text: str | None, cover_docx_output: Path) -> None:
    if cover_text is not None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(cover_text)
            cover_input = Path(f.name)
        try:
            docx_paths = DocxRenderPaths(cover_input, cover_docx_output)
            ensure_docx_dependencies(docx_paths)
            render_docx(docx_paths)
        finally:
            cover_input.unlink(missing_ok=True)
    else:
        docx_paths = DocxRenderPaths(config.cover_input_path, cover_docx_output)
        ensure_docx_dependencies(docx_paths)
        render_docx(docx_paths)


def build_cv_from_content(
    config: BuildConfig,
    markdown: str,
    output_name: str | None = None,
    cover_text: str | None = None,
    dry_run: bool = False,
) -> BuildResult:
    markdown = resolve_markdown_with_metadata(markdown, config.metadata_path)
    metadata = validate_markdown_contract(markdown)
    _, final_name = resolve_output_name(markdown, output_name)

    run_dir, markdown_output, pdf_output = resolve_run_artifact_paths(config.runs_dir, final_name)
    if cover_text is not None:
        cover_docx_output = resolve_cover_docx_path_from_text(cover_text, markdown_output)
    else:
        cover_docx_output = resolve_cover_docx_path(config.cover_input_path, markdown_output)

    if dry_run:
        return BuildResult(
            name=final_name,
            run_dir=run_dir,
            markdown_path=markdown_output,
            pdf_path=pdf_output,
            cover_docx_path=cover_docx_output,
            cleared_input=False,
            metadata=metadata,
        )

    markdown_output.write_text(markdown, encoding="utf-8")
    try:
        paths = RenderPaths(markdown_output, pdf_output, config.template_path)
        ensure_dependencies(paths)
        render_pdf(paths)
        if cover_docx_output is not None:
            _render_cover_docx(config, cover_text, cover_docx_output)
    except Exception:
        if markdown_output.exists():
            markdown_output.unlink()
        if pdf_output.exists():
            pdf_output.unlink()
        if cover_docx_output is not None and cover_docx_output.exists():
            cover_docx_output.unlink()
        raise

    return BuildResult(
        name=final_name,
        run_dir=run_dir,
        markdown_path=markdown_output,
        pdf_path=pdf_output,
        cover_docx_path=cover_docx_output,
        cleared_input=False,
        metadata=metadata,
    )


def build_cv(config: BuildConfig, output_name: str | None, dry_run: bool = False) -> BuildResult:
    markdown = read_input_markdown(config.input_path, config.example_input_path)
    return build_cv_from_content(config, markdown, output_name, dry_run=dry_run)


def build_pdf_from_file(config: BuildConfig, input_path: Path, output_path: Path) -> dict[str, str]:
    """Validate and render one Markdown CV without creating a run snapshot."""
    if not input_path.is_file():
        raise RenderError(f"Input file not found: {input_path}")

    markdown = input_path.read_text(encoding="utf-8")
    if not markdown.strip():
        raise RenderError(f"Input file is empty: {input_path}")

    metadata = validate_markdown_contract(markdown)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        dir=output_path.parent,
        prefix=f".{output_path.stem}-",
        suffix=".pdf",
        delete=False,
    ) as temp_file:
        temp_output = Path(temp_file.name)
    temp_output.unlink()

    try:
        paths = RenderPaths(input_path, temp_output, config.template_path)
        ensure_dependencies(paths)
        render_pdf(paths)
        temp_output.replace(output_path)
    finally:
        temp_output.unlink(missing_ok=True)

    return metadata
