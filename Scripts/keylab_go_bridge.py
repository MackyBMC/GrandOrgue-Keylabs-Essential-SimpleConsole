#!/usr/bin/env python3
"""
KeyLab Essential 61 mk2 (DAW mode)  <->  GrandOrgue bridge  (v3)

  KeyLab DAW port  --buttons/faders/jog-->  this script  --commands (CC on ch 16, stops on ch 15)-->  virtual cable --> GrandOrgue
  KeyLab LCD/LEDs  <--status/feedback----   this script  <--state feedback (ch 14, ch 15, label sysex)-- virtual cable <-- GrandOrgue

GrandOrgue keeps reading the KeyLab MAIN port directly (keys, pedal, wheels), so playing never
passes through Python.  Load Friesach-midi-settings-KeyLab.yaml in GrandOrgue (MIDI Objects > Import)
so it understands the messages below.

Controls (DAW mode)
  <<  / >>            previous / next step inside the loaded piece file (activates)
  Jog                 cue previous / next setter file (does NOT activate; Load file or your pedal does)
  Jog press           load the cued file (same as the sustain pedal)
  Part 2/Prev, Part 1/Next   previous / next fader bank (works in channel and bank mode)
  Faders 1-8          drawbars for the stops of the current bank: a fader you move sets its stop on
                      (above half travel) or off; faders you do not touch change nothing.
                      Bank overview (2.5 s after a bank change): # on/up  . off/down  ^ on but fader
                      down (raise it)  v off but fader up (lower it)  ? fader not seen yet
  Master fader        master volume;  Encoders 1-4: Pedal / Hauptwerk / Solowerk / Schwellwerk volume
  Play/Pause          GrandOrgue MIDI player;  Loop = repeat the same recording
  Stop                panic (all sound off); if a MIDI file is playing or paused it is stopped as well
  Save                setter "Save file"
  Metro               GrandOrgue metronome on/off

LCD: first two characters of each line are status (top: bank e.g. H2, bottom: step, or "->" when a
file is cued), the rest is the current file name.  Moving a fader or encoder shows its readout (stop
name and state, or volume bar) on every update while it moves (at most every --live seconds),
then the normal display returns after --hold seconds.  Encoders 1-4 = Pedal, Hauptwerk, Solowerk,
Schwellwerk volume; fader 9 = master volume.

Requires:  pip install mido python-rtmidi
Run:
  python keylab_go_bridge.py --list
  python keylab_go_bridge.py --go "LoopBe" --kl-in "DAW" --kl-out "KeyLab" --verbose
"""
import argparse
import time

# ------------------------------------------------------------------ shared vocabulary
CMD_CH, STOP_CH, FB_CH = 15, 14, 13          # mido channels are 0-based: 16, 15, 14
CMD = dict(prev_step=1, next_step=2, prev_file=3, next_file=4, load=5, save=6,
           metro=7, play=8, stop=9, pause=10, panic=11)             # commands, CC on ch 16
FB = dict(load_lit=1, play_lit=2, pause_lit=3, metro_lit=4)          # GrandOrgue -> bridge, CC on ch 14
CMD_PATHS = {                                                        # GrandOrgue MIDI object paths
    "prev_step": "Sequencer/Prev", "next_step": "Sequencer/Next",
    "prev_file": "Sequencer/PrevFile", "next_file": "Sequencer/NextFile",
    "load": "Sequencer/LoadFile", "save": "Sequencer/SaveFile",
    "metro": "Metronome/MetronomeOn",
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
}
ENCODER_VOLS = {0: "pedal", 1: "hw", 2: "sl", 3: "sw"}    # encoders 1-4
POSITION_LABEL_PATH = "Sequencer/sequencer position"   # sends the step number as a HWString, key 2
FILENAME_LABEL_KEY, POSITION_LABEL_KEY = 1, 2

