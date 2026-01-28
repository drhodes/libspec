#!/usr/bin/env python3
"""
Tic-Tac-Toe TUI Game
A two-player local Tic-Tac-Toe game with save/load functionality using urwid.
"""

import urwid
import json
import os
from typing import Optional, List


class GameState:
    """
    Data model for Tic-Tac-Toe game state.
    
    Fields:
    - board: list[list[str]] - 3x3 grid with 'X', 'O', or None
    - current_turn: str - Current player ('X' or 'O')
    - winner: str | None - Winner ('X', 'O', 'Draw') or None if game ongoing
    """
    
    def __init__(self):
        self.board: List[List[Optional[str]]] = [[None, None, None] for _ in range(3)]
        self.current_turn: str = 'X'
        self.winner: Optional[str] = None
    
    def reset(self):
        """REQ-001, feat-create-new-game: Resets board and sets current_turn to 'X'."""
        self.board = [[None, None, None] for _ in range(3)]
        self.current_turn = 'X'
        self.winner = None
    
    def make_move(self, row: int, col: int) -> bool:
        """
        CONST-MOVE-01: Place a move only on unoccupied squares.
        Returns True if move was successful, False otherwise.
        """
        if self.winner is not None:
            return False
        
        if self.board[row][col] is not None:
            return False
        
        self.board[row][col] = self.current_turn
        self._check_winner()
        
        if self.winner is None:
            self.current_turn = 'O' if self.current_turn == 'X' else 'X'
        
        return True
    
    def _check_winner(self):
        """Check if there's a winner or draw."""
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                self.winner = row[0]
                return
        
        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                self.winner = self.board[0][col]
                return
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            self.winner = self.board[0][0]
            return
        
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            self.winner = self.board[0][2]
            return
        
        # Check for draw
        if all(self.board[r][c] is not None for r in range(3) for c in range(3)):
            self.winner = 'Draw'
    
    def to_dict(self) -> dict:
        """feat-save-game-state: Serialize GameState to dictionary."""
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'winner': self.winner
        }
    
    def from_dict(self, data: dict):
        """feat-save-game-state: Deserialize GameState from dictionary."""
        self.board = data['board']
        self.current_turn = data['current_turn']
        self.winner = data['winner']
    
    def is_game_in_progress(self) -> bool:
        """Check if game is currently being played (has moves but no winner)."""
        has_moves = any(self.board[r][c] is not None for r in range(3) for c in range(3))
        return has_moves and self.winner is None


