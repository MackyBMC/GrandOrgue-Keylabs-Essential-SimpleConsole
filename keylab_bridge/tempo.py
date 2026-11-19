"""Session-wide tempo target and undo history. Nothing is persisted until a music file is saved.

CHANGELOG
2026-11-19  engine_bpm / engine_confirmed: the audio engine's (GrandOrgue) metronome BPM as last driven / read back, shown beside the slider.
2026-11-19  Default 80 BPM and range 1-500 follow GrandOrgue's metronome (the engine's values are the standard for the bridge).
"""

DEFAULT_BPM = 80      # GrandOrgue's own metronome default: bridge and engine start aligned
MIN_BPM = 1           # GrandOrgue metronome range 1..500: the bridge supports all of it
MAX_BPM = 500


class TempoSession:
    def __init__(self, bpm=DEFAULT_BPM):
        self.bpm = self._clamp(bpm)
        self._undo = []
        self._redo = []
        self._listeners = []
        self.keep_on_load = True      # opening a file keeps the BPM you set (universal tempo); False = adopt each file's own tempo
        self.user_set = False         # true once the BPM was changed by hand: until then the first files opened set it
        self.engine_bpm = None        # engine metronome BPM as last driven or read back (None = unknown)
        self.engine_confirmed = False # true once the engine itself reported that BPM
        self.file_bpm = None          # written (average) tempo of the file last opened, for display

    def adopt_file_tempo(self, file_bpm):
        """A file was opened: remember its written tempo; follow it unless the BPM is a universal setting you chose."""
        self.file_bpm = float(file_bpm)
        if not self.keep_on_load or not self.user_set:
            self.set_bpm(file_bpm, origin="load", record=False)

    @staticmethod
    def _clamp(bpm):
        return max(MIN_BPM, min(MAX_BPM, int(round(float(bpm)))))

    def add_listener(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def set_bpm(self, bpm, origin="user", record=True):
        bpm = self._clamp(bpm)
        if bpm == self.bpm:
            return False
        if origin == "user":
            self.user_set = True
        if record:
            self._undo.append(self.bpm)
            self._undo = self._undo[-100:]
            self._redo.clear()
        self.bpm = bpm
        for listener in tuple(self._listeners):
            listener(bpm, origin)
        return True

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self.bpm)
        return self.set_bpm(self._undo.pop(), origin="undo", record=False)

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self.bpm)
        return self.set_bpm(self._redo.pop(), origin="redo", record=False)
