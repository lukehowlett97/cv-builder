.PHONY: run dry-run clean

run:
	bash build_cv.sh

dry-run:
	PYTHONPATH=src python3 -m cv_builder --dry-run

clean:
	rm -rf runs