class TicTacToeGame:
    """Main game controller using urwid TUI."""
    
    SAVE_FILE = os.path.expanduser('~/.tictactoe_save.json')
    
    def __init__(self):
        self.game_state = GameState()
        self.status_text = urwid.Text("Player X's turn", align='center')
        self.buttons = []
        self._create_ui()
        
        # Try to load saved game
        self._load_game()
    
    def _create_ui(self):
        """Create the urwid user interface."""
        # Create 3x3 grid of buttons
        self.buttons = []
        grid_rows = []
        
        for row in range(3):
            button_row = []
            for col in range(3):
                btn = urwid.Button('   ', on_press=self._on_cell_click, user_data=(row, col))
                btn = urwid.AttrMap(btn, 'button', 'button_focus')
                button_row.append(btn)
                self.buttons.append((row, col, btn))
            grid_rows.append(urwid.Columns(button_row, dividechars=1))
        
        grid = urwid.Pile(grid_rows)
        grid_box = urwid.LineBox(grid, title='Tic-Tac-Toe')
        
        # Control buttons
        new_game_btn = urwid.Button('New Game', on_press=self._on_new_game)
        save_btn = urwid.Button('Save Game', on_press=self._on_save_game)
        load_btn = urwid.Button('Load Game', on_press=self._on_load_game)
        quit_btn = urwid.Button('Quit', on_press=self._on_quit)
        
        controls = urwid.Columns([
            urwid.AttrMap(new_game_btn, 'button', 'button_focus'),
            urwid.AttrMap(save_btn, 'button', 'button_focus'),
            urwid.AttrMap(load_btn, 'button', 'button_focus'),
            urwid.AttrMap(quit_btn, 'button', 'button_focus'),
        ], dividechars=2)
        
        # Main layout
        layout = urwid.Pile([
            urwid.Divider(),
            self.status_text,
            urwid.Divider(),
            grid_box,
            urwid.Divider(),
            controls,
            urwid.Divider(),
        ])
        
        self.main_widget = urwid.Filler(layout, valign='top')
        
        # Define color palette
        self.palette = [
            ('button', 'white', 'dark blue'),
            ('button_focus', 'white', 'dark cyan'),
            ('winner', 'yellow,bold', 'dark blue'),
        ]
    
    def _update_board_display(self):
        """Update the visual display of the board."""
        for row, col, btn_widget in self.buttons:
            cell_value = self.game_state.board[row][col]
            display_text = f' {cell_value} ' if cell_value else '   '
            btn_widget.original_widget.set_label(display_text)
        
        # Update status text
        if self.game_state.winner:
            if self.game_state.winner == 'Draw':
                self.status_text.set_text(('winner', "Game Over - It's a Draw!"))
            else:
                self.status_text.set_text(('winner', f"Game Over - Player {self.game_state.winner} Wins!"))
        else:
            self.status_text.set_text(f"Player {self.game_state.current_turn}'s turn")
    
    def _on_cell_click(self, button, user_data):
        """Handle cell button click - REQ-001: Two-player local play."""
        row, col = user_data
        
        if self.game_state.make_move(row, col):
            self._update_board_display()
    
    def _on_new_game(self, button):
        """
        feat-ask-before-new: Warn player if game is in progress.
        feat-create-new-game: Reset game state.
        """
        if self.game_state.is_game_in_progress():
            # Show confirmation dialog
            self._show_confirmation_dialog(
                "Current game in progress. Start new game and lose current progress?",
                self._confirm_new_game
            )
        else:
            self._confirm_new_game()
    
    def _confirm_new_game(self):
        """Actually create a new game after confirmation."""
        self.game_state.reset()
        self._update_board_display()
        self._close_dialog()
    
    def _on_save_game(self, button):
        """feat-save-game-state: Save game to local storage."""
        try:
            with open(self.SAVE_FILE, 'w') as f:
                json.dump(self.game_state.to_dict(), f)
            self._show_message_dialog("Game saved successfully!")
        except Exception as e:
            self._show_message_dialog(f"Error saving game: {e}")
    
    def _on_load_game(self, button):
        """Load game from local storage."""
        if self.game_state.is_game_in_progress():
            self._show_confirmation_dialog(
                "Current game in progress. Load saved game and lose current progress?",
                self._confirm_load_game
            )
        else:
            self._confirm_load_game()
    
    def _confirm_load_game(self):
        """Actually load the game after confirmation."""
        loaded = self._load_game()
        if loaded:
            self._show_message_dialog("Game loaded successfully!")
        else:
            self._show_message_dialog("No saved game found!")
        self._close_dialog()
    
    def _load_game(self) -> bool:
        """Load game state from file. Returns True if successful."""
        try:
            if os.path.exists(self.SAVE_FILE):
                with open(self.SAVE_FILE, 'r') as f:
                    data = json.load(f)
                self.game_state.from_dict(data)
                self._update_board_display()
                return True
        except Exception:
            pass
        return False
    
    def _on_quit(self, button):
        """Exit the application."""
        raise urwid.ExitMainLoop()
    
    def _show_confirmation_dialog(self, message: str, on_confirm):
        """Show a confirmation dialog with Yes/No buttons."""
        text = urwid.Text(message, align='center')
        
        yes_btn = urwid.Button('Yes', on_press=lambda b: on_confirm())
        no_btn = urwid.Button('No', on_press=lambda b: self._close_dialog())
        
        buttons = urwid.Columns([
            urwid.AttrMap(yes_btn, 'button', 'button_focus'),
            urwid.AttrMap(no_btn, 'button', 'button_focus'),
        ], dividechars=2)
        
        pile = urwid.Pile([
            urwid.Divider(),
            text,
            urwid.Divider(),
            buttons,
            urwid.Divider(),
        ])
        
        dialog = urwid.LineBox(urwid.Filler(pile))
        dialog = urwid.AttrMap(dialog, 'button')
        
        self.dialog_overlay = urwid.Overlay(
            dialog,
            self.main_widget,
            align='center',
            width=('relative', 60),
            valign='middle',
            height=('relative', 30)
        )
        
        self.loop.widget = self.dialog_overlay
    
    def _show_message_dialog(self, message: str):
        """Show a simple message dialog with OK button."""
        text = urwid.Text(message, align='center')
        ok_btn = urwid.Button('OK', on_press=lambda b: self._close_dialog())
        ok_btn = urwid.AttrMap(ok_btn, 'button', 'button_focus')
        
        pile = urwid.Pile([
            urwid.Divider(),
            text,
            urwid.Divider(),
            ok_btn,
            urwid.Divider(),
        ])
        
        dialog = urwid.LineBox(urwid.Filler(pile))
        dialog = urwid.AttrMap(dialog, 'button')
        
        self.dialog_overlay = urwid.Overlay(
            dialog,
            self.main_widget,
            align='center',
            width=('relative', 50),
            valign='middle',
            height=('relative', 25)
        )
        
        self.loop.widget = self.dialog_overlay
    
    def _close_dialog(self):
        """Close any open dialog."""
        self.loop.widget = self.main_widget
        self._update_board_display()
    
    def run(self):
        """Start the game loop."""
        self.loop = urwid.MainLoop(
            self.main_widget,
            palette=self.palette,
            unhandled_input=self._handle_input
        )
        self._update_board_display()
        self.loop.run()
    
    def _handle_input(self, key):
        """Handle keyboard shortcuts."""
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()


def main():
    """REQ-002: Single source file entry point."""
    game = TicTacToeGame()
    game.run()


if __name__ == '__main__':
    main()
