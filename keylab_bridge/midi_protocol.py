"""KeyLab and GrandOrgue MIDI protocol and bridge state."""

import itertools
from collections.abc import Callable

from .organ_layout import BANKS, BANK_SIZE, ITEMS, ITEM_BY_CC, ITEM_BY_WIRE
from .stop_grid import StopGridModel


CMD_CH, STOP_CH, FB_CH = 15, 14, 13          # mido channels are 0-based: 16, 15, 14


CMD = dict(prev_step=1, next_step=2, prev_file=3, next_file=4, load=5, save=6,
           metro=7, play=8, stop=9, pause=10, panic=11, tempo_up=12, tempo_down=13)  # CC on ch 16


FB = dict(load_lit=1, play_lit=2, pause_lit=3, metro_lit=4)          # GrandOrgue -> bridge, CC on ch 14


CMD_PATHS = {                                                        # GrandOrgue MIDI object paths
    "prev_step": "Sequencer/Prev", "next_step": "Sequencer/Next",
    "prev_file": "Sequencer/PrevFile", "next_file": "Sequencer/NextFile",
    "load": "Sequencer/LoadFile", "save": "Sequencer/SaveFile",
    "metro": "Metronome/MetronomeOn",
    "tempo_up": "Metronome/MetronomeBpmP1", "tempo_down": "Metronome/MetronomeBpmM1",
    "play": "MidiPlayer/MidiPlayerPlay", "stop": "MidiPlayer/MidiPlayerStop",
    "pause": "MidiPlayer/MidiPlayerPause", "panic": "Setter/PanicButton",
}


FB_PATHS = {"load_lit": "Sequencer/LoadFile", "play_lit": "MidiPlayer/MidiPlayerPlay",
            "pause_lit": "MidiPlayer/MidiPlayerPause", "metro_lit": "Metronome/MetronomeOn"}


VOL_CH = 11                                   # 0-based -> channel 12: volume levels, bridge -> GrandOrgue


VOLS = {   # key: (CC on ch 12, GrandOrgue object path, LCD name)
    "master": (1, "volumes/Master", "Master volume"),
    "pedal": (2, "volumes/Windchest001", "Pedal volume"),
    "hw": (3, "volumes/Windchest002", "Hauptwerk vol."),
    "sw": (4, "volumes/Windchest003", "Schwellwerk vol."),
    "sl": (5, "volumes/Windchest004", "Solowerk vol."),
    "noises": (6, "volumes/Windchest005", "Noises volume"),
    "swell": (7, "enclosures/001", "Swell (Schwellw.)"),
}


def volume_specs_for_profile(profile):
    specs = {"master": (1, "volumes/Master", "Master volume")}
    used = {"master"}
    aliases = (
        ("pedal", ("pedal",)), ("hw", ("hauptwerk", "manual 1")),
        ("sw", ("schwellwerk", "swell")), ("sl", ("solo", "solowerk")),
        ("noises", ("noise",)),
    )
    windchests = sorted(profile.get("windchests", []), key=lambda item: item["number"])
    for index, windchest in enumerate(windchests, 1):
        name = str(windchest.get("name") or f"Windchest {index}")
        folded = name.casefold()
        key = next((alias for alias, needles in aliases if any(needle in folded for needle in needles)),
                   f"windchest_{index:03d}")
        if key in used:
            key = f"windchest_{index:03d}"
        used.add(key)
        number = int(windchest["number"])
        specs[key] = (index + 1, f"volumes/Windchest{number:03d}", name[:LINE_WIDTH])
    for enclosure in sorted(profile.get("enclosures", []), key=lambda item: item["number"]):
        number = int(enclosure["number"])
        name = str(enclosure.get("name") or f"Enclosure {number}")
        key = "swell" if "swell" in name.casefold() or "schwell" in name.casefold() else f"enclosure_{number:03d}"
        if key in used:
            key = f"enclosure_{number:03d}"
        used.add(key)
        specs[key] = (len(windchests) + number + 1, f"enclosures/{number:03d}", name[:LINE_WIDTH])
    return specs


def pad_colors_for_spec(spec, overrides=None):
    palette = ((127, 0, 0), (0, 96, 127), (0, 127, 40), (127, 84, 0),
               (92, 0, 127), (0, 127, 105), (127, 0, 64), (86, 127, 0))
    colors = {**DEFAULT_PAD_COLORS, **(overrides or {})}
    used = {colors[str(division["code"])] for division in spec.get("divisions", [])
            if str(division["code"]) in colors}
    for index, division in enumerate(spec.get("divisions", [])):
        code = str(division["code"])
        if code not in colors:
            color = next((candidate for candidate in palette if candidate not in used), palette[index % len(palette)])
            colors[code] = color
            used.add(color)
    colors.setdefault("C", (100, 0, 127))
    return colors


ENCODER_VOLS = {0: "pedal", 1: "hw", 2: "sw", 3: "sl", 4: "swell"}    # encoders 1-5


POSITION_LABEL_PATH = "Sequencer/sequencer position"   # sends the step number as a HWString, key 2


