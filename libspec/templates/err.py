from libspec import Ctx, Feature, Requirement


class Err(Ctx):
    """
    It is important that error handling be done excellently.

    If a function can fail, then it needs to do so in the most elegant way
    possible. Error reporting, handling, exceptions and all aspects of failure
    must be taken to extreme. It should be possible to understand the program
    by reading the error messages.

    When an error occurs there should be a story about the failure at each step
    of the way. What went wrong and why.
    """


# Use multiple inheritance to endow Feature and Requirement specs with
# disciplined error handling guidance from above.


class BoilerPlate(Ctx):
    """
    If you can see a way to reduce boiler plate, then do it.
    """


class FunctionLines(Ctx):
    """
    Try to keep functions under 20 lines.
    """


class Indentation(Ctx):
    """
    Try to keep indentation under 4 levels.
    """


class PreCondition(Ctx):
    """
    Functions should validate preconditions at their entry point.

    Instead of using `assert` statements (which can be disabled globally),
    raise explicit, descriptive exceptions (e.g., ValueError, TypeError, or
    custom domain exceptions) to robustly reject malformed input.
    """


class GlobalMutableState(Ctx):
    """
    Broadly you should avoid global mutable state.
    """


class PostCondition(Ctx):
    """
    Before a function returns, it should verify postconditions to ensure
    invariant properties hold true.

    Raise explicit, descriptive exceptions (such as RuntimeError or domain
    exceptions) rather than using `assert` statements to handle post-execution
    verification failures.
    """


class DefensiveProgramming(PreCondition, PostCondition, GlobalMutableState):
    pass


class Refactor(BoilerPlate, FunctionLines, Indentation):
    """
    Always keep an eye out for ways to generalize a function if it's utility
    might be helpful to other functions.

    Classes should be implemented in their own files with filename being the
    classname with correct naming convention
    """


class Robustness(DefensiveProgramming):
    """
    Always prioritize library-provided constructors for complex objects. Ensure
    all components are fully initialized before calling any state- mutating
    methods. Assume private internal state is uninitialized until the official
    constructor has returned. When extending library components, prioritize
    composition (pointers) over embedding by value to avoid risky state-copying
    bugs.

    Use dependency injection for system level objects for composability and to
    make testing easier.
    """


class Feat(Err, Refactor, Robustness, Feature):
    pass


class Req(Err, Refactor, Robustness, Requirement):
    pass
