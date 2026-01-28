from libspec import Feature, Constraint, Requirement, DataSchema
from typing import List

DATE = "2026-01-26"

## --- DATA SCHEMA ---
class GameState(DataSchema):
    '''Specific notes about this game state for TicTacToe'''
    board: list[list[str]]
    current_turn: str
    winner: str | None
    
    def model_name(self):
        return "tic-tac-toe-state"
    
## --- REQUIREMENTS ---
class LocalPlay(Requirement):
    def req_id(self):  return "REQ-001"
    def title(self):   return "Two-Player Local Play"
    def actor(self):   return "player"
    def action(self):  return "take turns on the same device"
    def benefit(self): return "we can play a game together without a network"

class SingleFile(Requirement):
    def req_id(self):  return "REQ-002"
    def title(self):   return "one-source-file"
    def actor(self):   return "LLM"
    def action(self):  return "The LLM should generate a program in a single source file."
    def benefit(self): return "makes it easier to manage copy pasting"

class Target(Requirement):
    def req_id(self):  return "REQ-003"
    def title(self):   return "platform-target"
    def actor(self):   return "LLM"
    def action(self):  return "generate python using tkinter"
    def benefit(self): return "make for simple cross deployment demo"

class TargetTkinter(Target):
    def req_id(self):  return "REQ-003"
    def title(self):   return "platform-target"
    def actor(self):   return "LLM"
    def action(self):  return "generate python using tkinter"
    def benefit(self): return "make for simple cross deployment demo"

class TargetUrwid(Target):
      '''Ensure the grid layout is actually square and buttons share
      the same width.  The elements must be horizontally and
      vertically centered.  Use Filler with valign='middle' for
      vertical centering.
                                                                                                                                                                                                                
      To center content horizontally WITHOUT specifying a width in
      urwid.Padding:

      1. Use urwid.Padding(content, align='center').

      2. To prevent expansion, the 'content' must be wrapped in
      urwid.BigText or a urwid.BoxAdapter/urwid.FixedHandler to signal
      intrinsic width.

      3. Alternatively, wrap the inner Pile in a urwid.IntrinsicSize
      or set the Column widths to 'given' to ensure they do not
      stretch to the full screen width.
      '''       
    
## --- FEATURES ---
class CreateNewGame(Feature):
    def feature_name(self): return "create-new-game"
    def date(self):         return DATE
    def description(self):  return "Resets the GameState board and sets current_turn to 'X'."
    
class AskBeforeNew(Feature):
    def feature_name(self): return "ask-before-new"
    def date(self):         return DATE
    def description(self): return ''' if the game is currently being
    played and the `new game` button is pressed then warn the player
    that the current game will be lost unless they cancel'''

class SaveGame(Feature):
    def feature_name(self): return "save-game-state"
    def date(self):         return DATE
    def description(self):  return "Serializes the GameState to local storage for later resumption."
    
## --- CONSTRAINTS ---
class MoveValidation(Constraint):
    def constraint_id(self):
        return "CONST-MOVE-01"    
    def description(self):        
        return "Ensures moves are only placed on unoccupied squares."
    def enforcement_logic(self):  
        return "Check game_state.board[row][col] is None before writing."
    

class TicTacToeSpec:
    def __init__(self):
        self.components = [
            # DATA MODEL
            GameState(),
            
            # REQUIREMENTS,
            LocalPlay(),
            SingleFile(),
            # TargetTkinter(),
            TargetUrwid(),

            # FEATURES  
            CreateNewGame(),
            SaveGame(),
            AskBeforeNew(),

            # CONSTRAINTS
            MoveValidation()
        ]

    def generate_full_spec(self):
        return "\n\n".join(c.render() for c in self.components)

    
# Usage
spec_doc = TicTacToeSpec().generate_full_spec()
print(spec_doc)