# ------------------------------------------------------------------ organ layout
DIVISIONS = [   # (code, name, manual number in the organ, stop names as shown on the 16-char LCD)
    ("P", "Pedal", 0, ["Untersatz 32'", "Contrabass 16'", "Subbass 16'", "Octavbass 8'", "Gedackt 8'",
                       "Choralbass 4'", "Posaune 32'", "Posaune 16'", "Trompete 8'"]),
    ("H", "Hauptwerk", 1, ["Praestant 16'", "Principal 8'", "Holzflote 8'", "Rohrflote 8'", "Gambe 8'",
                           "Octave 4'", "Spitzflote 4'", "Quinte 2 2/3'", "Octave 2'", "Mixtur mj 2 2/3'",
                           "Mixtur mi 1 1/3'", "Trompete 16'", "Trompete 8'"]),
    ("S", "Schwellwerk", 2, ["Bourdon 16'", "Principal 8'", "Nacht.Ged. 8'", "Corno dolce 8'", "Viola 8'",
                             "V. celeste 8'", "Geigenpr. 4'", "Querflote 4'", "Nazard 2 2/3'", "Flageolett 2'",
                             "Tierce 1 3/5'", "Larigot 1 1/3'", "Plein jeu 2'", "Scharff 1'", "Trp. harm. 8'",
                             "Hautbois 8'", "Clairon 4'"]),
    ("L", "Solowerk", 3, ["Jubalflote 8'", "Trichterfl. 4'", "Cornet 8'", "Trp.chamade 8'", "Engl. Horn 8'"]),
]
OTHERS = [  # (kind, manual, number, LCD name, GrandOrgue object name) - couplers 1-3 pedal, 4-5 Hauptwerk, 6 Schwellwerk
    ("coupler", 0, 1, "Coupler 1 (ped)", "Coupler 1"), ("coupler", 0, 2, "Coupler 2 (ped)", "Coupler 2"),
    ("coupler", 0, 3, "Coupler 3 (ped)", "Coupler 3"), ("coupler", 1, 1, "Coupler 4 (HW)", "Coupler 4"),
    ("coupler", 1, 2, "Coupler 5 (HW)", "Coupler 5"), ("coupler", 2, 1, "Coupler 6 (SW)", "Coupler 6"),
    ("tremulant", None, 1, "Tremulant II", ""), ("tremulant", None, 2, "Tremulant III", ""),
]
BANK_SIZE = 8
SWITCH_OFFSET = {0: 3, 1: 2, 2: 1, 3: 0}     # manual -> how many switches come before its first stop
TREMULANT_SWITCH = {1: 47, 2: 53}           # tremulant number -> global switch number


class Item:
    def __init__(self, kind, manual, number, name, cc, bank_code, division, odf_name=""):
        self.kind, self.manual, self.number, self.name, self.cc = kind, manual, number, name, cc
        self.bank_code, self.division, self.odf_name = bank_code, division, odf_name

    @property
    def path(self):
        """The panel knobs are Switch objects in this organ: stops sit after the couplers in each manual's
        switch list (Pedal +3, Hauptwerk +2, Schwellwerk +1, Solowerk +0); couplers are switches 1-3 / 1-2 / 1;
        the two tremulant buttons are the global switches 47 and 53, which have no parent folder in the path."""
        if self.kind == "stop":
            return f"manuals/{self.manual:03d}/switches/{self.number + SWITCH_OFFSET[self.manual]:03d}"
        if self.kind == "coupler":
            return f"manuals/{self.manual:03d}/switches/{self.number:03d}"
        return f"{TREMULANT_SWITCH[self.number]:03d}"


def build_banks():
    items, banks, cc = [], [], 0
    for code, dname, manual, names in DIVISIONS:
        for b in range(0, len(names), BANK_SIZE):
            bank_items = []
            for i, nm in enumerate(names[b:b + BANK_SIZE], start=b):
                cc += 1
                bank_items.append(Item("stop", manual, i + 1, nm, cc, f"{code}{b // BANK_SIZE + 1}", dname))
            banks.append({"code": f"{code}{b // BANK_SIZE + 1}", "division": dname, "items": bank_items})
            items += bank_items
    other_items = []
    for kind, manual, number, nm, odf in OTHERS:
        cc += 1
        other_items.append(Item(kind, manual, number, nm, cc, "C1", "Cpl/Trem", odf))
    banks.append({"code": "C1", "division": "Cpl/Trem", "items": other_items})
    return items + other_items, banks


