import pytest
import sys
from libspec.spec import Requirement, Spec

# Requirement classes must be at module level for inspect.getmembers to find them
# and for __module__ to match correctly during discovery in generate_xml()

class MissingFooReq(Requirement):
    """
    Leaf Template
    Value: {{foo}}
    """
    pass


class MySpec(Spec):
    def modules(self):
        # Use the current module
        return [sys.modules[__name__]]

def test_missing_templated_variable_fails():
    # generate_xml() should fail with AttributeError because 'foo' is missing
    spec = MySpec()
    with pytest.raises(AttributeError, match=r"The variable '{{foo}}' was found in a docstring template for class 'MissingFooReq',\ndefined at .*\.py:\d+,\nbut no matching method or attribute 'foo' was found\."):
        spec.generate_xml()


