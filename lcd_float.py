"""Floating, always-on-top LCD panel in the spirit of a vintage Casio / Yamaha display: the KeyLab LCD text, which list the jog
drives, the loaded and cued setter, drawn stops per division, transport / recording / metronome state with clocks, the
volume knobs and the swell fader (they turn and slide as the real ones move; drag or wheel them to set a value), and a
spectrum / oscilloscope of the sound going to the output (audio_tap.py). Drag the panel anywhere; right-click for options.

CHANGELOG
2026-11-10  Cue preview: with a setter cued (not yet loaded) a "NEXT" line shows its name and +/- counts, stops it will add flash with "+",
            stops it will take away are struck through. Stops drawn / taken off by hand since the loaded setter flash with a pencil /
            are struck through too.
2026-11-10  Transport icons + clocks (file position, recording timer, tempo), metronome pendulum, loop, jog-list badge,
            volume knobs / swell fader (live and draggable), spectrum / oscilloscope, colour schemes + custom colours,
            section switches. Metronome pendulum is a visual aid: it keeps the metronome's BPM but is not phase-locked to GrandOrgue.
2026-11-09  New (first version): LCD lines, setter name / step / cued state, drawn stops by division.
"""
import math
import re
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QColorDialog, QMenu, QSizeGrip, QWidget

SCHEMES = {                       # name: (ink, back)
    "Amber (Casio)": ("#ffb84d", "#16130c"),
    "Green (vintage)": ("#8dff7a", "#0b140b"),
    "Ice blue (Montage)": ("#6fd6ff", "#08121a"),
    "Red": ("#ff6b5a", "#190c0a"),
    "Grey-green LCD": ("#1f2a1c", "#b7c5a0"),
}
BEZEL = QColor("#2a2a2e")
KNOB_ORDER = ("master", "pedal", "hw", "sw", "sl", "noises")
SHORT = {"master": "MASTER", "pedal": "PEDAL", "hw": "HAUPT", "sw": "SCHW", "sl": "SOLO", "noises": "NOISE", "swell": "SWELL"}


