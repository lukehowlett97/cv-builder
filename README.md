# cv-builder

This repository now contains a dedicated local CV workflow alongside the older report/document build targets.

The CV workflow is designed for editing a single root-level `input.md`, then generating named snapshots into `runs/`:

- `runs/<name>.md`
- `runs/<name>.pdf`

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
- suggest a filename from the first `# H1`
- prompt with `Output name [suggested-name]:`
- write `runs/<name>.md` and `runs/<name>.pdf`
- clear `input.md` only after a successful PDF build

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
├── input.md
├── runs/
├── src/cv_builder/
├── tex/cv-template.tex
├── build_cv.sh
├── Makefile
└── legacy report/docx scripts and assets
```

The older report build commands remain available in the `Makefile` and are intentionally left in place.

## Git Guidance

Recommended initial commit once you are happy with the merge:

```bash
git init
git add .
git commit -m "Add cv-builder workflow and preserve legacy document targets"
```
