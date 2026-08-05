.PHONY: run dry-run web host test clean

run:
	bash build_cv.sh

dry-run:
	PYTHONPATH=src python3 -m cv_builder --dry-run

web:
	PYTHONPATH=src python3 -m cv_builder.web

host: web

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	rm -rf runs
