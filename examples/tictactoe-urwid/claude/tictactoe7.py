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
        data = {"board": self.board, "current_turn": self.current_turn, "winner": self.winner}
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)

    def load(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                self.board, self.current_turn, self.winner = data["board"], data["current_turn"], data["winner"]

class TicTacToeUI:
    def __init__(self):
        self.game = GameState()
        self.game.load()
        self.buttons = []
        self.status_line = urwid.Text("", align='center')
        self.main_loop = None
        self.view = self.build_ui()

    def build_ui(self):
        grid_rows = []
        for r in range(3):
            cols = []
            for c in range(3):
                btn = urwid.Button(self.game.board[r][c] or " ")
                urwid.connect_signal(btn, 'click', self.handle_move, (r, c))
                # Fix: Use 'fixed' width in Columns to prevent horizontal stretching
                cols.append(('fixed', 7, urwid.AttrMap(btn, None, focus_map='reversed')))
                self.buttons.append(btn)
            grid_rows.append(urwid.Columns(cols, dividechars=1))
        
        # Control buttons also fixed to maintain square-ish proportions
        new_game_btn = urwid.Button("New Game", on_press=self.confirm_new_game)
        save_btn = urwid.Button("Save Game", on_press=lambda _: self.game.save())
        
        menu_content = urwid.Pile([
            self.status_line,
            urwid.Divider(),
            urwid.Pile(grid_rows),
            urwid.Divider(),
            urwid.Columns([('fixed', 11, new_game_btn), ('fixed', 11, save_btn)], dividechars=1)
        ])
        
        # Requirement: Padding without width, relying on fixed children for centering
        self.padded_view = urwid.Padding(menu_content, align='center')
        self.update_status()
        return urwid.Filler(self.padded_view, valign='middle')

    def update_status(self):
        if self.game.winner:
            self.status_line.set_text(f"Winner: {self.game.winner}!")
        elif all(all(row) for row in self.game.board):
            self.status_line.set_text("It's a Draw!")
        else:
            self.status_line.set_text(f"Turn: {self.game.current_turn}")
        
        for i, btn in enumerate(self.buttons):
            r, c = divmod(i, 3)
            btn.set_label(self.game.board[r][c] or " ")

    def handle_move(self, button, pos):
        r, c = pos
        if self.game.board[r][c] is None and not self.game.winner:
            self.game.board[r][c] = self.game.current_turn
            self.game.winner = self.check_winner()
            if not self.game.winner:
                self.game.current_turn = 'O' if self.game.current_turn == 'X' else 'X'
            self.update_status()

    def check_winner(self):
        b = self.game.board
        lines = b + list(map(list, zip(*b))) + [[b[i][i] for i in range(3)], [b[i][2-i] for i in range(3)]]
        for line in lines:
            if line[0] and all(x == line[0] for x in line): return line[0]
        return None

    def confirm_new_game(self, _):
        if any(any(row) for row in self.game.board) and not self.game.winner:
            overlay = urwid.Overlay(
                urwid.LineBox(urwid.Pile([
                    urwid.Text("Abandon game?", align='center'),
                    urwid.Columns([urwid.Button("Yes", on_press=self.reset_game), 
                                   urwid.Button("No", on_press=self.close_pop_up)])
                ])), self.view, 'center', 25, 'middle', 5
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