ITEMS, BANKS = build_banks()
ITEM_BY_CC = {it.cc: it for it in ITEMS}

# ------------------------------------------------------------------ KeyLab protocol
KEYLAB_HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]
LINE_WIDTH = 16
TEXT_WIDTH = 13            # 2 status characters + 1 spacer + 13 text characters
MIN_INTERVAL_S = 0.04      # default gap between LCD writes; the KeyLab LCD can lock up if flooded (--live to change)
LED_IDS = {"loop": 90, "metro": 89, "play": 94}
PAD_LED_BASE = [32, 35, 38, 41, 44, 47, 50, 53]      # first of 3 LEDs (R, G, B) of each pad; pads 1-4 top row, 5-8 bottom row
DEFAULT_PAD_CCS = list(range(0x24, 0x2C))              # CC sent by pads 1-8 - check with --learn-pads
DEFAULT_PAD_COLORS = {"P": (0, 0, 127), "H": (0, 127, 0), "S": (127, 100, 0), "L": (127, 0, 0), "C": (100, 0, 127)}
PAD_LED_GAP_S = 0.015
# DAW-mode (Mackie style) notes, channel 1
N_REWIND, N_FORWARD, N_STOP, N_PLAY, N_LOOP, N_METRO, N_SAVE = 0x5B, 0x5C, 0x5D, 0x5E, 0x56, 0x59, 0x50
N_NEXT_BANK, N_PREV_BANK = (0x31, 0x2F), (0x30, 0x2E)
N_JOG_PRESS = 0x54          # pressing the jog knob (seen once in the sniffer capture)
CC_JOG = 0x3C


def ascii_clean(text):
    fold = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e", "ê": "e", "à": "a",
            "â": "a", "ç": "c", "î": "i", "ô": "o", "û": "u", "Ä": "A", "Ö": "O", "Ü": "U", "É": "E"}
    out = "".join(fold.get(c, c) for c in text)
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


