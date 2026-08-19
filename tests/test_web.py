from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cv_builder.build import (
    BuildConfig,
    build_cv,
    build_cv_from_content,
    default_config,
    resolve_cover_docx_path_from_text,
    resolve_output_name,
    resolve_run_artifact_paths,
)
from cv_builder.render import RenderError
from cv_builder.web import (
    WebError,
    _open_in_file_manager,
    _running_under_wsl,
    _safe_relative_path,
    _validate_cover_text,
    _validate_markdown,
    _validate_output_name,
    create_server,
)

VALID_MARKDOWN = """---
name: Test Candidate
headline: Software Engineer
location: London, UK
email: test@example.com
---

## Profile

A short profile.

## Professional experience

### Software Engineer
**Example Co** — London
*2020 – Present*

- Built things.

## Core capabilities

- Python

## Education

**Degree** — University
"""


def make_config(tmp_path: Path) -> BuildConfig:
    config = default_config(tmp_path)
    (tmp_path / "input").mkdir(parents=True, exist_ok=True)
    (tmp_path / "input" / "metadata.yml").write_text(
        "name: Fallback Name\nheadline: Fallback Headline\nlocation: Fallback\nemail: fallback@example.com\n",
        encoding="utf-8",
    )
    (tmp_path / "tex").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tex" / "cv-template.tex").write_text("template", encoding="utf-8")
    return config


class BuildFromContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = make_config(self.tmp_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _patch_render_pdf(self):
        patcher = mock.patch("cv_builder.build.render_pdf")
        mock_render = patcher.start()
        mock_render.side_effect = lambda paths: paths.output_pdf.write_bytes(b"%PDF-1.4")
        self.addCleanup(patcher.stop)
        return mock_render

    def _patch_ensure_dependencies(self):
        patcher = mock.patch("cv_builder.build.ensure_dependencies")
        mock_ensure = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_ensure

    def _patch_render_docx(self):
        patcher = mock.patch("cv_builder.build.render_docx")
        mock_docx = patcher.start()
        mock_docx.side_effect = lambda paths: paths.output_docx.write_bytes(b"PK docx")
        self.addCleanup(patcher.stop)
        return mock_docx

    def _patch_ensure_docx_dependencies(self):
        patcher = mock.patch("cv_builder.build.ensure_docx_dependencies")
        mock_ensure = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_ensure

    def test_valid_generation_writes_files(self) -> None:
        mock_ensure = self._patch_ensure_dependencies()
        mock_render = self._patch_render_pdf()
        result = build_cv_from_content(
            self.config,
            VALID_MARKDOWN,
            output_name="test-cv",
        )
        self.assertEqual(result.name, "test-cv")
        self.assertTrue(result.markdown_path.is_file())
        self.assertTrue(result.pdf_path.is_file())
        self.assertIsNone(result.cover_docx_path)
        mock_ensure.assert_called_once()
        mock_render.assert_called_once()

    def test_cover_text_generates_docx(self) -> None:
        self._patch_ensure_dependencies()
        self._patch_render_pdf()
        mock_docx = self._patch_render_docx()
        mock_docx_ensure = self._patch_ensure_docx_dependencies()
        result = build_cv_from_content(
            self.config,
            VALID_MARKDOWN,
            output_name="my-cv",
            cover_text="Dear Hiring Manager,\n\nI am applying.",
        )
        self.assertIsNotNone(result.cover_docx_path)
        self.assertTrue(result.cover_docx_path.is_file())
        mock_docx.assert_called_once()
        mock_docx_ensure.assert_called_once()

    def test_empty_cover_text_skips_docx(self) -> None:
        self._patch_ensure_dependencies()
        self._patch_render_pdf()
        patcher = mock.patch("cv_builder.build.render_docx")
        mock_docx = patcher.start()
        self.addCleanup(patcher.stop)
        result = build_cv_from_content(
            self.config,
            VALID_MARKDOWN,
            output_name="my-cv",
            cover_text="   ",
        )
        self.assertIsNone(result.cover_docx_path)
        mock_docx.assert_not_called()

    def test_missing_required_frontmatter_raises(self) -> None:
        with self.assertRaises(RenderError):
            build_cv_from_content(
                self.config,
                "---\nname: Only Name\n---\n\n## Profile\n\nBody.",
                output_name="my-cv",
            )

    def test_empty_markdown_raises(self) -> None:
        with self.assertRaises(RenderError):
            build_cv_from_content(self.config, "", output_name="my-cv")

    def test_cleanup_on_render_failure(self) -> None:
        self._patch_ensure_dependencies()
        patcher = mock.patch("cv_builder.build.render_pdf")
        mock_render = patcher.start()
        mock_render.side_effect = RenderError("pandoc exploded")
        self.addCleanup(patcher.stop)
        with self.assertRaises(RenderError):
            build_cv_from_content(self.config, VALID_MARKDOWN, output_name="my-cv")
        self.assertFalse((self.config.runs_dir / "my-cv" / "my-cv.md").exists())
        self.assertFalse((self.config.runs_dir / "my-cv" / "my-cv.pdf").exists())

    def test_cli_build_cv_still_works(self) -> None:
        self._patch_ensure_dependencies()
        self._patch_render_pdf()
        (self.tmp_path / "input.md").write_text(VALID_MARKDOWN, encoding="utf-8")
        result = build_cv(self.config, "cli-cv")
        self.assertEqual(result.name, "cli-cv")
        self.assertTrue(result.pdf_path.is_file())


class OutputNameTests(unittest.TestCase):
    def test_resolve_output_name_uses_provided(self) -> None:
        suggestion, chosen = resolve_output_name(VALID_MARKDOWN, "My Custom Name")
        self.assertEqual(chosen, "my-custom-name")

    def test_resolve_output_name_falls_back_to_suggestion(self) -> None:
        suggestion, chosen = resolve_output_name(VALID_MARKDOWN, None)
        self.assertEqual(chosen, suggestion)

    def test_resolve_run_artifact_paths_creates_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            run_dir, md, pdf = resolve_run_artifact_paths(runs_dir, "test-cv")
            self.assertTrue(run_dir.is_dir())
            self.assertEqual(md.name, "test-cv.md")
            self.assertEqual(pdf.name, "test-cv.pdf")

    def test_resolve_run_artifact_paths_indexes_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            run_dir, md, pdf = resolve_run_artifact_paths(runs_dir, "test-cv")
            md.write_text("x", encoding="utf-8")
            pdf.write_text("x", encoding="utf-8")
            _, md2, pdf2 = resolve_run_artifact_paths(runs_dir, "test-cv")
            self.assertEqual(md2.name, "test-cv-1.md")
            self.assertEqual(pdf2.name, "test-cv-1.pdf")

    def test_resolve_cover_docx_path_from_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "my-cv.md"
            self.assertIsNone(resolve_cover_docx_path_from_text(None, md_path))
            self.assertIsNone(resolve_cover_docx_path_from_text("", md_path))
            self.assertIsNone(resolve_cover_docx_path_from_text("   ", md_path))
            path = resolve_cover_docx_path_from_text("Some text", md_path)
            self.assertEqual(path.name, "my-cv-cover.docx")


class ValidationTests(unittest.TestCase):
    def test_validate_output_name(self) -> None:
        self.assertEqual(_validate_output_name("  my-cv  "), "my-cv")
        for bad in ("", "   ", "a/b", "a\\b", "..", "a/../b"):
            with self.assertRaises(WebError):
                _validate_output_name(bad)

    def test_validate_markdown(self) -> None:
        self.assertEqual(_validate_markdown("  hello  "), "  hello  ")
        with self.assertRaises(WebError):
            _validate_markdown("")
        with self.assertRaises(WebError):
            _validate_markdown("   ")

    def test_validate_cover_text(self) -> None:
        self.assertIsNone(_validate_cover_text(None))
        self.assertIsNone(_validate_cover_text(""))
        self.assertIsNone(_validate_cover_text("   "))
        self.assertEqual(_validate_cover_text("  hello  "), "hello")


class SafePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = make_config(self.tmp_path)
        self.runs_dir = self.config.runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.runs_dir / "test.pdf").write_bytes(b"%PDF-1.4 test")
        (self.runs_dir / "test.md").write_text("# Test", encoding="utf-8")
        (self.runs_dir / "test.docx").write_bytes(b"PK test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allowed_extensions(self) -> None:
        for name in ("test.pdf", "test.md", "test.docx"):
            path = _safe_relative_path(self.config, name)
            self.assertEqual(path.name, name)

    def test_path_traversal_rejected(self) -> None:
        for raw in ("../secret.txt", "..%2Fsecret.txt", "%2e%2e/secret.txt", "a/../../secret.txt"):
            with self.assertRaises(WebError) as ctx:
                _safe_relative_path(self.config, raw)
            self.assertEqual(ctx.exception.status, 403)

    def test_unsupported_extension_rejected(self) -> None:
        (self.runs_dir / "test.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(WebError) as ctx:
            _safe_relative_path(self.config, "test.txt")
        self.assertEqual(ctx.exception.status, 403)

    def test_missing_file_returns_404(self) -> None:
        with self.assertRaises(WebError) as ctx:
            _safe_relative_path(self.config, "missing.pdf")
        self.assertEqual(ctx.exception.status, 404)


class FileManagerTests(unittest.TestCase):
    def test_wsl_interop_environment_is_detected(self) -> None:
        with mock.patch.dict("cv_builder.web.os.environ", {"WSL_INTEROP": "1"}, clear=True):
            self.assertTrue(_running_under_wsl())

    def test_wsl_proc_version_is_detected(self) -> None:
        with (
            mock.patch.dict("cv_builder.web.os.environ", {}, clear=True),
            mock.patch("cv_builder.web.Path.read_text", return_value="Linux Microsoft WSL2"),
        ):
            self.assertTrue(_running_under_wsl())

    def test_wsl_uses_windows_path_with_explorer(self) -> None:
        output_path = Path("/tmp/cv-builder/runs/example")
        with (
            mock.patch("cv_builder.web._running_under_wsl", return_value=True),
            mock.patch("cv_builder.web.shutil.which", return_value="/mnt/c/Windows/explorer.exe"),
            mock.patch(
                "cv_builder.web.subprocess.check_output",
                return_value="C:\\tmp\\cv-builder\\runs\\example\n",
            ) as mock_check_output,
            mock.patch("cv_builder.web.subprocess.Popen") as mock_popen,
        ):
            _open_in_file_manager(output_path)

        mock_check_output.assert_called_once_with(
            ["wslpath", "-w", str(output_path)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        mock_popen.assert_called_once_with(
            ["/mnt/c/Windows/explorer.exe", "C:\\tmp\\cv-builder\\runs\\example"],
            cwd="/mnt/c/Windows",
        )

    def test_linux_uses_xdg_open(self) -> None:
        output_path = Path("/tmp/cv-builder/runs/example")
        with (
            mock.patch("cv_builder.web.os.name", "posix"),
            mock.patch("cv_builder.web.sys.platform", "linux"),
            mock.patch("cv_builder.web._running_under_wsl", return_value=False),
            mock.patch("cv_builder.web.subprocess.Popen") as mock_popen,
        ):
            _open_in_file_manager(output_path)

        mock_popen.assert_called_once_with(["xdg-open", str(output_path)])


class WebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = make_config(self.tmp_path)
        self.server = create_server(self.config, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        import threading

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def _request_json(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import urllib.request

        url = self.base_url + path
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _request_bytes(self, path: str) -> tuple[int, bytes]:
        import urllib.request

        req = urllib.request.Request(self.base_url + path, method="GET")
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_status_endpoint(self) -> None:
        status, data = self._request_json("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertIn("ok", data)
        self.assertIn("missing", data)
        self.assertIn("runs_dir", data)

    def test_index_served(self) -> None:
        status, body = self._request_bytes("/")
        self.assertEqual(status, 200)
        self.assertIn("CV Builder", body.decode("utf-8"))

    def test_static_assets_served(self) -> None:
        for path in ("/static/style.css", "/static/app.js"):
            status, body = self._request_bytes(path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 0)

    @mock.patch("cv_builder.web.build_cv_from_content")
    def test_generate_valid_request(self, mock_build) -> None:
        result = mock.Mock()
        result.configure_mock(
            name="my-cv",
            run_dir=self.config.runs_dir / "my-cv",
            markdown_path=self.config.runs_dir / "my-cv" / "my-cv.md",
            pdf_path=self.config.runs_dir / "my-cv" / "my-cv.pdf",
            cover_docx_path=None,
        )
        mock_build.return_value = result
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": VALID_MARKDOWN, "name": "my-cv", "cover_text": ""},
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["name"], "my-cv")
        self.assertEqual(data["cover_status"], "not-requested")
        self.assertIn("pdf_url", data)
        self.assertIn("generated_at", data)
        self.assertEqual(data["run_dir_rel"], "runs/my-cv")
        self.assertEqual(len(data["files"]), 2)
        self.assertEqual(data["files"][0]["name"], "my-cv.md")
        self.assertEqual(data["files"][0]["path"], "runs/my-cv/my-cv.md")
        self.assertEqual(data["files"][1]["name"], "my-cv.pdf")
        self.assertEqual(data["files"][1]["path"], "runs/my-cv/my-cv.pdf")
        self.assertEqual(data["files"][1]["type"], "pdf")
        self.assertIn("url", data["files"][1])

    @mock.patch("cv_builder.web.build_cv_from_content")
    def test_generate_with_cover_text(self, mock_build) -> None:
        result = mock.Mock()
        result.configure_mock(
            name="my-cv",
            run_dir=self.config.runs_dir / "my-cv",
            markdown_path=self.config.runs_dir / "my-cv" / "my-cv.md",
            pdf_path=self.config.runs_dir / "my-cv" / "my-cv.pdf",
            cover_docx_path=self.config.runs_dir / "my-cv" / "my-cv-cover.docx",
        )
        mock_build.return_value = result
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": VALID_MARKDOWN, "name": "my-cv", "cover_text": "Cover letter text"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["cover_status"], "generated")
        self.assertIsNotNone(data["cover_url"])
        self.assertEqual(len(data["files"]), 3)
        cover = [f for f in data["files"] if f["type"] == "docx"][0]
        self.assertEqual(cover["name"], "my-cv-cover.docx")
        self.assertEqual(cover["path"], "runs/my-cv/my-cv-cover.docx")
        self.assertEqual(cover["kind"], "cover")

    def test_generate_missing_markdown(self) -> None:
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": "", "name": "my-cv", "cover_text": ""},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_generate_missing_name(self) -> None:
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": VALID_MARKDOWN, "name": "", "cover_text": ""},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_generate_invalid_name_path_traversal(self) -> None:
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": VALID_MARKDOWN, "name": "../evil", "cover_text": ""},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_generate_invalid_json(self) -> None:
        import urllib.request

        req = urllib.request.Request(
            self.base_url + "/api/generate",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as response:
                self.fail("Expected HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            data = json.loads(exc.read().decode("utf-8"))
            self.assertIn("error", data)

    @mock.patch("cv_builder.web.build_cv_from_content")
    def test_generate_render_error_returns_422(self, mock_build) -> None:
        mock_build.side_effect = RenderError("Missing required frontmatter field(s): email")
        status, data = self._request_json(
            "POST",
            "/api/generate",
            {"markdown": VALID_MARKDOWN, "name": "my-cv", "cover_text": ""},
        )
        self.assertEqual(status, 422)
        self.assertIn("error", data)

    def test_file_access_ok(self) -> None:
        (self.config.runs_dir / "my-cv").mkdir(parents=True, exist_ok=True)
        (self.config.runs_dir / "my-cv" / "my-cv.pdf").write_bytes(b"%PDF-1.4 test")
        status, body = self._request_bytes("/api/files/my-cv/my-cv.pdf")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"%PDF-1.4 test")

    def test_preview_route_serves_pdf_inline(self) -> None:
        (self.config.runs_dir / "my-cv").mkdir(parents=True, exist_ok=True)
        (self.config.runs_dir / "my-cv" / "my-cv.pdf").write_bytes(b"%PDF-1.4 preview")
        import urllib.request

        req = urllib.request.Request(
            self.base_url + "/api/preview/my-cv/my-cv.pdf?t=123&v=abc",
            method="GET",
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"%PDF-1.4 preview")
            self.assertEqual(response.headers.get("Content-Disposition"), "inline")

    def test_preview_route_rejects_non_pdf(self) -> None:
        (self.config.runs_dir / "my-cv").mkdir(parents=True, exist_ok=True)
        (self.config.runs_dir / "my-cv" / "my-cv.md").write_text("# Test", encoding="utf-8")
        status, data = self._request_json("GET", "/api/preview/my-cv/my-cv.md")
        self.assertEqual(status, 403)
        self.assertIn("error", data)

    def test_preview_route_rejects_traversal(self) -> None:
        status, data = self._request_json("GET", "/api/preview/../secret.pdf")
        self.assertEqual(status, 403)
        self.assertIn("error", data)

    def test_sample_route(self) -> None:
        (self.tmp_path / "example_input.md").write_text("# Sample CV", encoding="utf-8")
        status, data = self._request_json("GET", "/api/sample")
        self.assertEqual(status, 200)
        self.assertEqual(data["markdown"], "# Sample CV")

    def test_sample_route_missing(self) -> None:
        status, data = self._request_json("GET", "/api/sample")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    @mock.patch("cv_builder.web._open_in_file_manager")
    def test_open_output_route(self, mock_open) -> None:
        self.config.runs_dir.mkdir(parents=True, exist_ok=True)
        status, data = self._request_json("POST", "/api/open-output")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        mock_open.assert_called_once_with(self.config.runs_dir)

    @mock.patch("cv_builder.web._open_in_file_manager")
    def test_open_output_route_opens_selected_run(self, mock_open) -> None:
        run_dir = self.config.runs_dir / "my-cv"
        run_dir.mkdir(parents=True)
        status, data = self._request_json("POST", "/api/open-output", {"run": "my-cv"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        mock_open.assert_called_once_with(run_dir.resolve())

    @mock.patch("cv_builder.web._open_in_file_manager")
    def test_open_output_route_rejects_traversal(self, mock_open) -> None:
        self.config.runs_dir.mkdir(parents=True)
        status, data = self._request_json("POST", "/api/open-output", {"run": "../outside"})
        self.assertEqual(status, 400)
        self.assertIn("error", data)
        mock_open.assert_not_called()

    def test_open_output_route_missing_dir(self) -> None:
        status, data = self._request_json("POST", "/api/open-output")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_file_access_traversal_rejected(self) -> None:
        status, data = self._request_json("GET", "/api/files/../secret.txt")
        self.assertEqual(status, 403)
        self.assertIn("error", data)

    def test_file_access_unsupported_extension(self) -> None:
        (self.config.runs_dir / "my-cv").mkdir(parents=True, exist_ok=True)
        (self.config.runs_dir / "my-cv" / "notes.txt").write_text("x", encoding="utf-8")
        status, data = self._request_json("GET", "/api/files/my-cv/notes.txt")
        self.assertEqual(status, 403)
        self.assertIn("error", data)

    def test_file_access_missing(self) -> None:
        status, data = self._request_json("GET", "/api/files/missing.pdf")
        self.assertEqual(status, 404)
        self.assertIn("error", data)

    def test_unknown_route_404(self) -> None:
        import urllib.request

        try:
            with urllib.request.urlopen(self.base_url + "/api/nope"):
                self.fail("Expected HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_list_runs(self) -> None:
        (self.config.runs_dir / "my-cv").mkdir(parents=True, exist_ok=True)
        (self.config.runs_dir / "my-cv" / "my-cv.pdf").write_bytes(b"%PDF-1.4")
        (self.config.runs_dir / "my-cv" / "my-cv.md").write_text("# Test", encoding="utf-8")
        (self.config.runs_dir / "my-cv" / "my-cv-cover.docx").write_bytes(b"PK docx")
        (self.config.runs_dir / "my-cv" / "notes.txt").write_text("x", encoding="utf-8")
        status, data = self._request_json("GET", "/api/runs")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["runs"]), 1)
        self.assertEqual(data["runs"][0]["name"], "my-cv")
        self.assertEqual(len(data["runs"][0]["files"]), 3)
        types = {f["type"] for f in data["runs"][0]["files"]}
        self.assertEqual(types, {"pdf", "md", "docx"})
        self.assertTrue(all("url" in f for f in data["runs"][0]["files"]))
        pdf_entry = [f for f in data["runs"][0]["files"] if f["type"] == "pdf"][0]
        self.assertEqual(pdf_entry["preview_url"], "/api/preview/my-cv/my-cv.pdf")
        md_entry = [f for f in data["runs"][0]["files"] if f["type"] == "md"][0]
        self.assertNotIn("preview_url", md_entry)


if __name__ == "__main__":
    unittest.main()
