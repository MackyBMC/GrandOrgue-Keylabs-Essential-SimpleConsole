"""Engraving job run in a SEPARATE PROCESS by the stave editor.

Quantising, music21 and Verovio are pure CPU work that holds Python's GIL; run in a thread inside the bridge they starve
the bridge's own MIDI threads and the GUI (screens freeze, the controller seems to disconnect). A child process has its
own GIL, so the console stays responsive while a score is engraved.

CHANGELOG
2026-10-23  New: moved the engraving off the bridge's process.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import core
import render

PAGE_SIZES = {"A4": (2100, 2970), "Letter": (2159, 2794)}


def run(p, notes, anchors, beats, voice_names, page_wh):
    """Returns the same dict the in-process worker used to produce."""
    try:
        barmap = core.BarMap(list(anchors), list(beats))
        core.STAVE_HOLD = float(p.get("hold", 0.0))
        q = core.quantise(notes, barmap, p["grid"], p["triplets"], p["chord"], legato_gap=p["legato"], bar_grid=p["bar_grid"])
        hidden = {tuple(h) for h in p.get("hidden", [])}
        if hidden:                                           # tracks the user switched off are not engraved
            q = [x for x in q if (x.track, x.ch) not in hidden]
            notes = [n for n in notes if (n.track, n.ch) not in hidden]
        src_key = None
        if p["probe"]:
            k = render.detect_key(q)
            src_key = (k.tonic.pitchClass, f"{k.tonic.name.replace('-', 'b')} {k.mode}")
        staves = core.make_staves(p["kind"], p["split"], p["split2"], p["split3"], p["pedal"], notes, voice_names, organ=p.get("organ"))
        label = p["meter"] if p["meter"] in ("6/8", "12/8", "3/8", "2/2") else None
        score = render.build_score(q, barmap, staves, p["key"], p["title"], p["composer"], p["dynamics"], p["dyn_bias"],
                                   p["legato"], barmap.average_bpm(), {0: label} if label else None, p["transpose"],
                                   p["names"], p["slurs"], p["staccato"], p["final_bar"], p["setters"], p.get("signs"), p.get("adv"), p.get("lyrics"))
        xml = render.musicxml(score)
        render.init_verovio()
        pages = render.svg_pages(xml, page_wh[0], page_wh[1], p["scale"], spacing=p.get("spacing"))
        hits, dims, spaces = render.collect_hits(120.0)
        return {"q": q, "xml": xml, "pages": pages, "p": p, "src_key": src_key, "hits": hits, "dims": dims, "spaces": spaces}
    except Exception as exc:
        import traceback
        return {"error": f"{exc}", "trace": traceback.format_exc()}


def warm_up():
    render.init_verovio()
    return True
