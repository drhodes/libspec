"""
Specification of the core domain types.
"""

from .err import Feat


class DecoupledCommonTypes(Feat):
    """
    Core domain models must be defined in a decoupled, dependency-free module
    (e.g., `libspec.common`), allowing core compilation, database storage, and
    external scheduling packages to import them without circular dependencies.

    The primary types are defined in `spec/common.py`:
    - `SpecComponent`: Model representing a compiled specification node.
    - `SpecSnapshot`: Model representing a compile build instance.
    - `SpecImplemented`: Model representing an implementation claim.
    """

