"""Quantised notes -> MusicXML (music21) -> pages of SVG (Verovio) -> PDF (Qt, done by the GUI)."""

from fractions import Fraction

from core import melodic_line, assign, slur_phrases, split_voices

DYNAMICS = ["ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"]


def velocity_to_level(vel, bias=0):
    """Velocity 1-127 -> index into DYNAMICS; `bias` shifts everything softer (-) or louder (+)."""
    edges = [22, 40, 55, 70, 85, 100, 115]
    level = sum(1 for e in edges if vel >= e)
    return max(0, min(len(DYNAMICS) - 1, level + bias))


def _spell_map(key_obj):
    """pitch class -> pitch name, using the key's own scale spelling and flats/sharps by key signature."""
    from music21 import pitch
    flats = key_obj.sharps < 0
    names = {}
    for p in key_obj.pitches[:7]:
        names[p.pitchClass] = p.name
    for pc in range(12):
        if pc not in names:
            q = pitch.Pitch(pc)
            if flats and q.accidental is not None and q.accidental.name == "sharp":
                q = q.getEnharmonic()
            names[pc] = q.name
    return names


def detect_key(qnotes, transpose=0):
    from music21 import stream, note
    s = stream.Stream()
    for q in qnotes[:600]:
        s.append(note.Note(q.pitch + transpose, quarterLength=max(0.25, float(q.end - q.start))))
    return s.analyze("key")


def fill_rests(container, length, hidden=False):
    """Beat-aligned rests for every gap (engraver's rule): a rest never straddles a beat it does not start on, half rests only
    on beats 1 and 3, an empty bar is one whole-bar rest. hidden=True for a secondary voice (rests not printed)."""
    from music21 import note as m21note
    occupied = sorted((Fraction(float(x.offset)).limit_denominator(96),
                       Fraction(float(x.offset + x.quarterLength)).limit_denominator(96))
                      for x in container if isinstance(x, (m21note.Note, m21note.Rest)) or hasattr(x, "pitches"))
    total = Fraction(length).limit_denominator(96)
    gaps, pos = [], Fraction(0)
    for a, b in occupied:
        if a > pos:
            gaps.append((pos, a))
        pos = max(pos, b)
    if pos < total:
        gaps.append((pos, total))
    sizes = [Fraction(4), Fraction(2), Fraction(1), Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 16)]
    dotted = {Fraction(3): Fraction(1), Fraction(3, 2): Fraction(1), Fraction(3, 4): Fraction(1, 2)}
    for a, b in gaps:
        if hidden is False and a == 0 and b == total and not occupied:
            r = m21note.Rest(quarterLength=float(total))
            r.fullMeasure = True
            container.insert(0, r)
            continue
        o = a
        while o < b:
            left = b - o
            pick = next((d for d, al in dotted.items() if d == left and o % al == 0), None)
            if pick is None:
                pick = next((d for d in sizes if d <= left and o % d == 0), None)
            if pick is None:
                pick = left
            r = m21note.Rest(quarterLength=float(pick))
            if hidden:
                r.style.hideObjectOnPrint = True
            container.insert(float(o), r)
            o += pick


