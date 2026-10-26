"""Shape MIDI timing: time-based or grid quantise with strength, swing, humanise, legato / slur and a MIDI-number range.

CHANGELOG
2026-10-26  New.
"""
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout)

GRIDS = (("1/4 beat (16th)", 0.25), ("1/2 beat (8th)", 0.5), ("1 beat", 1.0), ("1/8 beat (32nd)", 0.125),
         ("1/3 beat (triplet 8th)", 1 / 3), ("1/6 beat (triplet 16th)", 1 / 6), ("2 beats", 2.0))


class ShapeDialog(QDialog):
    def __init__(self, stave):
        super().__init__(stave)
        self.stave = stave
        self.setWindowTitle("Shape MIDI timing")
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Grid (beats, follows the bar lines)", "Time (fixed milliseconds)"])
        self.grid = QComboBox()
        for label, _ in GRIDS:
            self.grid.addItem(label)
        self.ms = QSpinBox()
        self.ms.setRange(5, 1000)
        self.ms.setValue(50)
        self.ms.setSuffix(" ms")
        self.strength = QSpinBox()
        self.strength.setRange(0, 100)
        self.strength.setValue(100)
        self.strength.setSuffix(" %")
        self.strength.setToolTip("100% = fully on the grid. 50% moves each note half way and keeps some of the human feel.")
        self.swing = QSpinBox()
        self.swing.setRange(0, 75)
        self.swing.setSuffix(" %")
        self.swing.setToolTip("Delays the off-beat grid points (grid mode).")
        self.humanise = QSpinBox()
        self.humanise.setRange(0, 60)
        self.humanise.setSuffix(" ms")
        self.humanise.setToolTip("Random +/- shift after snapping, so a mechanical result sounds played. Same result every time.")
        self.ends = QComboBox()
        self.ends.addItems(["Keep note lengths", "Snap note ends too", "Legato / slur: run each note on to the next",
                          "Finger-numbered notes joined (legato along the fingering)",
                          "Organ-friendly: close gaps in piano-style MIDI"])
        self.legato = QSpinBox()
        self.legato.setRange(10, 150)
        self.legato.setValue(100)
        self.legato.setSuffix(" %")
        self.legato.setToolTip("Share of the gap to the next note that is held. 100% = joined, 120% = slight overlap (slur).")
        self.gap = QDoubleSpinBox()
        self.gap.setRange(0.0, 4.0)
        self.gap.setSingleStep(0.25)
        self.gap.setValue(1.0)
        self.gap.setSuffix(" beats")
        self.gap.setToolTip("Organ-friendly mode: gaps up to this length between notes of one part are closed.")
        self.lo, self.hi = QSpinBox(), QSpinBox()
        for box, value in ((self.lo, 0), (self.hi, 127)):
            box.setRange(0, 127)
            box.setValue(value)
        self.hi.setToolTip("Only MIDI notes numbered from-to are touched (e.g. 0-47 = pedal). Middle C is 60.")
        self.selected_only = QCheckBox("Selected notes only")
        self.selected_only.setChecked(bool(stave.sel_notes))
        for text, w in (("Quantise by", self.mode), ("Grid step", self.grid), ("Time step", self.ms), ("Strength", self.strength),
                        ("Swing", self.swing), ("Humanise", self.humanise), ("Note ends", self.ends), ("Legato hold", self.legato), ("Close gaps up to", self.gap),
                        ("From MIDI note", self.lo), ("To MIDI note", self.hi)):
            form.addRow(text, w)
        form.addRow(self.selected_only)
        box = QDialogButtonBox()
        apply = box.addButton("Apply", QDialogButtonBox.ButtonRole.AcceptRole)
        restore = box.addButton("Restore original timing", QDialogButtonBox.ButtonRole.ActionRole)
        box.addButton(QDialogButtonBox.StandardButton.Close)
        apply.clicked.connect(self.apply)
        restore.clicked.connect(self.restore)
        box.rejected.connect(self.close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        self.info = QLabel("Changes the recorded notes themselves (undo with Ctrl+Z). The score follows.")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        lay.addWidget(box)
        self.mode.currentIndexChanged.connect(self._mode)
        self._mode()

    def _mode(self):
        time_mode = self.mode.currentIndex() == 1
        self.ms.setEnabled(time_mode)
        self.grid.setEnabled(not time_mode)
        self.swing.setEnabled(not time_mode)

    def _scope(self):
        st = self.stave
        return (set(st.sel_notes) if self.selected_only.isChecked() and st.sel_notes else None), self.lo.value(), self.hi.value()

    def apply(self):
        import core
        st = self.stave
        only, lo, hi = self._scope()
        st.push_undo()
        old_keys = {id(n): st._sign_key(n) for n in st.notes}              # finger / pedal marks follow their notes
        fingered = {id(n) for n in st.notes if str(st.signs.get(old_keys[id(n)], "")).startswith("f:")}
        count = core.shape_notes(
            st.notes, st.barmap, mode="time" if self.mode.currentIndex() else "grid", grid_beats=GRIDS[self.grid.currentIndex()][1],
            ms=self.ms.value(), strength=self.strength.value() / 100.0, swing=self.swing.value() / 100.0,
            humanise_ms=float(self.humanise.value()), ends=("keep", "snap", "legato", "fingered", "organ")[self.ends.currentIndex()],
            legato=self.legato.value() / 100.0, lo=lo, hi=hi, only=only, fingered=fingered, max_gap=self.gap.value())
        self._rekey_signs(st, old_keys)
        st.after_edit()
        self.info.setText(f"{count} notes re-timed. Undo = Ctrl+Z.")

    @staticmethod
    def _rekey_signs(st, old_keys):
        moved = {}
        for n in st.notes:
            old = old_keys.get(id(n))
            if old in st.signs:
                moved[st._sign_key(n)] = st.signs[old]
        st.signs.clear()
        st.signs.update(moved)

    def restore(self):
        import core
        st = self.stave
        only, lo, hi = self._scope()
        st.push_undo()
        old_keys = {id(n): st._sign_key(n) for n in st.notes}
        count = core.restore_raw(st.notes, lo, hi, only)
        self._rekey_signs(st, old_keys)
        st.after_edit()
        self.info.setText(f"{count} notes back to their original timing.")
