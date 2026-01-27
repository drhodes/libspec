#!/usr/bin/env python3
"""
Tic-Tac-Toe Game
A two-player local game with save/load functionality
"""

import tkinter as tk
from tkinter import messagebox
import json
import os
from typing import Optional


class GameState:
    """Data model for Tic-Tac-Toe game state"""
    
    def __init__(self):
        self.board: list[list[Optional[str]]] = [[None, None, None] for _ in range(3)]
        self.current_turn: str = 'X'
        self.winner: Optional[str] = None
    
    def reset(self):
        """Resets the GameState board and sets current_turn to 'X' (REQ-001, feat-create-new-game)"""
        self.board = [[None, None, None] for _ in range(3)]
        self.current_turn = 'X'
        self.winner = None
    
    def make_move(self, row: int, col: int) -> bool:
        """
        Make a move on the board (CONST-MOVE-01)
        Returns True if move was successful, False otherwise
        """
        # CONST-MOVE-01: Ensures moves are only placed on unoccupied squares
        if self.board[row][col] is None and self.winner is None:
            self.board[row][col] = self.current_turn
            return True
        return False
    
    def check_winner(self) -> Optional[str]:
        """Check if there's a winner and update winner field"""
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                self.winner = row[0]
                return self.winner
        
        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                self.winner = self.board[0][col]
                return self.winner
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            self.winner = self.board[0][0]
            return self.winner
        
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            self.winner = self.board[0][2]
            return self.winner
        
        # Check for tie
        if all(self.board[i][j] is not None for i in range(3) for j in range(3)):
            self.winner = 'TIE'
            return self.winner
        
        return None
    
    def switch_turn(self):
        """Switch to the other player's turn"""
        self.current_turn = 'O' if self.current_turn == 'X' else 'X'
    
    def to_dict(self) -> dict:
        """Convert game state to dictionary for serialization"""
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'winner': self.winner
        }
    
    def from_dict(self, data: dict):
        """Load game state from dictionary"""
        self.board = data['board']
        self.current_turn = data['current_turn']
        self.winner = data['winner']


class TicTacToeGame:
    """Main game class with GUI (REQ-003: Python using tkinter)"""
    
    SAVE_FILE = 'tictactoe_save.json'
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Tic-Tac-Toe")
        self.game_state = GameState()
        self.buttons = []
        
        self.setup_ui()
        self.update_display()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Status label
        self.status_label = tk.Label(
            self.root,
            text=f"Player {self.game_state.current_turn}'s turn",
            font=('Arial', 16),
            pady=10
        )
        self.status_label.grid(row=0, column=0, columnspan=3)
        
        # Game board (REQ-001: Two-player local play on same device)
        for i in range(3):
            row_buttons = []
            for j in range(3):
                button = tk.Button(
                    self.root,
                    text='',
                    font=('Arial', 32, 'bold'),
                    width=5,
                    height=2,
                    command=lambda r=i, c=j: self.handle_click(r, c)
                )
                button.grid(row=i+1, column=j, padx=5, pady=5)
                row_buttons.append(button)
            self.buttons.append(row_buttons)
        
        # Control buttons
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        tk.Button(
            button_frame,
            text="New Game",
            font=('Arial', 12),
            command=self.new_game
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Save Game",
            font=('Arial', 12),
            command=self.save_game
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Load Game",
            font=('Arial', 12),
            command=self.load_game
        ).pack(side=tk.LEFT, padx=5)
    
    def handle_click(self, row: int, col: int):
        """Handle button click for game moves (REQ-001)"""
        if self.game_state.make_move(row, col):
            self.update_display()
            
            # Check for winner
            winner = self.game_state.check_winner()
            if winner:
                self.show_game_over(winner)
            else:
                self.game_state.switch_turn()
                self.update_display()
    
    def update_display(self):
        """Update the display to reflect current game state"""
        # Update board buttons
        for i in range(3):
            for j in range(3):
                cell_value = self.game_state.board[i][j]
                self.buttons[i][j].config(
                    text=cell_value if cell_value else '',
                    fg='blue' if cell_value == 'X' else 'red'
                )
        
        # Update status label
        if self.game_state.winner:
            if self.game_state.winner == 'TIE':
                self.status_label.config(text="Game Over - It's a Tie!")
            else:
                self.status_label.config(text=f"Game Over - Player {self.game_state.winner} Wins!")
        else:
            self.status_label.config(text=f"Player {self.game_state.current_turn}'s turn")
    
    def show_game_over(self, winner: str):
        """Show game over message"""
        if winner == 'TIE':
            message = "It's a tie!"
        else:
            message = f"Player {winner} wins!"
        
        messagebox.showinfo("Game Over", message)
    
    def new_game(self):
        """Create a new game (feat-create-new-game, feat-ask-before-new)"""
        # feat-ask-before-new: Warn if game is in progress
        game_in_progress = any(
            self.game_state.board[i][j] is not None 
            for i in range(3) for j in range(3)
        ) and self.game_state.winner is None
        
        if game_in_progress:
            response = messagebox.askyesno(
                "New Game",
                "A game is currently in progress. Starting a new game will lose the current game.\n\nDo you want to continue?"
            )
            if not response:  # User clicked 'No' or cancelled
                return
        
        self.game_state.reset()
        self.update_display()
    
    def save_game(self):
        """Save game state to local storage (feat-save-game-state)"""
        try:
            with open(self.SAVE_FILE, 'w') as f:
                json.dump(self.game_state.to_dict(), f)
            messagebox.showinfo("Success", "Game saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save game: {str(e)}")
    
    def load_game(self):
        """Load game state from local storage (feat-save-game-state)"""
        if not os.path.exists(self.SAVE_FILE):
            messagebox.showwarning("No Save", "No saved game found!")
            return
        
        try:
            with open(self.SAVE_FILE, 'r') as f:
                data = json.load(f)
            self.game_state.from_dict(data)
            self.update_display()
            messagebox.showinfo("Success", "Game loaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load game: {str(e)}")


def main():
    """Main entry point for the game"""
    root = tk.Tk()
    game = TicTacToeGame(root)
    root.mainloop()


if __name__ == '__main__':
    main()
