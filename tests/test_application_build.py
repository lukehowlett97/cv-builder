from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cv_builder.build import build_pdf_from_file, default_config
from cv_builder.render import RenderError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_CV = PROJECT_ROOT / "tests" / "fixtures" / "heading-structures.md"


class ApplicationBuildTests(unittest.TestCase):
    def test_direct_build_uses_existing_validator_and_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "cv.md"
            output_path = temp_path / "cv.pdf"
            input_path.write_text(VALID_CV.read_text(encoding="utf-8"), encoding="utf-8")

            def fake_render(paths: object) -> None:
                paths.output_pdf.write_bytes(b"pdf")  # type: ignore[attr-defined]

            with (
                patch("cv_builder.build.ensure_dependencies"),
                patch("cv_builder.build.render_pdf", side_effect=fake_render),
            ):
                metadata = build_pdf_from_file(
                    default_config(PROJECT_ROOT), input_path, output_path
                )

            self.assertEqual(metadata["name"], "Layout Fixture")
            self.assertEqual(output_path.read_bytes(), b"pdf")

    def test_direct_build_rejects_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "cv.md"
            input_path.write_text("## Profile\n\nText\n", encoding="utf-8")

            with self.assertRaisesRegex(RenderError, "Missing YAML frontmatter"):
                build_pdf_from_file(
                    default_config(PROJECT_ROOT), input_path, temp_path / "cv.pdf"
                )


if __name__ == "__main__":
    unittest.main()
