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

def test_cli_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        
        import os
        assert os.path.exists("spec")
        assert os.path.exists("spec/__init__.py")
        assert os.path.exists("spec/main_spec.py")
        assert os.path.exists("spec/app.py")
        assert os.path.exists("spec/err.py")
        
        with open("spec/err.py", "r", encoding="utf-8") as f:
            err_content = f.read()
            
        # Verify it copied templates/err.py which includes DefensiveProgramming, Refactor, Robustness
        assert "class DefensiveProgramming" in err_content
        assert "class Robustness" in err_content
        assert "class Refactor" in err_content
