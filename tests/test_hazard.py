"""
Tests for core Hazard specification types in libspec.
REQUIREMENT-ID: spec.types.HazardType
REQUIREMENT-ID: spec.types.IntegrationHazardType
REQUIREMENT-ID: spec.types.DeploymentHazardType
REQUIREMENT-ID: spec.types.SecurityHazardType
"""

import pytest
from libspec import Ctx, Feature, Requirement
from libspec.spec_types import (
    Hazard,
    IntegrationHazard,
    DeploymentHazard,
    SecurityHazard,
)


def test_hazard_class_hierarchy():
    """Verify Hazard is a Ctx subclass and specialized hazard types inherit appropriately."""
    assert issubclass(Hazard, Ctx)
    assert issubclass(IntegrationHazard, Hazard)
    assert issubclass(DeploymentHazard, Hazard)
    assert issubclass(SecurityHazard, Hazard)


def test_hazard_top_level_libspec_import():
    """Verify Hazard types are exported directly from the top-level libspec namespace."""
    import libspec
    assert hasattr(libspec, "Hazard")
    assert hasattr(libspec, "IntegrationHazard")
    assert hasattr(libspec, "DeploymentHazard")
    assert hasattr(libspec, "SecurityHazard")
    assert libspec.Hazard is Hazard
    assert libspec.IntegrationHazard is IntegrationHazard
    assert libspec.DeploymentHazard is DeploymentHazard
    assert libspec.SecurityHazard is SecurityHazard


def test_hazard_template_rendering():
    """Verify Hazard template rendering carries structured hazard and guardrail instructions."""
    class SubdomainCookieHazard(IntegrationHazard):
        """
        [HAZARD] Duplicate Cookie Resolution Conflict
        Python SimpleCookie takes the last cookie; JS takes the first.

        HARNESS INSTRUCTION:
        Verify client extracts the last matching cookie in document.cookie.
        """

    inst = SubdomainCookieHazard()
    xml = inst.render_xml()
    assert "SubdomainCookieHazard" in xml
    assert "Duplicate Cookie Resolution Conflict" in xml
    assert "HARNESS INSTRUCTION" in xml


def test_requirement_inheriting_hazard():
    """Verify Requirements can compose with Hazard classes in spec hierarchies."""
    class MyTrapHazard(SecurityHazard):
        """
        [HAZARD] Quoted Token Mismatch
        """

    class MyHandlerReq(Requirement, MyTrapHazard):
        """
        Handler requirement that must guard against MyTrapHazard.
        """

    inst = MyHandlerReq()
    xml = inst.render_xml()
    assert "MyHandlerReq" in xml
    assert "MyTrapHazard" in xml
