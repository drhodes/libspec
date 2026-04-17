from libspec.spec import Ctx

class A(Ctx):
    """Doc A"""
class B(A):
    """Doc B"""
class C(B):
    """Doc C"""

print(C().render_xml())
