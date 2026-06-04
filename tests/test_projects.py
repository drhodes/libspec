
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from projects.rest_api_project.spec import RestAPISpec
from projects.cli_tool_project.spec import CliToolSpec
from projects.database_project.spec import DatabaseSpec

def test_rest_api_project_compiles():
    spec = RestAPISpec()
    xml_content = spec.generate_xml()
    assert "UserSchema" in xml_content
    assert "UserAPI" in xml_content
    assert "Must be authenticated." in xml_content

def test_cli_tool_project_compiles():
    spec = CliToolSpec()
    xml_content = spec.generate_xml()
    assert "GitWrapperCmd" in xml_content
    assert "VersionControlFeature" in xml_content
    assert "GitInstallation" in xml_content
    assert "Clean working tree" in xml_content

def test_database_project_compiles():
    spec = DatabaseSpec()
    xml_content = spec.generate_xml()
    assert "EventLogSQLite" in xml_content
    assert "UserPreferencesPeeWee" in xml_content
    assert "event_type" in xml_content
    assert "theme" in xml_content
