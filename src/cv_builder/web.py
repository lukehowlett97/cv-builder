from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from cv_builder.build import BuildConfig, build_cv_from_content, default_config
from cv_builder.render import RenderError

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_REQUEST_BODY = 2 * 1024 * 1024  # 2 MB
ALLOWED_EXTENSIONS = {".pdf", ".md", ".docx"}


class WebError(Exception):
    """Raised for user-facing web errors with an HTTP status code."""

    def __init__(self, status: int, message: str, detail: str | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.detail = detail


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _error_response(handler: BaseHTTPRequestHandler, status: int, message: str, detail: str | None = None) -> None:
    _json_response(handler, status, {"error": message, "detail": detail})


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = handler.headers.get("Content-Length")
    if content_length is None:
        raise WebError(400, "Missing Content-Length header")
    try:
        length = int(content_length)
    except ValueError:
        raise WebError(400, "Invalid Content-Length header")
    if length > MAX_REQUEST_BODY:
        raise WebError(413, "Request body too large")
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WebError(400, "Invalid JSON body")
    if not isinstance(data, dict):
        raise WebError(400, "JSON body must be an object")
    return data


def _validate_output_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise WebError(400, "Output name is required")
    if "/" in name or "\\" in name or ".." in name:
        raise WebError(400, "Output name must not contain path separators or '..'")
    if len(name) > 200:
        raise WebError(400, "Output name is too long")
    return name


def _validate_markdown(markdown: str) -> str:
    if not markdown or not markdown.strip():
        raise WebError(400, "CV markdown is required")
    if len(markdown) > MAX_REQUEST_BODY:
        raise WebError(413, "CV markdown is too large")
    return markdown


def _validate_cover_text(cover_text: str | None) -> str | None:
    if cover_text is None:
        return None
    if len(cover_text) > MAX_REQUEST_BODY:
        raise WebError(413, "Cover letter text is too large")
    stripped = cover_text.strip()
    return stripped or None


def _safe_relative_path(config: BuildConfig, raw_path: str) -> Path:
    parsed = urllib.parse.urlparse(raw_path)
    path = urllib.parse.unquote(parsed.path)
    relative = path.lstrip("/")
    if not relative:
        raise WebError(400, "Missing file path")
    candidate = (config.runs_dir / relative).resolve()
    runs_resolved = config.runs_dir.resolve()
    if not candidate.is_relative_to(runs_resolved):
        raise WebError(403, "Access outside the runs directory is not allowed")
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise WebError(403, "Unsupported file type")
    if not candidate.is_file():
        raise WebError(404, "File not found")
    return candidate


def _project_relative(config: BuildConfig, path: Path) -> str:
    return path.relative_to(config.project_root).as_posix()


def _file_url(run_dir: Path, file_path: Path) -> str:
    return f"/api/files/{urllib.parse.quote(run_dir.name)}/{urllib.parse.quote(file_path.name)}"


def _preview_url(run_dir: Path, file_path: Path) -> str:
    return f"/api/preview/{urllib.parse.quote(run_dir.name)}/{urllib.parse.quote(file_path.name)}"


def _open_in_file_manager(path: Path) -> None:
    if os.name == "nt":
        subprocess.Popen(["explorer", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class CvBuilderHandler(BaseHTTPRequestHandler):
    server_version = "CvBuilderWeb/0.1"
    config: BuildConfig

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    # -- Helpers -----------------------------------------------------------

    def _send_static(self, relative_path: str) -> None:
        static_resolved = STATIC_DIR.resolve()
        candidate = (STATIC_DIR / relative_path).resolve()
        if not candidate.is_relative_to(static_resolved):
            self.send_error(403, "Forbidden")
            return
        if not candidate.is_file():
            self.send_error(404, "Not Found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, inline: bool = False) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if inline:
            self.send_header("Content-Disposition", "inline")
        self.end_headers()
        self.wfile.write(body)

    # -- Routes ------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_static("index.html")
            return
        if path.startswith("/static/"):
            self._send_static(path[len("/static/") :])
            return
        if path == "/api/status":
            self._handle_status()
            return
        if path == "/api/sample":
            self._handle_sample()
            return
        if path.startswith("/api/preview/"):
            self._handle_get_preview(path[len("/api/preview/") :])
            return
        if path.startswith("/api/files/"):
            self._handle_get_file(path[len("/api/files/") :])
            return
        if path == "/api/runs":
            self._handle_list_runs()
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/generate":
            self._handle_generate()
            return
        if parsed.path == "/api/open-output":
            self._handle_open_output()
            return
        self.send_error(404, "Not Found")

    # -- API handlers ------------------------------------------------------

    def _handle_status(self) -> None:
        missing = [name for name in ("pandoc", "xelatex") if shutil.which(name) is None]
        _json_response(
            self,
            200,
            {
                "ok": not missing,
                "missing": missing,
                "runs_dir": str(self.config.runs_dir),
            },
        )

    def _handle_generate(self) -> None:
        try:
            data = _read_json_body(self)
            markdown = _validate_markdown(data.get("markdown", ""))
            output_name = _validate_output_name(data.get("name", ""))
            cover_text = _validate_cover_text(data.get("cover_text"))

            result = build_cv_from_content(
                self.config,
                markdown,
                output_name=output_name,
                cover_text=cover_text,
            )

            files = [
                {
                    "name": result.markdown_path.name,
                    "type": "md",
                    "kind": "markdown",
                    "path": _project_relative(self.config, result.markdown_path),
                    "url": _file_url(result.run_dir, result.markdown_path),
                },
                {
                    "name": result.pdf_path.name,
                    "type": "pdf",
                    "kind": "pdf",
                    "path": _project_relative(self.config, result.pdf_path),
                    "url": _file_url(result.run_dir, result.pdf_path),
                },
            ]
            if result.cover_docx_path is not None:
                files.append(
                    {
                        "name": result.cover_docx_path.name,
                        "type": "docx",
                        "kind": "cover",
                        "path": _project_relative(self.config, result.cover_docx_path),
                        "url": _file_url(result.run_dir, result.cover_docx_path),
                    }
                )

            cover_status = "generated" if result.cover_docx_path else "not-requested"
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "name": result.name,
                    "run_dir": str(result.run_dir),
                    "run_dir_rel": _project_relative(self.config, result.run_dir),
                    "markdown_path": str(result.markdown_path),
                    "pdf_path": str(result.pdf_path),
                    "cover_docx_path": str(result.cover_docx_path) if result.cover_docx_path else None,
                    "cover_status": cover_status,
                    "pdf_url": _file_url(result.run_dir, result.pdf_path),
                    "preview_url": _preview_url(result.run_dir, result.pdf_path),
                    "markdown_url": _file_url(result.run_dir, result.markdown_path),
                    "cover_url": _file_url(result.run_dir, result.cover_docx_path) if result.cover_docx_path else None,
                    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "files": files,
                },
            )
        except WebError as exc:
            _error_response(self, exc.status, exc.message, exc.detail)
        except RenderError as exc:
            _error_response(self, 422, str(exc))
        except Exception as exc:
            print(f"[web] Unexpected error during generation: {exc}")
            _error_response(self, 500, "Internal server error during generation")

    def _handle_get_file(self, raw_path: str) -> None:
        try:
            path = _safe_relative_path(self.config, raw_path)
            self._send_file(path)
        except WebError as exc:
            _error_response(self, exc.status, exc.message, exc.detail)

    def _handle_get_preview(self, raw_path: str) -> None:
        try:
            path = _safe_relative_path(self.config, raw_path)
            if path.suffix.lower() != ".pdf":
                raise WebError(403, "Only PDF files can be previewed")
            self._send_file(path, inline=True)
        except WebError as exc:
            _error_response(self, exc.status, exc.message, exc.detail)

    def _handle_sample(self) -> None:
        sample = self.config.example_input_path
        if not sample.is_file():
            _error_response(self, 404, "Sample markdown not found")
            return
        _json_response(self, 200, {"markdown": sample.read_text(encoding="utf-8")})

    def _handle_open_output(self) -> None:
        target = self.config.runs_dir
        content_length = self.headers.get("Content-Length")
        if content_length and content_length != "0":
            try:
                data = _read_json_body(self)
                run_name = data.get("run")
                if run_name is not None:
                    if not isinstance(run_name, str) or not run_name or Path(run_name).name != run_name:
                        raise WebError(400, "Invalid output folder")
                    target = (self.config.runs_dir / run_name).resolve()
                    if not target.is_relative_to(self.config.runs_dir.resolve()):
                        raise WebError(403, "Access outside the runs directory is not allowed")
            except WebError as exc:
                _error_response(self, exc.status, exc.message, exc.detail)
                return
        if not target.is_dir():
            _error_response(self, 404, "Output directory does not exist yet")
            return
        try:
            _open_in_file_manager(target)
        except OSError as exc:
            _error_response(self, 500, "Could not open the output folder", str(exc))
            return
        _json_response(self, 200, {"ok": True})

    def _handle_list_runs(self) -> None:
        runs_dir = self.config.runs_dir
        if not runs_dir.is_dir():
            _json_response(self, 200, {"runs": []})
            return
        runs = []
        for run_dir in sorted(runs_dir.iterdir(), key=lambda p: p.name.lower()):
            if not run_dir.is_dir():
                continue
            files = []
            for path in sorted(run_dir.iterdir()):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix not in ALLOWED_EXTENSIONS:
                    continue
                entry: dict[str, Any] = {
                    "name": path.name,
                    "type": suffix.lstrip("."),
                    "url": f"/api/files/{urllib.parse.quote(run_dir.name)}/{urllib.parse.quote(path.name)}",
                }
                if suffix == ".pdf":
                    entry["preview_url"] = _preview_url(run_dir, path)
                files.append(entry)
            if not files:
                continue
            runs.append(
                {
                    "name": run_dir.name,
                    "path": str(run_dir),
                    "files": files,
                }
            )
        _json_response(self, 200, {"runs": runs})


def create_server(config: BuildConfig | None = None, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    resolved_config = config or default_config(Path.cwd())
    handler = type(
        "BoundCvBuilderHandler",
        (CvBuilderHandler,),
        {"config": resolved_config},
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Start the local CV builder web frontend.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing input.md, tex/cv-template.tex, and runs/.",
    )
    args = parser.parse_args(argv)

    config = default_config(args.project_root.resolve())
    server = create_server(config, host=args.host, port=args.port)
    print(f"CV Builder web frontend running at http://{args.host}:{args.port}")
    print(f"Project root: {config.project_root}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
