.PHONY: check compile test validate

check: compile test validate

compile:
	python3 -m compileall -q plugins scripts tests

test:
	python3 -m unittest discover -s tests -v

validate:
	python3 scripts/validate_repository.py
