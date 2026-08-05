# cv-builder

A local Markdown-to-PDF CV builder using Pandoc, XeLaTeX, and a custom LaTeX template.

The CV workflow is designed for editing a single root-level `input.md`, then generating named snapshots into `runs/`:

- `runs/<name>.md`
- `runs/<name>.pdf`
- `runs/<name>-cover.docx`

The output name is suggested from the first Markdown H1 and can be accepted by pressing Enter.

## CV Workflow

Edit the root `input.md`, then run:

```bash
make run
```

Or directly:

```bash
PYTHONPATH=src python3 -m cv_builder
```

The builder will:

- read `input.md`
- use frontmatter from `input/metadata.yml` if `input.md` does not start with YAML metadata
- suggest a filename from the first `# H1`
- prompt with `Output name [suggested-name]:`
- write `runs/<name>.md` and `runs/<name>.pdf`
- optionally render a local `cover_input.txt` to `runs/<name>-cover.docx`
- leave `input.md` unchanged after the build

If `input.md` is missing, the builder creates it from `example_input.md`.

An optional local `cover_input.txt` can be used for a cover letter or supporting statement. It is ignored by Git.

If no H1 is present, the fallback name is `cv-YYYY-MM-DD`.

Use dry-run mode to verify naming and paths without writing files:

```bash
make dry-run
```

Or:

```bash
PYTHONPATH=src python3 -m cv_builder --dry-run
```

Use `--name` to bypass the prompt:

```bash
PYTHONPATH=src python3 -m cv_builder --name platform-consultant-cv
```

## Web Frontend

A locally hosted HTML frontend is provided for editing CV content and
generating PDFs in the browser:

```bash
make host
```

The existing `make web` command remains available as an alias. Or run the
server directly:

```bash
PYTHONPATH=src python3 -m cv_builder.web
```

This starts a server at `http://127.0.0.1:8000` (override with `--host` and
`--port`). The frontend provides:

- a **Build a CV** editor panel with:
  - a CV Markdown text area (pasted content acts as `input.md`);
  - an output-name field that controls the run directory and file names;
  - a collapsed **Header options** section for editing the name, headline,
    location, email, LinkedIn, GitHub, and website frontmatter fields while
    keeping the Markdown YAML synchronized;
  - a collapsed **Add cover letter (optional)** section that generates a DOCX
    only when expanded and non-empty;
  - editor actions to load a Markdown file locally, use the bundled sample CV,
    pull generated Markdown back from the current preview, or clear the editor;
- a **Generate CV** button with stage feedback (validating, generating, complete),
  duplicate-submission protection, and `Ctrl+Enter`/`Cmd+Enter` support;
- a right-hand output panel with two tabs:
  - **Preview** — a full-width embedded PDF viewer (with `#toolbar=0&navpanes=0`
    fragment parameters where supported), a Markdown/PDF switch for viewing the
    generated source or rendered document, open-in-new-tab and copy-to-clipboard
    actions for Markdown, and a clear empty state before the first generation;
  - **Generated files** — a file-explorer-style tree of all run directories and
    their generated files (PDF, Markdown, DOCX), refreshed after each generation;
- a **Focus preview** control that hides the editor panel and a **Show editor**
  control that restores it;
- a success summary after each generation showing the generated file names,
  project-relative paths, open actions, copy-path actions, an **Open PDF in new tab**
  action for the PDF, and a generation timestamp;
- a tightly controlled **Open in folder** action beside the preview that opens
  the current PDF's run directory through the platform file manager;
- clear validation and generation error messages, with the page scrolling to the
  error after a failed request.

Generated files are written into the same `runs/<name>/` directory structure
as the CLI workflow, with the same collision-indexing behaviour. The server
binds to `127.0.0.1` by default, serves only expected file types from within
`runs/`, and rejects path traversal.

## Dependencies

Required for PDF output:

- Python 3.11+
- [Pandoc](https://pandoc.org/)
- XeLaTeX via TeX Live, MacTeX, or another TeX distribution

Example on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3 pandoc texlive-xetex texlive-latex-extra texlive-fonts-recommended
```

## Template

The CV renderer uses:

- `tex/cv-template.tex`
- `tex/multicol-core-capabilities.lua`
- `tex/keep-headings-with-content.lua`

The template is the styling layer for the generated PDF. The Lua filters add
structural layout behaviour before XeLaTeX renders it.

### Heading pagination

By default, level-two and level-three Markdown headings reserve enough
approximate vertical space to begin their following content. The filter uses
the Pandoc document structure rather than section names:

- an H2 immediately followed by an H3 gets one combined reservation covering
  the H2, H3, and expected opening content;
- the immediately following H3 does not add a competing reservation;
- later H3 entries receive their normal reservation;
- an H2 or H3 followed by ordinary content reserves a smaller opening area;
- complete sections and entries remain free to split across pages.

The defaults work without frontmatter configuration. They can be overridden
with optional scalar fields:

```yaml
layout_keep_headings_with_content: true
layout_h2_needspace: 6
layout_h2_before_h3_needspace: 10
layout_h3_needspace: 8
```

The numeric values are approximate multiples of LaTeX `\baselineskip`.
Accepted values are integers from 1 to 30. Disable the feature for a document
with:

```yaml
layout_keep_headings_with_content: false
```

Invalid layout values stop the build with a clear validation error. The
layout feature does not impose a universal page-count target; page count
depends on each document's content.

### Layout tests

Run the structural and PDF integration suite with:

```bash
make test
```

The PDF tests require Pandoc, XeLaTeX, and `mutool`. Warning comparisons are
baseline-aware: new overfull boxes fail, materially increased underfull boxes
fail, and pre-existing warnings may remain when unchanged.

## Repository Layout

```text
.
├── example_input.md
├── runs/
├── src/cv_builder/
├── tests/
├── tex/cv-template.tex
├── tex/keep-headings-with-content.lua
├── tex/multicol-core-capabilities.lua
├── build_cv.sh
├── Makefile
└── LICENSE
```

## Privacy

Personal CVs, cover letters, metadata, generated documents, and application-specific material are intentionally excluded from version control. Copy `example_input.md` to a local `input.md` and customise it privately.

## License

The source code and template are released under the MIT License. See [LICENSE](LICENSE).
