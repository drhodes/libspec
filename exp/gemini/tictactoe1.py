import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

# DATA-MODEL: tic-tac-toe-state
class GameState:
    """Manages the state of the Tic Tac Toe game."""
    def __init__(self):
        # FIELDS:
        #   - board: list[list[str]]
        #   - current_turn: <class 'str'>
        #   - winner: str | None
        self.board: List[List[Optional[str]]] = [[None, None, None], [None, None, None], [None, None, None]]
        self.current_turn: str = 'X'
        self.winner: Optional[str] = None

class TicTacToeApp:
    """Creates the main application for the Tic Tac Toe game."""
    def __init__(self, root):
        self.root = root
        self.root.title("Tic Tac Toe")
        self.game_state = GameState()
        self._create_widgets()

    def _create_widgets(self):
        """Creates and places the widgets in the main window."""
        self.buttons = [[None, None, None] for _ in range(3)]
        board_frame = tk.Frame(self.root)
        board_frame.pack()
        for i in range(3):
            for j in range(3):
                self.buttons[i][j] = tk.Button(board_frame, text="", font=('normal', 60), width=3, height=1,
                                               command=lambda row=i, col=j: self._on_button_click(row, col))
                self.buttons[i][j].grid(row=i, column=j)

        self.status_label = tk.Label(self.root, text="Player X's turn", font=('normal', 20))
        self.status_label.pack()
        new_game_button = tk.Button(self.root, text="New Game", command=self._new_game)
        new_game_button.pack()

    def _on_button_click(self, row, col):
        """Handles the logic when a button is clicked."""
        # CONSTRAINT-ID: CONST-MOVE-01
        # Ensures moves are only placed on unoccupied squares.
        if self.game_state.board[row][col] is None and self.game_state.winner is None:
            self.game_state.board[row][col] = self.game_state.current_turn
            self.buttons[row][col].config(text=self.game_state.current_turn)
            if self._check_winner():
                self.game_state.winner = self.game_state.current_turn
                self.status_label.config(text=f"Player {self.game_state.winner} wins!")
            elif self._check_draw():
                self.status_label.config(text="It's a draw!")
            else:
                self.game_state.current_turn = 'O' if self.game_state.current_turn == 'X' else 'X'
                self.status_label.config(text=f"Player {self.game_state.current_turn}'s turn")

    def _check_winner(self):
        """Checks if there is a winner."""
        # Check rows
        for i in range(3):
            if self.game_state.board[i][0] == self.game_state.board[i][1] == self.game_state.board[i][2] is not None:
                return True
        # Check columns
        for j in range(3):
            if self.game_state.board[0][j] == self.game_state.board[1][j] == self.game_state.board[2][j] is not None:
                return True
        # Check diagonals
        if self.game_state.board[0][0] == self.game_state.board[1][1] == self.game_state.board[2][2] is not None:
            return True
        if self.game_state.board[0][2] == self.game_state.board[1][1] == self.game_state.board[2][0] is not None:
            return True
        return False

    def _check_draw(self):
        """Checks if the game is a draw."""
        for row in self.game_state.board:
            if None in row:
                return False
        return self.game_state.winner is None

    # Feature Specification: create-new-game
    # Feature Specification: ask-before-new
    def _new_game(self):
        """Starts a new game."""
        if self.game_state.winner is None and any(any(cell is not None for cell in row) for row in self.game_state.board):
            if not messagebox.askyesno("New Game", "Are you sure you want to start a new game?"):
                return

        self.game_state = GameState()
        self.status_label.config(text="Player X's turn")
        for i in range(3):
            for j in range(3):
                self.buttons[i][j].config(text="")

# REQUIREMENT-ID: REQ-001
# TITLE: Two-Player Local Play
# USER-STORY: As a player, I want to take turns on the same device so that we can play a game together without a network.

# REQUIREMENT-ID: REQ-002
# TITLE: one-source-file
# USER-STORY: As a LLM, I want to The LLM should generate a program in a single source file. so that makes it easier to manage copy pasting.

# REQUIREMENT-ID: REQ-003
# TITLE: platform-target
# USER-STORY: As a LLM, I want to generate python using tkinter so that make for simple cross deployment demo.
if __name__ == "__main__":
    root = tk.Tk()
    app = TicTacToeApp(root)
    root.mainloop()