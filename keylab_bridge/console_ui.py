"""Simple and Textual terminal user interfaces."""

import os
import queue
import shutil
import sys
import threading
import time

from . import __version__
from .organ_layout import BANKS
from .midi_protocol import UNASSIGNED_PAD_COLOR, pad_screen_color
from translations import THEME_PALETTES, contrast_text

try:
    from rich.markup import escape
except ImportError:      # the simple console does not need Rich
    def escape(text):
        return text


class ConsoleUI:
    function_keys = {0: "F1", 1: "F2", 2: "F3", 3: "F4", 4: "F5", 5: "F6", 6: "F7", 7: "F8", 8: "F9", 9: "F10",
                     59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5", 64: "F6", 65: "F7", 66: "F8", 67: "F9", 68: "F10"}
    extended_keys = {72: "UP", 80: "DOWN", 75: "LEFT", 77: "RIGHT", 71: "HOME", 79: "END", 83: "DELETE",
                      73: "PAGEUP", 81: "PAGEDOWN"}

    def __init__(self, enabled=True):
        self.enabled = bool(enabled and sys.stdin.isatty() and sys.stdout.isatty())
        self.command = ""
        self.cursor = 0
        self.help = False
        self.help_scroll = 0
        self.raw_saved = None
        self.raw_fd = None
        if self.enabled and os.name != "nt":
            try:
                import termios
                import tty
                self.raw_fd = sys.stdin.fileno()
                self.raw_saved = termios.tcgetattr(self.raw_fd)
                tty.setcbreak(self.raw_fd)
            except Exception:
                self.raw_fd = None
                self.raw_saved = None
                self.enabled = False
        if self.enabled:
            sys.stdout.write("\x1b[?25l")

    def start(self, app):
        return

    @staticmethod
    def fit(text, width):
        text = " ".join(str(text).split())
        return text[:max(0, width)].ljust(max(0, width))

    def box(self, title, rows, width, height):
        label = f" {title} "
        if len(label) <= width - 4:
            top = "+-" + label[:width - 4] + "-" * (width - 4 - len(label[:width - 4])) + "+"
        else:
            top = "+" + "-" * max(1, width - 2)
        top = top[:width]
        out = [self.fit(top, width)]
        for index in range(height - 2):
            content = rows[index] if index < len(rows) else ""
            out.append("|" + self.fit(content, width - 2) + "|")
        out.append("+" + "-" * max(1, width - 2) + "+")
        return out

    def side_by_side(self, left_title, left, right_title, right, width, height):
        left_width = max(28, (width - 1) // 2)
        right_width = width - left_width - 1
        left_box = self.box(left_title, left, left_width, height)
        right_box = self.box(right_title, right, right_width, height)
        return [" ".join((left_box[i], right_box[i])) for i in range(height)]

    @staticmethod
    def uptime(seconds):
        seconds = max(0, int(seconds))
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def read_keys(self):
        if not self.enabled:
            return []
        keys = []
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    code = ord(msvcrt.getwch())
                    keys.append(self.function_keys.get(code, self.extended_keys.get(code, "")))
                elif char in ("\r", "\n"):
                    keys.append("ENTER")
                elif char in ("\b", "\x7f"):
                    keys.append("BACKSPACE")
                elif char == "\x03":
                    keys.append("QUIT")
                elif char == "\t":
                    keys.append("TAB")
                elif char == "\x0c":
                    keys.append("CLEAR")
                elif char == "\x1b":
                    keys.append("ESC")
                elif char.isprintable():
                    keys.append(char)
        else:
            import select as select_module
            while select_module.select([sys.stdin], [], [], 0)[0]:
                char = os.read(sys.stdin.fileno(), 1).decode(errors="ignore")
                if char in ("\r", "\n"):
                    keys.append("ENTER")
                elif char in ("\b", "\x7f"):
                    keys.append("BACKSPACE")
                elif char == "\x03":
                    keys.append("QUIT")
                elif char == "\t":
                    keys.append("TAB")
                elif char == "\x0c":
                    keys.append("CLEAR")
                elif char == "\x1b":
                    keys.append("ESC")
                elif char.isprintable():
                    keys.append(char)
        return [key for key in keys if key]

    def close(self):
        if self.enabled:
            sys.stdout.write("\x1b[0m\x1b[2J\x1b[H\x1b[?25h\n")
            sys.stdout.flush()
        if self.raw_fd is not None and self.raw_saved is not None:
            import termios
            termios.tcsetattr(self.raw_fd, termios.TCSADRAIN, self.raw_saved)  # type: ignore[attr-defined]
        self.raw_fd = None
        self.raw_saved = None

    def draw(self, app):
        if not self.enabled:
            return
        size = shutil.get_terminal_size((100, 30))
        width = max(60, min(size.columns, 180))
        height = max(20, min(size.lines, 60))
        top_h = 12
        bottom_h = height - top_h - 3
        title = " GRANDORGUE KEYLAB CONSOLE "
        version = f" v{__version__.split()[0]} "
        left_title = f" {version.strip()} "
        right_title = f" {time.strftime('%Y-%m-%d %H:%M:%S')} "
        header_fill = max(1, width - len(title) - len(left_title) - len(right_title))
        lines = [self.fit(app.t("title") + "-" * header_fill + left_title + right_title, width)]
        keybar = (f"{app.message} | [F1] {app.t('help')}  [F2] {app.t('debug')}  "
                  f"[F3] {app.t('reconnect')}  [F4] {app.t('recover')}  [F5] {app.t('restart')}  "
                  f"[F8] {app.t('resync')}  [F9] {app.t('clear')}  [F10] {app.t('quit')}")
        lines.append(self.fit(keybar, width))
        lines.extend(self.side_by_side(app.t("midi_links"), app.connection_rows(), app.t("grandorgue"), app.organ_rows(), width, top_h))
        if self.help:
            help_rows = app.help_rows()[self.help_scroll:]
            lines.extend(self.side_by_side(app.t("help"), help_rows, app.t("current_action"), app.help_rows()[-1:], width, bottom_h))
        else:
            lines.extend(self.side_by_side(app.t("registration"), app.registration_rows(), app.t("events"), app.event_rows(bottom_h - 2), width, bottom_h))
        command = self.command or app.t("command_prompt")
        prompt = f" :{self.fit(command, max(0, width - 3))}"
        lines.append(prompt[:width].ljust(width))
        screen = "\x1b[2J\x1b[H" + "\n".join(lines) + "\x1b[?25l"
        cursor_column = min(width, len(prompt) + self.cursor + 1)
        screen += f"\x1b[{height};{cursor_column}H\x1b[?25h"
        sys.stdout.write(screen)
        sys.stdout.flush()


class TextualConsoleUI:
    """Textual dashboard with the legacy console as a compatibility fallback."""

    def __init__(self, enabled=True):
        self.enabled = bool(enabled and sys.stdin.isatty() and sys.stdout.isatty())
        self.command = ""
        self.cursor = 0
        self.help = False
        self.help_scroll = 0
        self._events = queue.Queue()
        self._thread = None
        self._textual_app = None

    def start(self, bridge):
        if not self.enabled:
            return
        try:
            from textual.app import App, ComposeResult
            from textual.color import Color
            from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
            from textual.widgets import Footer, Header, Input, Static
        except ImportError as exc:
            self.enabled = False
            print(f"Textual UI unavailable ({exc}); using simple console.", file=sys.stderr)
            return

        ui = self

        _p = THEME_PALETTES

        class Dashboard(App):
            CSS = f"""
            Screen {{ background: {_p['light']['background']}; color: {_p['light']['text']}; }}
            Screen.theme-light {{ background: {_p['light']['background']}; color: {_p['light']['text']}; }}
            Screen.theme-dark {{ background: {_p['dark']['background']}; color: {_p['dark']['text']}; }}
            Screen.theme-contrast {{ background: {_p['contrast']['background']}; color: {_p['contrast']['text']}; }}

            Header {{ background: {_p['light']['surface']}; color: {_p['light']['accent']}; }}
            Footer {{ background: {_p['light']['surface']}; color: {_p['light']['text']}; }}
            Screen.theme-light Header, Screen.theme-light Footer {{ background: {_p['light']['surface']}; color: {_p['light']['accent']}; }}
            Screen.theme-dark Header, Screen.theme-dark Footer {{ background: {_p['dark']['surface']}; color: {_p['dark']['accent']}; }}
            Screen.theme-contrast Header, Screen.theme-contrast Footer {{ background: {_p['contrast']['surface']}; color: {_p['contrast']['text']}; }}

            #lcd, #bank, #status {{
                border: round {_p['light']['border']};
                padding: 0 1;
                overflow-y: auto;
            }}
            Screen.theme-dark #lcd, Screen.theme-dark #bank, Screen.theme-dark #status {{ border: round {_p['dark']['border']}; }}
            Screen.theme-contrast #lcd, Screen.theme-contrast #bank, Screen.theme-contrast #status {{ border: round {_p['contrast']['border']}; }}

            #main {{ height: 1fr; }}
            #hardware {{ width: 1fr; padding: 0 1; }}
            #debug-panels {{ display: none; height: 1fr; }}
            #debug-panels.debug-visible {{ display: block; }}
            #links, #organ, #registration, #events {{
                border: round {_p['light']['border']};
                padding: 0 1;
                overflow-y: auto;
            }}
            Screen.theme-dark #links, Screen.theme-dark #organ, Screen.theme-dark #registration, Screen.theme-dark #events {{
                border: round {_p['dark']['border']};
            }}
            Screen.theme-contrast #links, Screen.theme-contrast #organ, Screen.theme-contrast #registration, Screen.theme-contrast #events {{
                border: round {_p['contrast']['border']};
            }}
            #links, #organ {{ width: 1fr; }}
            #registration {{ width: 1.2fr; }}
            #events {{ width: 1fr; }}

            #lcd {{
                height: 7;
                background: {_p['light']['surface']};
                color: {_p['light']['text']};
                text-style: bold;
                content-align: center middle;
            }}
            Screen.theme-light #lcd {{ background: {_p['light']['surface']}; color: {_p['light']['text']}; }}
            Screen.theme-dark #lcd {{ background: {_p['dark']['surface']}; color: {_p['dark']['text']}; }}
            Screen.theme-contrast #lcd {{ background: {_p['contrast']['surface']}; color: {_p['contrast']['text']}; }}

            #bank {{ height: 4; color: {_p['light']['accent']}; }}
            Screen.theme-dark #bank {{ color: {_p['dark']['accent']}; }}
            Screen.theme-contrast #bank {{ color: {_p['contrast']['text']}; }}

            #status {{ height: 3; color: {_p['light']['text']}; }}
            Screen.theme-dark #status {{ color: {_p['dark']['text']}; }}
            Screen.theme-contrast #status {{ color: {_p['contrast']['text']}; }}

            #pads {{
                height: 1fr;
                grid-size: 4 2;
                grid-gutter: 1;
                padding: 1 0;
            }}
            .pad {{
                border: round {_p['light']['border']};
                content-align: center middle;
                text-align: center;
                min-height: 5;
            }}
            Screen.theme-dark .pad {{ border: round {_p['dark']['border']}; }}
            Screen.theme-contrast .pad {{ border: round {_p['contrast']['border']}; }}
            #command {{ margin: 1 1 0 1; border: round {_p['light']['accent']}; }}
            Screen.theme-dark #command {{ border: round {_p['dark']['accent']}; }}
            Screen.theme-contrast #command {{ border: round {_p['contrast']['accent']}; }}
            """
            BINDINGS = [
                ("f1", "toggle_help", bridge.t("help")),
                ("f2", "debug", bridge.t("debug")),
                ("f3", "reconnect", bridge.t("reconnect")),
                ("f4", "recover", bridge.t("recover")),
                ("f5", "restart", bridge.t("restart")),
                ("f6", "toggle_control_nav", "", False),
                ("ctrl+left", "menu_left", "", False),
                ("ctrl+right", "menu_right", "", False),
                ("ctrl+up", "menu_up", "", False),
                ("ctrl+down", "menu_down", "", False),
                ("f8", "resync", bridge.t("resync")),
                ("f9", "clear", bridge.t("clear")),
                ("f10", "exit_bridge", bridge.t("quit")),
            ]

            def compose(self) -> ComposeResult:
                yield Header(show_clock=True)
                with Horizontal(id="main"):
                    with Vertical(id="hardware"):
                        yield Static(id="lcd")
                        yield Static(id="bank")
                        with Grid(id="pads"):
                            for index in range(8):
                                yield Static(id=f"pad{index + 1}", classes="pad")
                with Horizontal(id="debug-panels"):
                    yield Static(id="links")
                    yield Static(id="organ")
                    yield VerticalScroll(Static(id="registration"))
                    yield VerticalScroll(Static(id="events"))
                yield Static(id="status")
                yield Input(placeholder=bridge.t("command_placeholder"), id="command")
                yield Footer()

            def on_mount(self):
                self.set_interval(0.2, self.refresh_dashboard)
                self.query_one("#command", Input).focus()
                self.apply_theme()
                self.refresh_dashboard()

            def apply_theme(self):
                for theme_name in ("light", "dark", "contrast"):
                    self.screen.remove_class(f"theme-{theme_name}")
                self.screen.add_class(f"theme-{bridge.theme}")

            def refresh_dashboard(self):
                if not self.screen.has_class(f"theme-{bridge.theme}"):
                    self.apply_theme()
                debug_panels = self.query_one("#debug-panels")
                debug_panels.set_class(bridge.debug, "debug-visible")
                if bridge.debug:
                    self.query_one("#links", Static).update("\n".join(bridge.connection_rows()))
                    self.query_one("#organ", Static).update("\n".join(bridge.organ_rows()))
                    self.query_one("#registration", Static).update("\n".join(bridge.registration_rows()))
                    self.query_one("#events", Static).update("\n".join(bridge.event_rows(14)))
                br = bridge.br
                lcd_line1, lcd_line2 = br._idle_lines()
                if br.detail_pending:
                    lcd_line1, lcd_line2, _ = br.detail_pending
                palette = THEME_PALETTES[bridge.theme]
                self.query_one("#lcd", Static).update(
                    f"[bold {palette['accent']}]{bridge.t('lcd')}[/]\n\n"
                    f"[bold {palette['text']}]{lcd_line1[:16].ljust(16)}[/]\n"
                    f"[bold {palette['text']}]{lcd_line2[:16].ljust(16)}[/]"
                )
                bank = BANKS[br.bank]
                bank_buttons = []
                for index, candidate in enumerate(BANKS):
                    marker = f"[bold {palette['accent']}]" if index == br.bank else f"[{palette['muted']}]"
                    bank_buttons.append(f"{marker}{candidate['code']} {candidate['division']}[/]")
                self.query_one("#bank", Static).update(
                    f"[bold {palette['accent']}]{bridge.t('bank_switch')}[/]  [{palette['muted']}]<[/] "
                    f"{'  |  '.join(bank_buttons)} [{palette['muted']}]>[/]\n"
                    f"{bridge.t('active')}: [bold {palette['text']}]{bank['code']} {bank['division']}[/]  "
                    f"{bridge.t('marks')}: {br._bank_marks()}\n{bridge.t('gui_marks_legend')}"
                )
                for index in range(8):
                    widget = self.query_one(f"#pad{index + 1}", Static)
                    if index >= len(bank["items"]):          # nothing assigned: plain grey tile, no text
                        widget.update("")
                        widget.styles.background = Color.parse(UNASSIGNED_PAD_COLOR)
                        widget.styles.color = Color.parse(contrast_text(UNASSIGNED_PAD_COLOR))
                        continue
                    item = bank["items"][index]
                    active = bool(br.state.get(item.cc))
                    color = pad_screen_color(item, br.pad_colors, active, br.pad_dim, br.pad_off_grey)
                    foreground = contrast_text(color)
                    lines = bridge.pad_lines(index + 1, item, active)
                    widget.update("\n".join(f"[bold {foreground}]{escape(line)}[/]" for line in lines))
                    widget.styles.background = Color.parse(color)
                    widget.styles.color = Color.parse(foreground)
                self.query_one("#status", Static).update(bridge.status_row())
                self.title = f"{bridge.t('title')} | {bridge.message}"

            def on_input_submitted(self, event: Input.Submitted):
                ui._events.put(f"COMMAND:{event.value}")
                event.input.value = ""

            def action_toggle_help(self):
                ui._events.put("F1")

            def action_debug(self):
                ui._events.put("F2")

            def action_reconnect(self):
                ui._events.put("F3")

            def action_recover(self):
                ui._events.put("F4")

            def action_restart(self):
                ui._events.put("F5")

            def action_toggle_control_nav(self):
                ui._events.put("F6")

            def action_menu_left(self):
                ui._events.put("LEFT")

            def action_menu_right(self):
                ui._events.put("RIGHT")

            def action_menu_up(self):
                ui._events.put("UP")

            def action_menu_down(self):
                ui._events.put("DOWN")

            def action_resync(self):
                ui._events.put("F8")

            def action_clear(self):
                ui._events.put("F9")

            def action_exit_bridge(self):
                ui._events.put("F10")

        dashboard = Dashboard()
        self._textual_app = dashboard

        def run_dashboard():
            try:
                dashboard.run()
            except Exception as exc:
                self.enabled = False
                print(f"Textual UI stopped ({exc}); use --ui simple to continue.", file=sys.stderr)

        self._thread = threading.Thread(target=run_dashboard, name="textual-ui", daemon=True)
        self._thread.start()

    def read_keys(self):
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def draw(self, app):
        return

    def close(self):
        if self._textual_app is not None and self._thread is not None and self._thread.is_alive():
            self._textual_app.exit()
            self._thread.join(timeout=2.0)


def create_console_ui(mode):
    if mode == "none":
        return ConsoleUI(False)
    if mode == "simple":
        return ConsoleUI(True)
    try:
        import textual  # noqa: F401
    except ImportError as exc:
        print(f"Textual UI unavailable ({exc}); using simple console.", file=sys.stderr)
        return ConsoleUI(True)
    ui = TextualConsoleUI(True)
    return ui if ui.enabled else ConsoleUI(True)

