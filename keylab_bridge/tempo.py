"""Session-wide tempo target and undo history. Nothing is persisted until a music file is saved."""

DEFAULT_BPM = 120
MIN_BPM = 30
MAX_BPM = 160


class TempoSession:
    def __init__(self, bpm=DEFAULT_BPM):
        self.bpm = self._clamp(bpm)
        self._undo = []
        self._redo = []
        self._listeners = []

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
