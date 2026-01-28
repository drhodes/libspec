import urwid
import json
import os

SAVE_FILE = "tictactoe_save.json"

class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [[None for _ in range(3)] for _ in range(3)]
        self.current_turn = 'X'
        self.winner = None

    def save(self):
        data = {
            "board": self.board,
            "current_turn": self.current_turn,
            "winner": self.winner
        }
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)

    def load(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                self.board = data["board"]
                self.current_turn = data["current_turn"]
                self.winner = data["winner"]

class TicTacToeUI:
    def __init__(self):
        self.game = GameState()
        self.game.load()
        self.buttons = []
        self.status_line = urwid.Text("", align='center')
        self.main_loop = None
        self.view = self.build_ui()

    def build_ui(self):
        # Create 3x3 Grid
        grid_rows = []
        for r in range(3):
            cols = []
            for c in range(3):
                val = self.game.board[r][c] or " "
                btn = urwid.Button(val)
                urwid.connect_signal(btn, 'click', self.handle_move, (r, c))
                cols.append(btn)
                self.buttons.append(btn)
            # Use columns to ensure uniform width
            grid_rows.append(urwid.Columns(cols, dividechars=1))
        
        # Grid Container
        grid_pile = urwid.Pile(grid_rows)
        
        # Control Buttons
        new_game_btn = urwid.Button("New Game")
        urwid.connect_signal(new_game_btn, 'click', self.confirm_new_game)
        
        save_btn = urwid.Button("Save Game")
        urwid.connect_signal(save_btn, 'click', lambda _: self.game.save())

        # Main Layout
        menu = urwid.Pile([
            self.status_line,
            urwid.Divider(),
            grid_pile,
            urwid.Divider(),
            new_game_btn,
            save_btn
        ])
        
        # Layout requirements: Padding (horizontal) inside Filler (vertical)
        padded_menu = urwid.Padding(menu, align='center')
        self.update_status()
        return urwid.Filler(padded_menu, valign='middle')

    def update_status(self):
        if self.game.winner:
            self.status_line.set_text(f"Winner: {self.game.winner}!")
        elif all(all(row) for row in self.game.board):
            self.status_line.set_text("It's a Draw!")
        else:
            self.status_line.set_text(f"Turn: {self.game.current_turn}")
        
        # Update button labels
        for i, btn in enumerate(self.buttons):
            r, c = divmod(i, 3)
            btn.set_label(self.game.board[r][c] or " ")

    def handle_move(self, button, pos):
        r, c = pos
        if self.game.board[r][c] is None and not self.game.winner:
            self.game.board[r][c] = self.game.current_turn
            if self.check_winner():
                self.game.winner = self.game.current_turn
            else:
                self.game.current_turn = 'O' if self.game.current_turn == 'X' else 'X'
            self.update_status()

    def check_winner(self):
        b = self.game.board
        lines = b + list(map(list, zip(*b))) # Rows + Cols
        lines.append([b[0][0], b[1][1], b[2][2]]) # Diag 1
        lines.append([b[0][2], b[1][1], b[2][0]]) # Diag 2
        return any(all(x == self.game.current_turn for x in line) for line in lines)

    def confirm_new_game(self, _):
        # Ask before new if game is in progress
        is_in_progress = any(any(row) for row in self.game.board) and not self.game.winner
        if is_in_progress:
            overlay = urwid.Overlay(
                urwid.LineBox(urwid.Pile([
                    urwid.Text("Abandon current game?", align='center'),
                    urwid.Columns([
                        urwid.Button("Yes", on_press=self.reset_game),
                        urwid.Button("No", on_press=self.close_pop_up)
                    ])
                ])),
                self.view, 'center', 30, 'middle', 5
            )
            self.main_loop.widget = overlay
        else:
            self.reset_game(None)

    def reset_game(self, _):
        self.game.reset()
        self.update_status()
        self.main_loop.widget = self.view

    def close_pop_up(self, _):
        self.main_loop.widget = self.view

    def run(self):
        self.main_loop = urwid.MainLoop(self.view)
        self.main_loop.run()

if __name__ == "__main__":
    TicTacToeUI().run()
