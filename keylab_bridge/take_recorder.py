"""Always-on take recorder: remembers everything played on the keyboard, without a record button.

Like Ableton's "Capture MIDI": play freely, and afterwards every take is already saved as a standard MIDI file in the
Takes folder (real-time, 120 BPM at 480 ticks per beat, so 1 tick = 1/960 s). A new take starts after GAP seconds of
silence, so a practice session becomes a row of separate takes. The take in progress is autosaved every
AUTOSAVE seconds, so a crash or power cut never loses more than that.

Config (config.yaml):
    recorder:
      enabled: true
      folder: Takes          # relative to the Scripts folder, or an absolute path
      gap: 25                # seconds of silence that end a take
      min_notes: 6           # shorter scraps are not kept
      autosave: 30
"""

import os
import time

def stave_module(name):
    """Import core / sessionmeta from the midi_stave folder (same flat module names the stave editor itself uses)."""
    import importlib, os, sys
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "midi_stave")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module(name)


TICKS_PER_SECOND = 960         # 480 ticks per beat at the fixed 500000 us/beat (120 BPM) tempo


class TakeRecorder:
    def __init__(self, folder, gap=25.0, min_notes=6, autosave=30.0, log=None):
        self.folder = folder
        self.gap = float(gap)
        self.min_notes = int(min_notes)
        self.autosave = float(autosave)
        self.log = log or (lambda *a, **k: None)
        self.events = []             # (seconds from take start, kind, a, b)
        self.started = None          # wall clock of the first note of this take
        self.last_activity = 0.0
        self.last_save = 0.0
        self.held = set()
        self.notes = 0
        self.path = None
        self.dirty = False

    # ------------------------------------------------------------------ input
    def feed(self, message, now):
        """Call with every MAIN-port message. Only channel-1 notes and the sustain pedal are kept."""
        kind = getattr(message, "type", "")
        if kind in ("note_on", "note_off"):
            if message.channel != 0:
                return
            on = kind == "note_on" and message.velocity > 0
            if on:
                if self.started is None:
                    self._begin(now)
                self.events.append((now - self.started, "on", message.note, message.velocity))
                self.held.add(message.note)
                self.notes += 1
            elif self.started is not None:
                self.events.append((now - self.started, "off", message.note, 0))
                self.held.discard(message.note)
            else:
                return
            self.last_activity, self.dirty = now, True
        elif kind == "control_change" and message.channel == 0 and message.control == 64 and self.started is not None:
            self.events.append((now - self.started, "cc", 64, message.value))
            self.last_activity, self.dirty = now, True

    def marker(self, now, text):
        """Organ setter change (or any text marker) at this moment of the take."""
        if self.started is not None:
            self.events.append((now - self.started, "marker", text, 0))
            self.last_activity, self.dirty = now, True

    def poll(self, now):
        """Call regularly: ends a take after the silence gap, autosaves a running one."""
        if self.started is None:
            return
        if not self.held and now - self.last_activity >= self.gap:
            self.close()
        elif self.dirty and now - self.last_save >= self.autosave:
            self._write()

    def close(self):
        """End the current take (also called when the console quits)."""
        if self.started is not None:
            if self.notes >= self.min_notes:
                self._write()
                self.log(f"Take saved: {os.path.basename(self.path)} ({self.notes} notes)")
            elif self.path and os.path.isfile(self.path):
                try:
                    os.remove(self.path)                       # a few stray notes are not a take
                except OSError:
                    pass
        self.events, self.started, self.held, self.notes, self.path, self.dirty = [], None, set(), 0, None, False

    # ----------------------------------------------------------------- output
    def _begin(self, now):
        self.started = now
        self.last_save = now
        os.makedirs(self.folder, exist_ok=True)
        self.path = os.path.join(self.folder, time.strftime("Take %Y-%m-%d %H-%M-%S", time.localtime(now)) + ".mid")

    def _write(self):
        try:
            import mido
            track = mido.MidiTrack()
            track.append(mido.MetaMessage("track_name", name="KeyLab take", time=0))
            track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
            previous = 0
            for at, kind, a, b in sorted(self.events, key=lambda e: e[0]):
                tick = int(round(at * TICKS_PER_SECOND))
                delta, previous = tick - previous, tick
                if kind == "on":
                    track.append(mido.Message("note_on", channel=0, note=a, velocity=b, time=delta))
                elif kind == "off":
                    track.append(mido.Message("note_off", channel=0, note=a, velocity=0, time=delta))
                elif kind == "marker":
                    track.append(mido.MetaMessage("marker", text=a, time=delta))
                else:
                    track.append(mido.Message("control_change", channel=0, control=a, value=b, time=delta))
            for note in sorted(self.held):                      # still sounding when saved: close them at the end
                track.append(mido.Message("note_off", channel=0, note=note, velocity=0, time=0))
            track.append(mido.MetaMessage("end_of_track", time=0))
            mid = mido.MidiFile(type=0, ticks_per_beat=480)
            mid.tracks.append(track)
            temporary = self.path + ".tmp"
            mid.save(temporary)
            os.replace(temporary, self.path)
            self.last_save, self.dirty = time.time(), False
        except Exception as exc:                                # recording must never disturb playing
            self.log(f"Take save failed: {exc}")


