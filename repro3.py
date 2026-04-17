import os
import sys
from libspec.spec import Ctx, Feature, Requirement

class BaseClass(Feature):
    """
    This is the base class docstring.
    """
    def feature_name(self):
        return "BaseFeature"

class DerivedClass(BaseClass):
    """
    This is the derived class docstring.
    """
    def feature_name(self):
        return "DerivedFeature"

if __name__ == "__main__":
    d = DerivedClass()
    print("=== Base Template ===")
    print(d._get_base_template())
    print("=== Instance Notes ===")
    print(d._get_instance_notes())
