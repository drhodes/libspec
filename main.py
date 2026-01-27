from spec import Feature, Constraint, Requirement, DataSchema

DATE = "2026-01-26"

## --- DATA SCHEMA ---
class GameState(DataSchema):
    def model_name(self): return "tic-tac-toe-board"
    def fields(self):
        return str({
            'board': List[List[str]],
            'current_turn': str,
            'status': str
        })
    def invariants(self): return "Board must always be 3x3. Cells must be 'X', 'O', or empty."

## --- REQUIREMENTS ---
class LocalPlay(Requirement):
    def req_id(self):  return "REQ-001"
    def title(self):   return "Two-Player Local Play"
    def actor(self):   return "player"
    def action(self):  return "take turns on the same device"
    def benefit(self): return "we can play a game together without a network"

## --- FEATURES ---
class CreateNewGame(Feature):
    def feature_name(self): return "create-new-game"
    def date(self):         return DATE
    def description(self):  return "Resets the GameState board and sets current_turn to 'X'."

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
            # data model
            GameState(),
            # features
            LocalPlay(),
            CreateNewGame(),
            SaveGame(),
            # constraints
            MoveValidation()
        ]

    def generate_full_spec(self):
        return "\n\n".join(c.render() for c in self.components)

    
# Usage
spec_doc = TicTacToeSpec().generate_full_spec()
print(spec_doc)