class Bridge:
    """All behaviour, no MIDI library needed (testable offline).  Methods return a list of
    outputs: {"to": "go", "ch", "cc", "val"} | {"to": "lcd", "data"} | {"to": "led", "data"}."""

    def __init__(self, threshold=64, settle_s=0.10, live_s=MIN_INTERVAL_S, hold_s=1.0, loop_restart_s=0.4, refresh_s=2.0,
                 encoder_step=2, volume_start=100, encoder_vols=None, jog_max=8,
                 pad_ccs=None, pad_dim=0.10, pad_colors=None, pads_enabled=True, pad_shared_window=0.7, led_refresh_s=2.0):
        self.threshold, self.settle_s, self.live_s, self.hold_s = threshold, settle_s, live_s, hold_s
        self.refresh_s, self.last_idle = refresh_s, 0.0
        self.min_interval = live_s
        self.fader_pos = [None] * BANK_SIZE   # last position seen on each physical fader
        self.loop_restart_s = loop_restart_s
        self.text, self.pos, self.cued = "", "", False
        self.bank = 0
        self.state = {}                       # cc -> bool, stop/coupler/tremulant state
        self.last_sent = {}                   # cc -> (state, time) of the last stop command sent
        self.encoder_step, self.jog_max = encoder_step, jog_max
        self.encoder_vols = dict(ENCODER_VOLS if encoder_vols is None else encoder_vols)
        self.vol = {k: volume_start for k in VOLS}   # last volume value sent per level (0-127)
        self.loop = False
        self.player, self.user_stopped = "stopped", False
        self.play_lit = self.pause_lit = self.metro_lit = False
        self.dirty = True
        self.last_activity = None
        self.last_kl = 0.0                    # time of the last message of any kind to the keyboard
        self.last_lcd = 0.0                   # time of the last LCD write (LED bursts must not starve the LCD)
        self.detail_pending, self.detail_until, self.last_detail = None, 0.0, 0.0
        self.scheduled = []                   # (due, outputs)
        self.leds_sent = {}
        self.pads_enabled, self.pad_dim = pads_enabled, pad_dim
        self.pad_ccs = list(pad_ccs or DEFAULT_PAD_CCS)
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

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _cc(ch, cc, val):
        return {"to": "go", "ch": ch, "cc": cc, "val": val}

    def _press(self, name):
        return [self._cc(CMD_CH, CMD[name], 127), self._cc(CMD_CH, CMD[name], 0)]

    def _detail(self, l1, l2="", hold=None):
        """Show this on the LCD, then go back to normal after `hold` seconds (default --hold)."""
        self.detail_pending = (l1, l2, hold)

    def _bank_items(self):
        return BANKS[self.bank]["items"]

    def _change_bank(self, step):
        self.bank = (self.bank + step) % len(BANKS)
        b = BANKS[self.bank]
        self._detail(f"{b['code']} {b['division']}", self._bank_marks(), hold=2.5)
        self.dirty = True

    def _bank_marks(self):
        """One mark per fader: # on and fader up, . off and fader down, ^ stop on but fader down
        (raise it), v stop off but fader up (lower it), ? fader position not seen yet."""
        marks = []
        for i, it in enumerate(self._bank_items()):
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
        cc, _path, name = VOLS[key]
        self._detail(name, self._bar(value))
        return [self._cc(VOL_CH, cc, value)]

    # ---------------------------------------------------------------- KeyLab DAW port
    def from_daw(self, msg, now):
        out = []
        t = msg.type
        if t == "note_on" and msg.velocity > 0 and msg.channel == 0:
            n = msg.note
            self._button_event(now)
            if n == N_REWIND:
                out += self._press("prev_step")
            elif n == N_FORWARD:
                out += self._press("next_step")
            elif n in N_NEXT_BANK:
                self._change_bank(+1)
            elif n in N_PREV_BANK:
                self._change_bank(-1)
            elif n == N_JOG_PRESS:                   # same as the sustain pedal: load the cued file
                out += self._press("load")
            elif n == N_SAVE:
                out += self._press("save")
                self._detail("Save file", "sent")
            elif n == N_METRO:
                out += self._press("metro")
            elif n == N_PLAY:
                if self.player == "stopped":
                    out += self._press("play")
                    self.player, self.user_stopped = "playing", False
                elif self.player == "playing":
                    out += self._press("pause")
                    self.player = "paused"
                else:
                    out += self._press("pause")
                    self.player = "playing"
            elif n == N_STOP:                       # MIDI file playing or paused: stop it AND panic; otherwise panic only
                was = self.player
                if was in ("playing", "paused"):
                    out += self._press("stop")
                out += self._press("panic")
                self.player, self.user_stopped = "stopped", True
                self._detail("PANIC", "player stopped" if was in ("playing", "paused") else "all sound off")
            elif n == N_LOOP:
                self.loop = not self.loop
                self._detail("Loop " + ("ON" if self.loop else "OFF"), "repeat MIDI")
        elif t == "control_change" and msg.control == CC_JOG:
            self._button_event(now)
            steps = max(1, msg.value & 0x3F)
            out += [o for _ in range(min(steps, self.jog_max)) for o in self._press("prev_file" if msg.value >= 64 else "next_file")]
        elif t == "control_change" and 0x10 <= msg.control <= 0x17:
            n = msg.control - 0x10
            self.last_activity = now
            delta = (msg.value & 0x3F) * (-1 if msg.value >= 64 else 1)
            if n in self.encoder_vols:
                key = self.encoder_vols[n]
                out += self._set_volume(key, self.vol[key] + delta * self.encoder_step)   # more when turned fast
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
                out = [self._cc(STOP_CH, it.cc, 127 if desired else 0)]
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
    def from_main(self, msg, now):
        """Pads toggle the stop under the same-numbered fader of the current bank."""
        if not self.pads_enabled or msg.type != "control_change" or msg.control not in self.pad_ccs:
            return []
        touched = [i for i, c in enumerate(self.pad_ccs) if c == msg.control]
        self._invalidate_pads(touched)
        self.led_invalidations += [(now + 0.25, touched), (now + 1.0, touched)]
        if self.shared_cc is not None and msg.control == self.shared_cc:
            toggle_pad, momentary_pad = self.shared_pads
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
        items = self._bank_items()
        if n >= len(items):
            return []
        it = items[n]
        new = not bool(self.state.get(it.cc))
        self.state[it.cc] = new
        self.last_sent[it.cc] = (new, now)
        self.last_activity = now
        self._detail(it.name, ("ON " if new else "off") + f" {BANKS[self.bank]['code']} pad {n + 1}")
        return [self._cc(STOP_CH, it.cc, 127 if new else 0)]

    def _desired_leds(self):
        want = {LED_IDS["loop"]: 127 if self.loop else 0, LED_IDS["metro"]: 127 if self.metro_lit else 0,
                LED_IDS["play"]: 127 if self.player == "playing" else 0}
        if self.pads_enabled:
            items = self._bank_items()
            for i, base in enumerate(PAD_LED_BASE):
                if i < len(items):
                    r, g, b = self.pad_colors[items[i].bank_code[0]]
                    k = 1.0 if self.state.get(items[i].cc) else self.pad_dim
                    rgb = (int(r * k), int(g * k), int(b * k))
                else:
                    rgb = (0, 0, 0)
                for j in range(3):
                    want[base + j] = rgb[j]
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
            return out
        if msg.type != "control_change":
            return out
        val = msg.value >= 64
        if msg.channel == STOP_CH and msg.control in ITEM_BY_CC:
            self.state[msg.control] = val
        elif msg.channel == FB_CH:
            c = msg.control
            if c == FB["load_lit"]:
                self.cued, self.dirty = val, True
            elif c == FB["play_lit"]:
                was, self.play_lit = self.play_lit, val
                if val and not was:
                    self.player = "playing"
                elif was and not val:
                    if self.pause_lit:
                        self.player = "paused"
                    elif self.loop and self.player == "playing" and not self.user_stopped:
                        self.scheduled.append((now + self.loop_restart_s, self._press("play")))
                    else:
                        self.player = "stopped"
            elif c == FB["pause_lit"]:
                was, self.pause_lit = self.pause_lit, val
                if val and not was:
                    self.player = "paused"
                elif was and not val and self.play_lit:
                    self.player = "playing"
            elif c == FB["metro_lit"]:
                self.metro_lit = val
        return out

    # ---------------------------------------------------------------- display
    def _idle_lines(self):
        code = BANKS[self.bank]["code"]
        l1, l2 = split_lines(self.text or "GrandOrgue", TEXT_WIDTH)
        step = "->" if self.cued else (self.pos[-2:].rjust(2) if self.pos else "  ")
        return f"{code:<2} {l1}", f"{step} {l2}"

    def tick(self, now):
        out = []
        if self.shared_down is not None and now - self.shared_down > self.shared_window:
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