FILENAME_LABEL_KEY, POSITION_LABEL_KEY = 1, 2


KEYLAB_HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]


LINE_WIDTH = 16


TEXT_WIDTH = 13            # 2 status characters + 1 spacer + 13 text characters


MIN_INTERVAL_S = 0.04      # default gap between LCD writes; the KeyLab LCD can lock up if flooded (--live to change)


LED_IDS = {"loop": 90, "metro": 89, "play": 94, "cat_char": 22}   # cat_char: sysex id from go_interface.yaml, UNVERIFIED on hardware


# This unit's pad LEDs take their three values in blue, green, red order (red and blue appeared swapped on
# the hardware, green was right), so the screen RGB is reversed on the wire. Use (0, 1, 2) if yours are R, G, B.
PAD_LED_ORDER = (2, 1, 0)
PAD_LED_BASE = [32, 35, 38, 41, 44, 47, 50, 53]      # first of 3 LEDs (R, G, B) of each pad; pads 1-4 top row, 5-8 bottom row


DEFAULT_PAD_CCS = list(range(0x24, 0x2C))              # CC sent by pads 1-8 - check with --learn-pads


DEFAULT_PAD_COLORS = {
    "P": (127, 0, 0), "P1": (48, 0, 0), "P2": (127, 0, 0),
    "H": (0, 127, 0), "H1": (0, 48, 0), "H2": (0, 127, 0),
    "S": (0, 0, 127), "S1": (0, 0, 48), "S2": (0, 0, 88), "S3": (0, 0, 127),
    "L": (127, 0, 0), "C": (100, 0, 127),
}


PAD_LED_GAP_S = 0.015


N_REWIND, N_FORWARD, N_STOP, N_PLAY, N_LOOP, N_METRO, N_SAVE = 0x5B, 0x5C, 0x5D, 0x5E, 0x56, 0x59, 0x50


N_NAV_LEFT, N_NAV_RIGHT = 0x62, 0x63


N_NEXT_BANK, N_PREV_BANK = (0x31, 0x2F), (0x30, 0x2E)


N_JOG_PRESS = 0x54          # pressing the jog knob (seen once in the sniffer capture)


N_CAT_CHAR, N_PRESET = 0x65, 0x64   # Cat/Char toggles menu navigation; Preset toggles stop-grid mode in the GUI


# Hardware menu pages. Index order MUST match the GUI's `main_tabs` order in qt_gui.py.
# Page 0 is the normal live view: "menu off" is simply page 0.
MENU_PAGES = (
    {"id": "live", "name": "Live / Main", "abbr": "Live"},
    {"id": "setter", "name": "Setter Editing", "abbr": "Setter Edit"},
    {"id": "files", "name": "Combination Files", "abbr": "Comb Files"},
    {"id": "couplings", "name": "Couplings", "abbr": "Couplings"},
    {"id": "system", "name": "System Console", "abbr": "Sys Console"},
    {"id": "config", "name": "Config", "abbr": "Config"},
    {"id": "organ", "name": "Organ Selection", "abbr": "Organ Select"},
)


CC_JOG, CC_SUSTAIN = 0x3C, 0x40


PLAYER_START_CONFIRM_S = 0.5


def ascii_clean(text):
    fold: dict[str, str] = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e", "ê": "e", "à": "a",
            "â": "a", "ç": "c", "î": "i", "ô": "o", "û": "u", "Ä": "A", "Ö": "O", "Ü": "U", "É": "E"}
    out = "".join(fold[c] if c in fold else c for c in text)
    return "".join(c if 32 <= ord(c) < 127 else " " for c in out)


def split_lines(text, width):
    text = " ".join(ascii_clean(text).split())
    if len(text) <= width:
        return text, ""
    cut = text.rfind(" ", 0, width + 1)
    if cut <= 0:
        cut = width
    return text[:cut].strip(), text[cut:].strip()[:width]


def parse_go_sysex(data):
    """GrandOrgue label sysex (without F0/F7) -> (key, text) or None."""
    d = list(data)
    if len(d) >= 6 and d[0] == 0x7D and d[1] == 0x01:      # Hauptwerk 32 byte LCD
        return (d[2] << 7) | d[3], "".join(chr(b & 0x7F) for b in d[5:37]).strip()
    if len(d) >= 3 and d[0] == 0x7D and d[1] == 0x19:      # Hauptwerk 16 byte string
        return d[2], "".join(chr(b & 0x7F) for b in d[3:19]).strip()
    return None


def lcd_data(line1, line2):
    body = [0x04, 0x00, 0x60, 0x01]
    body += [ord(c) for c in ascii_clean(line1).ljust(LINE_WIDTH)[:LINE_WIDTH]] + [0x00, 0x02]
    body += [ord(c) for c in ascii_clean(line2).ljust(LINE_WIDTH)[:LINE_WIDTH]] + [0x00, 0x7F]
    return KEYLAB_HEADER + body


def led_data(led_id, value):
    return KEYLAB_HEADER + [0x02, 0x00, 0x10, led_id, value]