def build_score(qnotes, barmap, staves, key_name="auto", title="", composer="", dynamics=True, dyn_bias=0,
                legato_gap=Fraction(1, 2), tempo_bpm=None, time_sigs=None, transpose=0, names=None, slurs=True,
                staccato=False, final_bar=True, setters=None, signs=None, adv=None, lyrics=None):
    """signs: {(pitch, start beat): "toe" | "heel"} pedal marks (organ staves, written above the note).
    Organ conventions applied: curly brace over the two manuals + one bracket over all staves (choir: one bracket),
    "Manual I / Manual II / Pedal" names (short names on later systems), pedal always bass clef, "Ped. tacet" over a pedal
    rest of 4 bars or more, ties across bar lines for sustained notes.
    setters: {bar_index: "012 Name"} organ setter changes, printed above the first stave.
    time_sigs: optional {bar_index: "6/8"} labels (display only; bar length comes from the bar map)."""
    from music21 import (stream, note, chord, meter, key, clef, tempo, dynamics as dyn, tie, metadata, layout, pitch, bar,
                         spanner, articulations)
    from music21 import bar as bar_module
    time_sigs = time_sigs or {}
    adv = adv or {}                       # advanced organ notation: {"multirest": N bars (0 = off), "clef_switch", "rehearsal"}
    key_obj = detect_key(qnotes, transpose) if key_name in ("auto", "", None) else key.Key(key_name)
    spell = _spell_map(key_obj)
    cum = barmap.cumulative()
    per_stave = assign(qnotes, staves)
    score = stream.Score()
    score.insert(0, metadata.Metadata())
    score.metadata.title = title or "Untitled"
    if composer:
        score.metadata.composer = composer
    if adv.get("arranger"):
        score.metadata.addContributor(metadata.Contributor(role="arranger", name=adv["arranger"]))
    parts = []
    for si, (spec, notes) in enumerate(zip(staves, per_stave)):
        part = stream.Part()
        part.partName = (names[si].strip() if names and si < len(names) and names[si].strip() else spec.name)
        part.partAbbreviation = _abbreviation(part.partName)
        is_pedal = spec.name.casefold().startswith("pedal")
        empty_bars = []
        in_bass = spec.clef != "treble"
        voices = split_voices(notes, int(adv.get("max_voices", 2))) if adv.get("voices") else [notes]      # overlapping lines -> separate voices (stems up / down)
        lines = [melodic_line(v, legato_gap) for v in voices]
        line = lines[0]
        last_level = None
        previous_ts = None
        phrases = slur_phrases(line) if slurs else []
        element_of = {}
        for bar in range(barmap.bar_count):
            b0, b1 = cum[bar], cum[bar + 1]
            measure = stream.Measure(number=bar + 1)
            if adv.get("clef_switch") and spec.clef == "treble" and not is_pedal:       # manual staves: bass clef when low
                inside = [m_ + transpose for ln_ in lines for s_, e_, ps_, *_r in ln_ if not (e_ <= b0 or s_ >= b1) for m_ in ps_]
                if inside:
                    want_bass = max(inside) <= 59 or (min(inside) < 43 and max(inside) <= 64)
                    want_treble = max(inside) >= 64 and not (min(inside) < 43 and max(inside) <= 64)
                    if want_bass and not in_bass:
                        in_bass = True
                        if bar > 0:
                            measure.insert(0, clef.BassClef())
                        else:
                            pass                          # bar 1: the opening clef below is already bass
                    elif want_treble and in_bass:
                        in_bass = False
                        measure.insert(0, clef.TrebleClef())
            if bar == 0:
                measure.insert(0, clef.TrebleClef() if (spec.clef == "treble" and not in_bass) else clef.BassClef())
                measure.insert(0, key_obj)
                if si == 0 and tempo_bpm:
                    measure.insert(0, tempo.TempoText(f"c. {int(round(tempo_bpm))} BPM"))   # text only: Qt cannot draw the note glyph
            if si == 0 and adv.get("divisions") and bar in adv["divisions"]:       # division / coupler labels (Great, Swell, II/I ...)
                from music21 import expressions
                label = expressions.TextExpression(adv["divisions"][bar])
                label.style.fontWeight = "bold"
                label.placement = "above"
                measure.insert(0, label)
            if si == 0 and setters and bar in setters:
                from music21 import expressions
                measure.insert(0, expressions.TextExpression(setters[bar]))
            length = float(b1 - b0)
            label = time_sigs.get(bar)
            if label is None and length != previous_ts:
                num = length
                label = f"{int(num)}/4" if float(num).is_integer() else f"{int(round(num * 2))}/8"
            if label and (bar == 0 or length != previous_ts or bar in time_sigs):
                measure.insert(0, meter.TimeSignature(label))
            previous_ts = length
            bar_vels = []
            for vi, vline in enumerate(lines):
                target = measure if len(lines) == 1 else stream.Voice()
                for ei, (s, e, pitches, vel, legato) in enumerate(vline):
                    if e <= b0 or s >= b1:
                        continue
                    seg_s, seg_e = max(s, b0), min(e, b1)
                    pitch_objs = []
                    for midi in pitches:
                        midi = midi + transpose
                        p_obj = pitch.Pitch(spell[midi % 12])
                        alter = int(p_obj.accidental.alter) if p_obj.accidental is not None else 0
                        p_obj.octave = (midi - alter) // 12 - 1          # B#3 = MIDI 60, Cb5 = MIDI 71
                        pitch_objs.append(p_obj)
                    el = note.Note(pitch_objs[0]) if len(pitch_objs) == 1 else chord.Chord(pitch_objs)
                    el.quarterLength = float(seg_e - seg_s)
                    if len(lines) > 1:                          # voice 1 / 3 stems up, voice 2 / 4 stems down
                        el.stemDirection = "up" if vi % 2 == 0 else "down"
                    kind = None
                    if s < b0 and e > b1:
                        kind = "continue"
                    elif s < b0:
                        kind = "stop"
                    elif e > b1:
                        kind = "start"
                    if kind:
                        for n in (el.notes if hasattr(el, "notes") else [el]):
                            n.tie = tie.Tie(kind)
                    if s >= b0:
                        sign = next((signs.get((int(m_), round(float(s), 3))) for m_ in pitches
                                     if signs and signs.get((int(m_), round(float(s), 3)))), None) if signs else None
                        if sign:                                  # Verovio draws no organ toe/heel articulation: print the sign as text
                            from music21 import expressions
                            mark = expressions.TextExpression(sign[2:] if sign.startswith("f:") else {"toe": "^", "heel": "U", "slide": "<"}.get(sign, "U"))
                            mark.placement = "above"
                            measure.insert(float(seg_s - b0), mark)
                        if vi == 0:
                            bar_vels.append(vel)
                        if vi == 0:
                            element_of[ei] = el
                        if staccato and legato < 0.5 and (e - s) <= 1 and ei + 1 < len(vline):
                            el.articulations.append(articulations.Staccato())
                    target.insert(float(seg_s - b0), el)
                if adv.get("tidy_rests", True):
                    fill_rests(target, float(length), hidden=vi > 0)
                if len(lines) > 1 and any(isinstance(x, (note.Note, chord.Chord)) for x in target):   # a silent 2nd voice is left out of the bar
                    target.id = str(vi + 1)
                    measure.insert(0, target)
            if dynamics and si == 0 and bar_vels:
                level = velocity_to_level(sum(bar_vels) // len(bar_vels), dyn_bias)
                if last_level is None or abs(level - last_level) >= 2 or (level != last_level and bar % 8 == 0):
                    measure.insert(0, dyn.Dynamic(DYNAMICS[level]))
                    last_level = level
            if not any(not (e <= b0 or s >= b1) for ln_ in lines for s, e, *_ in ln_):
                empty_bars.append(bar)
            if not adv.get("tidy_rests", True):
                measure.makeRests(fillGaps=True, timeRangeFromBarDuration=True, inPlace=True)
            elif len(lines) > 1 and not any(isinstance(x, stream.Voice) for x in measure):
                fill_rests(measure, float(length))             # only the main voice has notes here: ordinary rests
            if final_bar and bar == barmap.bar_count - 1:
                measure.rightBarline = bar_module.Barline("final")
            part.append(measure)
        if is_pedal:                                       # "Ped. tacet" over each pedal rest of 4 or more bars
            from music21 import expressions
            run = []
            for bar in empty_bars + [None]:
                if bar is not None and (not run or bar == run[-1] + 1):
                    run.append(bar)
                    continue
                if len(run) >= 4:
                    tacet = expressions.TextExpression("Ped. tacet")
                    tacet.placement = "above"
                    part.measure(run[0] + 1).insert(0, tacet)
                run = [bar] if bar is not None else []
        part.empty_set = set(empty_bars)
        for run in phrases:
            members = [element_of[i] for i in run if i in element_of]
            if len(members) >= 2:
                part.insert(0, spanner.Slur(members))
        if lyrics:
            verses = lyrics.get(str(si)) or lyrics.get("all")
            if verses:
                _attach_lyrics(element_of, verses)
        parts.append(part)
    for part in parts:
        score.insert(0, part)
    if adv.get("multirest") and parts:                    # a multi-measure rest only where EVERY stave is silent
        common = sorted(set.intersection(*[pt.empty_set for pt in parts]))
        need, run, runs = int(adv["multirest"]), [], []
        for bar in common + [None]:
            if bar is not None and (not run or bar == run[-1] + 1):
                run.append(bar)
                continue
            if len(run) >= need:
                runs.append((run[0] + 1, len(run)))
            run = [bar] if bar is not None else []
        for pt in parts:
            pt.multi_rests = runs
    if adv.get("rehearsal") and parts:
        from music21 import expressions
        note_ = expressions.TextExpression("Organ (for rehearsal only)")
        note_.placement = "above"
        note_.style.fontStyle = "italic"
        first = next((pt for pt, sp in zip(parts, staves) if not sp.name.casefold().startswith("pedal")), parts[0])
        first.measure(1).insert(0, note_)
    score.multi_rest_parts = [getattr(pt, "multi_rests", []) for pt in parts]
    organ_like = len(parts) == 3 and staves[2].name.casefold().startswith("pedal")
    if organ_like:                                       # { Manual I / Manual II }  [ + Pedal ]
        score.insert(0, layout.StaffGroup(parts[:2], name="", symbol="brace", barTogether=True))
        score.insert(0, layout.StaffGroup(parts, name="", symbol="bracket", barTogether=True))
    elif len(parts) > 1:
        score.insert(0, layout.StaffGroup(parts, name="", symbol="brace" if len(parts) == 2 else "bracket",
                                          barTogether=True))
    return score


def parse_words(text):
    """Words typed under a voice -> one entry per note: (syllable, "single" | "begin" | "middle" | "end"), or None to skip a
    note (type _ for a note that carries no new syllable, e.g. the 2nd note of a melisma). Hyphens split a word into
    syllables:  "Je-su, thy blood"  or  "Je - su, thy blood"."""
    import re
    text = re.sub(r"\s+-\s+", "-", text.replace("\n", " ").strip())
    out = []
    for word in text.split():
        if word in ("_", "__"):
            out.append(None)
            continue
        parts = [p for p in word.split("-") if p]
        for i, part in enumerate(parts):
            if len(parts) == 1:
                out.append((part, "single"))
            else:
                out.append((part, "begin" if i == 0 else "end" if i == len(parts) - 1 else "middle"))
    return out


def _attach_lyrics(element_of, verses):
    """Put each verse's syllables on the notes of one stave, in time order (chords carry one syllable)."""
    from music21 import note as _note
    ordered = [element_of[k] for k in sorted(element_of)]
    for number, text in enumerate(verses, 1):
        tokens = parse_words(text or "")
        for el, tok in zip(ordered, tokens):
            if tok is None:
                continue
            word, kind = tok
            label = {"single": word, "begin": word + "-", "middle": "-" + word + "-", "end": "-" + word}[kind]
            el.addLyric(label, lyricNumber=number)


def _abbreviation(name):
    """Short stave name for the second and later systems: Manual I -> Man. I, Pedal -> Ped."""
    low = name.casefold()
    if low.startswith("manual"):
        return "Man." + name[len("manual"):]
    if low.startswith("pedal"):
        return "Ped."
    return name[:4] + ("." if len(name) > 4 else "")


def musicxml(score):
    from music21.musicxml.m21ToXml import GeneralObjectExporter
    xml = GeneralObjectExporter(score).parse().decode("utf-8")
    xml = _add_credits(xml, score)
    runs = getattr(score, "multi_rest_parts", None)
    if runs and any(runs):
        xml = _add_multirests(xml, runs)
    return xml


def _add_credits(xml, score):
    """Title centred, composer and arranger right-aligned under it (Verovio only prints the title from the metadata)."""
    from xml.sax.saxutils import escape
    md = score.metadata
    title = (md.title or "") if md is not None else ""
    composer = (md.composer or "") if md is not None else ""
    arranger = ""
    try:
        arranger = next((c.name for c in md.contributors if c.role == "arranger"), "")
    except Exception:
        pass
    parts = []
    if title and title != "Untitled":
        parts.append(("title", "center", 1500, 22, title))
    if composer:
        parts.append(("composer", "right", 1450, 12, composer))
    if arranger:
        parts.append(("arranger", "right", 1420, 11, "arr. " + arranger))
    if not parts or "<part-list>" not in xml:
        return xml
    credits = "".join(f'<credit page="1"><credit-type>{kind}</credit-type><credit-words default-x="{600 if align == "center" else 1100}" '
                      f'default-y="{y}" justify="{align}" halign="{align}" valign="top" font-size="{size}">{escape(text)}</credit-words></credit>'
                      for kind, align, y, size, text in parts)
    return xml.replace("<part-list>", credits + "<part-list>", 1)


def _add_multirests(xml, runs):
    """MusicXML <measure-style><multiple-rest> on the first bar of each long rest, per part (Verovio then draws one
    multi-measure rest with the bar count over it)."""
    import re
    chunks = re.split(r'(?=<part id=")', xml)
    out, part_no = [], -1
    for chunk in chunks:
        if chunk.startswith('<part id="'):
            part_no += 1
            for first, count in runs[part_no] if part_no < len(runs) else []:
                m = re.search(rf'<measure [^>]*number="{first}"[^>]*>', chunk)
                if not m:
                    continue
                style = f"<measure-style><multiple-rest>{count}</multiple-rest></measure-style>"
                end = chunk.find("</measure>", m.end())
                body = chunk[m.end():end]
                if "</attributes>" in body:
                    body = body.replace("</attributes>", style + "</attributes>", 1)
                else:
                    body = f"<attributes>{style}</attributes>" + body
                chunk = chunk[:m.end()] + body + chunk[end:]
        out.append(chunk)
    return "".join(out)


_TOOLKIT = None


def init_verovio():
    """Create the Verovio toolkit on the MAIN thread: built on a worker thread it cannot find its fonts."""
    global _TOOLKIT
    if _TOOLKIT is None:
        import verovio
        _TOOLKIT = verovio.toolkit()
    return _TOOLKIT


def svg_pages(xml, page_width=2100, page_height=2970, scale=40, breaks="auto", spacing=None):
    tk = init_verovio()
    tk.setOptions({**(spacing or {}), "pageWidth": page_width, "pageHeight": page_height, "scale": scale, "adjustPageHeight": False,
                   "breaks": breaks, "condense": "none", "footer": "none", "header": "auto", "pageMarginLeft": 80, "pageMarginRight": 80,
                   "pageMarginTop": 80, "pageMarginBottom": 80, "svgViewBox": True, "svgBoundingBoxes": False})
    if not tk.loadData(xml):
        raise ValueError("Verovio could not read the score")
    return [flatten_svg(tk.renderToSVG(i + 1)) for i in range(tk.getPageCount())]


def staff_bands(svg):
    """Every staff of a flattened page: [{"sys", "idx" (position in its system), "x0", "x1", "y0", "y1"}] in the page's outer units."""
    import re
    kk = re.search(r'class="definition-scale" transform="scale\(([\d.]+)\)"', svg)
    k = float(kk.group(1)) if kk else 1.0
    margin = re.search(r'class="page-margin"[^>]*transform="translate\(([-\d.]+),\s*([-\d.]+)\)', svg)
    ox, oy = (float(margin.group(1)), float(margin.group(2))) if margin else (0.0, 0.0)
    systems = [m.start() for m in re.finditer(r'class="system"', svg)]
    out, counts = [], {}
    for m in re.finditer(r'class="staff"[^>]*>((?:\s*<path d="M[\d.]+ [\d.]+ L[\d.]+ [\d.]+"[^>]*/>){5})', svg):
        lines = re.findall(r'M([\d.]+) ([\d.]+) L([\d.]+)', m.group(1))
        ys = [float(l[1]) for l in lines]
        sys_i = max(0, sum(1 for st in systems if st < m.start()) - 1)
        idx = counts.get(sys_i, 0)
        counts[sys_i] = idx + 1
        out.append({"sys": sys_i, "idx": idx, "x0": (float(lines[0][0]) + ox) * k, "x1": (float(lines[0][2]) + ox) * k,
                    "y0": (min(ys) + oy) * k, "y1": (max(ys) + oy) * k})
    return out


def flatten_svg(svg):
    """Verovio nests an <svg class="definition-scale"> inside the page <svg>. Qt's SVG renderer (SVG Tiny) skips nested
    svg elements and would draw a blank page, so turn the inner one into a scaled <g>."""
    import re
    _seen = [0]

    def _header(m):                                  # header lines: Qt ignores nested tspans, x / y on them and text-anchor -> one plain <text>
        body = m.group(1)
        pos = re.search(r'<tspan[^>]*\bx="([-\d.]+)"[^>]*\by="([-\d.]+)"([^>]*)>', body)
        inner = re.findall(r'<tspan[^>]*font-size="([\d.]+)px"[^>]*>([^<]*)</tspan>', body)
        if not pos or not inner:
            return m.group(0)
        x, y = float(pos.group(1)), float(pos.group(2))
        size = float(inner[-1][0])
        if _seen[0] == 0 and "title" in body.lower() or _seen[0] == 0:
            size *= 1.6                              # the first header line is the title
        _seen[0] += 1
        text = "".join(t.strip() for _f, t in inner)
        width = len(text) * size * 0.5
        anchor = re.search(r'text-anchor="(middle|end)"', pos.group(0))
        if anchor:
            x -= width / 2 if anchor.group(1) == "middle" else width
        return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.0f}px">{text}</text>'
    svg = re.sub(r'<text font-size="0px">(.*?)</text>', _header, svg, flags=re.S)
    svg = svg.replace("font-size=\"0px\"", "font-size=\"1px\"").replace("currentColor", "#000000").replace("\u2013", "-").replace("\u2014", "-")   # Qt shows UTF-8 dashes (page numbers) as mojibake
    svg = re.sub(r'<(path|line|polyline|polygon|rect)(?![^>]*\bstroke=)([^>]*?)\bstroke-width=', r'<\1\2stroke="#000000" stroke-width=', svg)      # Qt draws currentColor strokes (staff lines, stems, ties) as nothing
    outer = re.search(r'<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    inner = re.search(r'<svg class="definition-scale"([^>]*)viewBox="0 0 ([\d.]+) ([\d.]+)"[^>]*>', svg)
    if not outer or not inner:
        return svg
    svg = re.sub(r"<title[^>]*>.*?</title>", "", svg, flags=re.S)       # Qt cannot place <title> inside <tspan>
    k = float(outer.group(1)) / float(inner.group(2))
    svg = svg.replace(inner.group(0), f'<g class="definition-scale" transform="scale({k})"{inner.group(1)}>', 1)
    cut = svg.rfind("</svg>", 0, svg.rfind("</svg>"))
    svg = svg[:cut] + "</g>" + svg[cut + len("</svg>"):] if cut > 0 else svg
    return _flatten_tspans(svg)


def _flatten_tspans(svg):
    """Qt draws <tspan> only directly inside <text>. Verovio nests them 3 deep (titles, composer): collapse each
    <text> to one tspan per leaf, keeping the outer position/anchor and the leaf font size."""
    import re
    import xml.etree.ElementTree as ET
    ns = "{http://www.w3.org/2000/svg}"
    if "<tspan" not in svg:
        return svg
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg)
    for text in root.iter(ns + "text"):
        kids = [k for k in text if k.tag == ns + "tspan"]
        if not any(len(list(k.iter(ns + "tspan"))) > 1 for k in kids):
            continue
        leaves = []

        def walk(el, inherited):
            attrs = dict(inherited)
            for key in ("x", "y", "text-anchor"):
                if key in el.attrib:
                    attrs[key] = el.attrib[key]
            children = [c for c in el if c.tag == ns + "tspan"]
            if not children:
                if (el.text or "").strip():
                    leaves.append((attrs, el))
                return
            for c in children:
                walk(c, attrs)
        for k in kids:
            walk(k, {})
        for k in kids:
            text.remove(k)
        for attrs, leaf in leaves:
            new = ET.SubElement(text, ns + "tspan", {a: attrs[a] for a in attrs})
            if "font-size" in leaf.attrib:
                new.set("font-size", leaf.attrib["font-size"])
            new.text = leaf.text
    return ET.tostring(root, encoding="unicode")


