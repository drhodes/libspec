#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tic‑Tac‑Toe (local two‑player) with a Urwid TUI.

Features
--------
* Two‑player local play – players take turns on the same device.
* One‑source‑file – everything lives in this single Python file.
* Urwid based text UI – works on Linux, macOS, Windows (with a terminal).
* “New Game” button with a confirmation dialog when a game is in progress.
* “Save Game” button – serialises the current GameState to a JSON file
  (`tictactoe_save.json`) for later resumption.
* Move‑validation (CONST‑MOVE‑01) – a move can only be placed on an empty
  square.
"""

import json
from pathlib import Path
from typing import List, Optional

import urwid

# ----------------------------------------------------------------------
# Data model (REQ‑001, REQ‑004)
# ----------------------------------------------------------------------
class GameState:
    """Simple container for the board, turn and winner."""

    def __init__(self):
        self.board: List[List[Optional[str]]] = [[None] * 3 for _ in range(3)]
        self.current_turn: str = "X"
        self.winner: Optional[str] = None

    # ------------------------------------------------------------------
    # Core game logic
    # ------------------------------------------------------------------
    def make_move(self, row: int, col: int) -> bool:
        """
        Attempt to place the current player's mark at (row, col).

        Returns True if the move was successful, False otherwise.
        Enforces CONST‑MOVE‑01.
        """
        if self.winner is not None:
            return False                      # game already finished
        if self.board[row][col] is not None:
            return False                      # square already occupied
        self.board[row][col] = self.current_turn
        self._update_winner()
        if self.winner is None:               # no winner yet → next turn
            self.current_turn = "O" if self.current_turn == "X" else "X"
        return True

    def _update_winner(self) -> None:
        """Detect a win or a draw and set ``self.winner`` accordingly."""
        lines = []  # rows, cols, diagonals
        lines.extend(self.board)                                 # rows
        lines.extend([[self.board[r][c] for r in range(3)] for c in range(3)])  # cols
        lines.append([self.board[i][i] for i in range(3)])       # main diag
        lines.append([self.board[i][2 - i] for i in range(3)])   # anti diag

        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                self.winner = line[0]
                return

        # draw?
        if all(cell is not None for row in self.board for cell in row):
            self.winner = "Draw"

    # ------------------------------------------------------------------
    # Serialisation (REQ‑004)
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "board": [[cell for cell in row] for row in self.board],
            "current_turn": self.current_turn,
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        gs = cls()
        gs.board = data["board"]
        gs.current_turn = data["current_turn"]
        gs.winner = data["winner"]
        return gs

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def is_empty(self) -> bool:
        """True if every cell is ``None``."""
        return all(cell is None for row in self.board for cell in row)

    def reset(self) -> None:
        """Reset the board for a brand‑new game."""
        self.__init__()


# ----------------------------------------------------------------------
# UI implementation (REQ‑002, REQ‑004)
# ----------------------------------------------------------------------
class TicTacToeUI:
    SAVE_PATH = Path("tictactoe_save.json")

    def __init__(self):
        self.state = GameState()

        # ---------- UI widgets ----------
        self.info_text = urwid.Text(self._info_message(), align="center")
        self.board_widgets = self._make_board_widgets()
        board_grid = urwid.GridFlow(self.board_widgets,
                                    cell_width=7, h_sep=1, v_sep=1,
                                    align="center")

        # ---- Buttons -------------------------------------------------
        new_btn = urwid.Button("New Game", on_press=self._on_new_game)
        save_btn = urwid.Button("Save Game", on_press=self._on_save_game)
        load_btn = urwid.Button("Load Game", on_press=self._on_load_game)

        # The *only* place where we previously used Columns(..., align=...)
        # is replaced by a Columns wrapped in Padding to achieve centring.
        button_columns = urwid.Columns(
            [
                urwid.Padding(new_btn, left=2, right=2),
                urwid.Padding(save_btn, left=2, right=2),
                urwid.Padding(load_btn, left=2, right=2),
            ],
            dividechars=2,
        )
        button_bar = urwid.Padding(button_columns, align="center", width=("relative", 60))

        # ---- Layout --------------------------------------------------
        pile = urwid.Pile([
            urwid.Divider(),
            self.info_text,
            urwid.Divider(),
            board_grid,
            urwid.Divider(),
            button_bar,
        ])

        self.main_filler = urwid.Filler(pile, valign="top")
        self.loop = urwid.MainLoop(self.main_filler, palette=self._palette())

    # ------------------------------------------------------------------
    # Palette (colours) – optional but nice
    # ------------------------------------------------------------------
    @staticmethod
    def _palette():
        return [
            ("info", "light cyan", ""),
            ("button normal", "light gray", "dark blue"),
            ("button select", "white", "dark green"),
            ("cell", "black", "light gray"),
            ("cell selected", "white", "dark red"),
            ("winner", "light green", ""),
        ]

    # ------------------------------------------------------------------
    # Board creation
    # ------------------------------------------------------------------
    def _make_board_widgets(self) -> List[urwid.Widget]:
        """Create a list of 9 Buttons that act as the 3×3 board."""
        widgets = []
        for r in range(3):
            for c in range(3):
                btn = urwid.Button(" ", on_press=self._on_cell_pressed,
                                   user_data=(r, c))
                btn = urwid.AttrMap(btn, "cell", focus_map="cell selected")
                widgets.append(btn)
        return widgets

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------
    def _on_cell_pressed(self, button: urwid.Button, user_data):
        row, col = user_data
        moved = self.state.make_move(row, col)
        if not moved:
            # either occupied or game already over → ignore
            return
        self._refresh_board()
        self.info_text.set_text(self._info_message())
        if self.state.winner:
            self._show_winner_overlay()

    def _on_new_game(self, button):
        """Feature: ask‑before‑new (feat‑ask‑before‑new)."""
        if not self.state.is_empty() and self.state.winner is None:
            # Game in progress → ask for confirmation
            confirm = urwid.Text(
                "A game is in progress. Starting a new game will lose the current one.\n"
                "Proceed?"
            )
            yes = urwid.Button("Yes", on_press=self._confirm_new_game)
            no = urwid.Button("No", on_press=lambda b: self._close_overlay())
            buttons = urwid.Columns([yes, no], dividechars=4, align="center")
            pile = urwid.Pile([confirm, urwid.Divider(), buttons])
            overlay = urwid.Overlay(
                urwid.LineBox(pile, title="Confirm New Game"),
                self.main_filler,
                align="center",
                width=("relative", 60),
                valign="middle",
                height=("relative", 30),
            )
            self.loop.widget = overlay
        else:
            # No game in progress – just reset
            self.state.reset()
            self._refresh_board()
            self.info_text.set_text(self._info_message())

    def _confirm_new_game(self, button):
        self.state.reset()
        self._refresh_board()
        self.info_text.set_text(self._info_message())
        self._close_overlay()

    def _on_save_game(self, button):
        """Feature: save‑game‑state (feat‑save‑game‑state)."""
        try:
            with self.SAVE_PATH.open("w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
            self._show_message(f"Game saved to '{self.SAVE_PATH}'.")
        except Exception as exc:
            self._show_message(f"Error saving game: {exc}")

    def _on_load_game(self, button):
        """Optional convenience: load previously saved game."""
        if not self.SAVE_PATH.is_file():
            self._show_message("No saved game found.")
            return
        try:
            with self.SAVE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self.state = GameState.from_dict(data)
            self._refresh_board()
            self.info_text.set_text(self._info_message())
            self._show_message("Game loaded.")
        except Exception as exc:
            self._show_message(f"Error loading game: {exc}")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _info_message(self) -> str:
        if self.state.winner:
            if self.state.winner == "Draw":
                return "The game is a draw!"
            return f"Player {self.state.winner} wins!"
        return f"Turn: Player {self.state.current_turn}"

    def _refresh_board(self) -> None:
        """Update the 9 cell buttons to reflect the current board."""
        for idx, (r, c) in enumerate(((i // 3, i % 3) for i in range(9))):
            cell = self.state.board[r][c]
            label = cell if cell is not None else " "
            btn = self.board_widgets[idx].original_widget   # the Button inside AttrMap
            btn.set_label(label)

    def _show_message(self, msg: str) -> None:
        """Show a transient modal message (OK → dismiss)."""
        txt = urwid.Text(msg, align="center")
        ok = urwid.Button("OK", on_press=lambda b: self._close_overlay())
        pile = urwid.Pile([txt, urwid.Divider(), urwid.Padding(ok, align="center", width=8)])
        overlay = urwid.Overlay(
            urwid.LineBox(pile, title="Message"),
            self.main_filler,
            align="center",
            width=("relative", 60),
            valign="middle",
            height=("relative", 30),
        )
        self.loop.widget = overlay

    def _show_winner_overlay(self) -> None:
        """When the game ends, pop‑up a small win/draw dialog."""
        if self.state.winner == "Draw":
            msg = "It’s a draw!"
        else:
            msg = f"Player {self.state.winner} wins!"
        txt = urwid.Text(msg, align="center")
        new = urwid.Button("New Game", on_press=self._on_new_game)
        close = urwid.Button("Close", on_press=lambda b: self._close_overlay())
        buttons = urwid.Columns([new, close], dividechars=4, align="center")
        pile = urwid.Pile([txt, urwid.Divider(), buttons])
        overlay = urwid.Overlay(
            urwid.LineBox(pile, title="Game Over"),
            self.main_filler,
            align="center",
            width=("relative", 60),
            valign="middle",
            height=("relative", 30),
        )
        self.loop.widget = overlay

    def _close_overlay(self):
        self.loop.widget = self.main_filler

    # ------------------------------------------------------------------
    # Run the app
    # ------------------------------------------------------------------
    def run(self):
        self.loop.run()


if __name__ == "__main__":
    TicTacToeUI().run()
