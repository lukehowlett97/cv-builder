from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cv_builder.contract import validate_markdown_contract
from cv_builder.naming import slugify_filename, suggested_name
from cv_builder.render import RenderError, RenderPaths, ensure_dependencies, render_pdf


@dataclass(frozen=True)
class BuildConfig:
    project_root: Path
    input_path: Path
    runs_dir: Path
    template_path: Path
    input_template_path: Path


@dataclass(frozen=True)
class BuildResult:
    name: str
    run_dir: Path
    markdown_path: Path
    pdf_path: Path
    cleared_input: bool
    metadata: dict[str, str]


def default_config(project_root: Path) -> BuildConfig:
    return BuildConfig(
        project_root=project_root,
        input_path=project_root / "input.md",
        runs_dir=project_root / "runs",
        template_path=project_root / "tex" / "cv-template.tex",
        input_template_path=project_root / "input" / "cv.md",
    )


def ensure_working_input(input_path: Path, input_template_path: Path) -> None:
    if input_path.is_file():
        return
    if not input_template_path.is_file():
        raise RenderError(
            f"Input file not found: {input_path} and template file not found: {input_template_path}"
        )
    input_path.write_text(input_template_path.read_text(encoding="utf-8"), encoding="utf-8")


def read_input_markdown(input_path: Path, input_template_path: Path) -> str:
    ensure_working_input(input_path, input_template_path)
    content = input_path.read_text(encoding="utf-8")
    if not content.strip():
        raise RenderError(f"Input file is empty: {input_path}")
    return content


def reset_working_input(input_path: Path, input_template_path: Path) -> None:
    if not input_template_path.is_file():
        raise RenderError(f"Input template file not found: {input_template_path}")
    input_path.write_text(input_template_path.read_text(encoding="utf-8"), encoding="utf-8")


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


def build_cv(config: BuildConfig, output_name: str | None, dry_run: bool = False) -> BuildResult:
    markdown = read_input_markdown(config.input_path, config.input_template_path)
    metadata = validate_markdown_contract(markdown)
    _, final_name = resolve_output_name(markdown, output_name)

    run_dir, markdown_output, pdf_output = resolve_run_artifact_paths(config.runs_dir, final_name)

    if dry_run:
        return BuildResult(
            name=final_name,
            run_dir=run_dir,
            markdown_path=markdown_output,
            pdf_path=pdf_output,
            cleared_input=False,
            metadata=metadata,
        )

    markdown_output.write_text(markdown, encoding="utf-8")
    try:
        paths = RenderPaths(markdown_output, pdf_output, config.template_path)
        ensure_dependencies(paths)
        render_pdf(paths)
    except Exception:
        if markdown_output.exists():
            markdown_output.unlink()
        raise

    reset_working_input(config.input_path, config.input_template_path)
    return BuildResult(
        name=final_name,
        run_dir=run_dir,
        markdown_path=markdown_output,
        pdf_path=pdf_output,
        cleared_input=True,
        metadata=metadata,
    )
