import pytest
from click.testing import CliRunner
from libspec.cli import main

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "unified CLI for spec-driven development" in result.output
    assert "build" in result.output
    assert "diff" in result.output
    assert "init" in result.output

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "libspec, version" in result.output
