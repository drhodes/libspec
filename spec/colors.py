"""
Specification for refactoring terminal color formatting using the `colored` library.
"""

from .err import Feat, Req


class TerminalColorFormatting(Feat):
    """
    All terminal output formatting, styling, and colorization must use the
    third-party `colored` library (https://pypi.org/project/colored/) as the
    central dependency.

    Raw ANSI escape codes (e.g., '\\033[1;33m') must be completely replaced.
    """


class CentralThemeColors(Req):
    """
    A centralized color theme module (e.g., `libspec/colors.py`) must be defined to
    encapsulate semantic colors and text styling.

    The module must expose named constants representing semantic colors (such as
    HEADER, SUCCESS, WARNING, ERROR, INFO, PROMPT, BOLD, RESET) utilizing `colored`
    primitives.
    """


class ThemeConfigurableColors(Req):
    """
    Semantic color styling must support runtime theme adjustments or toggling.
    It must be possible to programmatically enable or disable colors (for example,
    when stdout is not a TTY or via a `--no-color` option) by mapping all semantic
    color constants to empty strings.
    """


class ReplColorRefactoring(Req):
    """
    The interactive REPL (`libspec/repl.py`) must be refactored to use the central
    color theme module, ensuring consistent and maintainable styles for command
    descriptions, prompt strings, diff listings, and table formatting.
    """
