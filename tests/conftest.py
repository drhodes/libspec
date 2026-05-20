import pytest
import os

@pytest.fixture(autouse=True)
def isolated_spec_store(tmp_path):
    """
    Automatically isolate every test's SpecStore to a temporary directory.
    This prevents tests from polluting the main .libspec/libspec.jsonl log.
    """
    test_jsonl = tmp_path / "test_libspec.jsonl"
    os.environ["LIBSPEC_DATABASE_URL"] = f"jsonl://{test_jsonl}"
    yield
    if "LIBSPEC_DATABASE_URL" in os.environ:
        del os.environ["LIBSPEC_DATABASE_URL"]
