from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


class RenderError(RuntimeError):
    """Raised when rendering prerequisites or PDF generation fails."""


@dataclass(frozen=True)
class RenderPaths:
    input_path: Path
    output_pdf: Path
    template_path: Path


@dataclass(frozen=True)
class DocxRenderPaths:
    input_path: Path
    output_docx: Path


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


def ensure_docx_dependencies(paths: DocxRenderPaths) -> None:
    if shutil.which("pandoc") is None:
        raise RenderError("Missing required command(s): pandoc")
    if not paths.input_path.is_file():
        raise RenderError(f"Cover input file not found: {paths.input_path}")
    if not paths.input_path.read_text(encoding="utf-8").strip():
        raise RenderError(f"Cover input file is empty: {paths.input_path}")


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


def render_docx(paths: DocxRenderPaths) -> None:
    command = [
        "pandoc",
        str(paths.input_path),
        "--from",
        "markdown",
        "-o",
        str(paths.output_docx),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Pandoc failed."
        raise RenderError(message)
    set_docx_font(paths.output_docx, "Arial")


def set_docx_font(docx_path: Path, font_name: str) -> None:
    word_namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ElementTree.register_namespace("w", word_namespace)
    ns = {"w": word_namespace}
    rfonts_key = f"{{{word_namespace}}}rFonts"
    font_attributes = (
        f"{{{word_namespace}}}ascii",
        f"{{{word_namespace}}}hAnsi",
        f"{{{word_namespace}}}eastAsia",
        f"{{{word_namespace}}}cs",
    )
    theme_font_attributes = (
        f"{{{word_namespace}}}asciiTheme",
        f"{{{word_namespace}}}hAnsiTheme",
        f"{{{word_namespace}}}eastAsiaTheme",
        f"{{{word_namespace}}}cstheme",
    )

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with zipfile.ZipFile(docx_path, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            for item in source.infolist():
                content = source.read(item.filename)
                if item.filename == "word/styles.xml":
                    root = ElementTree.fromstring(content)

                    for rfonts in root.findall(".//w:rFonts", ns):
                        for attribute in theme_font_attributes:
                            rfonts.attrib.pop(attribute, None)
                        for attribute in font_attributes:
                            rfonts.set(attribute, font_name)

                    doc_defaults = root.find("w:docDefaults", ns)
                    if doc_defaults is None:
                        doc_defaults = ElementTree.SubElement(root, f"{{{word_namespace}}}docDefaults")
                    rpr_default = doc_defaults.find("w:rPrDefault", ns)
                    if rpr_default is None:
                        rpr_default = ElementTree.SubElement(doc_defaults, f"{{{word_namespace}}}rPrDefault")
                    rpr = rpr_default.find("w:rPr", ns)
                    if rpr is None:
                        rpr = ElementTree.SubElement(rpr_default, f"{{{word_namespace}}}rPr")
                    rfonts = rpr.find("w:rFonts", ns)
                    if rfonts is None:
                        rfonts = ElementTree.SubElement(rpr, rfonts_key)
                    for attribute in theme_font_attributes:
                        rfonts.attrib.pop(attribute, None)
                    for attribute in font_attributes:
                        rfonts.set(attribute, font_name)

                    content = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
                target.writestr(item, content)
        shutil.move(str(temp_path), docx_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
