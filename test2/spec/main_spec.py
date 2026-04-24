"""
main spec
"""

from libspec import Spec
from . import app

class MainSpec(Spec):
    def modules(self):
        return [app]

if __name__ == "__main__":
    MainSpec().write_xml("spec-build")
