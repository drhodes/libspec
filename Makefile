PY=uv run python

.PHONY: bump-major
bump-major:
	$(PY) util/bump_version.py major

.PHONY: bump-minor
bump-minor:
	$(PY) util/bump_version.py minor

.PHONY: bump-patch
bump-patch:
	$(PY) util/bump_version.py patch


.PHONY: test clean

test:
	uv run pytest

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