def mix(a, b, t):
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def fmt_clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class LcdFloat(QWidget):
    def __init__(self, parent=None, volume_cb=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("LCD")
        self.setMouseTracking(True)
        self.volume_cb = volume_cb                      # (key, 0..127) -> sets the real volume
        self.settings = QSettings("KeyLabGrandOrgue", "LcdFloat")
        S = self.settings.value
        self.scheme = str(S("scheme", "Amber (Casio)"))
        self.custom = (str(S("custom_ink", "#ffb84d")), str(S("custom_back", "#16130c")))
        self.size_pt = int(S("font", 15))
        self.show_ = {k: str(S("show_" + k, "true")) == "true" for k in ("transport", "stops", "volumes", "scope")}
        self.scope_mode = str(S("scope_mode", "spectrum"))
        self.audio_device = str(S("audio_device", ""))
        self.snap = {}
        self.vol_disp, self.vol_goal = {}, {}
        self.bands, self.peaks = None, None
        self._hit, self._drag, self._drag_knob = [], None, None
        self._last_cb = 0.0
        self.tap = None
        self.grip = QSizeGrip(self)
        self.setMinimumSize(380, 140)
        self.resize(int(S("w", 600)), int(S("h", 500)))
        pos = S("pos")
        if isinstance(pos, QPoint):
            self.move(pos)
        self.setWindowOpacity(float(S("opacity", 0.96)))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # ---------------------------------------------------------------- colours
    def colours(self):
        ink, back = self.custom if self.scheme == "Custom" else SCHEMES.get(self.scheme, SCHEMES["Amber (Casio)"])
        ink, back = QColor(ink), QColor(back)
        return ink, mix(ink, back, 0.62), back, mix(ink, back, 0.88)    # ink, dim, back, ghost

    # ---------------------------------------------------------------- data
    def update_state(self, snap):
        self.snap = snap
        for key, value in (snap.get("volumes") or {}).items():
            self.vol_goal[key] = float(value)
            self.vol_disp.setdefault(key, float(value))
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_audio()
        self.timer.start(33 if self._scope_live() else 66)

    def hideEvent(self, event):
        self.timer.stop()
        if self.tap is not None:
            self.tap.stop()
        self.settings.setValue("pos", self.pos())
        super().hideEvent(event)

    def closeEvent(self, event):
        self.hideEvent(event)
        super().closeEvent(event)

    def _scope_live(self):
        return self.show_["scope"]

    def _apply_audio(self):
        if self.show_["scope"]:
            if self.tap is None:
                from audio_tap import AudioTap
                self.tap = AudioTap()
            if not self.tap.running:
                self.tap.start(self.audio_device or None)
        elif self.tap is not None:
            self.tap.stop()

    def _tick(self):
        moving = False
        for key, goal in self.vol_goal.items():
            cur = self.vol_disp.get(key, goal)
            if abs(cur - goal) > 0.4:
                self.vol_disp[key] = cur + (goal - cur) * 0.35          # the knob / fader visibly turns to its new value
                moving = True
            else:
                self.vol_disp[key] = goal
        if self.show_["scope"] and self.tap is not None and self.tap.status == "on":
            self._analyse()
            moving = True
        t = self.snap.get("transport") or {}
        if moving or t.get("recording") or t.get("metro_on") or t.get("take_playing") or self.show_["transport"] \
                or self.snap.get("cue_diff") or self.snap.get("manual_diff"):
            self.update()

    def _analyse(self):
        import numpy as np
        from audio_tap import scope_trace, spectrum_bands
        samples = self.tap.latest(2048)
        if samples is None or len(samples) < 2048:
            return
        if self.scope_mode == "spectrum":
            now = spectrum_bands(samples, self.tap.rate, 40)
            if self.bands is None or len(self.bands) != len(now):
                self.bands, self.peaks = now.copy(), now.copy()
            self.bands = np.maximum(now, self.bands * 0.82)             # instant attack, smooth fall
            self.peaks = np.maximum(self.bands, self.peaks - 0.012)     # peak hold, slow fall
        else:
            self.trace = scope_trace(samples, 512)

    # ---------------------------------------------------------------- drawing helpers
    def _font(self, pt, bold=True):
        f = QFont()
        f.setFamilies(["Consolas", "DejaVu Sans Mono", "Courier New", "monospace"])
        f.setPointSize(max(6, pt))
        f.setBold(bold)
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    @staticmethod
    def _icon_play(p, r):
        p.drawPolygon(QPolygonF([QPointF(r.left(), r.top()), QPointF(r.right(), r.center().y()), QPointF(r.left(), r.bottom())]))

    @staticmethod
    def _icon_pause(p, r):
        w = r.width() * 0.34
        p.drawRect(QRectF(r.left(), r.top(), w, r.height()))
        p.drawRect(QRectF(r.right() - w, r.top(), w, r.height()))

    @staticmethod
    def _icon_loop(p, r):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(r.adjusted(1, 3, -1, -3), 30 * 16, 300 * 16)
        tip = QPointF(r.center().x() + r.width() * 0.42, r.center().y() - r.height() * 0.1)
        p.setBrush(p.pen().color())
        p.drawPolygon(QPolygonF([tip, QPointF(tip.x() - 5, tip.y() - 1), QPointF(tip.x() + 1, tip.y() - 6)]))

    @staticmethod
    def _icon_metronome(p, r, phase, running):
        p.setBrush(Qt.BrushStyle.NoBrush)
        body = QPolygonF([QPointF(r.center().x() - r.width() * 0.32, r.bottom()), QPointF(r.center().x() - r.width() * 0.12, r.top()),
                          QPointF(r.center().x() + r.width() * 0.12, r.top()), QPointF(r.center().x() + r.width() * 0.32, r.bottom())])
        p.drawPolygon(body)
        swing = math.sin(phase * 2 * math.pi) * 0.5 if running else 0.0         # -0.5..0.5 rad about vertical
        base = QPointF(r.center().x(), r.bottom() - 1)
        length = r.height() * 0.95
        tip = QPointF(base.x() + math.sin(swing) * length, base.y() - math.cos(swing) * length)
        p.drawLine(base, tip)

    def _text(self, p, x, y, w, h, text, align=Qt.AlignmentFlag.AlignLeft):
        p.drawText(QRectF(x, y, w, h), int(align | Qt.AlignmentFlag.AlignVCenter), text)

    # ---------------------------------------------------------------- paint
    def paintEvent(self, _event):
        ink, dim, back, ghost = self.colours()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, BEZEL.lighter(125)); grad.setColorAt(1, BEZEL.darker(120))
        p.fillRect(self.rect(), QBrush(grad))
        screen = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        p.fillRect(screen, back)
        p.setPen(QPen(dim, 1)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(screen)
        self._hit = []
        snap = self.snap
        t = snap.get("transport") or {}
        now = t.get("now") or time.time()
        inner = screen.adjusted(10, 6, -10, -6)
        x, w, y = inner.left(), inner.width(), inner.top()
        pt = self.size_pt
        small = max(8, pt - 6)

        # --- status row: transport icons + clocks
        if self.show_["transport"]:
            row_h = small * 2.1
            p.setFont(self._font(small))
            cx = x
            icon = QRectF(0, 0, small * 1.05, small * 1.05)
            playing = t.get("take_playing") or (t.get("go_playing") and not t.get("go_paused"))
            paused = t.get("go_paused")
            r = icon.translated(cx, y + (row_h - icon.height()) / 2)
            p.setPen(QPen(ink if (playing or paused) else dim, 1)); p.setBrush(QBrush(ink if playing else (dim if not paused else ink)))
            if paused:
                self._icon_pause(p, r)
            elif playing:
                self._icon_play(p, r)
            else:
                p.drawRect(r.adjusted(1, 1, -1, -1))                 # stop square
            cx += small * 1.9
            self._text(p, cx, y, small * 5, row_h, "PLAY" if playing else ("PAUSE" if paused else "STOP"))
            cx += small * 5.6
            rec = t.get("recording")
            blink = rec and int(now * 2) % 2 == 0
            p.setPen(QPen(ink if rec else dim, 1)); p.setBrush(QBrush(ink if blink else Qt.BrushStyle.NoBrush))
            p.drawEllipse(r.translated(cx - x, 0))
            cx += small * 1.6
            p.setPen(QPen(ink if rec else dim, 1))
            self._text(p, cx, y, small * 7, row_h, ("REC " + fmt_clock(now - t["rec_started"]) if rec and t.get("rec_started") else "REC") if rec else "REC")
            cx += small * 9
            loop = t.get("loop")
            p.setPen(QPen(ink if loop else dim, 1.4)); self._icon_loop(p, r.translated(cx - x, 0).adjusted(0, -1, 2, 1))
            cx += small * 2.2
            metro_on = t.get("metro_on")
            bpm_text = (re.search(r"\d+", str(snap.get("metro_bpm") or "")) or [None])[0]
            tempo = float(bpm_text) if bpm_text else float(snap.get("tempo_bpm") or 120)
            phase = (now * tempo / 60.0) % 1.0
            p.setPen(QPen(ink if metro_on else dim, 1.3))
            self._icon_metronome(p, r.translated(cx - x, -2).adjusted(0, 0, 3, 3), phase, bool(metro_on))
            if metro_on and phase < 0.12:                              # beat flash
                p.setBrush(QBrush(ink)); p.drawEllipse(QPointF(cx + small * 2.5, y + row_h / 2), 3, 3)
            cx += small * 3.6
            p.setPen(QPen(ink, 1))
            self._text(p, cx, y, small * 9, row_h, f"♩={int(snap.get('tempo_bpm') or 0):3d}")
            clock = time.strftime("%H:%M", time.localtime(now))
            p.setPen(QPen(dim, 1))
            self._text(p, x + w - small * 6, y, small * 6, row_h, clock, Qt.AlignmentFlag.AlignRight)
            y += row_h + 2

        # --- the LCD itself: two lines on ghost cells, jog-list badge on the right
        lcd_font = self._font(pt)
        p.setFont(lcd_font)
        fm = p.fontMetrics()
        cell_w, line_h = fm.horizontalAdvance("M"), fm.height() + 2
        lines = [str(s) for s in (snap.get("lcd") or ("", ""))[:2]] + ["", ""]
        for i in range(2):
            for col in range(16):
                p.fillRect(QRectF(x + col * cell_w + 0.5, y + i * line_h + 1, cell_w - 1.5, line_h - 3), ghost)
            p.setPen(QPen(ink))
            for col, ch in enumerate(lines[i][:16].ljust(16)):
                if ch != " ":
                    p.drawText(QRectF(x + col * cell_w, y + i * line_h, cell_w, line_h), int(Qt.AlignmentFlag.AlignCenter), ch)
        zone = snap.get("sheet_zone") or ""
        bx = x + 16 * cell_w + 12
        if zone:
            p.setFont(self._font(small))
            p.setPen(QPen(ink)); p.setBrush(QBrush(ink))
            p.drawRoundedRect(QRectF(bx, y + 2, min(x + w - bx, small * 7.5), small * 1.9), 3, 3)
            p.setPen(QPen(back))
            self._text(p, bx, y + 2, min(x + w - bx, small * 7.5), small * 1.9, "JOG:" + zone[:5], Qt.AlignmentFlag.AlignHCenter)
            p.setPen(QPen(dim)); p.setBrush(Qt.BrushStyle.NoBrush)
            self._text(p, bx, y + 2 + small * 2.0, small * 9, small * 1.8, "Cat/Char ⇅", Qt.AlignmentFlag.AlignLeft)
        y += 2 * line_h + 6

        # --- setter / file progress rows
        p.setFont(self._font(small))
        combos = snap.get("combinations", [])
        idx, cued_i = snap.get("active_combination_index"), snap.get("combination_index")
        loaded = combos[idx]["name"] if isinstance(idx, int) and 0 <= idx < len(combos) else ""
        cue = combos[cued_i]["name"] if isinstance(cued_i, int) and 0 <= cued_i < len(combos) and cued_i != idx else ""
        step = snap.get("internal_position", "")
        row = small * 1.9
        p.setPen(QPen(ink)); self._text(p, x, y, w, row, (loaded or "-") + (f"   step {step}" if step else ""))
        y += row
        if cue:
            p.setPen(QPen(mix(ink, QColor("#ffffff"), 0.4))); self._text(p, x, y, w, row, "cued: " + cue); y += row
        if self.show_["transport"] and t.get("take_file"):
            speed = max(0.05, t.get("speed") or 1.0)
            pos = (t.get("take_pos") or 0.0) / speed
            length = (t.get("take_len") or 0.0) / speed
            p.setPen(QPen(dim)); self._text(p, x, y, w * 0.62, row, "♫ " + t["take_file"][:34])
            p.setPen(QPen(ink)); self._text(p, x + w * 0.62, y, w * 0.38, row, f"{fmt_clock(pos)} / {fmt_clock(length)}", Qt.AlignmentFlag.AlignRight)
            y += row
            bar = QRectF(x, y, w, 4)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(ghost); p.drawRect(bar)
            if length > 0:
                p.setBrush(ink); p.drawRect(QRectF(x, y, w * max(0.0, min(1.0, pos / length)), 4))
            y += 9
        p.setPen(QPen(dim, 1)); p.drawLine(QPointF(x, y), QPointF(x + w, y)); y += 5

        # --- bottom area budget
        bottom = inner.bottom()
        scope_h = 0
        if self.show_["scope"]:
            scope_h = max(60, min(130, (bottom - y) * 0.34))
        mid_h = bottom - y - scope_h - (6 if scope_h else 0)
        if mid_h > 40:
            vol_w = 0
            if self.show_["volumes"]:
                vol_w = min(w * 0.56, 7 * 62)
            stops_w = w - vol_w - (10 if vol_w and self.show_["stops"] else 0)
            if self.show_["stops"]:
                self._draw_stops(p, QRectF(x, y, stops_w, mid_h), small, ink, dim)
            if vol_w:
                self._draw_volumes(p, QRectF(x + w - vol_w, y, vol_w, mid_h), small, ink, dim, back, ghost)
        if scope_h:
            self._draw_scope(p, QRectF(x, bottom - scope_h, w, scope_h), small, ink, dim, ghost)
        p.end()

    def _stop_rows(self):
        """{division: [(name, state)]}: state "on" | "add" (the cued setter will draw it) | "remove" (it will take it in)
        | "madd" / "mremove" (changed by hand since the loaded setter). Cue wins over the manual changes."""
        snap = self.snap
        cue, manual = snap.get("cue_diff"), snap.get("manual_diff")
        rows = {}
        for division, name in (snap.get("active_stop_items") or []):
            rows.setdefault(division, []).append([name, "on"])
        mark = {}
        if cue:
            for d, n, _k in cue.get("remove", []): mark[(d, n)] = "remove"
            for d, n, _k in cue.get("add", []): rows.setdefault(d, []).append([n, "add"])
        elif manual:
            for d, n, _k in manual.get("add", []): mark[(d, n)] = "madd"
            for d, n, _k in manual.get("remove", []): rows.setdefault(d, []).append([n, "mremove"])
        for d, items in rows.items():
            for item in items:
                if item[1] == "on" and (d, item[0]) in mark:
                    item[1] = mark[(d, item[0])]
        return {d: [tuple(i) for i in items] for d, items in rows.items()}

    def _draw_stops(self, p, area, small, ink, dim):
        p.setFont(self._font(small))
        line_h = small * 1.9
        cue = self.snap.get("cue_diff")
        now = (self.snap.get("transport") or {}).get("now") or time.time()
        flash = int(now * 2.5) % 2 == 0
        if cue:                                                     # the intention: what pressing Jog / the pedal will do
            p.setPen(QPen(ink if flash else dim))
            self._text(p, area.left(), area.top(), area.width(), line_h,
                       f"\u25b6 NEXT: {cue.get('name', '')[:24]}  (+{len(cue['add'])} / -{len(cue['remove'])})")
            area = QRectF(area.left(), area.top() + line_h * 1.1, area.width(), area.height() - line_h * 1.1)
        grouped = self._stop_rows()
        if not grouped:
            p.setPen(QPen(dim)); self._text(p, area.left(), area.top(), area.width(), line_h, "no stops drawn")
            return
        col_w = p.fontMetrics().horizontalAdvance("M") * 16
        fit = max(1, int(area.width() // col_w))
        items = list(grouped.items())
        row_y, i = area.top(), 0
        while i < len(items) and row_y + line_h * 2 <= area.bottom() + 1:      # divisions flow into columns, then on to the next row
            row = items[i:i + fit]
            row_h = 0.0
            for c, (division, stops) in enumerate(row):
                cx, cy = area.left() + c * col_w, row_y
                p.setPen(QPen(dim)); self._text(p, cx, cy, col_w, line_h, division.upper()[:15]); cy += line_h
                for name, state in stops:
                    if cy + line_h > area.bottom() + 1:
                        p.setPen(QPen(ink)); self._text(p, cx, cy, col_w, line_h, "..."); break
                    if state == "on":
                        p.setPen(QPen(ink)); self._text(p, cx, cy, col_w, line_h, "\u2611 " + name[:13])
                    elif state in ("remove", "mremove"):                  # struck through: going away / taken off by hand
                        p.setPen(QPen(dim)); label = ("\u2612 " if state == "remove" else "\u2610 ") + name[:13]
                        self._text(p, cx, cy, col_w, line_h, label)
                        w = p.fontMetrics().horizontalAdvance(label)
                        p.setPen(QPen(ink if flash else dim, 1.5)); p.drawLine(QPointF(cx, cy + line_h / 2), QPointF(cx + w, cy + line_h / 2))
                    else:                                                  # "add" (cued) / "madd" (drawn by hand): flashing
                        p.setPen(QPen(ink if flash else dim))
                        self._text(p, cx, cy, col_w, line_h, ("+ " if state == "add" else "\u270e ") + name[:13])
                    cy += line_h
                row_h = max(row_h, cy - row_y)
            row_y += row_h + line_h * 0.3
            i += fit
        if i < len(items):
            p.setPen(QPen(dim)); self._text(p, area.right() - 70, area.bottom() - line_h, 70, line_h, f"+{len(items) - i} more", Qt.AlignmentFlag.AlignRight)

    def _draw_volumes(self, p, area, small, ink, dim, back, ghost):
        vols = self.vol_disp
        keys = [k for k in KNOB_ORDER if k in vols]
        fader = "swell" if "swell" in vols else None
        slots = len(keys) + (1 if fader else 0)
        if not slots:
            return
        cell = min(area.width() / slots, 70)
        r = min(cell * 0.34, area.height() * 0.30)
        cy = area.top() + r + 6
        x0 = area.left() + (area.width() - cell * slots) / 2
        p.setFont(self._font(max(7, small - 2)))
        for i, key in enumerate(keys):
            cx = x0 + cell * (i + 0.5)
            v = max(0.0, min(127.0, vols[key])) / 127.0
            rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            p.setPen(QPen(ghost, 3)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawArc(rect, 225 * 16, -270 * 16)
            p.setPen(QPen(ink, 3)); p.drawArc(rect, 225 * 16, int(-270 * 16 * v))
            a = math.radians(225 - 270 * v)
            p.setPen(QPen(ink, 2)); p.drawLine(QPointF(cx + math.cos(a) * r * 0.25, cy - math.sin(a) * r * 0.25),
                                              QPointF(cx + math.cos(a) * r * 0.85, cy - math.sin(a) * r * 0.85))
            p.setPen(QPen(ink)); self._text(p, cx - cell / 2, cy + r + 1, cell, small * 1.3, f"{int(round(v * 100)):3d}", Qt.AlignmentFlag.AlignHCenter)
            p.setPen(QPen(dim)); self._text(p, cx - cell / 2, cy + r + 1 + small * 1.3, cell, small * 1.3, SHORT.get(key, key[:6].upper()), Qt.AlignmentFlag.AlignHCenter)
            self._hit.append((QRectF(cx - cell / 2, cy - r - 4, cell, 2 * r + small * 2.8 + 8), key, "knob"))
        if fader:
            cx = x0 + cell * (len(keys) + 0.5)
            v = max(0.0, min(127.0, vols[fader])) / 127.0
            top, bot = area.top() + 6, area.top() + 6 + 2 * r + small * 1.3
            p.setPen(QPen(dim, 1)); p.drawLine(QPointF(cx, top), QPointF(cx, bot))
            for n in range(11):                                      # graduated ticks: major every 5th
                ty = bot - (bot - top) * n / 10.0
                half = 6 if n % 5 == 0 else 3
                p.drawLine(QPointF(cx - half, ty), QPointF(cx + half, ty))
            cap_y = bot - (bot - top) * v
            p.setPen(QPen(ink, 1)); p.setBrush(QBrush(ink))
            p.drawRoundedRect(QRectF(cx - 9, cap_y - 5, 18, 10), 2, 2)
            p.setPen(QPen(back, 2)); p.drawLine(QPointF(cx - 6, cap_y), QPointF(cx + 6, cap_y))
            p.setPen(QPen(ink)); self._text(p, cx - cell / 2, bot + 3, cell, small * 1.3, f"{int(round(v * 100)):3d}", Qt.AlignmentFlag.AlignHCenter)
            p.setPen(QPen(dim)); self._text(p, cx - cell / 2, bot + 3 + small * 1.3, cell, small * 1.3, SHORT.get(fader, "SWELL"), Qt.AlignmentFlag.AlignHCenter)
            self._hit.append((QRectF(cx - cell / 2, top - 6, cell, bot - top + small * 2.8 + 12), fader, "fader"))
            self._fader_span = (top, bot)

    def _draw_scope(self, p, area, small, ink, dim, ghost):
        p.setPen(QPen(dim, 1)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(area)
        tap = self.tap
        label = "SPECTRUM" if self.scope_mode == "spectrum" else "SCOPE"
        p.setFont(self._font(max(7, small - 2)))
        if tap is None or tap.status != "on":
            p.setPen(QPen(dim)); self._text(p, area.left() + 6, area.top(), area.width() - 12, area.height(), (tap.status if tap else "starting") if tap is None or tap.status != "off" else "audio off")
            return
        p.setPen(QPen(dim)); self._text(p, area.left() + 4, area.top() + 1, 90, small * 1.4, label)
        inner = area.adjusted(4, small * 1.5, -4, -3)
        if self.scope_mode == "spectrum" and self.bands is not None:
            n = len(self.bands)
            bw = inner.width() / n
            for i in range(n):
                h = float(self.bands[i]) * inner.height()
                segs = max(0, int(h // 4))
                for s in range(segs):                                 # LED-style segments
                    p.fillRect(QRectF(inner.left() + i * bw + 1, inner.bottom() - (s + 1) * 4 + 1, bw - 2, 3), ink)
                ph = float(self.peaks[i]) * inner.height()
                p.fillRect(QRectF(inner.left() + i * bw + 1, inner.bottom() - ph - 2, bw - 2, 2), dim if ph > 4 else ghost)
        elif getattr(self, "trace", None) is not None:
            mid = inner.center().y()
            p.setPen(QPen(ghost, 1)); p.drawLine(QPointF(inner.left(), mid), QPointF(inner.right(), mid))
            path = QPainterPath()
            tr = self.trace
            for i, v in enumerate(tr):
                px = inner.left() + inner.width() * i / (len(tr) - 1)
                py = mid - float(v) * inner.height() * 0.48 * 2.0
                (path.moveTo if i == 0 else path.lineTo)(px, max(inner.top(), min(inner.bottom(), py)))
            p.setPen(QPen(ink, 1.6)); p.drawPath(path)

    # ---------------------------------------------------------------- mouse: move panel, turn knobs
    def _knob_at(self, pos):
        for rect, key, kind in self._hit:
            if rect.contains(pos):
                return key, kind
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._knob_at(event.position())
        if hit:
            self._drag_knob = (hit[0], hit[1], event.position().y(), self.vol_goal.get(hit[0], 0.0))
            if hit[1] == "fader":
                self._fader_to(hit[0], event.position().y())
            return
        self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_knob and event.buttons() & Qt.MouseButton.LeftButton:
            key, kind, y0, v0 = self._drag_knob
            if kind == "fader":
                self._fader_to(key, event.position().y())
            else:
                self._set_volume(key, v0 + (y0 - event.position().y()) * 0.8)     # drag up = louder
        elif self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        if self._drag_knob:
            key = self._drag_knob[0]
            self._set_volume(key, self.vol_goal.get(key, 0.0), force=True)
        self._drag, self._drag_knob = None, None
        self.settings.setValue("pos", self.pos())

    def wheelEvent(self, event):
        hit = self._knob_at(event.position())
        if hit:
            self._set_volume(hit[0], self.vol_goal.get(hit[0], 0.0) + (3 if event.angleDelta().y() > 0 else -3), force=True)
            event.accept()

    def _fader_to(self, key, y):
        top, bot = getattr(self, "_fader_span", (0, 1))
        self._set_volume(key, 127.0 * (bot - y) / max(1.0, bot - top))

    def _set_volume(self, key, value, force=False):
        value = max(0.0, min(127.0, value))
        self.vol_goal[key] = value
        self.vol_disp[key] = value
        self.update()
        now = time.time()
        if self.volume_cb and (force or now - self._last_cb > 0.06):         # live while dragging, but not a flood
            self._last_cb = now
            self.volume_cb(key, int(round(value)))

    # ---------------------------------------------------------------- options
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        show = menu.addMenu("Show")
        for key, label in (("transport", "Transport, clocks, metronome"), ("stops", "Drawn stops"),
                           ("volumes", "Volume knobs / swell fader"), ("scope", "Audio spectrum / scope")):
            a = show.addAction(label); a.setCheckable(True); a.setChecked(self.show_[key])
            a.triggered.connect(lambda on, k=key: self._set_show(k, on))
        scope = menu.addMenu("Audio display")
        for mode, label in (("spectrum", "Spectrum"), ("scope", "Oscilloscope")):
            a = scope.addAction(label); a.setCheckable(True); a.setChecked(self.scope_mode == mode)
            a.triggered.connect(lambda _=False, m=mode: self._set_scope_mode(m))
        scope.addSeparator()
        auto = scope.addAction("Default output device"); auto.setCheckable(True); auto.setChecked(not self.audio_device)
        auto.triggered.connect(lambda _=False: self._set_device(""))
        try:
            from audio_tap import AudioTap
            for name in AudioTap.loopback_devices():
                a = scope.addAction(name[:60]); a.setCheckable(True); a.setChecked(self.audio_device == name)
                a.triggered.connect(lambda _=False, n=name: self._set_device(n))
        except Exception:
            pass
        colours = menu.addMenu("Colours")
        for name in list(SCHEMES) + ["Custom"]:
            a = colours.addAction(name); a.setCheckable(True); a.setChecked(self.scheme == name)
            a.triggered.connect(lambda _=False, n=name: self._set_scheme(n))
        colours.addSeparator()
        colours.addAction("Custom text colour...").triggered.connect(lambda: self._pick(0))
        colours.addAction("Custom background...").triggered.connect(lambda: self._pick(1))
        sizes = menu.addMenu("Text size")
        for pt in (12, 15, 18, 22, 28):
            a = sizes.addAction(f"{pt} pt"); a.triggered.connect(lambda _=False, v=pt: self._set_size(v))
        ops = menu.addMenu("Opacity")
        for pct in (100, 92, 80, 60):
            a = ops.addAction(f"{pct} %"); a.triggered.connect(lambda _=False, v=pct: self._set_opacity(v / 100))
        menu.addSeparator()
        menu.addAction("Hide").triggered.connect(self.hide)
        menu.exec(event.globalPos())

    def _set_show(self, key, on):
        self.show_[key] = bool(on)
        self.settings.setValue("show_" + key, "true" if on else "false")
        if key == "scope":
            self._apply_audio()
            self.timer.start(33 if on else 66)
        self.update()

    def _set_scope_mode(self, mode):
        self.scope_mode = mode
        self.settings.setValue("scope_mode", mode)
        self.update()

    def _set_device(self, name):
        self.audio_device = name
        self.settings.setValue("audio_device", name)
        if self.tap is not None:
            self.tap.stop()
        self._apply_audio()

    def _set_scheme(self, name):
        self.scheme = name
        self.settings.setValue("scheme", name)
        self.update()

    def _pick(self, which):
        ink, _dim, back, _g = self.colours()
        colour = QColorDialog.getColor(ink if which == 0 else back, self, "Colour")
        if colour.isValid():
            custom = list(self.custom if self.scheme == "Custom" else (ink.name(), back.name()))
            custom[which] = colour.name()
            self.custom = tuple(custom)
            self.settings.setValue("custom_ink", self.custom[0]); self.settings.setValue("custom_back", self.custom[1])
            self._set_scheme("Custom")

    def _set_size(self, pt):
        self.size_pt = pt
        self.settings.setValue("font", pt)
        self.update()

    def _set_opacity(self, value):
        self.setWindowOpacity(value)
        self.settings.setValue("opacity", value)

    def resizeEvent(self, event):
        self.grip.move(self.width() - 16, self.height() - 16)
        self.settings.setValue("w", self.width()); self.settings.setValue("h", self.height())
        super().resizeEvent(event)