# ------------------------------------------------------------------ configuration
def default_config_path():
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path):
    """Read config.yaml (if it exists) and return (flat dict of command-line defaults, other settings)."""
    import os
    if not path or not os.path.exists(path):
        return {}, {}
    import yaml
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    ports, faders, disp = raw.get("ports") or {}, raw.get("faders") or {}, raw.get("display") or {}
    flat = {"go": ports.get("go"), "go_out": ports.get("go_out") or None,
            "kl_in": ports.get("keylab_in"), "kl_out": ports.get("keylab_out"), "kl_main": ports.get("keylab_main_in") or None,
            "threshold": faders.get("threshold"), "hold": disp.get("hold"), "live": disp.get("live"),
            "refresh": disp.get("refresh"), "verbose": raw.get("verbose")}
    return {k: v for k, v in flat.items() if v is not None}, raw


def bridge_settings(raw):
    """Bridge() keyword arguments taken from the 'controls' section of the config."""
    c, out = raw.get("controls") or {}, {}
    for key, arg in (("encoder_step", "encoder_step"), ("volume_start", "volume_start"),
                     ("jog_max_steps", "jog_max"), ("loop_restart", "loop_restart_s")):
        if c.get(key) is not None:
            out[arg] = c[key]
    p = raw.get("pads") or {}
    if p.get("enabled") is not None:
        out["pads_enabled"] = bool(p["enabled"])
    if p.get("ccs"):
        out["pad_ccs"] = [int(x) for x in p["ccs"]]
    if p.get("refresh") is not None:
        out["led_refresh_s"] = float(p["refresh"])
    if p.get("shared_window") is not None:
        out["pad_shared_window"] = float(p["shared_window"])
    if p.get("dim") is not None:
        out["pad_dim"] = float(p["dim"])
    if p.get("colors"):
        names = {"pedal": "P", "hw": "H", "sw": "S", "sl": "L", "other": "C"}
        out["pad_colors"] = {names[k]: tuple(int(x) for x in v) for k, v in p["colors"].items() if k in names}
    if c.get("encoders"):
        out["encoder_vols"] = {int(k) - 1: v for k, v in c["encoders"].items() if v in VOLS}
    return out