def highlight_measure(svg, index, colour="#e02020"):
    """Return the page SVG with measure number `index` (0-based on this page) drawn in red: the playback indicator."""
    import re
    starts = [m.start() for m in re.finditer(r'<g [^>]*class="measure"', svg)]
    if index >= len(starts):
        return svg
    a, depth, end = starts[index], 0, None
    for m in re.finditer(r"<g\b[^>]*?/>|<g\b|</g>", svg[a:]):
        if m.group(0).endswith("/>"):          # self-closing group: no depth change (it unbalanced the count before)
            continue
        depth += 1 if m.group(0) == "<g" else -1
        if depth == 0:
            end = a + m.end()
            break
    if end is None:
        return svg
    part = svg[a:end].replace('stroke="#000000"', f'stroke="{colour}"')
    part = part.replace('class="measure"', f'class="measure" fill="{colour}"', 1)
    return svg[:a] + part + svg[end:]


def collect_hits(bpm):
    """Clickable note heads of the pages just engraved by svg_pages: per page a list of
    (x, y, pitch, beat, element id) in the page's outer SVG units, plus (width, height) of each page.
    The toolkit still holds the last score, so each page is asked for its raw SVG again."""
    import re
    tk = init_verovio()
    pages, dims, spaces = [], [], []
    try:
        tk.renderToTimemap()                       # builds the MIDI timemap getMIDIValuesForElement reads
    except Exception:
        pass
    for i in range(tk.getPageCount()):
        svg = tk.renderToSVG(i + 1)
        outer = re.search(r'<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        inner = re.search(r'<svg class="definition-scale"[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        if not outer or not inner:
            pages.append([])
            dims.append((1.0, 1.0))
            spaces.append(18.0)
            continue
        k = float(outer.group(1)) / float(inner.group(1))        # same factor flatten_svg scales the page by
        dims.append((float(outer.group(1)), float(outer.group(2))))
        lines = re.search(r'class="staff"[^>]*>\s*((?:<path d="M[\d.]+ ([\d.]+) L[^"]*"[^>]*/>\s*){2})', svg)
        ys = [float(y) for y in re.findall(r'<path d="M[\d.]+ ([\d.]+) L', lines.group(1))] if lines else []
        spaces.append(abs(ys[1] - ys[0]) * k if len(ys) == 2 else 18.0)       # one staff space in the page's outer units
        half = 0.59 * (abs(ys[1] - ys[0]) if len(ys) == 2 else 18.0 / k)       # origin of the head glyph is its left edge: use its centre
        hits = []
        margin = re.search(r'class="page-margin"[^>]*transform="translate\(([-\d.]+),\s*([-\d.]+)\)', svg)
        ox, oy = (float(margin.group(1)), float(margin.group(2))) if margin else (0.0, 0.0)    # the page margin shifts everything
        for m in re.finditer(r'<g id="([^"]+)" class="note">', svg):
            head = re.search(r'class="notehead">\s*<use [^>]*transform="translate\(([-\d.]+),\s*([-\d.]+)\)', svg[m.end():m.end() + 3000])
            if not head:
                continue
            try:
                midi = tk.getMIDIValuesForElement(m.group(1))
                beat = midi["time"] / 1000.0 * bpm / 60.0 if bpm else 0.0
                hits.append(((float(head.group(1)) + ox + half) * k, (float(head.group(2)) + oy) * k, int(midi["pitch"]), beat, m.group(1)))
            except Exception:
                continue
        pages.append(hits)
    return pages, dims, spaces
