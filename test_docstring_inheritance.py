class GrandParent:
    """GrandParent Doc"""
class Parent(GrandParent):
    pass
class Child(Parent):
    """Child Doc"""

print(f"Parent doc: {Parent.__doc__}")
