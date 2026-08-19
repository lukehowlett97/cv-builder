from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cv_builder.contract import validate_markdown_contract
from cv_builder.render import RenderError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "tex" / "cv-template.tex"
MULTICOL_FILTER = PROJECT_ROOT / "tex" / "multicol-core-capabilities.lua"
HEADING_FILTER = PROJECT_ROOT / "tex" / "keep-headings-with-content.lua"
FIXTURES = Path(__file__).parent / "fixtures"


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def require_commands(testcase: unittest.TestCase, *commands: str) -> None:
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        testcase.skipTest(f"Missing integration command(s): {', '.join(missing)}")


def pandoc_latex(markdown_path: Path) -> str:
    result = run(
        [
            "pandoc",
            str(markdown_path),
            "--to=latex",
            f"--lua-filter={MULTICOL_FILTER}",
            f"--lua-filter={HEADING_FILTER}",
        ]
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout


def render_twice(markdown_path: Path, output_dir: Path, stem: str) -> tuple[Path, str]:
    tex_path = output_dir / f"{stem}.tex"
    pdf_path = output_dir / f"{stem}.pdf"
    pandoc_result = run(
        [
            "pandoc",
            str(markdown_path),
            "--standalone",
            "--to=latex",
            f"--template={TEMPLATE}",
            f"--lua-filter={MULTICOL_FILTER}",
            f"--lua-filter={HEADING_FILTER}",
            f"--output={tex_path}",
        ]
    )
    if pandoc_result.returncode != 0:
        raise AssertionError(pandoc_result.stderr or pandoc_result.stdout)

    final_log = ""
    for _ in range(2):
        latex_result = run(
            [
                "xelatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={output_dir}",
                str(tex_path),
            ]
        )
        if latex_result.returncode != 0:
            raise AssertionError(latex_result.stdout + latex_result.stderr)
        final_log = (output_dir / f"{stem}.log").read_text(encoding="utf-8")
    return pdf_path, final_log


def page_texts(pdf_path: Path, output_dir: Path, stem: str) -> list[str]:
    pattern = output_dir / f"{stem}-page-%d.txt"
    result = run(["mutool", "draw", "-F", "txt", "-o", str(pattern), str(pdf_path)])
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return [
        path.read_text(encoding="utf-8")
        for path in sorted(output_dir.glob(f"{stem}-page-*.txt"))
    ]


def warning_summary(log: str) -> dict[str, int]:
    return {
        "latex_or_package": len(
            re.findall(r"^(?:LaTeX|Package \S+) Warning:", log, re.MULTILINE)
        ),
        "overfull": len(re.findall(r"^Overfull \\[hv]box", log, re.MULTILINE)),
        "underfull": len(re.findall(r"^Underfull \\[hv]box", log, re.MULTILINE)),
    }


def latex_and_package_warnings(log: str) -> set[str]:
    return set(
        re.findall(r"^(?:LaTeX|Package \S+) Warning:.*$", log, re.MULTILINE)
    )


class HeadingFilterStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_commands(cls, "pandoc")

    def test_h2_before_h3_uses_one_larger_reservation(self) -> None:
        latex = pandoc_latex(FIXTURES / "heading-structures.md")
        section_index = latex.index("\\subsection{H2 Before H3}")
        immediate_index = latex.index("\\subsubsection{Immediate H3}")
        later_index = latex.index("\\subsubsection{Later H3}")

        self.assertIn("\\cvneedspace{10}", latex[:section_index])
        self.assertNotIn("\\cvneedspace{8}", latex[section_index:immediate_index])
        self.assertNotIn(
            "\\cvneedspace{8}",
            latex[immediate_index : latex.rfind("\\cvneedspace{8}", 0, later_index)],
        )
        self.assertEqual(latex[:later_index].count("\\cvneedspace{8}"), 1)

    def test_h2_before_content_uses_normal_reservation(self) -> None:
        latex = pandoc_latex(FIXTURES / "heading-structures.md")
        for heading in ("H2 Before Paragraph", "H2 Before List"):
            heading_index = latex.index(f"\\subsection{{{heading}}}")
            self.assertEqual(
                latex.rfind("\\cvneedspace{6}", 0, heading_index),
                latex.rfind("\\cvneedspace", 0, heading_index),
            )

    def test_h3_paragraph_list_and_direct_list_are_guarded(self) -> None:
        latex = pandoc_latex(FIXTURES / "heading-structures.md")
        immediate_index = latex.index("\\subsubsection{Immediate H3}")
        later_index = latex.index("\\subsubsection{Later H3}")
        direct_index = latex.index("\\subsubsection{Direct List H3}")

        # The first H3 is covered by its preceding H2's combined reservation.
        self.assertNotEqual(
            latex.rfind("\\cvneedspace{8}", 0, immediate_index),
            latex.rfind("\\cvneedspace", 0, immediate_index),
        )
        self.assertEqual(
            latex.rfind("\\cvneedspace{8}", 0, later_index),
            latex.rfind("\\cvneedspace", 0, later_index),
        )
        self.assertEqual(
            latex.rfind("\\cvneedspace{8}", 0, direct_index),
            latex.rfind("\\cvneedspace", 0, direct_index),
        )

    def test_disabled_configuration_emits_no_reservations(self) -> None:
        source = (FIXTURES / "heading-structures.md").read_text(encoding="utf-8")
        source = source.replace(
            "email: test@example.com",
            "email: test@example.com\nlayout_keep_headings_with_content: false",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "disabled.md"
            path.write_text(source, encoding="utf-8")
            self.assertNotIn("\\cvneedspace", pandoc_latex(path))

    def test_custom_reservations_are_used(self) -> None:
        source = (FIXTURES / "heading-structures.md").read_text(encoding="utf-8")
        source = source.replace(
            "email: test@example.com",
            "\n".join(
                (
                    "email: test@example.com",
                    "layout_h2_needspace: 7",
                    "layout_h2_before_h3_needspace: 12",
                    "layout_h3_needspace: 9",
                )
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "custom.md"
            path.write_text(source, encoding="utf-8")
            latex = pandoc_latex(path)
            self.assertIn("\\cvneedspace{7}", latex)
            self.assertIn("\\cvneedspace{12}", latex)
            self.assertIn("\\cvneedspace{9}", latex)

    def test_invalid_layout_metadata_is_rejected(self) -> None:
        source = (FIXTURES / "heading-structures.md").read_text(encoding="utf-8")
        source = source.replace(
            "email: test@example.com",
            "email: test@example.com\nlayout_h3_needspace: many",
        )
        with self.assertRaisesRegex(
            RenderError,
            "Invalid layout_h3_needspace: expected an integer from 1 to 30",
        ):
            validate_markdown_contract(source)

    def test_markdown_email_metadata_is_rejected(self) -> None:
        source = (FIXTURES / "heading-structures.md").read_text(encoding="utf-8")
        source = source.replace(
            "email: test@example.com",
            "email: '[test@example.com](mailto:test@example.com)'",
        )
        with self.assertRaisesRegex(
            RenderError,
            "Invalid email frontmatter: use a plain email address",
        ):
            validate_markdown_contract(source)

    def test_core_capabilities_filter_still_wraps_content(self) -> None:
        latex = pandoc_latex(FIXTURES / "links-and-core.md")
        self.assertIn("\\begin{multicols}{2}", latex)
        self.assertIn("\\end{multicols}", latex)
        core_index = latex.index("\\subsection{Core Capabilities}")
        self.assertEqual(
            latex.rfind("\\cvneedspace{6}", 0, core_index),
            latex.rfind("\\cvneedspace", 0, core_index),
        )

    def test_template_keeps_github_in_footer_and_normalises_website_url(self) -> None:
        result = run(
            [
                "pandoc",
                str(FIXTURES / "links-and-core.md"),
                "--standalone",
                "--to=latex",
                f"--template={TEMPLATE}",
                f"--lua-filter={MULTICOL_FILTER}",
                f"--lua-filter={HEADING_FILTER}",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("\\href{https://github.com/example}{GitHub}"), 1)
        self.assertIn("\\href{https://example.com}{Website}", result.stdout)


class HeadingFilterPdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_commands(cls, "pandoc", "xelatex", "mutool")

    def test_h2_h3_combined_reservation_prevents_stranded_h2(self) -> None:
        source = (FIXTURES / "h2-h3-boundary.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            enabled_md = temp_path / "enabled.md"
            disabled_md = temp_path / "disabled.md"
            enabled_md.write_text(source, encoding="utf-8")
            disabled_md.write_text(
                source.replace(
                    "layout_keep_headings_with_content: true",
                    "layout_keep_headings_with_content: false",
                ),
                encoding="utf-8",
            )

            disabled_pdf, _ = render_twice(disabled_md, temp_path, "disabled")
            enabled_pdf, _ = render_twice(enabled_md, temp_path, "enabled")
            disabled_pages = page_texts(disabled_pdf, temp_path, "disabled")
            enabled_pages = page_texts(enabled_pdf, temp_path, "enabled")

            self.assertIn("Boundary Section", disabled_pages[0])
            self.assertNotIn("Boundary Entry", disabled_pages[0])
            self.assertNotIn("Boundary Section", enabled_pages[0])
            self.assertIn("Boundary Section", enabled_pages[1])
            self.assertIn("Boundary Entry", enabled_pages[1])
            self.assertIn("This introduction must stay", enabled_pages[1])
            self.assertIn("This first bullet must begin", enabled_pages[1])

    def test_large_entry_remains_splittable(self) -> None:
        bullets = "\n".join(
            f"- Large-section marker {index}: content remains normally breakable."
            for index in range(1, 61)
        )
        source = f"""---
name: Layout Fixture
headline: Splittable section test
location: Test
email: test@example.com
---

## Large Section

### Large Entry

Introductory content stays with the heading.

{bullets}
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            markdown_path = temp_path / "large.md"
            markdown_path.write_text(source, encoding="utf-8")
            pdf_path, _ = render_twice(markdown_path, temp_path, "large")
            pages = page_texts(pdf_path, temp_path, "large")

            self.assertGreaterEqual(len(pages), 2)
            self.assertIn("Large Entry", pages[0])
            self.assertIn("Large-section marker 1", pages[0])
            self.assertTrue(any("Large-section marker 60" in page for page in pages[1:]))

    def test_links_destinations_and_warning_delta(self) -> None:
        source = (FIXTURES / "links-and-core.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            enabled_md = temp_path / "enabled.md"
            disabled_md = temp_path / "disabled.md"
            enabled_md.write_text(source, encoding="utf-8")
            disabled_md.write_text(
                source.replace(
                    "email: test@example.com",
                    "email: test@example.com\nlayout_keep_headings_with_content: false",
                ),
                encoding="utf-8",
            )

            baseline_pdf, baseline_log = render_twice(
                disabled_md, temp_path, "warning-baseline"
            )
            enabled_pdf, enabled_log = render_twice(
                enabled_md, temp_path, "warning-enabled"
            )
            baseline = warning_summary(baseline_log)
            enabled = warning_summary(enabled_log)

            self.assertFalse(
                latex_and_package_warnings(enabled_log)
                - latex_and_package_warnings(baseline_log)
            )
            self.assertLessEqual(
                enabled["latex_or_package"], baseline["latex_or_package"]
            )
            self.assertLessEqual(enabled["overfull"], baseline["overfull"])
            self.assertLessEqual(enabled["underfull"], baseline["underfull"] + 1)

            uri_structure = run(
                ["mutool", "show", str(enabled_pdf), "grep", "URI"]
            ).stdout
            destination_structure = run(
                ["mutool", "show", str(enabled_pdf), "grep", "Dests"]
            ).stdout
            self.assertIn("https://example.org/test", uri_structure)
            self.assertIn("linked-entry", destination_structure)
            self.assertTrue(baseline_pdf.is_file())

    def test_current_cv_remains_two_pages(self) -> None:
        input_path = PROJECT_ROOT / "input.md"
        if not input_path.is_file():
            self.skipTest("Private input.md is not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path, final_log = render_twice(input_path, temp_path, "current-cv")
            info = run(["mutool", "info", str(pdf_path)])
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertRegex(info.stdout, r"Pages:\s+2")
            self.assertEqual(warning_summary(final_log)["overfull"], 0)


if __name__ == "__main__":
    unittest.main()
