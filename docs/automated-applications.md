# Automated application CVs

ChatGPT-generated applications belong under `applications/` using this layout:

```text
applications/
  YYYY-MM-DD/
    company-role/
      cv.md
      job.md
```

- `cv.md` is the tailored CV. It must follow the same front matter and Markdown
  structure as `example_input.md`; `docs/chatgpt_prompt.md` describes the exact
  contract.
- `job.md` records the job description, source URL, and any generation notes.
  It is retained for context but is not included in the PDF.
- Use lowercase, hyphen-separated directory names, for example
  `applications/2026-08-19/example-company-data-engineer/cv.md`.

Both Markdown files are committed to the repository. Review their contents
before pushing and do not put credentials, API keys, or other secrets in them.

## GitHub Actions

A push that adds or modifies any `applications/**/cv.md` starts the **Build
application CVs** workflow. The workflow detects only CVs added or modified by
that push, validates each one with the repository's existing Markdown contract,
and builds all of them independently with the existing Pandoc/XeLaTeX renderer.

The generated files are named `cv.pdf`. They are created next to their matching
`cv.md` files in the Actions runner and uploaded together as an artifact named
`application-cvs-<run-id>-<attempt>`. Open the workflow run in GitHub and download
that artifact from its **Artifacts** section. PDFs are intentionally ignored by
Git and are not committed back to the repository.

Validation or rendering errors fail the workflow and identify the source file
being built. Deleting a `cv.md` can trigger the workflow, but deleted files are
not built.

## Run the same build locally

Install the dependencies listed in the main README, then run:

```bash
PYTHONPATH=src python3 -m cv_builder \
  --input applications/2026-08-19/example-company-data-engineer/cv.md
```

This uses the same validation, template, Lua filters, Pandoc command, and
XeLaTeX engine as GitHub Actions. It writes
`applications/2026-08-19/example-company-data-engineer/cv.pdf`. Use `--output`
only when a different PDF path is needed.