def pad_color_key(item, colors):
    if item.kind in ("coupler", "tremulant"):
        return "C"
    return item.bank_code if item.bank_code in colors else item.bank_code[0]


def pad_rgb(item, colors, active, dim, off_grey=0):
    """Return the exact 7-bit RGB values sent to the KeyLab for one pad. An off pad shows its colour at `dim`
    brightness, but never less than a low neutral grey of `off_grey` (0 = no grey, the LED may go fully dark)."""
    key = pad_color_key(item, colors)
    factor = 1.0 if active else max(0.0, min(1.0, dim))
    rgb = [max(0, min(127, round(channel * factor))) for channel in colors[key]]
    if not active and off_grey:
        grey = max(0, min(127, int(off_grey)))
        rgb = [max(channel, grey) for channel in rgb]
    return tuple(rgb)


UNASSIGNED_PAD_COLOR = "#9aa0a8"          # screen colour of a pad with nothing assigned (no text is drawn on it)


def pad_screen_color(item, colors, active, dim, off_grey=0):
    """Screen colour of a pad tile. The hardware LEDs are very non-linear, so a faint LED grey would look black
    on a monitor; the tile uses a visible dark grey that grows with `off_grey`."""
    color = screen_rgb(pad_rgb(item, colors, active, dim, 0))
    if active or not off_grey:
        return color
    level = min(200, 40 + int(off_grey) * 6)
    channels = [max(int(color[i:i + 2], 16), level) for i in (1, 3, 5)]
    return "#" + "".join(f"{c:02x}" for c in channels)


def screen_rgb(led_rgb):
    """Render 7-bit KeyLab LED values as the equivalent 8-bit screen color."""
    channels = (round(channel * 255 / 127) for channel in led_rgb)
    return "#" + "".join(f"{channel:02x}" for channel in channels)


