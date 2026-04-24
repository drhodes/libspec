"""
Error and requirement base classes.
"""

from libspec import Ctx, Feature, Requirement

class Err(Ctx):
    '''It is important that error handling be done excellently. If a
    function can fail, then it needs to do so in the most elegant way
    possible. Error reporting, handling, exceptions and all aspects
    of failure must be taken to extreme. It should be possible to
    understand the program by reading the error messages.
    '''

# Use multiple inheritance to endow Feature and Requirement specs with
# disciplined error handling guidance from above.

class Feat(Err, Feature): pass
class Req(Err, Requirement): pass
