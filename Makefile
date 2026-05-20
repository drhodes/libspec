PY=uv run python
LIBSPEC=LIBSPEC_DATABASE_URL=sqlite:///.libspec/libspec.db uv run libspec


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
	$(LIBSPEC) build ./spec/main_spec.py

.PHONY: spec
spec: build

.PHONY: diff
diff: 
	$(LIBSPEC) diff

.PHONY: test

test:
	uv run pytest -n auto

.PHONY: format
format:
	-uvx docformatter --wrap-summaries 79 --wrap-descriptions 79 --in-place spec/*.py
	uv run ruff format --line-length=80 spec/*.py

.PHONY: clean
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov test_project
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name "*.bak" -delete
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
