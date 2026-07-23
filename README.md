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

This template is the styling layer for the generated PDF. It can be adjusted to tune typography, spacing, heading rules, colours, and layout.

## Repository Layout

```text
.
├── example_input.md
├── runs/
├── src/cv_builder/
├── tex/cv-template.tex
├── build_cv.sh
├── Makefile
└── LICENSE
```

## Privacy

Personal CVs, cover letters, metadata, generated documents, and application-specific material are intentionally excluded from version control. Copy `example_input.md` to a local `input.md` and customise it privately.

## License

The source code and template are released under the MIT License. See [LICENSE](LICENSE).
