"""Tonic sol-fa version of a score (SATB alone, or with the organ staves), as printable HTML.

Doh is the key note (for a minor key: the relative major, lah-based minor). Notes are d r m f s l t, chromatic d de r ma m f
fe s lo l ta t; the octave is shown with a small number above (higher) or below (lower) the syllable, relative to the doh
nearest middle C. Layout is the traditional one: bars separated by |, beats by :, half beats by ., quarter beats by ,;
a held note continues with a dash; a rest is blank. One line per voice, bars aligned.

CHANGELOG
2026-10-24  New.
"""
import html
from fractions import Fraction

SYL = ["d", "de", "r", "ma", "m", "f", "fe", "s", "lo", "l", "ta", "t"]


def doh_for(tonic_pc, minor):
    """Pitch class of doh: the tonic, or for a minor key its relative major (lah = tonic)."""
    return (tonic_pc + 3) % 12 if minor else tonic_pc % 12


def _doh_near_middle(doh_pc):
    base = 60 + doh_pc if doh_pc < 6 else 48 + doh_pc            # the doh within a tritone of middle C
    return base


def syllable(pitch, doh_pc, ref):
    rel = pitch - ref
    octave, step = divmod(rel, 12)
    name = SYL[(pitch - doh_pc) % 12]
    mark = ""
    if octave > 0:
        mark = f"<sup>{octave}</sup>"
    elif octave < 0:
        mark = f"<sub>{-octave}</sub>"
    return html.escape(name) + mark


def _voice_line(notes, bar_starts, bar_beats, doh_pc, ref, transpose):
    """[[beat string, ...] per bar] for one voice (top note of any chord)."""
    cells = []
    top = {}
    for q in notes:
        top.setdefault((q.start, q.end), []).append(q.pitch)
    events = sorted(((s, e, max(ps)) for (s, e), ps in top.items()), key=lambda x: (x[0], x[1]))
    for bar, start in enumerate(bar_starts):
        beats = int(round(float(bar_beats[bar])))
        row = []
        for beat in range(max(1, beats)):
            slots = []
            for sub in range(4):
                t = Fraction(start) + beat + Fraction(sub, 4)
                owner = next((ev for ev in events if ev[0] <= t < ev[1]), None)
                if owner is None:
                    slots.append(("rest", None))
                elif abs(owner[0] - t) < Fraction(1, 8):
                    slots.append(("new", syllable(owner[2] + transpose, doh_pc, ref)))
                else:
                    slots.append(("hold", None))
            row.append(_beat_text(slots))
        cells.append(row)
    return cells


def _slot_text(slot):
    kind, text = slot
    return text if kind == "new" else ("&ndash;" if kind == "hold" else "&nbsp;")


def _beat_text(slots):
    if all(k == "hold" for k, _ in slots):
        return "&ndash;"
    if all(k == "rest" for k, _ in slots):
        return "&nbsp;"
    halves = []
    for a, b in ((slots[0], slots[1]), (slots[2], slots[3])):
        if b[0] == "new" or (a[0] == "rest" and b[0] != "rest" and b[0] != "hold"):
            halves.append(_slot_text(a) + "," + _slot_text(b))
        elif a[0] == "rest" and b[0] == "hold":
            halves.append(_slot_text(b))
        else:
            halves.append(_slot_text(a))
    if halves[0] == halves[1] == "&ndash;":
        return "&ndash;"
    if slots[2][0] == "hold" and slots[1][0] == "hold" and slots[3][0] == "hold":
        return halves[0]
    return ".".join(halves)


def build_html(title, key_text, time_text, voices, barmap_cum, bar_beats, doh_pc, transpose=0, bars_per_line=4,
               dark=False):
    """voices: [(name, [QNote])]. Returns an HTML document."""
    ref = _doh_near_middle(doh_pc)
    bar_count = len(bar_beats)
    lines = {name: _voice_line(notes, barmap_cum[:bar_count], bar_beats, doh_pc, ref, transpose) for name, notes in voices}
    fg, bg = ("#e6eef1", "#101820") if dark else ("#000000", "#ffffff")
    out = [f"<html><body style='background:{bg};color:{fg};font-family:Georgia,serif;'>",
           f"<h2 style='text-align:center'>{html.escape(title)}</h2>",
           f"<p style='text-align:center'>Key {html.escape(key_text)} (doh = {html.escape(key_text.split()[0])}) &nbsp; {html.escape(time_text)}</p>"]
    for first in range(0, bar_count, bars_per_line):
        group = range(first, min(bar_count, first + bars_per_line))
        out.append("<table cellspacing='0' cellpadding='3' style='margin-bottom:14px;'>")
        for name, _ in voices:
            out.append("<tr>")
            out.append(f"<td width='90' style='padding-right:8px;white-space:nowrap;'><b>{html.escape(name[:12])}</b></td>")
            for bar in group:
                beats = lines[name][bar]
                cells = "".join(f"<td width='54' align='center' style='{'border-left:1px dotted #888;' if i else ''}'>{b}</td>"
                                for i, b in enumerate(beats))
                out.append(f"<td width='{54 * max(1, len(beats))}' style='border-left:2px solid {fg};'><table cellspacing='0' cellpadding='2' width='{54 * max(1, len(beats))}'><tr>{cells}</tr></table></td>")
            out.append(f"<td style='border-left:2px solid {fg};'></td></tr>")
        out.append(f"<tr><td></td>" + "".join(f"<td style='font-size:8pt;color:#888;'>{b + 1}</td>" for b in group) + "</tr>")
        out.append("</table>")
    out.append("<p style='font-size:8pt;color:#888;'>Small number above a syllable = octave higher, below = octave lower "
               "(relative to the doh nearest middle C). &ndash; = held, blank = rest.</p></body></html>")
    return "".join(out)