def apply_lcd_names(raw):
    """Optional display names for stops/couplers/tremulants: lcd_names: {"manuals/000/couplers/Coupler 1": "III/P"}"""
    names = raw.get("lcd_names") or {}
    for it in ITEMS:
        if it.path in names:
            it.name = str(names[it.path])[:LINE_WIDTH]


# ------------------------------------------------------------------ MIDI plumbing
def learn_pads(mido, wanted):
    """Ask for pads 1-8 (top row left to right, then bottom row) and print the CC numbers."""
    port = mido.open_input(find_port(mido.get_input_names(), wanted))
    found, raws = [], []
    print("Press each pad once, top row left to right, then bottom row left to right.")
    for n in range(1, 9):
        print(f"  pad {n} ... ", end="", flush=True)
        while True:
            m = port.receive()
            if m.type == "control_change" and m.value >= 64:
                found.append(m.control)
                raws.append(" ".join(f"{x:02X}" for x in m.bytes()))
                print(f"CC {m.control}, channel {m.channel + 1}   raw {raws[-1]}")
                break
            if m.type == "note_on" and m.velocity > 0:
                print(f"note {m.note} - these pads send notes, tell me and I will add support")
                return
            print(f"[other message: {m}]")
    port.close()
    dups = sorted({c for c in found if found.count(c) > 1})
    if dups:
        print(f"\nWarning: CC {dups} is sent by more than one pad, so those pads cannot be told apart by CC alone.")
        print("Run keylab_sniffer.py and press those pads one at a time to see what else differs.")
    print("\nPut this in config.yaml:\npads:\n  ccs: " + str(found))


