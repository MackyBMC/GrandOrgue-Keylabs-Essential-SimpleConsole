"""Bridge application state, event handling, and lifecycle.

CHANGELOG
2026-10-17  Sheet music open: Punch (notes 0x57/0x58) and Save (0x50) now toggle the jog between the Files list and
            the Setters list, in addition to Cat/Char. Save does not send GrandOrgue Save while the score is open
            (the save function is not ready). A 0.3 s lockout stops a Punch that sends both notes toggling twice.
2026-10-18  Pedal/jog "sticky / bouncy" fix: one activation per pedal press (repeats while held are swallowed), 0.25 s
            bounce guard per combination, a newer press cancels step pulses still waiting from the previous one, and
            the organ-echo ignore window now lasts up to ~5 s (ends early when the organ shows the target), so a slow
            file load can no longer overwrite the tick/selection with its intermediate 000 state.
2026-10-24  Loading a MIDI file shows what is loaded (name, length, channel > manual list), maps its channels to
            manuals from the track names / instruments, stops playback; timeline + Space = play/stop; encoders 3/4 =
            Schwellwerk / Solowerk (were swapped). Playhead position is exact between notes.
2026-10-24  GrandOrgue MIDI setup (go_midi_setup.py): the import file for GrandOrgue is regenerated automatically when the
            bridge's needs change; "GrandOrgue MIDI setup" button (check / create / open folder / test the four manuals).
            Playback log now says how many messages were sent.
2026-10-23  Stave editor step sequence: selected notes are played again chord by chord on the organ ("chord" event);
            KeyLab >> / << step it while its Step mode is ticked (stave_step_hook).
2026-10-21  Tempo for MIDI file playback: Transport "Tempo %" (25-200), changeable while playing.
2026-10-21  Playback diagnostics (log says when the output port is down / messages were dropped); a plain channel-1
            keyboard recording is fanned out to the manual channels like the KeyLab key ranges. Stave editor: "MIDI
            tracks in this file" list (track name, channel, GM instrument, note count, range, empty tracks marked) and
            voices are named from the track name or GM instrument.
2026-10-21  Registrations by bar and by single stop: a voice's "Reg" list holds changes per bar, each a setter or an
            exact set of stops (STOPS markers; stops of that manual not listed are switched off). Stave editor "Play on
            organ" / "Stop" export a preview (midi\\_preview.mid) and play it through the bridge at once.
2026-10-21  Orchestral MIDI: files are read per track (tempo map aware); stave editor layout "one stave per MIDI
            track / channel" (drums skipped) with a P/H/Sc/S manual tick per voice (none ticked = voice not
            exported) and a "Reg" button giving the voice the stops of an existing setter for its manual(s). Stored as
            REG markers; the bridge sets those manuals' stops on playback and re-applies them after every setter change.
2026-10-21  Recording keeps the << / >> step moves (internal step 000-0xx) as setter markers. Stave editor: each stave
            plays on one or more manuals (P/H/Sc/S ticks), each manual has its own MIDI channel (config.yaml
            manual_channels:, default 2-5); make_go_midi_import.py adds those channels to GrandOrgue's settings.
2026-10-21  Organ sessions: setter changes (file + step 000-0xx) made while recording are stored in the MIDI file as
            SETTER markers and re-applied on playback; staves can be written on their own channels (stave editor) and
            playback keeps them (optional per-file remap: Transport > Channels...). Stave editor: per-stave GrandOrgue
            channel, "Organ setters" list with a setter-file / step picker, markers shown above the bar and exported.
2026-10-20  Transport frame: Previous/Next file step through the MIDI files in the midi folder, "Open MIDI..." picks any
            file for Play, Save is Save As for the current MIDI file, and the active file is shown in the frame.
2026-10-20  Record button (0x5F) is a real recording: Scripts\\midi\\Recording ....mid (GrandOrgue version) plus
            "... (stave).mid" (Stave Friendly, bars straightened). Play then plays that recording through GrandOrgue
            (Stop ends it; playback_channel in recorder: block, default 1). Stave editor button opens midi_stave.
2026-10-20  Always-on take recorder (take_recorder.py): every channel-1 note and sustain-pedal move from the keyboard
            is kept and saved as Takes folder: Take <date time>.mid, a new take after 25 s of silence, autosaved every
            30 s. Configure / disable with the recorder: block in config.yaml.
2026-10-17  (superseded by the 2026-10-18 rewrite below) pedal tick follow-up.
2026-10-18  SETTER LOGIC REWRITE (one path for main GUI, sheet music, jog, pedal):
            - Selecting a setter (click, jog, sheet music) only moves the selection in staged mode; direct mode
              also activates it. It never walks the organ one entry at a time any more.
            - Sustain pedal, Jog press and the Load button call activate_selected() while play is NOT active: same
              file loaded -> step straight to the wanted step (no reload); other file -> select file, Load, then step
              to the wanted step after LOAD_SETTLE_S. The old "Load file always jumps to step 000" no longer applies.
            - While play IS active (MIDI player / manual sequence) nothing switches: selection only, and the pedal
              keeps its play behaviour (the 000 reset stays exclusive to Stop).
            - The loaded tick is set by the bridge at activation; organ echo is ignored for 2 s.
2026-10-17  Earlier "cue_setter" event now just calls request_navigate (same as a click).
"""

import os
import queue
import shlex
import shutil
import sys
import tempfile
import threading
import time
import traceback
from collections import deque
from typing import Any, cast

from . import __version__
from .console_ui import ConsoleUI
from .midi_ports import MidiPorts
from .organ_layout import BANKS, ITEMS, configure_layout
from .midi_protocol import (
    Bridge, CMD, CMD_CH, CC_JOG, CC_SUSTAIN, N_FORWARD, N_JOG_PRESS, N_LOOP, N_METRO,
    MENU_PAGES, N_CAT_CHAR, N_NAV_LEFT, N_NAV_RIGHT, N_NEXT_BANK, N_PLAY, N_PRESET, N_PREV_BANK, N_REWIND,
    N_SAVE, N_STOP, STOP_CH, VOLS, pad_rgb, screen_rgb, split_lines,
    pad_screen_color, UNASSIGNED_PAD_COLOR,
)
from .go_settings import build_go_settings, compare_with_export, merge_settings_export
from .combination_transfer import (
    _contains_combinations, load_transfer_aliases, transfer_combinations, write_transfer_alias_template,
)
from .odf_scan import compare_with_builtin, scan_odf, spec_from_profile, summarize
from .organ_layout import ACTIVE_LAYOUT, STOP_CHANNELS
from .preset_store import (
    _normalized_mapping_key, _write_managed_switches, combination_root, load_combinations, project_root, set_config_key,
    load_language, load_preset_activation, load_theme, bridge_settings,
)
from translations import LANGUAGE_NAMES, translate


