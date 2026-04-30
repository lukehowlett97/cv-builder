.PHONY: all run dry-run report legacy docx input-pdfs input-docx input-all clean-final-docx clean clean-report clean-legacy clean-docx
SHELL := /bin/bash

OUTPUT_DIR := output
REPORT_MD := input/report.md
REPORT_PDF := $(OUTPUT_DIR)/report.pdf
LEGACY_MD := data_logging_overhaul_report_input/clean_final.md
LEGACY_PDF := $(OUTPUT_DIR)/clean_final.pdf
DOCX_MD := ppp-ar_plan/report.md
DOCX_DOCX := $(OUTPUT_DIR)/report.docx
DOCX_TEMPLATE := Example\ Template/Example-BM-TEM-008-Rev1_\ Example\ Generic\ Doc\ Template.docx
DOCX_TEMPLATE_PATH := Example Template/Example-BM-TEM-008-Rev1_ Example Generic Doc Template.docx
CLEAN_DOCX_MD := input/clean_final.md
CLEAN_DOCX_DOCX := $(OUTPUT_DIR)/clean_final.docx

PANDOC_FLAGS := --from markdown --pdf-engine=xelatex \
  --include-in-header=tex/table-spacing.tex \
  -V geometry:margin=1.8cm \
  -V fontsize=11pt \
  -V colorlinks=true \
  -V linkcolor=blue

all: report

run:
	bash build_cv.sh

dry-run:
	PYTHONPATH=src python3 -m cv_builder --dry-run

report: $(REPORT_PDF)

$(REPORT_PDF): $(REPORT_MD) | $(OUTPUT_DIR)
	pandoc $< -o $@ $(PANDOC_FLAGS)

legacy: $(LEGACY_PDF)

$(LEGACY_PDF): $(LEGACY_MD) | $(OUTPUT_DIR)
	pandoc $< -o $@ $(PANDOC_FLAGS)

docx: $(DOCX_DOCX)

$(DOCX_DOCX): $(DOCX_MD) $(DOCX_TEMPLATE) build_report_docx.sh | $(OUTPUT_DIR)
	TEMPLATE="$(DOCX_TEMPLATE_PATH)" bash build_report_docx.sh "$(DOCX_MD)" "$(DOCX_DOCX)"

clean-final-docx: $(CLEAN_DOCX_DOCX)

$(CLEAN_DOCX_DOCX): $(CLEAN_DOCX_MD) $(DOCX_TEMPLATE) build_report_docx.sh | $(OUTPUT_DIR)
	TEMPLATE="$(DOCX_TEMPLATE_PATH)" bash build_report_docx.sh "$(CLEAN_DOCX_MD)" "$(CLEAN_DOCX_DOCX)"

input-pdfs: | $(OUTPUT_DIR)
	@find input -maxdepth 1 -type f -name '*.md' -print0 | while IFS= read -r -d '' f; do \
		stem=$$(basename "$$f" .md); \
		echo "Building PDF for $$f"; \
		pandoc "$$f" -o "$(OUTPUT_DIR)/$$stem.pdf" $(PANDOC_FLAGS); \
	done

input-docx: | $(OUTPUT_DIR)
	@find input -maxdepth 1 -type f -name '*.md' -print0 | while IFS= read -r -d '' f; do \
		stem=$$(basename "$$f" .md); \
		echo "Building DOCX for $$f"; \
		TEMPLATE="$(DOCX_TEMPLATE_PATH)" bash build_report_docx.sh "$$f" "$(OUTPUT_DIR)/$$stem.docx"; \
	done

input-all: input-pdfs input-docx

$(OUTPUT_DIR):
	mkdir -p $@

clean: clean-report clean-docx

clean-report:
	rm -f $(REPORT_PDF)

clean-legacy:
	rm -f $(LEGACY_PDF)

clean-docx:
	rm -f $(DOCX_DOCX) $(CLEAN_DOCX_DOCX)

cv:
	xelatex -interaction=nonstopmode -halt-on-error -jobname="example-cv" -output-directory=$(OUTPUT_DIR) tex/cv.tex
	xelatex -interaction=nonstopmode -halt-on-error -jobname="example-cv" -output-directory=$(OUTPUT_DIR) tex/cv.tex
