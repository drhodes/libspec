"""
Central Theme and Terminal Color Manager for libspec.
"""
import os
import sys

try:
    from colored import fore, back, style
    HAS_COLORED = True
except ImportError:
    HAS_COLORED = False


class Theme:
    # Semantic Style Constants
    CMD_HEADER: str = ""
    CMD_NAME: str = ""
    WARNING: str = ""
    ERROR: str = ""
    INFO: str = ""
    SUCCESS: str = ""
    MUTED: str = ""
    PROMPT: str = ""
    BOLD: str = ""
    RESET: str = ""
    
    # Specific semantic colors mapped from raw ANSI in REPL
    BOLD_YELLOW: str = ""
    BOLD_GREEN: str = ""
    BOLD_RED: str = ""
    BOLD_CYAN: str = ""
    BOLD_MAGENTA: str = ""
    BOLD_BLACK: str = ""
    GREEN: str = ""
    CYAN: str = ""
    RED: str = ""
    YELLOW: str = ""
    GRAY: str = ""

    _enabled: bool = False

    @classmethod
    def enable(cls):
        """Enables color formatting using colored."""
        if not HAS_COLORED:
            cls.disable()
            return
        
        try:
            cls.BOLD_YELLOW = fore("yellow") + style("bold")
            cls.BOLD_GREEN = fore("green") + style("bold")
            cls.BOLD_RED = fore("red") + style("bold")
            cls.BOLD_CYAN = fore("cyan") + style("bold")
            cls.BOLD_MAGENTA = fore("magenta") + style("bold")
            cls.BOLD_BLACK = fore("dark_gray") + style("bold")
            cls.GREEN = fore("green")
            cls.CYAN = fore("cyan")
            cls.RED = fore("red")
            cls.YELLOW = fore("yellow")
            cls.GRAY = fore("dark_gray")
            cls.RESET = style("reset")
            
            # Semantic aliases
            cls.CMD_HEADER = cls.BOLD_YELLOW
            cls.CMD_NAME = cls.BOLD_GREEN
            cls.WARNING = cls.YELLOW
            cls.ERROR = cls.BOLD_RED
            cls.INFO = cls.CYAN
            cls.SUCCESS = cls.GREEN
            cls.MUTED = cls.GRAY
            cls.PROMPT = cls.BOLD_MAGENTA
            cls.BOLD = style("bold")
            
            cls._enabled = True
        except Exception:
            cls.disable()

    @classmethod
    def disable(cls):
        """Disables all color formatting (evaluates to empty strings)."""
        cls.BOLD_YELLOW = ""
        cls.BOLD_GREEN = ""
        cls.BOLD_RED = ""
        cls.BOLD_CYAN = ""
        cls.BOLD_MAGENTA = ""
        cls.BOLD_BLACK = ""
        cls.GREEN = ""
        cls.CYAN = ""
        cls.RED = ""
        cls.YELLOW = ""
        cls.GRAY = ""
        cls.RESET = ""
        
        cls.CMD_HEADER = ""
        cls.CMD_NAME = ""
        cls.WARNING = ""
        cls.ERROR = ""
        cls.INFO = ""
        cls.SUCCESS = ""
        cls.MUTED = ""
        cls.PROMPT = ""
        cls.BOLD = ""
        cls._enabled = False

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled


# Auto-configure based on environment (TTY check and NO_COLOR standard)
if sys.stdout.isatty() and not os.environ.get("NO_COLOR"):
    Theme.enable()
else:
    Theme.disable()