class BridgeApp:
    def __init__(self, backend, args, raw, br_settings, cfg_path, ui):
        self.backend = backend
        self.args = args
        self.raw = raw
        self.br_settings = br_settings
        self.cfg_path = cfg_path
        self.ui = ui
        self.combinations = load_combinations(cfg_path, raw)
        self.selected_combination_index = None
        self.loaded_combination_index = None
        self.loaded_switch_paths = None
        self.recorder = None
        recorder_cfg = raw.get("recorder") if isinstance(raw.get("recorder"), dict) else {}
        if recorder_cfg.get("enabled", True):                  # always-on take recorder (see take_recorder.py)
            from .take_recorder import TakeRecorder
            folder = str(recorder_cfg.get("folder", "Takes"))
            if not os.path.isabs(folder):
                folder = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), folder)
            self.recorder = TakeRecorder(folder, recorder_cfg.get("gap", 25), recorder_cfg.get("min_notes", 6),
                                         recorder_cfg.get("autosave", 30), log=lambda text, **k: self.log(text, notify=False))
        from .take_recorder import make_midi_recorder, TakePlayer
        midi_dir = str(recorder_cfg.get("midi_folder", "midi"))
        if not os.path.isabs(midi_dir):
            midi_dir = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), midi_dir)
        self.midi_dir = midi_dir
        self._voice_regs = {}                   # manual name -> (setter file, step, name) from REG markers during playback
        self.midi_rec = None                    # explicit Record-button session
        self.take_to_play = None
        self.take_length, self.take_info = 0.0, ""                # last recorded take: the next Play button press plays it
        forced = recorder_cfg.get("playback_channel")             # optional: force every note onto one channel
        self.take_player = TakePlayer(lambda m: self.ports.send("go_out", m),
                                      int(forced) - 1 if forced else None,
                                      on_marker=lambda text: self.post_ui_event("setter_marker", text))
        self.language = load_language(cfg_path, raw)
        self.language_path = os.path.join(os.path.dirname(cfg_path), "language.txt") if cfg_path else ""
        self.theme = load_theme(cfg_path, raw)
        self.theme_path = os.path.join(os.path.dirname(cfg_path), "theme.txt") if cfg_path else ""
        self.preset_activation = load_preset_activation(cfg_path, raw)
        self.preset_activation_path = os.path.join(os.path.dirname(cfg_path), "preset_activation.txt") if cfg_path else ""
        self._baseline_settle_at = None
        self._last_confirmed_identity = None
        self._last_feedback_cued = False
        self.pending_navigation_target = None
        self.started = time.perf_counter()
        self.stats = {"daw_in": 0, "main_in": 0, "go_in": 0, "go_out": 0, "kl_out": 0, "relay_out": 0,
                      "errors": 0, "loops": 0, "loop_total": 0.0, "loop_max": 0.0}
        self.recent = deque(maxlen=500)
        self.recent_times = {}
        self.stop_grid_pad_handler = None
        self.ports = MidiPorts(backend, args, self.stats, self.recent_times, br_settings.get("pad_ccs"))
        self.br = self.make_bridge()
        self.debug = bool(args.verbose)
        self.running = True
        self.fatal = None
        self.interrupted = False
        self.cleaned = False
        self.restarts = 0
        self.reconnects = 0
        self.message = translate(self.language, "ready")
        self.last_reconnect_attempt = 0.0
        self.reconnect_delay = 3.0
        self.ui_events = queue.Queue()
        self.snapshot_lock = threading.Lock()
        self._ui_snapshot = {}
        self.gui_hosted = False
        self.sheet_music_navigation_enabled = threading.Event()
        self.sheet_music_navigation_handler = None
        self.menu_jog_handler = None
        self.menu_press_handler = None
        self.main_jog_handler = None
        self.main_press_handler = None
        self.sheet_jog_handler = None
        self.sheet_press_handler = None
        self.sheet_zone_handler = None
        self.modal_open = threading.Event()     # set by the GUI while a popup dialog is open
        self.modal_jog_handler = None
        self.modal_press_handler = None
        self.active_organ_path = str(raw.get("organ_path", ""))
        self.organ_path = self.active_organ_path
        self.combination_set = str(raw.get("combination_set", "Friesach"))
        self.organ_profile = None
        self.organ_spec = None
        self.organ_problems = []
        self.organ_summary = "No organ profile loaded"
        self.organ_settings_path = ""
        self.organ_selection = None
        self.organ_switching = False
        self.pending_organ_import = None
        if self.organ_path and os.path.isfile(self.organ_path):
            try:
                self._scan_organ_file(self.organ_path)
                if self.organ_profile is not None and self.organ_spec is not None:
                    self.br.configure_organ_controls(self.organ_profile, self.organ_spec)
            except (OSError, ValueError) as exc:
                self.log(f"Could not configure active organ controls: {exc}", level="ERROR")

    def t(self, key, **values):
        return translate(self.language, key, **values)

    def set_language(self, language):
        if language not in LANGUAGE_NAMES:
            self.message = self.t("language_invalid")
            return
        self.language = language
        try:
            if self.language_path:
                with open(self.language_path, "w", encoding="utf-8") as language_file:
                    language_file.write(language + "\n")
        except OSError as exc:
            self.message = self.t("language_saved_error", error=exc)
            return
        self.message = self.t("language_changed", name=LANGUAGE_NAMES[language])

    def set_theme(self, theme):
        theme = str(theme).lower()
        if theme not in ("light", "dark", "contrast"):
            return False
        self.theme = theme
        try:
            if self.theme_path:
                with open(self.theme_path, "w", encoding="utf-8") as theme_file:
                    theme_file.write(theme + "\n")
        except OSError:
            self.message = self.t("theme_save_error")
            return False
        return True

    def set_preset_activation(self, mode):
        mode = str(mode).lower()
        if mode not in ("staged", "direct"):
            self.message = self.t("preset_mode_usage")
            return False
        self.preset_activation = mode
        try:
            if self.preset_activation_path:
                with open(self.preset_activation_path, "w", encoding="utf-8") as mode_file:
                    mode_file.write(mode + "\n")
        except OSError:
            self.message = self.t("preset_mode_save_error")
            return False
        return True

    LOAD_SETTLE_S = 1.0            # time GrandOrgue needs to load a file before the step pulses are sent

    def _play_locked(self):
        """Play is active (MIDI player or manual sequence): the << >> / pedal step the piece and nothing may switch."""
        br = self.br
        return bool(br.sequence_mode or br.player in ("playing", "paused") or br.play_start_pending_until is not None)

    def activate_combination(self, index):
        if 0 <= index < len(self.combinations):
            self._activate_index(index)

    def cue_combination(self, index):
        """THE selection entry point (mouse, jog, sheet music). Selecting never touches the organ in staged mode;
        in direct mode it activates at once, unless play is active."""
        if not 0 <= index < len(self.combinations):
            return
        self.selected_combination_index = index
        if self.preset_activation == "direct" and not self._play_locked():
            self._activate_index(index)
            return
        self.br._button_event(time.time())
        self.br._detail(self.combinations[index]["name"], self.t("preset_cued"))

    def activate_selected(self):
        """Pedal / Jog press / Load button: activate the selected combination wherever it is. Returns True if handled."""
        index = self.selected_combination_index
        if index is None or not 0 <= index < len(self.combinations):
            return False
        self._activate_index(index)
        return True

    def _activate_if_free(self):
        """Used by pedal, jog press and Load: while play is active they keep their play behaviour."""
        return bool(self.combinations) and not self._play_locked() and self.activate_selected()

    def _activate_index(self, index):
        """Put the organ on exactly this file AND step. Same file already loaded: just step to it (no file reload, so
        no jump to 000). Other file, or re-activating the current one: select the file, Load it (that lands on 000),
        then step forward to the wanted step once the load has settled."""
        br, combos, now = self.br, self.combinations, time.time()
        if index == self.__dict__.get("_last_activate_index") and now - self.__dict__.get("_last_activate_at", 0.0) < 0.25:
            return                                                   # contact bounce / double event
        self._last_activate_index, self._last_activate_at = index, now
        self.record_setter(index)                                   # an explicit recording keeps the setter changes
        stale = self.__dict__.pop("_steps_item", None)
        if stale in br.scheduled:
            br.scheduled.remove(stale)                              # a newer press replaces still-waiting step pulses
        target = combos[index]
        if now < getattr(self, "_activation_until", 0.0) and self.loaded_combination_index is not None:
            current = self.loaded_combination_index           # organ feedback still catching up with our last move
        else:
            current = self._combination_index_from_feedback()
            if current is None:
                current = self.loaded_combination_index
            if current is None:
                current = index
        in_file = [i for i, c in enumerate(combos) if c["filename"] == target["filename"]]
        position = in_file.index(index)
        files = list(dict.fromkeys(c["filename"] for c in combos))
        out = []
        later = []
        if combos[current]["filename"] == target["filename"] and not br.cued and current != index:
            delta = position - in_file.index(current)
            for _ in range(abs(delta)):
                out += br._press("next_step" if delta > 0 else "prev_step")
        else:
            count = len(files)
            forward = (files.index(target["filename"]) - files.index(combos[current]["filename"])) % count
            backward = forward - count
            steps = backward if abs(backward) < forward else forward
            for _ in range(abs(steps)):
                out += br._press("next_file" if steps > 0 else "prev_file")
            out += br._press("load")
            for _ in range(position):
                later += br._press("next_step")
        self.emit(out)
        if later:
            self._steps_item = (now + self.LOAD_SETTLE_S, later)
            br.scheduled.append(self._steps_item)
        self.selected_combination_index = index
        self._set_loaded_combination(index)
        self._activation_until = now + self.LOAD_SETTLE_S + 0.2 * position + 4.0   # ends early once the organ agrees
        br._button_event(now)
        br._detail(target["name"], self.t("preset_loaded"))
        self.log(self.t("message_combination_loaded", name=target["name"]))

    def _step_selected_index(self, direction):
        """Mirror a physical >>/<< step (already sent straight to GrandOrgue
        by from_daw) into our own tracked index, so the GUI/tree stay honest
        about where hardware navigation actually left things."""
        if not self.combinations:
            return
        current = self.selected_combination_index
        if current is None:
            current = self._combination_index_from_feedback()
        if current is None:
            current = 0
        candidate = (current + direction) % len(self.combinations)
        self.selected_combination_index = candidate
        self.br._button_event(time.time())
        self.br._detail(self.combinations[candidate]["name"], self.t("preset_cued"))

    def navigate_combinations(self, steps):
        if not self.combinations:
            return
        current = self.selected_combination_index
        if current is None:
            current = self._combination_index_from_feedback()
        target = (0 if steps >= 0 else len(self.combinations) - 1) if current is None else \
            (current + steps) % len(self.combinations)
        self.request_navigate(target)

    def _organs_folder(self):
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(self.cfg_path))), "Organs")
        os.makedirs(folder, exist_ok=True)
        return folder

    def _scan_organ_file(self, path):
        path = path.strip().strip('"')
        try:
            profile = scan_odf(path)
        except (OSError, ValueError) as exc:
            self.organ_profile = None
            self.organ_summary = f"Scan failed: {exc}"
            self.log(f"ODF scan failed for {path}: {exc}", level="ERROR")
            return
        self.organ_path = path
        self.organ_profile = profile
        self.organ_problems = compare_with_builtin(profile)
        self.organ_summary = summarize(profile, self.organ_problems)
        try:
            self.organ_spec = spec_from_profile(profile)
        except ValueError as exc:
            self.organ_spec = None
            self.organ_summary += f"  Could not derive a layout: {exc}"
        self.organ_selection = path if self.organ_spec else None
        self.log(f"ODF scanned: {profile['name']}")

    @staticmethod
    def _safe_name(text):
        cleaned = "".join("_" if ch in '<>:"/\\|?*' else ch for ch in text).strip().rstrip(". ")
        return cleaned or "organ"

    @staticmethod
    def _go_settings_for(profile, spec):
        return build_go_settings(
            profile["name"], spec,
            windchest_numbers=[w["number"] for w in sorted(profile["windchests"], key=lambda w: w["number"])],
            enclosure_numbers=[e["number"] for e in sorted(profile["enclosures"], key=lambda e: e["number"])])

    def _organ_stem(self):
        """The .organ file's own name without extension; the generated files are named after it."""
        if self.organ_profile is None:
            return "organ"
        return self._safe_name(os.path.splitext(os.path.basename(self.organ_profile["file"]))[0])

    def _settings_folder(self):
        folder = os.path.join(project_root(self.cfg_path), "Settings")
        os.makedirs(folder, exist_ok=True)
        return folder

    def _combination_alias_path(self):
        return os.path.join(self._settings_folder(), f"{self._organ_stem()} combination aliases.yaml")

    def _write_layout_file(self):
        import yaml
        if self.organ_spec is None:
            raise ValueError("organ layout has not been generated")
        target = os.path.join(self._organs_folder(), f"{self._organ_stem()}.layout.yaml")
        spec = {k: v for k, v in self.organ_spec.items() if k not in ("notes", "problems")}
        with open(target, "w", encoding="utf-8") as out:
            yaml.safe_dump(spec, out, sort_keys=False, allow_unicode=True)
        return target

    def _generate_organ_map(self, export_path):
        """Write this organ's layout file and the GrandOrgue MIDI-settings yaml to import. If an existing
        GrandOrgue export is given it is used only as a check: every generated object is compared against it."""
        import yaml
        if self.organ_profile is None or self.organ_spec is None:
            self.organ_summary = "Scan the organ first, then generate."
            return
        profile = self.organ_profile
        if self.organ_spec.get("problems"):
            self.organ_summary = ("Nothing written, the result would be incomplete: " + "; ".join(self.organ_spec["problems"]) + ".")
            return
        document = self._go_settings_for(profile, self.organ_spec)
        try:
            with open(export_path, encoding="utf-8") as export_stream:
                export = yaml.safe_load(export_stream) or {}
            document = merge_settings_export(export, document)
        except (OSError, yaml.YAMLError, ValueError) as exc:
            self.organ_summary = f"Could not merge GrandOrgue MIDI settings: {exc}"
            return
        settings_path = os.path.join(self._settings_folder(), f"{self._organ_stem()} midi import.yaml")
        aliases_path = self._combination_alias_path()
        try:
            layout_path = self._write_layout_file()
            with open(settings_path, "w", encoding="utf-8") as out:
                yaml.safe_dump(document, out, sort_keys=False, allow_unicode=True)
            write_transfer_alias_template(aliases_path, self.combination_set)
        except OSError as exc:
            self.organ_summary = f"Could not write organ files: {exc}"
            return
        self.organ_settings_path = settings_path
        message = (f"Wrote Settings/{os.path.basename(settings_path)} ({len(document['objects'])} objects) and "
                    f"Organs/{os.path.basename(layout_path)}. Merged bridge routes with the selected GrandOrgue export. "
                    f"Optional registration aliases: Settings/{os.path.basename(aliases_path)}.")
        if self.organ_spec.get("notes"):
            message += "  Notes: " + "; ".join(self.organ_spec["notes"][:3]) + "."
        self.organ_summary = message
        self.log(f"Organ files written for {profile['name']}")

    def _apply_organ_layout(self):
        """Make the scanned organ the bridge's layout. The layout is read at start-up, so this saves it into
        config.yaml and asks for a restart rather than hot-swapping the live banks under a performance."""
        if self.organ_profile is None or self.organ_spec is None:
            self.organ_summary = "Scan the organ first."
            return False
        if self.organ_spec.get("problems"):
            self.organ_summary = ("Not applied, the layout would be incomplete: " + "; ".join(self.organ_spec["problems"]) +
                                  ". Your current layout is unchanged.")
            return False
        same_organ = (os.path.normcase(os.path.abspath(self.organ_path)) ==
                      os.path.normcase(os.path.abspath(self.active_organ_path)) if self.active_organ_path else False)
        transfer_report = None
        source_set = self.combination_set
        aliases_path = self._combination_alias_path()
        try:
            layout_path = self._write_layout_file()
            if not same_organ:
                folder = self._safe_name(self.organ_profile["name"])
                root = combination_root(self.cfg_path, source_set)
                source_folder = os.path.join(root, "Combinations", source_set)
                target_folder = os.path.join(root, "Combinations", folder)
                os.makedirs(target_folder, exist_ok=True)
                aliases_path = self._combination_alias_path()
                write_transfer_alias_template(aliases_path, source_set)
                aliases = load_transfer_aliases(aliases_path)
                transfer_report = transfer_combinations(source_folder, target_folder, self.organ_profile, aliases)
                set_config_key(self.cfg_path, "combination_set", folder)
                self.combination_set = folder
            set_config_key(self.cfg_path, "organ_path", self.organ_path)
            set_config_key(self.cfg_path, "organ_layout_file",
                           os.path.relpath(layout_path, project_root(self.cfg_path)).replace(os.sep, "/"))
        except (OSError, ValueError) as exc:
            self.organ_summary = f"Could not save the organ layout: {exc}"
            return False
        self.organ_summary = (f"Saved {self.organ_profile['name']} as the active organ in config.yaml. Restart the bridge to "
                              f"use its layout, and start GrandOrgue with this organ. Setter files: Combinations/{self.combination_set}"
                              + ("" if same_organ else self._format_combination_transfer(transfer_report, source_set, aliases_path))
                              + ".")
        self.log(f"Organ layout applied to config: {self.organ_profile['name']}")
        return True

    def _write_organ_import_log(self, organ_path, message, level="INFO"):
        stem = self._safe_name(os.path.splitext(os.path.basename(str(organ_path)))[0])
        folder = os.path.join(project_root(self.cfg_path), "Logs")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{stem}.log")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp} [{level}] {message}\n")
        self.log(f"Organ import [{stem}]: {message}", level=level)

    def import_organ(self, organ_path, export_path):
        import yaml

        organ_path = str(organ_path).strip().strip('"')
        self._write_organ_import_log(organ_path, f"Starting import; MIDI export: {export_path}")
        if self.pending_organ_import is not None:
            self.discard_organ_import("A new import replaced the pending candidate.")

        prior_profile, prior_spec, prior_selection = self.organ_profile, self.organ_spec, self.organ_selection
        prior_path = self.organ_path
        self._scan_organ_file(organ_path)
        candidate_profile, candidate_spec = self.organ_profile, self.organ_spec
        scan_summary = self.organ_summary
        self.organ_profile, self.organ_spec, self.organ_selection = prior_profile, prior_spec, prior_selection
        self.organ_path = prior_path
        if candidate_profile is None or candidate_spec is None:
            self._write_organ_import_log(organ_path, scan_summary, level="ERROR")
            self.organ_summary = f"{scan_summary} The current organ remains active."
            return
        if candidate_spec.get("problems"):
            error = "; ".join(candidate_spec["problems"])
            self._write_organ_import_log(organ_path, f"Import stopped: {error}", level="ERROR")
            self.organ_summary = f"Import stopped: {error}. The current organ remains active."
            return

        root = project_root(self.cfg_path)
        stage_root = tempfile.mkdtemp(prefix="organ-import-", dir=root)
        settings_path = ""
        try:
            with open(export_path, encoding="utf-8") as export_stream:
                export = yaml.safe_load(export_stream) or {}
            self._validate_organ_midi_export(export, candidate_profile["name"])
            generated_settings = self._go_settings_for(candidate_profile, candidate_spec)
            merged_settings = merge_settings_export(export, generated_settings)
            settings_path = os.path.join(
                self._settings_folder(), f"{self._safe_name(os.path.splitext(os.path.basename(organ_path))[0])} "
                f"midi import candidate {time.time_ns()}.yaml",
            )
            with open(settings_path, "w", encoding="utf-8") as settings_file:
                yaml.safe_dump(merged_settings, settings_file, sort_keys=False, allow_unicode=True)

            candidate_stem = self._safe_name(os.path.splitext(os.path.basename(organ_path))[0])
            aliases_path = os.path.join(self._settings_folder(), f"{candidate_stem} combination aliases.yaml")
            write_transfer_alias_template(aliases_path, self.combination_set)
            aliases = load_transfer_aliases(aliases_path)
            target_set = self._safe_name(candidate_profile["name"])
            combinations_root = combination_root(self.cfg_path, self.combination_set)
            target_folder = os.path.join(combinations_root, "Combinations", target_set)
            source_set = str(aliases.get("source-combination-set") or self.combination_set)
            target_has_combinations = _contains_combinations(target_folder) if os.path.isdir(target_folder) else False
            transfer_report = {"status": "target-not-empty", "files": 0, "steps": 0,
                               "matched_objects": 0, "heuristic_matches": 0, "unmatched": []}
            combination_stage = os.path.join(stage_root, "Combinations")
            if not target_has_combinations and source_set != target_set:
                transfer_report = transfer_combinations(
                    os.path.join(combinations_root, "Combinations", source_set), combination_stage,
                    candidate_profile, aliases,
                )

            layout_stage = os.path.join(stage_root, f"{self._safe_name(os.path.splitext(os.path.basename(organ_path))[0])}.layout.yaml")
            spec_to_write = {key: value for key, value in candidate_spec.items()
                             if key not in ("notes", "problems")}
            with open(layout_stage, "w", encoding="utf-8") as layout_file:
                yaml.safe_dump(spec_to_write, layout_file, sort_keys=False, allow_unicode=True)
            self.pending_organ_import = {
                "organ_path": organ_path,
                "profile": candidate_profile,
                "spec": candidate_spec,
                "target_set": target_set,
                "target_folder": target_folder,
                "target_has_combinations": target_has_combinations,
                "layout_stage": layout_stage,
                "combination_stage": combination_stage,
                "transfer_report": transfer_report,
                "source_set": source_set,
                "aliases_path": aliases_path,
                "settings_path": settings_path,
                "generated_settings": merged_settings,
                "stage_root": stage_root,
            }
        except (OSError, ValueError, yaml.YAMLError) as exc:
            shutil.rmtree(stage_root, ignore_errors=True)
            if settings_path:
                try:
                    os.remove(settings_path)
                except OSError:
                    pass
            self._write_organ_import_log(organ_path, f"Preparation failed: {exc}; active organ unchanged", level="ERROR")
            self.organ_summary = f"Could not prepare this organ: {exc}. The current organ remains active."
            return

        report = self.pending_organ_import["transfer_report"]
        self.organ_settings_path = settings_path
        self.organ_summary = (
            f"Candidate ready: {candidate_profile['name']}. Import {settings_path} in GrandOrgue, load the organ, "
            "export MIDI settings, then press Confirm MIDI import. The current GUI/TUI organ remains active until verified. "
            + self._format_combination_transfer(report, source_set, self.pending_organ_import["aliases_path"])
        )
        self._write_organ_import_log(
            organ_path,
            f"Candidate prepared: {report['files']} combination files, {report['steps']} steps, "
            f"{report['matched_objects']} matched objects, {len(report['unmatched'])} omitted, "
            f"{report['heuristic_matches']} heuristic matches; staged settings={settings_path}",
        )
        self.br.dirty = True

    @staticmethod
    def _validate_organ_midi_export(export, organ_name):
        if not isinstance(export, dict) or not isinstance(export.get("objects"), list):
            raise ValueError("selected file is not a GrandOrgue MIDI Settings export with an objects list")
        info = export.get("info") or {}
        if str(info.get("content-type", "")).casefold() != "midi settings":
            raise ValueError("selected file is not labeled as GrandOrgue MIDI Settings")
        exported_organ = " ".join(str(info.get("organ-name", "")).casefold().split())
        expected_organ = " ".join(str(organ_name).casefold().split())
        if exported_organ and exported_organ != expected_organ:
            raise ValueError(f"MIDI export is for {info['organ-name']}, not {organ_name}")

    def discard_organ_import(self, reason):
        pending = self.pending_organ_import
        self.pending_organ_import = None
        if pending is not None:
            shutil.rmtree(pending["stage_root"], ignore_errors=True)
            self._write_organ_import_log(pending["organ_path"], reason, level="ERROR")
        self.organ_path = self.active_organ_path
        self.organ_settings_path = ""
        self.organ_summary = reason
        self.br.dirty = True

    def confirm_organ_import(self, export_path):
        import yaml

        pending = self.pending_organ_import
        if pending is None:
            self.organ_summary = "No staged organ import to confirm."
            return
        try:
            with open(export_path, encoding="utf-8") as export_stream:
                export = yaml.safe_load(export_stream) or {}
            self._validate_organ_midi_export(export, pending["profile"]["name"])
            result = compare_with_export(pending["generated_settings"], export)
        except (OSError, yaml.YAMLError, TypeError, ValueError) as exc:
            self.discard_organ_import(f"Could not verify GrandOrgue MIDI settings: {exc}. Previous organ retained.")
            return
        if result["mismatches"]:
            details = "; ".join(result["mismatches"][:5])
            self.discard_organ_import(
                f"GrandOrgue MIDI verification failed ({details}). Previous organ retained."
            )
            return
        self._commit_organ_import(pending)

    def _commit_organ_import(self, pending):
        root = project_root(self.cfg_path)
        organ_stem = self._safe_name(os.path.splitext(os.path.basename(pending["organ_path"]))[0])
        layout_folder = os.path.join(root, "Organs")
        layout_path = os.path.join(layout_folder, f"{organ_stem}.layout.yaml")
        target_folder = pending["target_folder"]
        config_backup = open(self.cfg_path, "rb").read()
        layout_backup = None
        if os.path.isfile(layout_path):
            layout_backup = open(layout_path, "rb").read()
        copied_combinations = []
        config_replaced = False
        layout_replaced = False
        try:
            os.makedirs(layout_folder, exist_ok=True)
            os.replace(pending["layout_stage"], layout_path)
            layout_replaced = True
            report = pending["transfer_report"]
            if (report["status"] == "ok" and report["files"]
                    and not pending["target_has_combinations"]):
                if _contains_combinations(target_folder):
                    raise ValueError("target combination folder gained files during import")
                os.makedirs(target_folder, exist_ok=True)
                for filename in os.listdir(pending["combination_stage"]):
                    source = os.path.join(pending["combination_stage"], filename)
                    target = os.path.join(target_folder, filename)
                    if os.path.exists(target):
                        raise ValueError(f"target combination already exists: {filename}")
                    shutil.copy2(source, target)
                    copied_combinations.append(target)

            descriptor, staged_config = tempfile.mkstemp(prefix="organ-config-", suffix=".yaml", dir=root)
            os.close(descriptor)
            shutil.copy2(self.cfg_path, staged_config)
            set_config_key(staged_config, "organ_path", pending["organ_path"])
            set_config_key(staged_config, "organ_layout_file",
                           os.path.relpath(layout_path, root).replace(os.sep, "/"))
            set_config_key(staged_config, "combination_set", pending["target_set"])
            os.replace(staged_config, self.cfg_path)
            config_replaced = True

            configure_layout(pending["spec"], source=os.path.basename(layout_path))
            self.br.configure_organ_controls(pending["profile"], pending["spec"])
        except (OSError, ValueError, KeyError) as exc:
            if config_replaced:
                descriptor, restore_config = tempfile.mkstemp(prefix="organ-config-restore-", suffix=".yaml", dir=root)
                os.close(descriptor)
                with open(restore_config, "wb") as restore_file:
                    restore_file.write(config_backup)
                os.replace(restore_config, self.cfg_path)
            if layout_replaced:
                if layout_backup is None:
                    try:
                        os.remove(layout_path)
                    except OSError:
                        pass
                else:
                    with open(layout_path, "wb") as layout_file:
                        layout_file.write(layout_backup)
            for path in copied_combinations:
                try:
                    os.remove(path)
                except OSError:
                    pass
            self.discard_organ_import(f"Import commit failed: {exc}. Previous organ retained.")
            return

        self.raw["organ_path"] = pending["organ_path"]
        self.raw["organ_layout_file"] = os.path.relpath(layout_path, root).replace(os.sep, "/")
        self.raw["combination_set"] = pending["target_set"]
        self.active_organ_path = pending["organ_path"]
        self.organ_path = pending["organ_path"]
        self.combination_set = pending["target_set"]
        self.organ_profile = pending["profile"]
        self.organ_spec = pending["spec"]
        self.organ_selection = pending["organ_path"]
        self.organ_selection_routes_ready = True
        self.br.state.clear()
        self.br.last_sent.clear()
        self.br.bank = 0
        self.br.text = ""
        self.br.pos = ""
        self.br.cued = False
        self.br.dirty = True
        self.combinations = load_combinations(self.cfg_path, self.raw)
        self.selected_combination_index = 0 if self.combinations else None
        self.loaded_combination_index = None
        self.loaded_switch_paths = None
        self._last_confirmed_identity = None
        self._last_feedback_cued = False
        self.pending_organ_import = None
        report = pending["transfer_report"]
        transfer = self._format_combination_transfer(report, pending["source_set"], pending["aliases_path"])
        self.organ_settings_path = pending["settings_path"]
        self.organ_summary = (
            f"{pending['profile']['name']} verified in GrandOrgue; GUI/TUI switched successfully. "
            f"Combinations/{pending['target_set']}{transfer}."
        )
        self._write_organ_import_log(
            pending["organ_path"],
            f"Import committed: {report['files']} combination files, {report['steps']} steps; "
            f"{report['matched_objects']} objects matched, {len(report['unmatched'])} omitted, "
            f"{report['heuristic_matches']} heuristic matches",
        )

    @staticmethod
    def _format_combination_transfer(report, source_set, aliases_path):
        if report is None:
            return ""
        if report["status"] == "target-not-empty":
            return " (existing target combination files left unchanged)"
        if report["status"] == "source-missing":
            return f" (source combination set {source_set} was not found)"
        if report["status"] == "no-source-combinations":
            return " (no source combination files found)"
        unmatched = len(report["unmatched"])
        detail = (f"; {unmatched} unmatched stop/switch references were omitted"
                  if unmatched else "")
        if unmatched:
            detail += f"; aliases: Settings/{os.path.basename(aliases_path)}"
        return (f" (copied {report['files']} files / {report['steps']} steps from "
                f"Combinations/{source_set}; {report['matched_objects']} matched objects, "
                f"{report['heuristic_matches']} heuristic matches{detail})")

    def _current_registration_paths(self):
        return {item.path for item in ITEMS if self.br.state.get(item.cc)}

    def _set_loaded_combination(self, index):
        if index is None or not 0 <= index < len(self.combinations):
            self.loaded_combination_index = None
            self.loaded_switch_paths = None
            return
        managed_paths = {item.path for item in ITEMS}
        self.loaded_combination_index = index
        self.loaded_switch_paths = frozenset(
            self.combinations[index]["switch_paths"] & managed_paths
        )
        # Once GrandOrgue's stop feedback has settled, the stops actually
        # drawn become the baseline, so quirks between file and organ never
        # look like user edits.
        self._baseline_settle_at = time.time() + 1.0

    def _sync_loaded_combination_from_feedback(self, load_confirmed=False):
        # A changed file/step identity while cued is only a pending selection;
        # wait for the cue to clear before treating it as the loaded step.
        if self.br.cued or not load_confirmed:
            return
        index = self._combination_index_from_feedback()
        if index is not None and index != self.loaded_combination_index:
            self._set_loaded_combination(index)

    BASELINE_QUIET_S = 0.8         # the organ must stop echoing stop changes this long before the baseline is adopted
    BASELINE_MAX_S = 6.0           # ...but never wait longer than this after a load

    def _baseline_ready(self, now):
        """True when the loaded stops have settled: the minimum settle time passed AND GrandOrgue has been quiet
        (or the hard cap passed). Stops that arrive late - a slow organ, or several loads in quick succession from
        the jog - are then still treated as the loaded combination, not as user edits."""
        if self._baseline_settle_at is None:
            return True
        if now < self._baseline_settle_at:
            return False
        quiet = now - getattr(self.br, "go_state_changed_at", 0.0) >= self.BASELINE_QUIET_S
        return quiet or now >= self._baseline_settle_at + self.BASELINE_MAX_S

    def _tick_baseline(self, now=None):
        """Adopt the settled registration as the baseline as soon as the organ has finished echoing the loaded
        stops. This must not wait for a navigation request or depend on the player state: otherwise stops
        changed while playing/testing get adopted as the baseline later, and reverting them looks dirty."""
        if self._baseline_settle_at is None or self.loaded_switch_paths is None:
            return
        now = now or time.time()
        if self._baseline_ready(now):
            self.loaded_switch_paths = frozenset(self._current_registration_paths())
            self._baseline_settle_at = None

    def _combination_is_dirty(self):
        """True when the stops currently drawn differ from the combination
        we think is selected -- i.e. someone has been tinkering with the
        registration without saving it anywhere yet."""
        self._tick_baseline()
        if self.br.player != "stopped":
            # Anywhere in the play cycle (playing or paused) counts as live:
            # impromptu performances can happen, so never interrupt with prompts.
            return False
        if self.loaded_combination_index is None or self.loaded_switch_paths is None:
            return False
        if self._baseline_settle_at is not None:
            return False                   # organ still echoing the loaded stops
        return frozenset(self._current_registration_paths()) != self.loaded_switch_paths

    def request_navigate(self, index):
        """Entry point for BOTH mouse-click and jog navigation. If the live
        registration doesn't match what's currently selected, hold off and
        let the UI ask the user whether to save it first -- it's easy to
        forget to save a good combination while tinkering, and better to
        ask than to silently lose it the moment they move on."""
        if not 0 <= index < len(self.combinations):
            return
        if self.preset_activation == "direct" and self._combination_is_dirty():   # staged: selecting changes nothing live
            self.pending_navigation_target = index
            return
        self.cue_combination(index)

    def resolve_pending_navigation(self, action):
        """action: 'update' (save over the current combination in place),
        'discard' (move on without saving), or 'cancel' (stay put)."""
        target = self.pending_navigation_target
        self.pending_navigation_target = None
        if target is None:
            return
        if action == "update":
            self._update_current_combination_stops()
        elif action == "discard":
            # Knowingly discarded: what is drawn now is no longer "changed".
            self.loaded_switch_paths = frozenset(self._current_registration_paths())
            self._baseline_settle_at = None
        if action != "cancel":
            self.cue_combination(target)

    def _update_current_combination_stops(self):
        """Quick in-place save: write the currently drawn stops into the
        currently selected combination's existing file/step."""
        import yaml

        loaded_index = self.loaded_combination_index
        if loaded_index is None:
            return
        selected = self.combinations[loaded_index]
        folder = os.path.join(
            combination_root(self.cfg_path, str(self.raw.get("combination_set", "Friesach"))),
            "Combinations", str(self.raw.get("combination_set", "Friesach")),
        )
        path = os.path.join(folder, selected["filename"])
        try:
            with open(path, encoding="utf-8") as combination_file:
                data = yaml.safe_load(combination_file) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.log(f"Could not update setter: {exc}", level="ERROR")
            return
        sequences = data.setdefault("sequencer", {})
        internal_id = selected["internal_id"]
        sequence_key = _normalized_mapping_key(sequences, internal_id)
        for candidate_key in list(sequences):
            try:
                candidate_id = f"{int(candidate_key):03d}"
            except (TypeError, ValueError):
                continue
            if candidate_id == internal_id and candidate_key != sequence_key:
                del sequences[candidate_key]
        sequence = cast(dict[str, Any], sequences.setdefault(
            sequence_key, {"manuals": {}, "switches": {}}))
        _write_managed_switches(sequence, self._current_registration_paths())
        try:
            with open(path, "w", encoding="utf-8") as combination_file:
                yaml.safe_dump(data, combination_file, sort_keys=False, allow_unicode=True, default_flow_style=False)
        except OSError as exc:
            self.log(f"Could not update setter: {exc}", level="ERROR")
            return
        self.combinations = load_combinations(self.cfg_path, self.raw)
        saved_index = next(
            (index for index, preset in enumerate(self.combinations)
             if preset["filename"] == selected["filename"]
             and preset["internal_id"] == internal_id), None)
        self.selected_combination_index = saved_index
        self._set_loaded_combination(saved_index)
        self.message = f"Updated setter {selected['filename']} #{internal_id}"
        self.br.dirty = True

    def _combination_index_from_feedback(self):
        current_name = " ".join(self.br.text.casefold().split())
        named_matches = [
            (index, preset) for index, preset in enumerate(self.combinations)
            if current_name == " ".join(preset["name"].casefold().split())
        ]
        matches = named_matches or [
            (index, preset) for index, preset in enumerate(self.combinations)
            if current_name == " ".join(os.path.splitext(preset["filename"])[0].casefold().split())
        ]
        if not matches:
            return None
        position = self.br.pos.strip()
        if position.isdigit():
            internal_id = f"{int(position):03d}"
            for index, preset in matches:
                if preset["internal_id"] == internal_id:
                    return index
        return matches[0][0]

    def save_combination_editor(self, payload):
        import yaml

        loaded_identity = None
        if self.loaded_combination_index is not None:
            loaded = self.combinations[self.loaded_combination_index]
            loaded_identity = (loaded["filename"], loaded["internal_id"])
        filename = os.path.basename(str(payload.get("filename", "")).strip())
        if not filename.lower().endswith((".yaml", ".yml")):
            filename += ".yaml"
        if not filename or filename in (".yaml", ".yml"):
            return
        folder = os.path.join(
            combination_root(self.cfg_path, str(self.raw.get("combination_set", "Friesach"))),
            "Combinations", str(self.raw.get("combination_set", "Friesach")),
        )
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        try:
            with open(path, encoding="utf-8") as combination_file:
                data = yaml.safe_load(combination_file) or {}
        except FileNotFoundError:
            data = {"info": {"content-type": "GrandOrgue Combinations",
                              "organ-name": str(self.raw.get("combination_set", "Friesach"))},
                    "sequencer": {}}
        selected_id = str(payload.get("selected_id", "000")).zfill(3)
        sequences = data.setdefault("sequencer", {})
        requested_ids = {str(step.get("id", "000")).zfill(3) for step in payload.get("steps", [])}
        seen_ids = set()
        for internal_id in list(sequences):
            normalized_id = str(internal_id).zfill(3)
            if normalized_id not in requested_ids or normalized_id in seen_ids:
                del sequences[internal_id]
            else:
                seen_ids.add(normalized_id)
        for step in payload.get("steps", []):
            internal_id = str(step.get("id", "000")).zfill(3)
            sequence_key = _normalized_mapping_key(sequences, internal_id)
            sequence = cast(dict[str, Any], sequences.setdefault(
                sequence_key, {"manuals": {}, "switches": {}}))
            sequence["name"] = str(step.get("name", "")).strip() or f"Step {internal_id}"
            # Rebuild this step's stops from whatever the editor actually
            # sent -- this is what lets a NEW or altered step be saved with
            # whichever stops were chosen in the dialog, instead of only
            # ever capturing whatever happens to be drawn live on the real
            # instrument for the one step that was already selected there.
            # If "stops" is omitted entirely (an older caller), this step's
            # existing stops are left untouched.
            if "stops" in step:
                _write_managed_switches(sequence, step["stops"])
        try:
            with open(path, "w", encoding="utf-8") as combination_file:
                yaml.safe_dump(data, combination_file, sort_keys=False, allow_unicode=True, default_flow_style=False)
        except OSError as exc:
            self.log(f"Could not save setter: {exc}", level="ERROR")
            return
        self.combinations = load_combinations(self.cfg_path, self.raw)
        self.selected_combination_index = next(
            (index for index, preset in enumerate(self.combinations)
             if preset["filename"] == filename and preset["internal_id"] == selected_id), None)
        if loaded_identity is not None:
            loaded_index = next(
                (index for index, preset in enumerate(self.combinations)
                 if (preset["filename"], preset["internal_id"]) == loaded_identity), None)
            self._set_loaded_combination(loaded_index)
        self.message = f"Saved setter {filename}"
        self.br.dirty = True

    def post_ui_event(self, event, value=None):
        self.ui_events.put((event, value))

    def process_ui_event(self, event, value):
        if event == "command":
            self.execute(str(value))
        elif event == "key":
            self.key(str(value))
        elif event == "pad":
            self.emit(self.br._pad_press(int(value), time.time()))
        elif event == "bank":
            self.br._change_bank((int(value) - self.br.bank) % len(BANKS))
        elif event == "volume":
            key, level = value
            if key in VOLS:
                self.emit(self.br._set_volume(key, int(level)))
        elif event == "combination":
            self.request_navigate(int(value))
        elif event == "cue_setter":
            self.request_navigate(int(value))
        elif event == "confirm_navigate":
            self.resolve_pending_navigation(str(value))
        elif event == "navigate_combination":
            self.navigate_combinations(int(value))
        elif event == "metro_down":
            self.br.begin_metro_hold(time.time())
        elif event == "metro_up":
            self.emit(self.br.end_metro_hold(time.time()))
        elif event == "metro_adjust":
            self.emit(self.br.adjust_metro(int(value)))
        elif event == "reload_config":
            self.reload_pad_settings()
        elif event == "theme":
            self.set_theme(str(value))
        elif event == "preset_activation":
            self.set_preset_activation(str(value))
        elif event == "save_combination":
            self.save_combination_editor(value)
        elif event == "menu_focus":
            self.br.set_menu_focus(value)
        elif event == "menu_tab":
            self.br.set_menu_tab(int(value))
        elif event == "toggle_switch":
            self.emit(self.br.toggle_cc(int(value), time.time()))
        elif event == "toggle_grid_switch":
            item = next((item for item in self.br.stop_grid.items if item.path == value), None)
            if item is not None:
                self.emit(self.br.toggle_cc(item.cc, time.time()))
        elif event == "stop_grid_mode":
            self.br.stop_grid_mode = bool(value)
            self.br.dirty = True
        elif event == "stop_grid_context":
            self.br.stop_grid_context = str(value)
            self.br.dirty = True
        elif event == "stop_grid_draft_paths":
            self.br.stop_grid_draft_paths = set(value or ())
            self.br.dirty = True
        elif event == "reload_combinations":
            self.combinations = load_combinations(self.cfg_path, self.raw)
            if self.selected_combination_index is not None and self.selected_combination_index >= len(self.combinations):
                self.selected_combination_index = 0 if self.combinations else None
            self.br.dirty = True
        elif event == "organ_path":
            self.organ_path = str(value)
        elif event == "organ_import":
            self.import_organ(value.get("organ_path", ""), value.get("midi_export", ""))
        elif event == "organ_confirm":
            self.confirm_organ_import(str(value))
        elif event == "organ_cancel":
            self.discard_organ_import("Organ import cancelled. The previous organ remains active.")
        elif event == "test_manuals":
            self.test_manuals()
        elif event == "chord":
            items, hold = value
            self.take_player.chord(items, hold)
        elif event == "take_tempo":
            self.take_player.speed = max(0.25, min(2.0, float(value) / 100.0))      # percent of the written tempo
        elif event == "preview_play":
            path, _, offset = str(value).partition("|@")       # "path|@seconds" starts part-way in
            self.set_take(path)
            self._start_take(path, offset=float(offset or 0.0))
        elif event == "take_seek":
            self.seek_take(float(value))
        elif event == "preview_stop":
            self.take_player.stop()
        elif event == "regs_apply":
            self.apply_voice_regs()
        elif event == "setter_marker":
            self.apply_setter_marker(str(value))
        elif event == "take_file":
            self.step_take_file(int(value))
        elif event == "take_toggle":
            if self.take_to_play and not self.br.sequence_mode:
                self.toggle_take_playback()
            else:
                self.post_ui_event("transport", "play")
        elif event == "take_open":
            self.set_take(str(value))
        elif event == "take_saveas":
            self.save_take_as(str(value))
        elif event == "transport":
            if value == "play" and self.take_to_play and not self.br.sequence_mode:
                self.toggle_take_playback()
                return
            if value == "stop" and self.take_player.active:
                self.take_player.stop()
                return
            notes = {
                "previous_step": N_REWIND, "next_step": N_FORWARD,
                "load": N_JOG_PRESS, "save": N_SAVE, "metro": N_METRO,
                "play": N_PLAY, "stop": N_STOP, "loop": N_LOOP,
            }
            if value in ("previous_file", "next_file"):
                midi_value = 64 if value == "previous_file" else 1
                message = self.backend.Message("control_change", channel=0, control=CC_JOG, value=midi_value)
                self.emit(self.br.from_daw(message, time.time()))
                return
            if value in ("previous_step", "next_step"):
                self.note_step(-1 if value == "previous_step" else 1)
            if value == "load" and self._activate_if_free():
                return
            note = notes.get(str(value))
            if note is not None:
                message = self.backend.Message("note_on", channel=0, note=note, velocity=127)
                self.emit(self.br.from_daw(message, time.time()))

    PANEL_SYSEX_NOTES = {0x16: N_CAT_CHAR, 0x17: N_PRESET, 0x18: N_NAV_LEFT, 0x19: N_NAV_RIGHT}

    def toggle_record(self, now=None):
        """Record button: first press starts a take, second saves it into the midi folder in two versions:
        'Take ....mid' (GrandOrgue: exactly as played) and 'Take .... (stave).mid' (Stave Friendly: bars straightened)."""
        from .take_recorder import make_midi_recorder, write_stave_friendly
        now = time.time() if now is None else now
        if self.midi_rec is None:
            if self.recorder is not None:
                self.recorder.close()
            self.take_player.stop()
            self.midi_rec = make_midi_recorder(self.midi_dir, log=lambda t, **k: self.log(t, notify=False))
            self.midi_rec._begin(now)
            self.midi_rec.path = self.midi_rec.path.replace("Take ", "Recording ")
            start = self.loaded_combination_index
            if start is None:
                start = self._combination_index_from_feedback()
            self.record_setter(start if start is not None else -1)
            self.log("Recording started (Record button again to stop)")
            return
        rec, self.midi_rec = self.midi_rec, None
        path = rec.path
        rec.close()
        if path and os.path.isfile(path):
            stave = path[:-4] + " (stave).mid"
            ok = write_stave_friendly(path, stave)
            self.take_to_play = path
            self.log(f"Recording saved: {os.path.basename(path)}" + (" + stave version" if ok else "")
                     + ". Press Play to hear it through GrandOrgue.")
        else:
            self.log("Recording was empty and not kept")

    def apply_setter_marker(self, text):
        """Markers from a playing MIDI file. SETTER|file|step|name: put the organ on that file + step (000-0xx).
        REG|manual|file|step|name: a voice registration - the stops of that manual are set like that setter's, and kept
        that way after later setter changes."""
        from .take_recorder import stave_module
        sm = stave_module('sessionmeta')
        reg = sm.parse_reg(text)
        if reg:
            manual, filename, internal_id, name = reg
            self._voice_regs[manual] = ("setter", filename, internal_id, name)
            self.apply_voice_regs()
            return
        stops = sm.parse_stops(text)
        if stops:
            manual, paths, label = stops
            self._voice_regs[manual] = ("stops", set(paths), label)
            self.apply_voice_regs()
            return
        parsed = sm.parse_marker(text)
        if not parsed:
            return
        filename, internal_id, name = parsed
        index = self._find_combination(filename, internal_id)
        if index is None:
            self.log(f"MIDI file asks for setter {internal_id} {name} [{filename}], which is not in the setter list", level="WARN")
            return
        self._activate_index(index)
        self.log(f"Setter {internal_id} {self.combinations[index]['name']} ({filename})", notify=False)
        if self._voice_regs:                       # the setter overwrote every manual: put the voice registrations back
            import threading
            threading.Timer(3.0, lambda: self.post_ui_event("regs_apply")).start()

    def _find_combination(self, filename, internal_id):
        for index, c in enumerate(self.combinations):
            if c["filename"] == filename and c["internal_id"] == internal_id:
                return index
        return None

    def apply_voice_regs(self):
        """For each registered manual set its stops to those of the chosen setter (other manuals are left alone)."""
        from .take_recorder import stave_module
        numbers = {name: int(path.rsplit("/", 1)[-1]) for name, path, _ch in stave_module('sessionmeta').MANUALS}
        now, out = time.time(), []
        for manual, reg in self._voice_regs.items():
            if manual not in numbers:
                continue
            if reg[0] == "stops":
                wanted = reg[1]
            else:
                _kind, filename, internal_id, name = reg
                index = self._find_combination(filename, internal_id)
                if index is None:
                    self.log(f"Registration {internal_id} {name} [{filename}] for {manual} not found", level="WARN")
                    continue
                wanted = self.combinations[index]["switch_paths"]
            for item in ITEMS:
                if item.kind == "stop" and item.manual == numbers[manual]:
                    if bool(self.br.state.get(item.cc)) != (item.path in wanted):
                        out += self.br.toggle_cc(item.cc, now)
        self.emit(out)

    def note_step(self, delta):
        """Hardware << / >> (or the GUI step buttons): the internal step 000-0xx of the active setter file moved.
        While recording this is a setter change like any other, so it is stored in the take as the combination reached."""
        if self.midi_rec is None:
            return
        current = self.__dict__.get("_rec_index")
        if current is None:
            current = self.loaded_combination_index
        if current is None or not 0 <= current < len(self.combinations):
            return
        same = [i for i, c in enumerate(self.combinations) if c["filename"] == self.combinations[current]["filename"]]
        position = same.index(current) + delta
        if 0 <= position < len(same):
            self.record_setter(same[position])

    def record_setter(self, index):
        self._rec_index = index
        if self.midi_rec is not None and 0 <= index < len(self.combinations):
            from .take_recorder import stave_module
            format_marker = stave_module('sessionmeta').format_marker
            c = self.combinations[index]
            self.midi_rec.marker(time.time(), format_marker(c["filename"], c["internal_id"], c["name"]))

    def list_takes(self):
        try:
            return sorted(os.path.join(self.midi_dir, f) for f in os.listdir(self.midi_dir)
                          if f.lower().endswith((".mid", ".midi")) and not f.startswith("_"))
        except OSError:
            return []

    def set_take(self, path):
        """Make this MIDI file the one Play plays (any file, not only the last recording)."""
        if path and os.path.isfile(path):
            self.take_player.stop()
            self.take_to_play = path
            self.take_length, self.take_info = 0.0, ""
            try:
                import mido
                self.take_length = mido.MidiFile(path).length
                from .take_recorder import stave_module
                sm = stave_module("sessionmeta")
                voices = sm.file_voices(path)
                if not sm.channel_map(path):                     # no remap yet: use what the file says its tracks are
                    auto = sm.auto_channel_map(path)
                    if auto:
                        sm.save_channel_map(path, auto)
                names = {sm.manual_channels()[i][2] - 1: sm.manual_channels()[i][0] for i in range(4)}
                cm = sm.channel_map(path)
                parts = [f"ch{c + 1}{(' ' + v['name']) if v['name'] else ''} > {names.get(cm.get(c, c), 'as file')}"
                         for c, v in sorted(voices.items()) if c != 9]
                self.take_info = "; ".join(parts[:6]) + (" ..." if len(parts) > 6 else "")
            except Exception:
                pass
            self.log(f"MIDI file loaded: {os.path.basename(path)} ({self.take_length:.0f} s). {self.take_info}", notify=False)

    def step_take_file(self, direction):
        """Previous / Next file = the neighbouring MIDI file in the midi folder."""
        files = self.list_takes()
        if not files:
            self.log("No MIDI files in the midi folder")
            return
        current = os.path.normcase(os.path.abspath(self.take_to_play)) if self.take_to_play else None
        names = [os.path.normcase(os.path.abspath(f)) for f in files]
        index = names.index(current) + direction if current in names else (0 if direction > 0 else len(files) - 1)
        self.set_take(files[index % len(files)])

    def save_take_as(self, target):
        """Save = Save As for the current take: copies it (and its stave version, if any) to the chosen name."""
        import shutil
        if not self.take_to_play or not os.path.isfile(self.take_to_play) or not target:
            self.log("No MIDI file to save")
            return
        if not target.lower().endswith((".mid", ".midi")):
            target += ".mid"
        shutil.copyfile(self.take_to_play, target)
        stave = self.take_to_play[:-4] + " (stave).mid"
        if os.path.isfile(stave):
            shutil.copyfile(stave, target[:-4] + " (stave).mid")
        self.take_to_play = target
        self.log(f"Saved as {os.path.basename(target)}")

    def test_manuals(self):
        """Sound one short note on each manual's file channel (Pedal, Hauptwerk, Schwellwerk, Solowerk), one after the
        other. Hearing all four means GrandOrgue is set up for MIDI-file playback; silence means import the settings."""
        import threading
        from .take_recorder import stave_module
        for i, (name, _path, ch) in enumerate(stave_module('sessionmeta').manual_channels()):
            note = 36 if name == "Pedal" else 60
            threading.Timer(i * 0.9, lambda c=ch - 1, n=note: self.take_player.chord([(c, n, 90)], 0.6)).start()
        self.log("Test: sounding Pedal, Hauptwerk, Schwellwerk, Solowerk in turn (listen for four notes)", notify=False)

    def seek_take(self, seconds, play_if_stopped=True):
        """Move playback to a position (seconds in the file); starts playing from there when stopped."""
        if not self.take_to_play:
            return
        if self.take_player.active:
            self.take_player.seek(seconds)
        elif play_if_stopped:
            self._start_take(self.take_to_play, offset=seconds)

    def _start_take(self, path, offset=0.0):
        self._voice_regs = {}
        worker = self.ports.workers.get("go_out") if hasattr(self.ports, "workers") else None
        if worker is not None and not worker.connected:
            self.log("Cannot play: the GrandOrgue output port (Bridge2GO) is not connected", level="WARN")
            return
        self.take_player.error = ""
        self.take_player.start(path, offset=offset, on_done=lambda: self.log(
            f"Playback finished: {self.take_player.sent} messages sent, {self.take_player.failed} not sent" + (f": {self.take_player.error}" if self.take_player.error else ""),
            notify=False))
        self.log(f"Playing {os.path.basename(path)} on the organ (GrandOrgue must listen on the manual channels: run "
                 "make_go_midi_import.py and import the result, once)", notify=False)

    def toggle_take_playback(self):
        if self.take_player.active:
            self.take_player.stop()
        else:
            self._start_take(self.take_to_play)

    PANEL_SYSEX_NOTES = {0x16: N_CAT_CHAR, 0x17: N_PRESET, 0x18: N_NAV_LEFT, 0x19: N_NAV_RIGHT}

    def handle_main_message(self, message, now):
        """MAIN-port message. When the keyboard is not in a clean DAW state, the panel buttons (Cat/Char, Preset,
        Nav arrows) arrive here as sysex F0 00 20 6B 7F 42 02 00 00 <id> <value> F7 instead of DAW-port notes;
        turn a press into the same DAW note so one code path handles both."""
        self._check_pad_note_form(message)
        if self.midi_rec is not None:
            self.midi_rec.feed(message, now)
        elif self.recorder is not None:
            self.recorder.feed(message, now)
        if message.type == "control_change" and message.control == CC_SUSTAIN and message.value < 64:
            self._pedal_down = False
        if message.type == "control_change" and message.control == CC_SUSTAIN and message.value >= 64:
            if self.combinations and not self._play_locked() and self.selected_combination_index is not None:
                if not self.__dict__.get("_pedal_down", False):   # one activation per press: swallow repeats while held
                    self._pedal_down = True
                    self.activate_selected()
                return
        if message.type == "sysex" and getattr(self.br, "accept_panel_sysex", True):
            d = list(message.data)
            if len(d) >= 10 and d[:7] == [0x00, 0x20, 0x6B, 0x7F, 0x42, 0x02, 0x00] and d[7] == 0x00:
                note = self.PANEL_SYSEX_NOTES.get(d[8])
                if getattr(self.br, "daw_trace", False):
                    self.pad_trace_sink(f"MAIN panel sysex id={d[8]:02X} value={d[9]:02X} -> "
                                        + (f"note {note:02X}" if note is not None else "unmapped"))
                if note is not None and d[9]:
                    self.handle_daw_message(self.backend.Message("note_on", channel=0, note=note, velocity=127), now, via_sysex=True)
                return
        elif getattr(self.br, "daw_trace", False) and message.type in ("control_change", "pitchwheel", "sysex"):
            self.pad_trace_sink(f"MAIN {message.type:<15} " + " ".join(f"{b:02X}" for b in message.bytes()))
        self.emit(self.br.from_main(message, now))

    PANEL_DEDUP_S = 0.4

    def _panel_duplicate(self, note, now, source):
        """The keyboard can report the same panel button twice (DAW-port note AND MAIN-port sysex). Handle the first,
        drop the other if it arrives within PANEL_DEDUP_S, so a toggle button is never toggled twice."""
        seen = self.__dict__.setdefault("_panel_seen", {})
        previous = seen.get(note)
        seen[note] = (source, now)
        return previous is not None and previous[0] != source and 0 <= now - previous[1] < self.PANEL_DEDUP_S

    def handle_daw_message(self, message, now, via_sysex=False):
        if message.type == "control_change" and message.control in (0x0F, 0x2F) and not self.br.hui_seen:
            self.br.hui_seen = True          # zone-select / port pairs are HUI, the Mackie map never sends them
            self.log("The DAW port is speaking HUI (zone/port CCs 0x0F/0x2F, faders on CC 0-7), not Mackie Control. "
                     "Buttons such as Part 1/Part 2 will not be recognised. Switch the keyboard back to Mackie Control "
                     "(Map Select / DAW mode setting, see KeyLab_GrandOrgue_HardwareSettings.md). Encoders are accepted "
                     "in HUI form as a stopgap.", level="WARN")
        if getattr(self.br, "daw_trace", False):
            channel = f"ch{message.channel + 1}" if hasattr(message, "channel") else "-"
            self.pad_trace_sink(f"DAW  {message.type:<15} {channel:>4} {' '.join(f'{b:02X}' for b in message.bytes())}")
        if (message.type == "note_on" and message.channel == 0 and message.velocity > 0
                and message.note in self.PANEL_SYSEX_NOTES.values()
                and self._panel_duplicate(message.note, now, "sysex" if via_sysex else "daw")):
            return
        modal = getattr(self, "modal_open", None)
        if modal is not None and modal.is_set() and self.modal_jog_handler is not None and self.modal_press_handler is not None:
            if message.type == "control_change" and message.control == CC_JOG:      # popup open: jog walks its buttons
                self.modal_jog_handler(-1 if message.value >= 64 else 1)
                return
            if message.type == "note_on" and message.channel == 0 and message.velocity > 0 and message.note == N_JOG_PRESS:
                self.modal_press_handler()                                           # jog press = click the focused button
                return
        hook = getattr(self, "stave_step_hook", None)
        if (hook is not None and message.type == "note_on" and message.channel == 0 and message.velocity > 0
                and message.note in (N_REWIND, N_FORWARD)):
            try:
                if hook(1 if message.note == N_FORWARD else -1):       # stave editor in step mode: it takes >> / <<
                    return
            except Exception:
                pass
        sheet = getattr(self, "sheet_music_navigation_enabled", None)
        if sheet is not None and sheet.is_set() and getattr(self, "sheet_jog_handler", None) is not None:
            # Sheet music open: jog walks its file/setter list, jog press acts on it, Cat/Char swaps the list.
            if message.type == "control_change" and message.control == CC_JOG:
                self.sheet_jog_handler(-1 if message.value >= 64 else 1)
                return
            if message.type == "note_on" and message.channel == 0 and message.velocity > 0:
                if message.note == N_JOG_PRESS:
                    self.sheet_press_handler()
                    return
                if message.note in (N_CAT_CHAR, N_SAVE, 0x57, 0x58):
                    if now - self.__dict__.get("_sheet_zone_at", -1.0) > 0.3:
                        self._sheet_zone_at = now
                        self.sheet_zone_handler()
                    return
        if message.type == "note_on" and message.channel == 0 and message.velocity > 0:
            if message.note in (N_REWIND, N_FORWARD):
                self.note_step(-1 if message.note == N_REWIND else 1)      # recorded; the press still reaches the organ
            if message.note == 0x5F:                                  # Record button: real start/stop recording
                self.toggle_record(now)
                return
            if message.note == N_PLAY and self.take_to_play and not self.br.sequence_mode:
                self.toggle_take_playback()                           # play the recorded take through GrandOrgue
                return
            if message.note == N_STOP and self.take_player.active:
                self.take_player.stop()
                return
        if message.channel == 0 and message.type == "note_on" and message.velocity > 0:
            if message.note == N_PRESET and self.br.stop_grid_ui_enabled:
                self.br.stop_grid_mode = not self.br.stop_grid_mode
                self.br.dirty = True
                return
            if message.note == N_CAT_CHAR:
                self.br.toggle_menu_override()          # plain on/off; the LED mirrors this state
                return
            if message.note == N_JOG_PRESS:
                if self.br.menu_override:
                    if self.menu_press_handler is not None:
                        self.menu_press_handler()
                    elif self.combinations:
                        index = self.selected_combination_index
                        if index is not None:
                            self.request_navigate(index)
                    return
                if self.br.menu_tab != 0 and self.main_press_handler is not None:
                    self.main_press_handler()
                    return
                if self.br.menu_tab != 0:
                    return
                if self._activate_if_free():
                    return
            if message.note in (N_NAV_LEFT, N_NAV_RIGHT):
                direction = -1 if message.note == N_NAV_LEFT else 1
                handler = getattr(self, "sheet_music_navigation_handler", None)
                enabled = getattr(self, "sheet_music_navigation_enabled", None)
                if handler is not None and enabled is not None and enabled.is_set():
                    handler(direction)           # sheet music window open: the arrows turn its pages
                    return
                if self.br.stop_grid_mode:
                    self.br.stop_grid_move_horizontal(direction)
                else:
                    self.br.step_menu_tab(direction)
                return
            if message.note in N_PREV_BANK:
                # Part 2 / Prev and its alternate code are physical stop-bank controls.
                self.br._change_bank(-1)
                return
            if message.note in N_NEXT_BANK:
                # Part 1 / Next and its alternate code are physical stop-bank controls.
                self.br._change_bank(1)
                return
            if message.note in (N_REWIND, N_FORWARD):
                # The physical >>/<< buttons step within the CURRENT
                # combination set's own sequence, in both play and stopped
                # states, regardless of preset_activation. They go straight
                # to GrandOrgue (bypassing cue_combination's file/step
                # routing entirely), so mirror that same move into our own
                # tracked index here -- otherwise the GUI/tree never
                # reflects where hardware navigation actually left things.
                self._step_selected_index(1 if message.note == N_FORWARD else -1)
        if message.type == "control_change" and message.control == CC_JOG:
            direction = -1 if message.value >= 64 else 1
            if self.br.metro_held:
                self.emit(self.br.adjust_metro(direction))
                return
            if self.br.stop_grid_mode:
                self.br.stop_grid_move_vertical(direction)
                return
            if self.br.menu_override:
                if self.menu_jog_handler is not None:
                    self.menu_jog_handler(direction)
                elif self.combinations:
                    self.navigate_combinations(direction)
                    if self.selected_combination_index is not None:
                        self.br.set_menu_focus(self.combinations[self.selected_combination_index]["name"])
                return
            if self.main_jog_handler is not None:
                self.main_jog_handler(direction)
                return
            if self.gui_hosted or self.br.menu_tab == 0:
                steps = max(1, message.value & 0x3F)
                self.navigate_combinations(direction * min(steps, self.br.jog_max))
                return
            self.br.set_menu_focus(MENU_PAGES[self.br.menu_tab]["abbr"])
            return
        self.emit(self.br.from_daw(message, now))

    VOLUME_MANUAL = {"pedal": 0, "hw": 1, "sw": 2, "sl": 3, "swell": 2}     # volume key -> manual it belongs to

    def _volume_activity(self):
        """{volume key: True (stops drawn) | False (none drawn) | None (this volume has no stops)} for the
        status light beside each volume slider; it follows setter loads and pad presses alike."""
        on_manuals = {item.manual for item in ITEMS if item.kind == "stop" and self.br.state.get(item.cc)}
        any_on = any(self.br.state.get(item.cc) for item in ITEMS)
        out = {}
        for key in VOLS:
            if key == "master":
                out[key] = any_on
            elif key in self.VOLUME_MANUAL:
                out[key] = self.VOLUME_MANUAL[key] in on_manuals
            else:
                out[key] = None
        return out

    def pad_lines(self, number, item, active):
        """Text lines for one pad tile at the configured verbosity. 1 = stop name (with [d] if it belongs to the
        loaded setter combination); 2 = + pad number and state; 3 = + CC number and division."""
        verbosity = self.br.pad_verbosity
        default = bool(self.loaded_switch_paths and item.path in self.loaded_switch_paths)
        name = ("[d]" if default else "") + item.name
        if verbosity <= 1:
            return [name]
        state = self.t("on") if active else self.t("off")
        head = f"{self.t('pad', number=number)}  {state}"
        if verbosity == 2:
            return [head, name]
        wire = f"{item.key}" if item.channel == STOP_CHANNELS[0] - 1 else f"ch{item.channel + 1} {item.key}"
        return [head, name, f"{self.t('cc')} {wire}  {item.division}"]

    def reload_pad_settings(self):
        """Re-read config.yaml and apply the pad display settings live (colours, dim, grey, verbosity)."""
        import yaml
        try:
            with open(self.cfg_path, encoding="utf-8") as stream:
                raw = yaml.safe_load(stream) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.log(f"Could not reload config.yaml: {exc}", level="WARN")
            return
        self.raw = raw
        settings = bridge_settings(raw)
        for key, attribute in (("pad_dim", "pad_dim"), ("pad_colors", "pad_colors"),
                               ("pad_verbosity", "pad_verbosity"), ("pad_off_grey", "pad_off_grey"),
                               ("note_pads", "note_pads"), ("note_pad_first", "note_pad_first"),
                               ("ch1_aftertouch_pads", "ch1_aftertouch_pads"), ("pad_trace", "pad_trace"), ("daw_trace", "daw_trace")):
            if key in settings:
                value = settings[key]
                if key == "pad_colors":
                    value = {**self.br.pad_colors, **value}
                setattr(self.br, attribute, value)
        if "note_pad_channel" in settings:
            self.br.note_pad_channel = max(1, min(16, int(settings["note_pad_channel"]))) - 1
        self.br.leds_sent.clear()            # resend every LED with the new look
        self.br.dirty = True
        self.log("config.yaml saved; pad display settings applied (other changes need a restart, F5)", notify=False)

    def publish_snapshot(self):
        br = self.br
        if self.pending_navigation_target is not None and br.player != "stopped":
            # Play started while a save prompt was pending: never interrupt a
            # performance. Carry on to the requested combination without asking.
            self.resolve_pending_navigation("discard")
        bank = BANKS[br.bank]
        lcd_lines = br._idle_lines()
        if br.detail_pending:
            lcd_lines = br.detail_pending[:2]
        pad_items = br.stop_grid.mapped_slots() if br.stop_grid_mode else bank["items"]
        draft_grid = br.stop_grid_mode and br.stop_grid_context == "draft"
        pads = []
        for index, item in enumerate(pad_items):
            if item is None:
                pads.append({"number": index + 1, "name": "", "division": "", "cc": None, "lines": [],
                             "path": None, "active": False, "color": UNASSIGNED_PAD_COLOR, "wire": ""})
                continue
            active = (item.path in br.stop_grid_draft_paths if draft_grid
                      else bool(br.state.get(item.cc)))
            pads.append({
                "number": index + 1, "name": item.name, "division": item.division,
                "cc": item.cc, "path": item.path, "active": active,
                "lines": self.pad_lines(index + 1, item, active),
                "color": pad_screen_color(item, br.pad_colors, active, br.pad_dim, br.pad_off_grey),
                # the real wire address: bare "CC n" on the first stop channel, "ch13 CC n" on a spill channel
                "wire": (f"{item.key}" if item.channel == STOP_CHANNELS[0] - 1 else f"ch{item.channel + 1} {item.key}"),
            })
        while len(pads) < 8:
            pads.append({"number": len(pads) + 1, "name": "", "division": "", "cc": None, "lines": [],
                         "active": False, "color": UNASSIGNED_PAD_COLOR})
        active_stops = [f"{item.bank_code}  {item.name}" for item in ITEMS
                        if item.kind == "stop" and self.br.state.get(item.cc)]
        stop_grid_rows = [{
            "division": row["division"],
            "grid_row": row["grid_row"],
            "focus_x": row["focus_x"],
            "cells": ([{"path": item.path, "name": item.name, "cc": item.cc,
                        "division": item.division}
                       if item is not None else None for item in row["cells"]]),
        } for row in br.stop_grid.window_rows()]
        if self.selected_combination_index is None:
            self.selected_combination_index = self._combination_index_from_feedback()
            if self.selected_combination_index is None and self.combinations:
                self.selected_combination_index = 0
        current_position = br.pos.strip()
        current_identity = (
            " ".join(br.text.casefold().split()),
            f"{int(current_position):03d}" if current_position.isdigit() else current_position,
        )
        identity_changed = current_identity != self._last_confirmed_identity
        activating = time.time() < getattr(self, "_activation_until", 0.0)   # we just moved the organ: ignore its echo
        if activating and not br.cued and getattr(self, "_steps_item", None) not in br.scheduled \
                and self._combination_index_from_feedback() == self.loaded_combination_index:
            self._activation_until, activating = 0.0, False         # organ now shows what we asked for
        load_confirmed = not br.cued and (identity_changed or self._last_feedback_cued) and not activating
        if not br.cued and identity_changed and not activating:
            self._last_confirmed_identity = current_identity
            index = self._combination_index_from_feedback()
            if index is not None:
                self.selected_combination_index = index
        self._last_feedback_cued = br.cued
        self._sync_loaded_combination_from_feedback(load_confirmed=load_confirmed)
        active_combination_index = self.loaded_combination_index
        snapshot = {
            "title": self.t("title"), "language": self.language, "language_names": dict(LANGUAGE_NAMES),
            "theme": self.theme, "message": self.message, "status": self.status_row(), "lcd": tuple(lcd_lines),
            "bank_index": br.bank, "banks": [f"{b['code']} {b['division']}" for b in BANKS],
            "marks": br._bank_marks(), "pads": pads,
            "mark_legend": self.t("mark_legend"),
            "combinations": [{"name": preset["name"], "filename": preset["filename"],
                              "internal_id": preset["internal_id"],
                              "switch_paths": sorted(preset["switch_paths"])}
                             for preset in self.combinations],
            "available_stops": [{"path": item.path, "name": item.name, "division": item.division,
                                  "kind": item.kind, "cc": item.cc} for item in br.stop_grid.items],
            "active_stop_paths": sorted(self._current_registration_paths()),
            "stop_grid": {
                "available": br.stop_grid_ui_enabled,
                "mode": br.stop_grid_mode,
                "context": br.stop_grid_context,
                "focus_x": br.stop_grid.focus_x,
                "focus_y": br.stop_grid.focus_y,
                "focus_division": stop_grid_rows[0]["division"] if stop_grid_rows else "",
                "mapped_paths": br.stop_grid.mapped_paths() if br.stop_grid_mode else [],
                "rows": stop_grid_rows,
                "draft_paths": sorted(br.stop_grid_draft_paths),
            },
            "confirm_navigate": (
                {
                    "target_name": self.combinations[self.pending_navigation_target]["name"],
                    "current_name": (
                        self.combinations[self.loaded_combination_index]["name"]
                        if self.loaded_combination_index is not None else ""
                    ),
                }
                if self.pending_navigation_target is not None else None
            ),
            "combination_index": self.selected_combination_index,
            "active_combination_index": active_combination_index,
            "internal_position": br.pos.strip(),
            "preset_activation": self.preset_activation,
            "active_stops": active_stops, "metro_bpm": br.metro_bpm, "metro_lit": br.metro_lit,
            "volumes": {key: br.vol_sent.get(key, br.vol[key]) for key in VOLS},
            "volume_active": self._volume_activity(),
            "menu": {"tab": br.menu_tab, "active": br.menu_override, "pages": [dict(page) for page in MENU_PAGES]},
            "couplings": [{"cc": item.cc, "name": item.name, "division": item.division,
                           "active": bool(br.state.get(item.cc))}
                          for item in ITEMS if item.kind in ("coupler", "tremulant")],
            "combination_files": list(dict.fromkeys(preset["filename"] for preset in self.combinations)),
            "organ_path": self.organ_path,
            "organ_summary": self.organ_summary,
            "organ_settings_path": self.organ_settings_path,
            "organ_import_pending": self.pending_organ_import is not None,
            "organ_routes_ready": not self.organ_switching,
            "organ_selection": self.organ_selection,
            "organ_switching": self.organ_switching,
            "debug": self.debug,
            "debug_text": "\n".join(self.connection_rows() + self.layout_rows() + self.organ_rows() +
                                      self.registration_rows() + self.event_rows(14)),
        }
        with self.snapshot_lock:
            self._ui_snapshot = snapshot

    def get_snapshot(self):
        with self.snapshot_lock:
            return self._ui_snapshot

    def make_bridge(self):
        bridge = Bridge(threshold=self.args.threshold, hold_s=self.args.hold, refresh_s=self.args.refresh,
                        live_s=self.args.live, **self.br_settings)
        bridge.stop_grid_ui_enabled = getattr(self, "gui_hosted", False)
        bridge.stop_grid_pad_handler = self.stop_grid_pad_handler
        bridge.trace_sink = self.pad_trace_sink
        return bridge

    def pad_trace_sink(self, text):
        """testing.pad_trace: every pad-related MAIN message goes to the log and to Logs/pad_trace.txt."""
        stamp = time.strftime("%H:%M:%S")
        self.log(text, notify=False, level="TRACE")
        try:
            folder = os.path.join(project_root(self.cfg_path), "Logs")
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "pad_trace.txt"), "a", encoding="utf-8") as out:
                out.write(f"{stamp} {text}\n")
        except OSError:
            pass

    def log(self, text, notify=True, level="INFO"):
        stamp = time.strftime("%H:%M:%S")
        self.recent.append(f"{stamp} {level:<5} {text}")
        if notify:
            self.message = text

    def debug_log(self, text):
        if self.debug:
            self.log(text, notify=False, level="DEBUG")

    def start(self):
        self.log(self.t("message_settings_path", path=self.cfg_path) if self.raw else self.t("message_settings_builtin"))
        self.log(self.t("message_version", version=__version__))
        self.ports.open_all()
        self.last_reconnect_attempt = time.perf_counter()
        for key in sorted(self.ports.errors):
            self.log(self.t("message_port_error", port=key, error=self.ports.errors[key]), level="WARN")
        missing = [key for key in self.ports.required() if not self.ports.connected(key)]
        if missing:
            self.log(self.t("message_waiting_ports", ports=", ".join(missing)), level="WARN")
        elif self.ports.degraded():
            self.log(self.t("message_main_wait"), level="WARN")
        else:
            self.log(self.t("message_all_links"))
        self.log(self.t("message_controls"))

    def emit(self, outputs):
        for output in outputs:
            target = output["to"]
            port_key = "go_out" if target == "go" else "kl_out"
            if target == "go":
                message = self.backend.Message("control_change", channel=output["ch"], control=output["cc"], value=output["val"])
            else:
                message = self.backend.Message("sysex", data=output["data"])
            if self.ports.send(port_key, message) and target == "kl":
                self.debug_log(f"TX KL  SysEx {len(output['data'])} bytes")

    def drain_port(self, key, count_key, handler, sysex=False):
        for message in self.ports.drain_input(key):
            self.stats[count_key] += 1
            self.recent_times[key] = time.time()
            if not sysex or message.type != "sysex":
                self.debug_log(f"RX {key.upper()} {message}")
            handler(message)

    def _check_pad_note_form(self, message):
        """Tell the user once if the pads arrive as channel-10 notes (the post-reset / User-map form)."""
        if (not getattr(self, "_pad_note_warned", False) and message.type in ("note_on", "note_off")
                and message.channel == 9 and 0x24 <= message.note <= 0x2B):
            self._pad_note_warned = True
            if getattr(self.br, "note_pads", False):
                self.log("Pads are arriving as channel-10 NOTES (36-43); accepted because testing.accept_note_pads is on. "
                         "This is not the DAW-mode baseline (CCs on channel 1): see KeyLab_GrandOrgue_HardwareSettings.md.",
                         level="WARN")
            else:
                self.log("Pads are arriving as channel-10 NOTES (36-43) and testing.accept_note_pads is off, so pad "
                         "presses are ignored. Turn that option on, or use the HUI -> Mackie Control round trip.",
                         level="WARN")

    def poll_midi(self, now):
        self._tick_baseline(now)
        self.drain_port("kl_in", "daw_in", lambda message: self.handle_daw_message(message, now))
        if self.ports.relay_queue is not None and self.args.relay_main:
            overflow_count = self.ports.take_relay_overflows()
            if overflow_count:
                self.log(f"MAIN relay queue overflowed; dropped {overflow_count} messages; panic sent", level="ERROR")
                self.ports.clear_relay_queue()
                self.send_panic(quiet=True)
            for message in self.ports.drain_relay_queue():
                self.recent_times["main_in"] = now
                self.debug_log(f"RX MAIN {message}")
                sustain = message.type == "control_change" and message.control == CC_SUSTAIN
                if not sustain:
                    self.ports.send_relay_message(message)
                self.handle_main_message(message, now)
        else:
            self.drain_port("main_in", "main_in", lambda message: self.handle_main_message(message, now))
        self.drain_port("go_in", "go_in", lambda message: self.emit(self.br.from_go(message, now)), sysex=True)
        for key, error in self.ports.take_error_events():
            self.log(f"{key} MIDI worker failed: {error}", level="ERROR")

    def send_panic(self, quiet=False, reset_all_channels=True):
        if not self.ports.connected("go_out"):
            return
        messages = [self.backend.Message("control_change", channel=CMD_CH, control=CMD["panic"], value=127),
                    self.backend.Message("control_change", channel=CMD_CH, control=CMD["panic"], value=0)]
        if reset_all_channels:
            reserved = {CMD_CH, 13, 11} | {c - 1 for c in STOP_CHANNELS}      # controls 120+ live on these channels
            for channel in (c for c in range(16) if c not in reserved):
                messages.extend([self.backend.Message("control_change", channel=channel, control=120, value=0),
                                self.backend.Message("control_change", channel=channel, control=121, value=0),
                                self.backend.Message("control_change", channel=channel, control=123, value=0)])
        if not self.ports.send_batch("go_out", messages):
            if not quiet:
                self.log("panic could not be queued", level="ERROR")
            return
        if not quiet:
            self.log(self.t("message_panic"))

    def resync(self):
        self.emit(self.br.resync_outputs())
        self.log(self.t("message_resync"))

    def reconnect(self, manual=True):
        if self.ports.connected("go_out"):
            self.send_panic(quiet=True)
        self.ports.open_all()
        if manual:
            self.reconnect_delay = 3.0
            self.last_reconnect_attempt = time.perf_counter()
        self.reconnects += 1
        for key in sorted(self.ports.errors):
            self.log(self.t("message_port_error", port=key, error=self.ports.errors[key]), level="WARN")
        self.log(self.t("message_reopened") if not self.ports.degraded() else self.t("message_reopened_partial"), level="WARN" if self.ports.degraded() else "INFO")
        if not self.ports.needs_reconnect():
            self.resync()

    def recover(self):
        self.br._detail("RECOVERY", "reopening MIDI links")
        self.send_panic()
        self.reconnect()
        self.br._detail("RECOVERY", "links restored" if not self.ports.degraded() else "waiting for links")
        self.log(self.t("message_recovery_done") if not self.ports.degraded() else self.t("message_recovery_wait"), level="INFO" if not self.ports.degraded() else "WARN")

    def restart(self):
        self.send_panic(quiet=True)
        try:                                   # pick up config.yaml edits (the Config tab saves to the file)
            import yaml
            with open(self.cfg_path, encoding="utf-8") as stream:
                self.raw = yaml.safe_load(stream) or {}
            self.br_settings = bridge_settings(self.raw)
        except Exception as exc:
            self.log(f"Restart kept the previous settings; config.yaml could not be read: {exc}", level="WARN")
        self.ports.open_all()
        self.br = self.make_bridge()
        if self.organ_profile is not None and self.organ_spec is not None:
            self.br.configure_organ_controls(self.organ_profile, self.organ_spec)
        self.restarts += 1
        self.log(self.t("message_restart"), level="WARN")

    def clear(self):
        self.recent.clear()
        self.message = self.t("message_clear")

    def execute(self, command):
        text = command.strip().lower()
        if not text:
            return
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            self.message = f"Command parse error: {exc}"
            return
        if len(parts) >= 2 and parts[0].casefold() == "organ" and parts[1].casefold() == "import":
            if len(parts) != 4:
                self.message = 'Usage: organ import "organ-file.organ" "midi-export.yaml"'
            else:
                self.import_organ(parts[2], parts[3])
        elif len(parts) == 3 and parts[0].casefold() == "organ" and parts[1].casefold() == "confirm":
            self.confirm_organ_import(parts[2])
        elif len(parts) == 2 and parts[0].casefold() == "organ" and parts[1].casefold() == "cancel":
            self.discard_organ_import("Organ import cancelled from console. Previous organ remains active.")
        elif text in ("quit", "exit"):
            self.running = False
            self.message = self.t("message_quit")
        elif text in ("help", "?"):
            self.ui.help = True
            self.message = self.t("message_help")
        elif text == "status":
            self.message = self.t("running") if not self.ports.degraded() else self.t("degraded")
        elif text == "language" or text.startswith("language "):
            parts = text.split()
            if len(parts) == 1:
                self.message = self.t("language_current", name=LANGUAGE_NAMES[self.language], code=self.language)
            elif len(parts) == 2:
                self.set_language(parts[1])
            else:
                self.message = self.t("language_usage")
        elif text == "theme" or text.startswith("theme "):
            parts = text.split()
            if len(parts) == 1:
                self.message = self.t("theme_current", name=self.t(f"theme_{self.theme}"))
            elif len(parts) == 2:
                if parts[1] not in ("light", "dark", "contrast"):
                    self.message = self.t("theme_usage")
                elif self.set_theme(parts[1]):
                    self.message = self.t("theme_changed", name=self.t(f"theme_{self.theme}"))
            else:
                self.message = self.t("theme_usage")
        elif text == "preset-mode" or text.startswith("preset-mode "):
            parts = text.split()
            if len(parts) == 2 and self.set_preset_activation(parts[1]):
                self.message = self.t("preset_mode_changed", name=self.t("preset_mode_direct" if self.preset_activation == "direct" else "preset_mode_staged"))
            else:
                self.message = self.t("preset_mode_usage")
        elif text in ("debug", "debug toggle"):
            self.debug = not self.debug
            self.message = self.t("debug_on" if self.debug else "debug_off")
        elif text in ("debug on", "debug enable"):
            self.debug = True
            self.message = self.t("debug_on")
        elif text in ("debug off", "debug disable"):
            self.debug = False
            self.message = self.t("debug_off")
        elif text in ("reconnect", "connect"):
            self.reconnect()
        elif text in ("recover", "repair"):
            self.recover()
        elif text in ("resync", "sync"):
            self.resync()
        elif text in ("restart", "engine"):
            self.restart()
        elif text == "panic":
            self.send_panic()
        elif text in ("clear", "cls"):
            self.clear()
        else:
            self.message = self.t("message_unknown_command", command=command)

    def key(self, key):
        if key == "F6":
            self.br.toggle_menu_override()
        elif key == "LEFT" and not self.ui.command:
            self.br.step_menu_tab(-1)
        elif key == "RIGHT" and not self.ui.command:
            self.br.step_menu_tab(1)
        elif key in ("UP", "DOWN") and not self.ui.command:
            value = 64 if key == "UP" else 0
            message = self.backend.Message("control_change", channel=0, control=CC_JOG, value=value)
            self.handle_daw_message(message, time.time())
        elif key == "ENTER" and not self.ui.command and (self.br.menu_override or self.br.menu_tab != 0):
            message = self.backend.Message("note_on", channel=0, note=N_JOG_PRESS, velocity=127)
            self.handle_daw_message(message, time.time())
        elif key == "F1":
            self.ui.help = not self.ui.help
            self.ui.help_scroll = 0
        elif key == "F2":
            self.execute("debug")
        elif key == "F3":
            self.reconnect()
        elif key == "F4":
            self.recover()
        elif key == "F5":
            self.restart()
        elif key == "F8":
            self.resync()
        elif key == "F9":
            self.clear()
        elif key == "F10" or key == "QUIT":
            self.running = False
            self.message = self.t("message_quit")
        elif key == "TAB":
            self.ui.help = not self.ui.help
        elif key == "ESC":
            self.ui.command = ""
            self.ui.cursor = 0
            self.ui.help = False
        elif key == "CLEAR":
            self.clear()
        elif key == "PAGEUP":
            self.ui.help_scroll = max(0, self.ui.help_scroll - 3)
        elif key == "PAGEDOWN":
            self.ui.help_scroll += 3
        elif key == "ENTER":
            command = self.ui.command
            self.ui.command = ""
            self.ui.cursor = 0
            self.execute(command)
        elif key == "BACKSPACE":
            if self.ui.cursor:
                self.ui.command = self.ui.command[:self.ui.cursor - 1] + self.ui.command[self.ui.cursor:]
                self.ui.cursor -= 1
        elif key == "DELETE":
            if self.ui.cursor < len(self.ui.command):
                self.ui.command = self.ui.command[:self.ui.cursor] + self.ui.command[self.ui.cursor + 1:]
        elif key == "LEFT":
            self.ui.cursor = max(0, self.ui.cursor - 1)
        elif key == "RIGHT":
            self.ui.cursor = min(len(self.ui.command), self.ui.cursor + 1)
        elif key == "HOME":
            self.ui.cursor = 0
        elif key == "END":
            self.ui.cursor = len(self.ui.command)
        elif len(key) == 1 and key.isprintable():
            self.ui.command = self.ui.command[:self.ui.cursor] + key + self.ui.command[self.ui.cursor:]
            self.ui.cursor += 1

    def layout_rows(self):
        return [f"Layout  {ACTIVE_LAYOUT['source']}  {len(ITEMS)} controls on MIDI ch {','.join(str(c) for c in STOP_CHANNELS)}, {len(BANKS)} banks   "
                f"organ: {self.active_organ_path or 'not set'}   setters: Combinations/{self.combination_set}"]

    def connection_rows(self):
        roles = [("role_daw_in", "kl_in"), ("role_daw_out", "kl_out"),
                 ("role_go_in", "go_in"), ("role_go_out", "go_out")]
        if self.args.relay_main:
            roles += [("role_main_relay", "main_in"), ("role_relay_out", "relay_out")]
        elif self.args.kl_main:
            roles += [("role_main_in", "main_in")]
        rows = [f"{self.t('engine')}  {self.t('running') if not self.ports.degraded() else self.t('degraded')}  up {ConsoleUI.uptime(time.perf_counter() - self.started)}  "
                f"restarts {self.restarts}  reconnects {self.reconnects}"]
        for label_key, key in roles:
            state = self.t("link_ok") if self.ports.connected(key) else self.t("link_error")
            label = self.t(label_key)
            name = self.ports.actual.get(key, self.ports.wanted(key) or "not configured")
            age = self.recent_times.get(key)
            if age:
                age_text = f"last {max(0, time.time() - age):.1f}s"
            else:
                age_text = self.t("no_rx") if key.endswith("_in") else self.t("ready")
            rows.append(f"[{state}] {label:<10} {name}  {age_text}")
        average = self.stats["loop_total"] / self.stats["loops"] if self.stats["loops"] else 0.0
        rows.append(f"{self.t('traffic')} RX DAW {self.stats['daw_in']} / MAIN {self.stats['main_in']} / GO {self.stats['go_in']}   "
                    f"TX GO {self.stats['go_out']} / KeyLab {self.stats['kl_out']}")
        rows.append(f"{self.t('loop_average')} {average * 1000:.2f} ms   max {self.stats['loop_max'] * 1000:.2f} ms   "
                    f"errors {self.stats['errors']}   relay queue {self.ports.relay_queue.qsize()}   "
                    f"worker drops TX {sum(worker.dropped_output for worker in self.ports.workers.values())} / "
                    f"RX {sum(worker.dropped_input for worker in self.ports.workers.values())}")
        if self.ports.degraded():
            rows.append(self.t("auto_repair"))
        else:
            rows.append(self.t("links_healthy") if self.stats["go_in"] else
                        f"Ports open, but GrandOrgue has not answered yet. In GrandOrgue (Audio/MIDI > Settings > MIDI Devices) enable "
                        f"input '{self.ports.wanted('go_out')}' and output '{self.ports.wanted('go')}', import the bridge MIDI settings "
                        f"yaml for the loaded organ, and start loopMIDI before GrandOrgue.")
        return rows

    def status_row(self):
        br = self.br
        source = "EXE" if getattr(sys, "frozen", False) or "__compiled__" in globals() else "PYTHON"
        links = self.t("midi_ok") if not self.ports.degraded() else self.t("midi_degraded")
        feedback = self.t("feedback_ok") if self.stats["go_in"] else self.t("feedback_wait")
        player = self.t("player", value=br.player.upper())
        loop = self.t("loop_on") if br.loop else self.t("loop_off")
        diagnostics = self.t("debug_on") if self.debug else self.t("debug_off")
        return f"[{source}]  |  {links}  |  {feedback}  |  {player}  |  {loop}  |  {diagnostics}  |  {self.message}"

    def organ_rows(self):
        br = self.br
        filename = br.text or "GrandOrgue"
        name1, name2 = split_lines(filename, 27)
        organ_name = self.organ_profile["name"] if self.organ_profile else os.path.basename(self.active_organ_path)
        state = (f"{self.t('player_lower')} {br.player}  {self.t('loop_lower')} "
             f"{self.t('on') if br.loop else self.t('off')}  {self.t('metro_lower')} "
             f"{self.t('on') if br.metro_lit else self.t('off')}")
        active = sum(1 for value in br.state.values() if value)
        rows = [f"{self.t('feedback')}  {self.t('link') if self.ports.connected('go_in') else self.t('no_link')}",
            f"Organ      {organ_name}",
            f"Setters    {self.combination_set} ({len(self.combinations)} steps)",
            f"Import     {'PENDING' if self.pending_organ_import else 'verified' if self.organ_profile else 'not set'}",
            f"{self.t('file')}       {name1}", f"          {name2}",
            f"{self.t('step')}       {br.pos or '-'}{'  cued' if br.cued else ''}", state,
            f"{self.t('stops')}      {self.t('stops_count', active=active, total=len(ITEMS))}"]
        for key, (_cc, _path, label) in VOLS.items():
            value = br.vol_sent.get(key, br.vol[key])
            filled = round(value / 127 * 10)
            rows.append(f"{label[:8].upper():<8} [{'#' * filled}{'.' * (10 - filled)}] {round(value * 100 / 127):3d}%")
        return rows

    def registration_rows(self):
        bank = BANKS[self.br.bank]
        rows = [f"{self.t('bank_switch')} {bank['code']}  {bank['division']}   {self.t('marks')} {self.br._bank_marks()}", f"{self.t('state'):<5} {'CC':<4} {self.t('stop_switch')}"]
        for item in bank["items"]:
            rows.append(f"{(self.t('on') if self.br.state.get(item.cc) else self.t('off')):<5} {item.cc:<4} {item.name}")
        return rows

    def help_rows(self):
        return translate(self.language, "help_rows") + [self.t("gui_marks_legend"), self.t("theme_command_help")]

    def event_rows(self, count):
        rows = list(self.recent)[-max(0, count):]
        return rows or [self.t("no_events")]

    def run(self):
        self.start()
        self.ui.start(self)
        if not self.ui.enabled and not self.gui_hosted:
            for line in list(self.recent)[-8:]:
                print(line)
        self.publish_snapshot()
        last_draw = 0.0
        previous_loop = time.perf_counter()
        try:
            while self.running:
                loop_started = time.perf_counter()
                self.stats["loops"] += 1
                self.stats["loop_total"] += loop_started - previous_loop
                self.stats["loop_max"] = max(self.stats["loop_max"], loop_started - previous_loop)
                previous_loop = loop_started
                now = time.time()
                self.poll_midi(now)
                self.emit(self.br.tick(now))
                if self.midi_rec is not None:
                    self.midi_rec.poll(now)
                elif self.recorder is not None:
                    self.recorder.poll(now)
                while True:
                    try:
                        event, value = self.ui_events.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self.process_ui_event(event, value)
                    except Exception:
                        self.log(f"Action '{event}' failed: " + traceback.format_exc(limit=4).strip().splitlines()[-1],
                                 level="ERROR")
                        self.debug_log(traceback.format_exc())
                for key in self.ui.read_keys():
                    try:
                        if key.startswith("COMMAND:"):
                            self.execute(key[8:])
                        else:
                            self.key(key)
                    except Exception:
                        self.log(f"Key '{key}' failed: " + traceback.format_exc(limit=4).strip().splitlines()[-1],
                                 level="ERROR")
                if self.ui.enabled and time.perf_counter() - last_draw >= 0.2:
                    self.ui.draw(self)
                    last_draw = time.perf_counter()
                if self.ports.needs_reconnect() and time.perf_counter() - self.last_reconnect_attempt >= self.reconnect_delay:
                    self.last_reconnect_attempt = time.perf_counter()
                    self.reconnect(False)
                    self.reconnect_delay = min(30.0, self.reconnect_delay * 2.0)
                elif not self.ports.needs_reconnect():
                    self.reconnect_delay = 3.0
                self.publish_snapshot()
                time.sleep(0.005)
        except KeyboardInterrupt:
            self.interrupted = True
        except Exception:
            self.fatal = traceback.format_exc()
            self.log("Console engine failed; see the final error", level="ERROR")
        finally:
            self.running = False          # a dead engine must let the GUI close instead of freezing on stale data
            self.cleanup()
        return 1 if self.fatal else 0

    def cleanup(self):
        if self.cleaned:
            return
        self.cleaned = True
        if self.midi_rec is not None:
            self.toggle_record()
        self.take_player.stop()
        if self.recorder is not None:
            self.recorder.close()
        self.send_panic(quiet=True, reset_all_channels=False)
        self.ports.close()
        self.log("Console stopped cleanly", notify=False)
