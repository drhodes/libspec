PY=uv run python
LIBSPEC=uv run libspec


.PHONY: bump-major
bump-major:
	$(PY) util/bump_version.py major

.PHONY: bump-minor
bump-minor:
	$(PY) util/bump_version.py minor

.PHONY: bump-patch
bump-patch:
	$(PY) util/bump_version.py patch

.PHONY: build
build:
    # libspec build <spec_file> [-o <output_dir> | --output=<output_dir>]
	$(LIBSPEC) build ./spec/main_spec.py --output ./spec-build

.PHONY: diff
diff: 
	$(LIBSPEC) diff ./spec-build

.PHONY: test

test:
	uv run pytest -n auto

.PHONY: clean
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov spec-build test_project
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name "*.bak" -delete
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