# ---------------------------------------------------------------------- explicit recording (Record button)
def make_midi_recorder(folder, log=None):
    """Explicit recorder for the Record button: starts at once, never ends on silence, keeps even a short take."""
    return TakeRecorder(folder, gap=1e12, min_notes=1, autosave=10, log=log)


def write_stave_friendly(path, out_path):
    """'Stave Friendly' copy of a take: bar lines found and straightened to a steady beat (midi_stave.export_fixed_midi).
    Returns True when written; False when midi_stave / music21 are not installed."""
    try:
        core = stave_module('core')
        load_midi, estimate_bars, export_fixed_midi = core.load_midi, core.estimate_bars, core.export_fixed_midi
        notes, _info = load_midi(path)
        if not notes:
            return False
        sm = stave_module('sessionmeta')
        read_all_markers = sm.read_all_markers
        barmap = estimate_bars(notes)
        marks = [(barmap.sec_to_beat(t), text) for t, text in read_all_markers(path)]
        export_fixed_midi(notes, barmap, out_path, markers=marks)
        return True
    except Exception:
        return False


class TakePlayer:
    """Plays a take file into GrandOrgue on a background thread. send(mido message) delivers to the GO port."""

    def __init__(self, send, channel=None, on_marker=None):
        """channel: force every note onto this channel (0-15); None keeps the file's channels (stave channels), after
        the per-file remap sidecar. on_marker(text): called from the player thread at each MIDI marker (setter change)."""
        self.send, self.channel, self.on_marker = send, channel, on_marker
        self.chmap = {}
        self.fanout = {}
        self.failed = 0
        self.speed = 1.0
        self.pos_file, self.pos_wall = 0.0, 0.0
        self.sent = 0
        self.next_file = 0.0
        self.thread = None
        self.stop_flag = False

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, path, on_done=None, offset=0.0):
        import threading
        self.stop()
        self.path, self.on_done_cb = path, on_done
        self.stop_flag = False
        try:
            channel_map = stave_module('sessionmeta').channel_map
            self.chmap = channel_map(path)
        except Exception:
            self.chmap = {}
        try:
            self.fanout = {n: ch - 1 for n, _p, ch in stave_module('sessionmeta').manual_channels()}
        except Exception:
            self.fanout = {}
        self.failed = 0
        self.sent = 0
        self.thread = threading.Thread(target=self._run, args=(path, on_done, float(offset)), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        if self.thread is not None and self.thread is not threading_current():
            self.thread.join(timeout=1.0)

    def chord(self, items, hold):
        """Sound [(channel, note, velocity)] now and release after `hold` seconds (step sequence from the stave editor)."""
        import mido, threading
        for ch, note, vel in items:
            self.send(mido.Message("note_on", channel=ch, note=note, velocity=vel))

        def release():
            for ch, note, _vel in items:
                self.send(mido.Message("note_off", channel=ch, note=note, velocity=0))
        threading.Timer(hold, release).start()

    def position(self):
        """Seconds into the file now (file time, so tempo scaling does not matter); None when nothing is playing."""
        if not self.active:
            return None
        import time as _time
        return self.pos_file + max(0.0, min(self.next_file - self.pos_file, (_time.perf_counter() - self.pos_wall) * self.speed))

    def _targets(self, msg):
        """Channels a message is sent on. A plain channel-1 keyboard recording is fanned out the way the KeyLab's own
        key ranges do it (pedal 36-53, solo 54-96, Hauptwerk + Schwellwerk everything), onto the manual channels
        GrandOrgue listens to for files; otherwise the file's own channel, after the per-file remap."""
        if self.channel is not None:
            return [self.channel]
        if msg.channel in self.chmap:
            return [self.chmap[msg.channel]]
        if msg.channel == 0 and self.fanout:
            ch = self.fanout
            if msg.type == "control_change":
                return list(ch.values())
            result = [ch["Hauptwerk"], ch["Schwellwerk"]]
            if 36 <= msg.note <= 53:
                result.append(ch["Pedal"])
            if 54 <= msg.note <= 96:
                result.append(ch["Solowerk"])
            return result
        return [msg.channel]

    def seek(self, seconds):
        """Jump to a point of the file (seconds at the file's own tempo): restarts the player there. Controller changes and
        the last setter marker before that point are replayed so the registration is right."""
        path = getattr(self, "path", None)
        if not path:
            return False
        self.start(path, getattr(self, "on_done_cb", None), max(0.0, float(seconds)))
        return True

    def _run(self, path, on_done, offset=0.0):
        import mido
        sounding, used = set(), set()
        boost = _realtime_boost()
        try:
            import time as _time
            clock = _time.perf_counter()
            self.pos_file, self.pos_wall = offset, clock
            cumulative = 0.0
            skipping, last_marker = offset > 0, None
            for msg in list(mido.MidiFile(path)):      # parsed up front, so nothing is read from disk mid-play; msg.time = seconds at the file's own tempo
                cumulative += msg.time
                self.next_file = max(cumulative, offset)
                if skipping:
                    if cumulative < offset - 1e-9:     # before the wanted point: keep only the state (controllers, setter)
                        if msg.type == "marker":
                            last_marker = msg.text
                        elif msg.type == "control_change":
                            for target in self._targets(msg):
                                self.send(msg.copy(channel=target))
                        continue
                    skipping = False
                    clock = _time.perf_counter() + (cumulative - offset) / max(0.1, self.speed)
                    self.pos_file, self.pos_wall = offset, _time.perf_counter()
                    if last_marker and self.on_marker:
                        self.on_marker(last_marker)
                else:
                    clock += msg.time / max(0.1, self.speed)       # speed: live tempo factor (1.0 = as written)
                while not self.stop_flag:
                    wait = clock - _time.perf_counter()
                    if wait <= 0:
                        break
                    if wait > 0.004:                   # coarse sleep, then spin the last ~2 ms: no timer-tick jitter (Windows sleeps in 1-15 ms steps)
                        _time.sleep(min(wait - 0.002, 0.01))
                if self.stop_flag:
                    break
                self.pos_file, self.pos_wall = cumulative, _time.perf_counter()     # the position this message sits at
                if msg.type == "marker":
                    if self.on_marker:
                        self.on_marker(msg.text)
                elif msg.type in ("note_on", "note_off", "control_change"):
                    for target in self._targets(msg):
                        out = msg.copy(channel=target)
                        used.add(target)
                        if out.type == "note_on" and out.velocity > 0:
                            sounding.add((target, out.note))
                        elif out.type != "control_change":
                            sounding.discard((target, out.note))
                        if self.send(out) is False:
                            self.failed += 1
                        else:
                            self.sent += 1
        except Exception as exc:
            self.error = str(exc)
        finally:
            _realtime_restore(boost)
            for target, note in sounding:
                self.send(mido.Message("note_off", channel=target, note=note, velocity=0))
            for target in used:
                self.send(mido.Message("control_change", channel=target, control=64, value=0))
            if on_done:
                on_done()


def _realtime_boost():
    """Playback thread: 1 ms Windows timer + highest thread priority, so note times do not wobble when the GUI is busy."""
    try:
        import ctypes, sys
        if sys.platform == "win32":
            ctypes.windll.winmm.timeBeginPeriod(1)
            k = ctypes.windll.kernel32
            handle = k.GetCurrentThread()
            old = k.GetThreadPriority(handle)
            k.SetThreadPriority(handle, 15)                 # THREAD_PRIORITY_TIME_CRITICAL
            return (handle, old)
    except Exception:
        pass
    return None


def _realtime_restore(state):
    try:
        import ctypes
        if state:
            ctypes.windll.kernel32.SetThreadPriority(state[0], state[1])
            ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass


def threading_current():
    import threading
    return threading.current_thread()
