from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cv_builder.build import (
    BuildConfig,
    build_cv,
    default_config,
    read_input_markdown,
    resolve_output_name,
    resolve_markdown_with_metadata,
)
from cv_builder.render import RenderError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a polished PDF CV from Markdown.")
    parser.add_argument("--name", help="Bypass the interactive output-name prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve output paths without writing files.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing input.md, tex/cv-template.tex, and runs/.",
    )
    return parser.parse_args(argv)


def prompt_for_name(suggested: str) -> str:
    response = input(f"Output name [{suggested}]: ").strip()
    return response or suggested


def choose_output_name(args: argparse.Namespace, suggested: str) -> str:
    if args.name:
        return args.name
    if args.dry_run or not sys.stdin.isatty():
        return suggested
    return prompt_for_name(suggested)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config: BuildConfig = default_config(args.project_root.resolve())

    try:
        markdown = resolve_markdown_with_metadata(
            read_input_markdown(config.input_path, config.example_input_path),
            config.metadata_path,
        )
        suggested, _ = resolve_output_name(markdown, args.name)
        chosen_name = choose_output_name(args, suggested)
        result = build_cv(config, chosen_name, dry_run=args.dry_run)
    except RenderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130

    if args.dry_run:
        print("Dry run only. No files were written.")
        print(f"Resolved name: {result.name}")
        print(f"CV name: {result.metadata['name']}")
        print(f"Run directory: {result.run_dir}")
        print(f"Markdown output: {result.markdown_path}")
        print(f"PDF output: {result.pdf_path}")
        if result.cover_docx_path:
            print(f"Cover DOCX output: {result.cover_docx_path}")
        return 0

    print("Build successful.")
    print(f"CV name: {result.metadata['name']}")
    print(f"Run directory: {result.run_dir}")
    print(f"Markdown snapshot: {result.markdown_path}")
    print(f"PDF output: {result.pdf_path}")
    if result.cover_docx_path:
        print(f"Cover DOCX output: {result.cover_docx_path}")
    print(f"Input file left unchanged: {config.input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