def find_port(names, wanted):
    for n in names:
        if wanted.lower() in n.lower():
            return n
    raise SystemExit(f"No MIDI port containing '{wanted}'. Use --list to see the names.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="settings file (default: config.yaml next to this script)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--go", default="LoopBe", help="virtual cable used with GrandOrgue (in and out)")
    ap.add_argument("--go-out", help="if you use a second cable for bridge -> GrandOrgue")
    ap.add_argument("--kl-in", default="DAW", help="KeyLab DAW INPUT port (part of its name)")
    ap.add_argument("--kl-out", default="KeyLab", help="KeyLab OUTPUT port for LCD and LEDs")
    ap.add_argument("--kl-main", help="KeyLab MAIN input port (part of its name); needed for the pads")
    ap.add_argument("--learn-pads", action="store_true", help="press pads 1-8 in turn and print the CC numbers for config.yaml")
    ap.add_argument("--threshold", type=int, default=64, help="fader value that switches a stop on")
    ap.add_argument("--hold", type=float, default=1.0, help="seconds a fader/knob readout stays before the normal display returns")
    ap.add_argument("--test-stop", type=int, help="send stop number N (1-52, see the bank table) on and exit")
    ap.add_argument("--test-off", action="store_true", help="with --test-stop: send off instead of on")
    ap.add_argument("--live", type=float, default=MIN_INTERVAL_S, help="minimum seconds between LCD writes while a fader moves (raise it if the LCD misbehaves)")
    ap.add_argument("--refresh", type=float, default=2.0, help="seconds between re-sending the normal display (0 = never)")
    ap.add_argument("--verbose", action="store_true")
    pre, _ = ap.parse_known_args()
    cfg_path = pre.config or default_config_path()
    cfg_defaults, raw = load_config(cfg_path)
    ap.set_defaults(**cfg_defaults)                    # config.yaml values; anything typed on the command line wins
    a = ap.parse_args()
    apply_lcd_names(raw)
    print(f"Settings: {cfg_path}" if raw else "Settings: built-in defaults (no config.yaml found)")

    import mido
    mido.set_backend("mido.backends.rtmidi")
    if a.list:
        print("INPUT ports :", *mido.get_input_names(), sep="\n  ")
        print("OUTPUT ports:", *mido.get_output_names(), sep="\n  ")
        return

    if a.learn_pads:
        learn_pads(mido, a.kl_main or "Ess Midi In")
        return

    if a.test_stop:
        it = ITEM_BY_CC[a.test_stop]
        with mido.open_output(find_port(mido.get_output_names(), a.go_out or a.go)) as p:
            p.send(mido.Message("control_change", channel=STOP_CH, control=it.cc, value=0 if a.test_off else 127))
        print(f"sent {'off' if a.test_off else 'on'} to {it.division} '{it.name}' ({it.path}), CC {it.cc} on channel {STOP_CH + 1}")
        return

    go_in = mido.open_input(find_port(mido.get_input_names(), a.go))
    go_out = mido.open_output(find_port(mido.get_output_names(), a.go_out or a.go))
    kl_in = mido.open_input(find_port(mido.get_input_names(), a.kl_in))
    kl_out = mido.open_output(find_port(mido.get_output_names(), a.kl_out))
    main_in = None
    if a.kl_main:
        try:
            main_in = mido.open_input(find_port(mido.get_input_names(), a.kl_main))
        except Exception as e:                       # the port may be held exclusively by GrandOrgue
            print(f"Pads: cannot read the KeyLab main port ({e}). Pad lights still work, pad presses do not.")
    print("Bridge running. Ctrl+C to stop.")

    br = Bridge(threshold=a.threshold, hold_s=a.hold, refresh_s=a.refresh, live_s=a.live, **bridge_settings(raw))

    def emit(outputs):
        for o in outputs:
            if o["to"] == "go":
                go_out.send(mido.Message("control_change", channel=o["ch"], control=o["cc"], value=o["val"]))
            else:
                kl_out.send(mido.Message("sysex", data=o["data"]))
            if a.verbose:
                print("->", o["to"], {k: v for k, v in o.items() if k != "to"} if o["to"] == "go" else "")

    try:
        while True:
            now = time.time()
            for m in kl_in.iter_pending():
                if a.verbose and m.type != "pitchwheel":
                    print("DAW:", m)
                emit(br.from_daw(m, now))
            if main_in:
                for m in main_in.iter_pending():
                    emit(br.from_main(m, now))
            for m in go_in.iter_pending():
                if a.verbose and m.type != "sysex":
                    print("GO :", m)
                emit(br.from_go(m, now))
            emit(br.tick(now))
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    for p in (go_in, go_out, kl_in, kl_out, main_in):
        if p:
            p.close()


if __name__ == "__main__":
    main()
