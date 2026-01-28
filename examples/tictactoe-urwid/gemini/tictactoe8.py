import urwid
import json
import os

# REQ-002: one-source-file
SAVE_FILE = "tictactoe_state.json"

class GameState:
    """DATA-MODEL: tic-tac-toe-state"""
    def __init__(self):
        self.reset()

    def reset(self):
        # Input: Resets the GameState board and sets current_turn to 'X'
        self.board = [[None for _ in range(3)] for _ in range(3)]
        self.current_turn = 'X'
        self.winner = None

    def save(self):
        # [feat-save-game-state] Serializes to local storage
        data = {"board": self.board, "current_turn": self.current_turn, "winner": self.winner}
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)

    def load(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                d = json.load(f)
                self.board, self.current_turn, self.winner = d["board"], d["current_turn"], d["winner"]

class TicTacToeUI:
    def __init__(self):
        self.game = GameState()
        self.game.load()
        self.buttons = []
        self.status_line = urwid.Text("", align='center')
        self.main_loop = None
        self.view = self.build_ui()

    def build_ui(self):
        # REQ-004: Ensure grid layout is square and buttons share same width
        grid_rows = []
        for r in range(3):
            cols = []
            for c in range(3):
                btn = urwid.Button(self.game.board[r][c] or " ")
                urwid.connect_signal(btn, 'click', self.handle_move, (r, c))
                # Set Column width to 'given' via fixed tuple to prevent stretching
                cols.append((8, urwid.AttrMap(btn, None, focus_map='reversed')))
                self.buttons.append(btn)
            grid_rows.append(urwid.Columns(cols, dividechars=1))
        
        # Action buttons
        new_btn = urwid.Button("New Game", on_press=self.confirm_new)
        save_btn = urwid.Button("Save Game", on_press=lambda _: self.game.save())
        ctrls = urwid.Columns([(13, new_btn), (13, save_btn)], dividechars=1)

        # Pile containing all UI elements
        inner_pile = urwid.Pile([
            self.status_line,
            urwid.Divider(),
            urwid.Pile(grid_rows),
            urwid.Divider(),
            ctrls
        ])

        # REQ-004: Center horizontally WITHOUT specifying width in Padding
        # Using BoxAdapter to signal intrinsic width to the Padding widget
        content_box = urwid.BoxAdapter(urwid.Filler(inner_pile), height=11)
        self.padded_view = urwid.Padding(content_box, align='center')
        
        self.update_status()
        
        # REQ-004: Main layout uses Filler with valign='middle' for vertical centering
        return urwid.Filler(self.padded_view, valign='middle')

    def update_status(self):
        if self.game.winner:
            self.status_line.set_text(f"Winner: {self.game.winner}!")
        elif all(all(row) for row in self.game.board):
            self.status_line.set_text("Draw!")
        else:
            self.status_line.set_text(f"Turn: {self.game.current_turn}")
        
        for i, btn in enumerate(self.buttons):
            r, c = divmod(i, 3)
            btn.set_label(self.game.board[r][c] or " ")

    def handle_move(self, _, pos):
        r, c = pos
        # CONST-MOVE-01: Check board is None before writing
        if self.game.board[r][c] is None and not self.game.winner:
            self.game.board[r][c] = self.game.current_turn
            self.game.winner = self.check_winner()
            if not self.game.winner:
                # REQ-001: Two-Player Local Play
                self.game.current_turn = 'O' if self.game.current_turn == 'X' else 'X'
            self.update_status()

    def check_winner(self):
        b = self.game.board
        lines = b + list(map(list, zip(*b))) + [[b[i][i] for i in range(3)], [b[i][2-i] for i in range(3)]]
        for line in lines:
            if line[0] and all(x == line[0] for x in line): return line[0]
        return None

    def confirm_new(self, _):
        # [feat-ask-before-new] Warn if game is in progress
        is_playing = any(any(row) for row in self.game.board) and not self.game.winner
        if is_playing:
            overlay = urwid.Overlay(
                urwid.LineBox(urwid.Pile([
                    urwid.Text("Abandon current game?", align='center'),
                    urwid.Divider(),
                    urwid.Columns([
                        urwid.Button("Yes", on_press=self.reset_game),
                        urwid.Button("No", on_press=self.close_pop_up)
                    ])
                ])), self.view, 'center', 30, 'middle', 7
            )
            self.main_loop.widget = overlay
        else:
            self.reset_game(None)

    def reset_game(self, _):
        self.game.reset()
        self.update_status()
        self.close_pop_up(None)

    def close_pop_up(self, _):
        self.main_loop.widget = self.view

    def run(self):
        self.main_loop = urwid.MainLoop(self.view)
        self.main_loop.run()

if __name__ == "__main__":
    TicTacToeUI().run()
