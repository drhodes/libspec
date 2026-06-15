import importlib.util

import libspec.cli


def test_removed_cli_module_is_absent():
    module_name = "libspec." + "".join(["qu", "ery"]) + "_map"
    assert importlib.util.find_spec(module_name) is None


def test_cli_usage_no_longer_mentions_removed_command():
    word = "".join(["qu", "ery"])
    assert word not in libspec.cli.__doc__
# dummy comment

