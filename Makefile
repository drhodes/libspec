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

# .PHONY: build
# build:
# 	uv run python -c "from libspec.util import compile_live_spec; compile_live_spec()"

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
	uv run ruff format

.PHONY: lint
lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy -p libspec
	uv run mypy tests/
	uv run radon cc -s -nb -a libspec/
	uv run radon mi -nb libspec/

.PHONY: coverage
coverage:
	uv run pytest --cov=libspec -n auto

.PHONY: clean
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov test_project
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name "*.bak" -delete
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete


.PHONY: packout
packout:
	packout spec/* libspec/* design/* > /tmp/packout.txt

.PHONY: release
release:
	bash util/release.sh