class Bridge:
    """All behaviour, no MIDI library needed (testable offline).  Methods return a list of
    outputs: {"to": "go", "ch", "cc", "val"} | {"to": "lcd", "data"} | {"to": "led", "data"}."""

    def __init__(self, threshold=64, settle_s=0.10, live_s=MIN_INTERVAL_S, hold_s=1.0, loop_restart_s=0.4, refresh_s=2.0,
                 encoder_step=2, volume_start=100, encoder_vols=None, jog_max=8,
                 pad_ccs=None, pad_dim=0.10, pad_colors=None, pads_enabled=True, pad_shared_window=0.7, led_refresh_s=2.0, tremulant_encoders=None,
                 pad_verbosity=2, pad_off_grey=0, note_pads=True, note_pad_channel=10, note_pad_first=36,
                 ch1_aftertouch_pads=False, pad_trace=False, daw_trace=False):
        self.threshold, self.settle_s, self.live_s, self.hold_s = threshold, settle_s, live_s, hold_s
        self.refresh_s, self.last_idle = refresh_s, 0.0
        self.min_interval = live_s
        self.fader_pos = [None] * BANK_SIZE   # last position seen on each physical fader
        self.loop_restart_s = loop_restart_s
        self.text, self.pos, self.cued = "", "", False
        self.bank = 0
        self.stop_grid = StopGridModel(ITEMS)
        self.stop_grid_ui_enabled = False
        self.stop_grid_mode = False
        self.stop_grid_context = "live"
        self.stop_grid_draft_paths = set()
        self.stop_grid_pad_handler: Callable[[str], None] | None = None
        self.menu_tab = 0                     # index into MENU_PAGES; 0 = Live / Main
        self.menu_override = False            # Cat/Char toggle: jog focus navigation within the active tab
        self.menu_focus = ""                  # text of the GUI's jog-focused control, shown on LCD line 2
        self.cat_led_enabled = True           # SysEx ID 22 from go_interface.yaml; physical behavior still needs verification
        self.state = {}                       # cc -> bool, stop/coupler/tremulant state
        self.last_sent = {}                   # cc -> (state, time) of the last stop command sent
        self.encoder_step, self.jog_max = encoder_step, jog_max
        self.volume_start = volume_start
        self.trem_encoders = dict({6: 1, 7: 2} if tremulant_encoders is None else tremulant_encoders)   # encoder index -> tremulant number
        self.encoder_vols = dict(ENCODER_VOLS if encoder_vols is None else encoder_vols)
        self.vol = {k: volume_start for k in VOLS}   # last volume value sent per level (0-127)
        self.vol_sent = {}
        self.loop = False
        self.player, self.user_stopped = "stopped", False
        self.sequence_mode = False
        self.play_start_pending_until = None
        self.pending_sequence_steps = 0
        self.play_lit = self.pause_lit = self.metro_lit = False
        self.dirty = True
        self.last_activity = None
        self.last_kl = 0.0                    # time of the last message of any kind to the keyboard
        self.last_lcd = 0.0                   # time of the last LCD write (LED bursts must not starve the LCD)
        self.detail_pending, self.detail_until, self.last_detail = None, 0.0, 0.0
        self.scheduled = []                   # (due, outputs)
        self.leds_sent = {}
        self.pads_enabled, self.pad_dim = pads_enabled, pad_dim
        self.pad_verbosity, self.pad_off_grey = max(1, min(3, int(pad_verbosity))), max(0, min(127, int(pad_off_grey)))
        # Pads can arrive in more than one form depending on the keyboard's (unstable) mode state: CCs on channel 1
        # (the DAW-mode baseline), notes 36-43 on channel 10 (after a reset / User maps), or, as a last resort,
        # notes 36-43 on channel 1 told apart from keys only by poly aftertouch. See the testing: section of config.yaml.
        self.note_pads, self.note_pad_channel = bool(note_pads), max(1, min(16, int(note_pad_channel))) - 1
        self.note_pad_first = int(note_pad_first)
        self.ch1_aftertouch_pads, self.pad_trace = bool(ch1_aftertouch_pads), bool(pad_trace)
        self.daw_trace = bool(daw_trace)
        self.hui_seen = False
        self.go_state_changed_at = 0.0
        self.map_number = None                # last "F0 00 20 6B 7F 42 05 nn F7" seen on MAIN
        self.trace_sink: Callable[[str], None] | None = None
        self._aftertouch_press = {}           # note -> time of the last aftertouch-triggered pad press
        self.metro_held = False
        self.metro_adjusted = False
        self.metro_target = None
        self.metro_bpm = ""
        self.pad_ccs = list(pad_ccs or DEFAULT_PAD_CCS)
        self.custom_pad_colors = dict(pad_colors or {})
        self.pad_colors = {**DEFAULT_PAD_COLORS, **(pad_colors or {})}
        # In DAW mode pad 4 (a toggle: it sends only "down" on one press and only "up" on the next) and pad 5 (momentary:
        # down then up within a moment) both send the same CC. Told apart by whether a release follows quickly.
        self.shared_window, self.shared_down = pad_shared_window, None
        self.shared_cc, self.shared_pads = None, None
        self.led_refresh_s, self.next_led_refresh = led_refresh_s, 0.0   # the keyboard forgets pad colours: re-send them regularly
        self.refresh_queue, self.led_invalidations = [], []
        for c in dict.fromkeys(self.pad_ccs):
            idx = [i for i, x in enumerate(self.pad_ccs) if x == c]
            if len(idx) == 2:
                self.shared_cc, self.shared_pads = c, (idx[0], idx[1])
                break

    def configure_organ_controls(self, profile, spec):
        global VOLS

        previous_values = self.vol
        volume_specs = volume_specs_for_profile(profile)
        VOLS.clear()
        VOLS.update(volume_specs)
        self.vol = {key: previous_values.get(key, self.volume_start) for key in VOLS}
        self.vol_sent = {key: value for key, value in self.vol_sent.items() if key in VOLS}

        encoder_vols = {index: key for index, key in self.encoder_vols.items() if key in VOLS}
        occupied = set(encoder_vols)
        free_indices = [index for index in range(7) if index not in occupied]
        for key in VOLS:
            if key == "master" or key in encoder_vols.values() or not free_indices:
                continue
            encoder_vols[free_indices.pop(0)] = key
        self.encoder_vols = encoder_vols
        tremulant_numbers = {int(item["number"]) for item in profile.get("tremulants", [])}
        self.trem_encoders = {
            index: number for index, number in self.trem_encoders.items()
            if index not in encoder_vols and number in tremulant_numbers
        }
        self.pad_colors = pad_colors_for_spec(spec, self.custom_pad_colors)
        self.dirty = True

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _cc(ch, cc, val):
        return {"to": "go", "ch": ch, "cc": cc, "val": val}

    def _press(self, name):
        return [self._cc(CMD_CH, CMD[name], 127), self._cc(CMD_CH, CMD[name], 0)]

    def begin_metro_hold(self, now):
        self.metro_held = True
        self.metro_adjusted = False
        self._button_event(now)

    def end_metro_hold(self, now):
        if not self.metro_held:
            return []
        self.metro_held = False
        if self.metro_adjusted:
            return []
        self._button_event(now)
        return self.toggle_metro()

    def toggle_metro(self):
        current = self.metro_lit if self.metro_target is None else self.metro_target
        self.metro_target = not current
        return [self._cc(CMD_CH, CMD["metro"], 127 if self.metro_target else 0)]

    def adjust_metro(self, direction):
        if not self.metro_held:
            return []
        self.metro_adjusted = True
        name = "tempo_up" if direction > 0 else "tempo_down"
        return self._press(name)

    def _detail(self, l1, l2="", hold=None):
        """Show this on the LCD, then go back to normal after `hold` seconds (default --hold)."""
        self.detail_pending = (l1, l2, hold)

    def _bank_items(self):
        return BANKS[self.bank]["items"]

    def stop_grid_move_horizontal(self, direction):
        changed = self.stop_grid.move_horizontal(direction)
        if changed:
            self.dirty = True
        return changed

    def stop_grid_move_vertical(self, direction):
        changed = self.stop_grid.move_vertical(direction)
        if changed:
            self.dirty = True
        return changed

    @property
    def menu_shows(self):
        """The LCD shows the menu header whenever the override is on or a non-Live tab is open."""
        return self.menu_override or self.menu_tab != 0

    def set_menu_tab(self, index):
        index = int(index)
        if not 0 <= index < len(MENU_PAGES) or index == self.menu_tab:
            return
        self.menu_tab = index
        self.menu_focus = ""
        self.dirty = True

    def set_menu_focus(self, text):
        text = str(text)
        if text != self.menu_focus:
            self.menu_focus = text
            self.dirty = True

    def step_menu_tab(self, direction):
        """Nav Left/Right: previous/next tab, wrapping."""
        self.set_menu_tab((self.menu_tab + direction) % len(MENU_PAGES))

    def toggle_menu_override(self):
        """Cat/Char: plain on/off. On = arrows always change tab and jog always walks controls."""
        self.menu_override = not self.menu_override
        self.menu_focus = ""
        self.dirty = True

    def toggle_cc(self, cc, now):
        """Toggle one stop/coupler/tremulant by CC number (GUI Couplings tab), independent of the bank."""
        it = ITEM_BY_CC.get(cc)
        if it is None:
            return []
        new = not bool(self.state.get(it.cc))
        self.state[it.cc] = new
        self.last_sent[it.cc] = (new, now)
        self.last_activity = now
        self._detail(it.name, "ON" if new else "off")
        return [self._cc(it.channel, it.key, 127 if new else 0)]

    def _change_bank(self, step):
        self.bank = (self.bank + step) % len(BANKS)
        b = BANKS[self.bank]
        self._detail(f"{b['code']} {b['division']}", self._bank_marks(), hold=2.5)
        self.dirty = True

    def _bank_marks(self):
        """One mark per fader: # on and fader up, . off and fader down, ^ stop on but fader down
        (raise it), v stop off but fader up (lower it), ? fader position not seen yet."""
        marks = []
        for i, it in enumerate(self._bank_items()[:BANK_SIZE]):   # the coupler bank can hold more than 8 items
            pos, on = self.fader_pos[i], bool(self.state.get(it.cc))
            if pos is None:
                marks.append("?")
                continue
            up = pos >= self.threshold - 2
            marks.append("#" if on and up else "." if not on and not up else "^" if on else "v")
        return " ".join(marks)

    def _button_event(self, now):
        self.last_activity, self.detail_until, self.dirty = now, 0.0, True   # cancel any detail: show status at once

    @staticmethod
    def _bar(value, width=10):
        n = round(value * width / 127)
        return "#" * n + "." * (width - n) + f" {round(value * 100 / 127):3d}%"

    def _set_volume(self, key, value):
        value = max(0, min(127, value))
        self.vol[key] = value
        self.vol_sent[key] = value
        cc, _path, name = VOLS[key]
        self._detail(name, self._bar(value))
        return [self._cc(VOL_CH, cc, value)]

    # ---------------------------------------------------------------- KeyLab DAW port
    def from_daw(self, msg, now):
        out = []
        t = msg.type
        if t in ("note_off", "note_on") and msg.channel == 0 and msg.note == N_METRO:
            if t == "note_on" and msg.velocity > 0:
                self.begin_metro_hold(now)
                return out
            return self.end_metro_hold(now)
        if t == "note_on" and msg.velocity > 0 and msg.channel == 0:
            n = msg.note
            self._button_event(now)
            if n == N_REWIND:
                out += self._press("prev_step")
            elif n == N_FORWARD:
                out += self._press("next_step")
            elif n == N_JOG_PRESS:                   # load the cued file
                out += self._press("load")
            elif n == N_SAVE:
                out += self._press("save")
                self._detail("Save file", "sent")
            elif n == N_METRO:
                self.begin_metro_hold(now)
            elif n == N_PLAY:
                if self.sequence_mode:
                    self.player = "paused" if self.player == "playing" else "playing"
                elif self.player == "stopped":
                    out += self._press("play")
                    self.player, self.user_stopped = "playing", False
                    self.play_start_pending_until = now + PLAYER_START_CONFIRM_S
                elif self.player == "playing":
                    out += self._press("pause")
                    self.player = "paused"
                else:
                    out += self._press("pause")
                    self.player = "playing"
            elif n == N_STOP:
                was = self.player
                out += self._press("stop")
                if self.sequence_mode:
                    digits = "".join(itertools.takewhile(str.isdigit, self.pos.strip()))
                    if digits:
                        for _ in range(int(digits)):
                            out += self._press("prev_step")
                out += self._press("panic")
                self.player, self.user_stopped = "stopped", True
                self.sequence_mode = False
                self.play_start_pending_until = None
                self.pending_sequence_steps = 0
                self._detail("PANIC", "player reset; all sound off" if was in ("playing", "paused") else "all sound off")
            elif n == N_LOOP:
                self.loop = not self.loop
                self._detail("Loop " + ("ON" if self.loop else "OFF"), "repeat MIDI")
        elif t == "control_change" and msg.control == CC_JOG:
            self._button_event(now)
            steps = max(1, msg.value & 0x3F)
            out += [o for _ in range(min(steps, self.jog_max)) for o in self._press("prev_file" if msg.value >= 64 else "next_file")]
        elif t == "control_change" and (0x10 <= msg.control <= 0x17 or (self.hui_seen and 0x40 <= msg.control <= 0x47)):
            n = msg.control - (0x40 if msg.control >= 0x40 else 0x10)      # HUI sends V-pots as CC 0x40-0x47, same relative coding
            self.last_activity = now
            delta = (msg.value & 0x3F) * (-1 if msg.value >= 64 else 1)
            if n in self.encoder_vols:
                key = self.encoder_vols[n]
                out += self._set_volume(key, self.vol[key] + delta * self.encoder_step)   # more when turned fast
            elif n in self.trem_encoders:                              # turn right = tremolo on, left = off
                it = next((x for x in ITEMS if x.kind == "tremulant" and x.number == self.trem_encoders[n]), None)
                if it and delta:
                    new = delta > 0
                    self.state[it.cc] = new
                    self.last_sent[it.cc] = (new, now)
                    out += [self._cc(it.channel, it.key, 127 if new else 0)]
                    self._detail(it.name, "ON" if new else "off")
            else:
                self._detail(f"Encoder {n + 1}", "not assigned")
        elif t == "pitchwheel" and msg.channel < BANK_SIZE:
            out += self._fader(msg.channel, (msg.pitch + 8192) >> 7, now)
        elif t == "pitchwheel" and msg.channel == 8:                       # master fader
            self.last_activity = now
            out += self._set_volume("master", (msg.pitch + 8192) >> 7)
        return out

    def _fader(self, n, value, now):
        """A fader that is moved takes control of its stop: on at/above the threshold, off below it.
        Faders that are not touched never change anything, so changing bank is safe."""
        self.last_activity = now
        self.fader_pos[n] = value
        items = self._bank_items()
        it = items[n] if n < len(items) else None
        out = []
        desired = True if value >= self.threshold else (False if value < self.threshold - 4 else None)
        if it and desired is not None:
            last = self.last_sent.get(it.cc)
            if last is None or last[0] != desired or now - last[1] >= 0.3:   # repeat now and then: harmless, self-healing
                self.last_sent[it.cc] = (desired, now)
                out = [self._cc(it.channel, it.key, 127 if desired else 0)]
            self.state[it.cc] = desired
        if it is None:
            self._detail(f"Fader {n + 1}", "no stop in bank")
        else:
            on = bool(self.state.get(it.cc, False))
            up = value >= self.threshold
            bar = "#" * round(value * 8 / 127) + "." * (8 - round(value * 8 / 127))
            flag = "!" if on != up else " "
            self._detail(it.name, ("ON " if on else "off") + " " + bar + " " + flag + f"{n + 1}")
        return out

    # ---------------------------------------------------------------- KeyLab main port (pads)
    def _trace(self, msg, what):
        if self.pad_trace and self.trace_sink is not None:
            channel = f"ch{msg.channel + 1}" if hasattr(msg, "channel") else "-"
            self.trace_sink(f"MAIN {what:<22} {channel:>4} {' '.join(f'{b:02X}' for b in msg.bytes())}  "
                            f"map={self.map_number if self.map_number is not None else '?'}")

    def _pad_note_index(self, note):
        index = note - self.note_pad_first
        return index if 0 <= index < 8 else None

    def _pad_via_note(self, index, now):
        self._invalidate_pads([index])
        self.led_invalidations += [(now + 0.25, [index]), (now + 1.0, [index])]
        return self._pad_press(index, now)

    def from_main(self, msg, now):
        """Handle sustain transport and pads that toggle stops in the current bank."""
        if msg.type == "sysex":
            data = list(msg.data)
            if data[:6] == [0x00, 0x20, 0x6B, 0x7F, 0x42, 0x05] and len(data) >= 7:
                self.map_number = data[6]
                self._trace(msg, f"MAP CHANGE n={data[6]} (pad state may have changed)")
            return []
        if self.pads_enabled and self.pad_trace:
            if msg.type in ("note_on", "note_off") and self._pad_note_index(msg.note) is not None:
                self._trace(msg, f"pad-range {msg.type} {msg.note}")
            elif msg.type == "polytouch" and self._pad_note_index(msg.note) is not None:
                self._trace(msg, f"pad-range aftertouch {msg.note}")
            elif msg.type == "control_change" and msg.control in self.pad_ccs:
                self._trace(msg, f"pad CC {msg.control}")
        if self.pads_enabled and self.note_pads and msg.type in ("note_on", "note_off") and msg.channel == self.note_pad_channel:
            index = self._pad_note_index(msg.note)
            if index is not None:                    # note-form pads: never confused with keys, they are on their own channel
                if msg.type == "note_on" and msg.velocity > 0:
                    return self._pad_via_note(index, now)
                return []
        if self.pads_enabled and self.ch1_aftertouch_pads and msg.type == "polytouch" and msg.channel == 0:
            index = self._pad_note_index(msg.note)
            if index is not None and now - self._aftertouch_press.get(msg.note, -9.0) > 0.5:
                self._aftertouch_press[msg.note] = now     # keys do not send aftertouch here, pads do (experimental)
                return self._pad_via_note(index, now)
        if msg.type == "control_change" and msg.control == CC_SUSTAIN:
            if msg.value < 64:
                return []
            self._button_event(now)
            if self.play_start_pending_until is not None:
                self.pending_sequence_steps += 1
                return []
            if self.sequence_mode:
                if self.player == "playing":
                    return self._press("next_step")
                if self.player == "paused":
                    return []
                self.sequence_mode = False
                self.pending_sequence_steps = 0
            return self._press("load")
        if not self.pads_enabled or msg.type != "control_change" or msg.control not in self.pad_ccs:
            return []
        touched = [i for i, c in enumerate(self.pad_ccs) if c == msg.control]
        self._invalidate_pads(touched)
        self.led_invalidations += [(now + 0.25, touched), (now + 1.0, touched)]
        shared_pads = self.shared_pads
        if self.shared_cc is not None and msg.control == self.shared_cc and shared_pads is not None:
            toggle_pad, momentary_pad = shared_pads
            if msg.value >= 64:                                   # a down: wait to see whether a release follows
                out = self._pad_press(toggle_pad, now) if self.shared_down is not None else []
                self.shared_down = now
                return out
            if self.shared_down is not None and now - self.shared_down <= self.shared_window:
                self.shared_down = None                           # down + quick release = the momentary pad
                return self._pad_press(momentary_pad, now)
            self.shared_down = None                               # release on its own = the toggle pad switching off
            return self._pad_press(toggle_pad, now)
        if msg.value < 64:
            return []
        return self._pad_press(self.pad_ccs.index(msg.control), now)

    def _invalidate_pads(self, indices):
        for i in indices:
            for j in range(3):
                self.leds_sent.pop(PAD_LED_BASE[i] + j, None)

    def _pad_press(self, n, now):
        items = self.stop_grid.mapped_slots() if self.stop_grid_mode else self._bank_items()
        if n >= len(items):
            return []
        it = items[n]
        if it is None:
            return []
        if self.stop_grid_mode and self.stop_grid_context == "draft":
            if self.stop_grid_pad_handler is not None:
                self.stop_grid_pad_handler(it.path)
            return []
        new = not bool(self.state.get(it.cc))
        self.state[it.cc] = new
        self.last_sent[it.cc] = (new, now)
        self.last_activity = now
        location = (it.division if self.stop_grid_mode else BANKS[self.bank]["code"])
        self._detail(it.name, ("ON " if new else "off") + f"{location} pad {n + 1}")
        return [self._cc(it.channel, it.key, 127 if new else 0)]

    def _desired_leds(self):
        want = {LED_IDS["loop"]: 127 if self.loop else 0, LED_IDS["metro"]: 127 if self.metro_lit else 0,
                LED_IDS["play"]: 127 if self.player == "playing" else 0}
        if self.cat_led_enabled:
            want[LED_IDS["cat_char"]] = 127 if self.menu_override else 0
        if self.pads_enabled:
            items = self.stop_grid.mapped_slots() if self.stop_grid_mode else self._bank_items()
            for i, base in enumerate(PAD_LED_BASE):
                if i < len(items) and items[i] is not None:
                    active = (items[i].path in self.stop_grid_draft_paths
                              if self.stop_grid_mode and self.stop_grid_context == "draft"
                              else bool(self.state.get(items[i].cc)))
                    rgb = pad_rgb(items[i], self.pad_colors, active, self.pad_dim, self.pad_off_grey)
                else:
                    rgb = (0, 0, 0)
                for j in range(3):
                    want[base + j] = rgb[PAD_LED_ORDER[j]]
        return want

    # ---------------------------------------------------------------- GrandOrgue feedback
    def from_go(self, msg, now):
        out = []
        if msg.type == "sysex":
            parsed = parse_go_sysex(msg.data)
            if parsed:
                key, text = parsed
                if key == FILENAME_LABEL_KEY and text:
                    self.text, self.dirty = text, True
                elif key == POSITION_LABEL_KEY:
                    self.pos, self.dirty = text, True
                elif key == 3:
                    self.metro_bpm = text
            return out
        if msg.type != "control_change":
            return out
        val = msg.value >= 64
        wired = ITEM_BY_WIRE.get((msg.channel, msg.control))
        if wired is not None:
            sent = self.last_sent.get(wired.cc)
            if self.state.get(wired.cc) != val and not (sent and now - sent[1] < 1.0):
                self.go_state_changed_at = now          # the organ is echoing a loaded combination (not our own press)
            self.state[wired.cc] = val
        elif msg.channel == FB_CH:
            c = msg.control
            if c == FB["load_lit"]:
                self.cued, self.dirty = val, True
            elif c == FB["play_lit"]:
                was, self.play_lit = self.play_lit, val
                if self.play_start_pending_until is not None:
                    return out
                if self.sequence_mode:
                    return out
                if val and not was:
                    self.player = "playing"
                    self.sequence_mode = False
                    self.play_start_pending_until = None
                    self.pending_sequence_steps = 0
                elif was and not val:
                    if self.pause_lit:
                        self.player = "paused"
                    elif self.loop and self.player == "playing" and not self.user_stopped:
                        self.scheduled.append((now + self.loop_restart_s, self._press("play")))
                    else:
                        self.player = "stopped"
            elif c == FB["pause_lit"]:
                was, self.pause_lit = self.pause_lit, val
                if self.play_start_pending_until is not None:
                    return out
                if self.sequence_mode:
                    return out
                if val and not was:
                    self.player = "paused"
                    self.sequence_mode = False
                    self.play_start_pending_until = None
                    self.pending_sequence_steps = 0
                elif was and not val and self.play_lit:
                    self.player = "playing"
            elif c == FB["metro_lit"]:
                self.metro_lit = val
                self.metro_target = val
        return out

    def resync_outputs(self):
        self.dirty = True
        self.leds_sent.clear()
        self.refresh_queue = []
        self.next_led_refresh = 0.0
        out = [self._cc(ITEM_BY_CC[cc].channel, ITEM_BY_CC[cc].key, 127 if on else 0)
               for cc, on in self.state.items() if cc in ITEM_BY_CC]
        for key, value in self.vol_sent.items():
            out.append(self._cc(VOL_CH, VOLS[key][0], value))
        return out

    # ---------------------------------------------------------------- display
    def _idle_lines(self):
        if self.menu_shows:
            page = MENU_PAGES[self.menu_tab]
            header = "Control Nav" if self.menu_override else f"{self.menu_tab}/{len(MENU_PAGES) - 1} {page['abbr']}"
            hint = self.menu_focus or ("Jog: browse" if self.menu_override else "Jog: main")
            return header[:16], ascii_clean(hint)[:16]
        code = BANKS[self.bank]["code"]
        l1, l2 = split_lines(self.text or "GrandOrgue", TEXT_WIDTH)
        step = "->" if self.cued else (self.pos[-2:].rjust(2) if self.pos else "  ")
        return f"{code:<2} {l1}", f"{step} {l2}"

    def tick(self, now):
        out = []
        if self.play_start_pending_until is not None and now >= self.play_start_pending_until:
            self.play_start_pending_until = None
            if not (self.play_lit or self.pause_lit):
                self.sequence_mode = True
                out += self._press("load")
                if self.player == "playing":
                    for _ in range(self.pending_sequence_steps):
                        out += self._press("next_step")
            self.pending_sequence_steps = 0
        if self.shared_down is not None and now - self.shared_down > self.shared_window and self.shared_pads is not None:
            self.shared_down = None                               # no release came: it was the toggle pad going on
            out += self._pad_press(self.shared_pads[0], now)
        for item in list(self.led_invalidations):
            if now >= item[0]:
                self.led_invalidations.remove(item)
                self._invalidate_pads(item[1])
        for item in list(self.scheduled):
            if now >= item[0]:
                self.scheduled.remove(item)
                out += item[1]
        act = self.last_activity
        settled = act is None or now - act >= self.settle_s
        spaced = now - self.last_lcd >= self.min_interval and now - self.last_kl >= PAD_LED_GAP_S
        if self.detail_pending and spaced and (settled or now - self.last_detail >= self.live_s):
            l1, l2, hold = self.detail_pending
            self.detail_pending, self.detail_until = None, now + (hold or self.hold_s)
            self.last_detail = self.last_kl = self.last_lcd = now
            out.append({"to": "lcd", "data": lcd_data(l1, l2)})
        elif spaced and not self.detail_pending and self.detail_until and now >= self.detail_until:
            self.detail_until, self.dirty, self.last_kl, self.last_lcd, self.last_idle = 0.0, False, now, now, now  # back to status
            out.append({"to": "lcd", "data": lcd_data(*self._idle_lines())})
        elif spaced and not self.detail_pending and not self.detail_until and settled and (
                self.dirty or (self.refresh_s and now - self.last_idle >= self.refresh_s)):
            self.dirty, self.last_kl, self.last_lcd, self.last_idle = False, now, now, now
            out.append({"to": "lcd", "data": lcd_data(*self._idle_lines())})
        elif now - self.last_kl >= PAD_LED_GAP_S:      # LEDs: one message per tick at most
            want = self._desired_leds()
            for led_id, val in want.items():           # 1. anything that differs from what was last sent
                if self.leds_sent.get(led_id) != val:
                    self.leds_sent[led_id] = val
                    self.last_kl = now
                    out.append({"to": "led", "data": led_data(led_id, val)})
                    break
            else:                                      # 2. otherwise a slow rolling refresh of every LED
                if self.led_refresh_s and not self.refresh_queue and now >= self.next_led_refresh:
                    self.refresh_queue = list(want)
                    self.next_led_refresh = now + self.led_refresh_s
                if self.refresh_queue:
                    led_id = self.refresh_queue.pop(0)
                    self.last_kl = now
                    out.append({"to": "led", "data": led_data(led_id, want[led_id])})
        return out
