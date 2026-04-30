from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class RenderError(RuntimeError):
    """Raised when rendering prerequisites or PDF generation fails."""


@dataclass(frozen=True)
class RenderPaths:
    input_path: Path
    output_pdf: Path
    template_path: Path


def ensure_dependencies(paths: RenderPaths) -> None:
    missing = [name for name in ("pandoc", "xelatex") if shutil.which(name) is None]
    if missing:
        raise RenderError(f"Missing required command(s): {', '.join(missing)}")
    if not paths.template_path.is_file():
        raise RenderError(f"Template file not found: {paths.template_path}")
    if not paths.input_path.is_file():
        raise RenderError(f"Input file not found: {paths.input_path}")
    if not paths.input_path.read_text(encoding="utf-8").strip():
        raise RenderError(f"Input file is empty: {paths.input_path}")


def render_pdf(paths: RenderPaths) -> None:
    command = [
        "pandoc",
        str(paths.input_path),
        "-o",
        str(paths.output_pdf),
        "--pdf-engine=xelatex",
        f"--template={paths.template_path}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Pandoc failed."
        raise RenderError(message)
