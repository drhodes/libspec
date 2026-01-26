from speclib import spec, layer, interface, implements

@layer("domain")
class Board:
    """3x3 grid tracking game state"""
    def place(self):
        """Place X or O, returns success bool"""
    def get(self):
        """Returns None, X, or O"""
    @spec
    def is_full(self):
        """No empty cells left"""
    @spec
    def get_winner(self):
        """Returns X, O, or None - checks rows/cols/diags"""

@layer("domain")
class Game:
    """Manages turn order and win conditions"""
    @spec
    def make_move(self):
        """Attempt move, switch turns if valid"""
    @spec
    def is_over(self):
        """Game ended by win or draw"""
    @spec
    def get_status(self):
        """Returns 'playing', 'X_wins', 'O_wins', 'draw'"""
    @spec
    def reset(self):
        """Start new game"""

@interface("domain->application", version="1.0")
class GameService:
    """Contract for game operations"""
    @spec
    def new_game(self):        ...
    @spec
    def play_move(self):       """Returns {success, status, message}"""
    @spec
    def get_board_state(self): """Returns 3x3 grid for display"""

@layer("application")
@implements("domain->application", version="1.0")
class TicTacToeApp():
    """
    Main game controller
    """
    def start_game(self): ...
    def handle_move(self): ...
    def get_display_state(self): """Board state + current player + status"""

@interface("application->ui", version="1.0")
class DisplayContract:
    """
    What UI needs
    """
    @spec
    def get_cell_value(self): """Returns '', 'X', or 'O'"""
    @spec
    def get_current_player(self): """Whose turn"""
    @spec
    def get_message(self): """Status message for player"""
    @spec
    def is_cell_playable(self): """Can this cell be clicked"""

@layer("ui")
@implements("application->ui", version="1.0")
class GameUI:
    """
    Rendering - details TBD
    """
    @spec
    def render_board(self): ...
    @spec
    def handle_click(self): ...
    @spec
    def show_message(self): ...
