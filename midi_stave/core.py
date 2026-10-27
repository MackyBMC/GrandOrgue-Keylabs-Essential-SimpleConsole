"""MIDI -> stave: reading, bar warping, quantising and layout (no GUI, no notation library in here).

The key idea is the BAR MAP: a list of bar-start times in seconds. Everything inside a bar is placed by where it
falls between the two bar lines, so a bar played slowly or in a rush still comes out as a tidy bar. Move a bar line and
only the notes around it change. A bar may have its own length (pick-up bars, 3/4 -> 4/4 changes) and its own grid.
"""

import bisect
import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass
class Note:
    start: float        # seconds
    end: float
    pitch: int
    vel: int
    ch: int = 0
    track: int = 0      # MIDI track (or MusicXML part) the note came from: orchestral files map voices by (track, channel)
    stave: int = -1     # -1 = by pitch; 0,1,2... = shown on that stave whatever its pitch (cross-staff: right hand on the lower stave)
    mute: bool = False  # muted notes stay in the score but are not played


# ----------------------------------------------------------------------------------------------------- reading
GM_NAMES = ("Acoustic Grand Piano,Bright Acoustic Piano,Electric Grand Piano,Honky-tonk Piano,Electric Piano 1,Electric Piano 2,"
            "Harpsichord,Clavinet,Celesta,Glockenspiel,Music Box,Vibraphone,Marimba,Xylophone,Tubular Bells,Dulcimer,"
            "Drawbar Organ,Percussive Organ,Rock Organ,Church Organ,Reed Organ,Accordion,Harmonica,Tango Accordion,"
            "Nylon Guitar,Steel Guitar,Jazz Guitar,Clean Guitar,Muted Guitar,Overdriven Guitar,Distortion Guitar,Guitar Harmonics,"
            "Acoustic Bass,Finger Bass,Pick Bass,Fretless Bass,Slap Bass 1,Slap Bass 2,Synth Bass 1,Synth Bass 2,"
            "Violin,Viola,Cello,Contrabass,Tremolo Strings,Pizzicato Strings,Orchestral Harp,Timpani,"
            "String Ensemble 1,String Ensemble 2,Synth Strings 1,Synth Strings 2,Choir Aahs,Voice Oohs,Synth Voice,Orchestra Hit,"
            "Trumpet,Trombone,Tuba,Muted Trumpet,French Horn,Brass Section,Synth Brass 1,Synth Brass 2,"
            "Soprano Sax,Alto Sax,Tenor Sax,Baritone Sax,Oboe,English Horn,Bassoon,Clarinet,"
            "Piccolo,Flute,Recorder,Pan Flute,Blown Bottle,Shakuhachi,Whistle,Ocarina,"
            "Square Lead,Saw Lead,Calliope Lead,Chiff Lead,Charang Lead,Voice Lead,Fifths Lead,Bass+Lead,"
            "New Age Pad,Warm Pad,Polysynth Pad,Choir Pad,Bowed Pad,Metallic Pad,Halo Pad,Sweep Pad,"
            "Rain,Soundtrack,Crystal,Atmosphere,Brightness,Goblins,Echoes,Sci-fi,"
            "Sitar,Banjo,Shamisen,Koto,Kalimba,Bagpipe,Fiddle,Shanai,"
            "Tinkle Bell,Agogo,Steel Drums,Woodblock,Taiko Drum,Melodic Tom,Synth Drum,Reverse Cymbal,"
            "Guitar Fret Noise,Breath Noise,Seashore,Bird Tweet,Telephone Ring,Helicopter,Applause,Gunshot").split(",")


def load_midi(path):
    """Return (notes, info). Notes are in real seconds whatever the file's tempo map. Sustain is ignored.
    Every note remembers its MIDI track; info["voice_names"] maps (track, channel) to the track name."""
    import mido
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat or 480
    changes = sorted({(m_tick, tempo) for m_tick, tempo in _tempo_changes(mid)})
    segments, sec, last_tick, tempo = [], 0.0, 0, 500000
    for tick, new_tempo in changes:
        sec += (tick - last_tick) * tempo / 1e6 / tpb
        segments.append((tick, sec, new_tempo))
        last_tick, tempo = tick, new_tempo
    starts = [x[0] for x in segments]

    def to_sec(tick):
        i = bisect.bisect_right(starts, tick) - 1
        if i < 0:
            return tick * 500000 / 1e6 / tpb
        t0, s0, tp = segments[i]
        return s0 + (tick - t0) * tp / 1e6 / tpb

    notes, names, programs, titles = [], {}, {}, {}
    for ti, track in enumerate(mid.tracks):
        tick, open_notes, title = 0, {}, ""
        for msg in track:
            tick += msg.time
            if msg.type == "program_change":
                programs.setdefault((ti, msg.channel), msg.program)
            if msg.type == "track_name" and not title:
                title = msg.name.strip()
                titles[ti] = title
            elif msg.type == "note_on" and msg.velocity > 0:
                key = (msg.channel, msg.note)
                if key in open_notes:                                  # retrigger without off: close the old one
                    s0, v = open_notes.pop(key)
                    notes.append(Note(to_sec(s0), to_sec(tick), msg.note, v, msg.channel, ti))
                open_notes[key] = (tick, msg.velocity)
                names.setdefault((ti, msg.channel), title)
            elif msg.type in ("note_off", "note_on"):
                started = open_notes.pop((msg.channel, msg.note), None)
                if started:
                    notes.append(Note(to_sec(started[0]), to_sec(tick), msg.note, started[1], msg.channel, ti))
        for (ch, pitch), (s0, v) in open_notes.items():
            notes.append(Note(to_sec(s0), max(to_sec(tick), to_sec(s0) + 0.1), pitch, v, ch, ti))
    notes = [n for n in notes if n.end > n.start]
    notes.sort(key=lambda n: (n.start, n.pitch))
    # what is in the file: every track with its name, and every (track, channel) voice that really has notes
    voices = {}
    for n in notes:
        v = voices.setdefault((n.track, n.ch), [0, 127, 0])
        v[0] += 1
        v[1], v[2] = min(v[1], n.pitch), max(v[2], n.pitch)
    rows = []
    for ti in range(len(mid.tracks)):
        mine = sorted(k for k in voices if k[0] == ti)
        if not mine:
            rows.append({"track": ti, "name": titles.get(ti, ""), "channel": None, "program": None, "notes": 0, "lo": 0, "hi": 0})
        for k in mine:
            prog = programs.get(k)
            rows.append({"track": ti, "name": titles.get(ti, ""), "channel": k[1], "program": prog,
                         "instrument": ("Drums" if k[1] == 9 else GM_NAMES[prog] if prog is not None and prog < 128 else ""),
                         "notes": voices[k][0], "lo": voices[k][1], "hi": voices[k][2]})
    for k in list(names):                                      # name voices by track name, else the GM instrument
        if not names[k]:
            prog = programs.get(k)
            names[k] = "Drums" if k[1] == 9 else (GM_NAMES[prog] if prog is not None and prog < 128 else "")
    info = {"duration": max((n.end for n in notes), default=0.0), "channels": sorted({n.ch for n in notes}),
            "voice_names": names, "tracks": rows}
    return notes, info


def _tempo_changes(mid):
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                yield tick, msg.tempo


# ---------------------------------------------------------------------------------------------------- bar map
class BarMap:
    """anchors: n+1 bar-line times (seconds). beats: quarter-note length of each of the n bars."""

    def __init__(self, anchors, beats=None, default_beats=4.0):
        self.anchors = sorted(float(a) for a in anchors)
        n = max(0, len(self.anchors) - 1)
        self.beats = list(beats) if beats else [float(default_beats)] * n
        self.beats = (self.beats + [self.beats[-1] if self.beats else float(default_beats)] * n)[:n]

    @property
    def bar_count(self):
        return max(0, len(self.anchors) - 1)

    def cumulative(self):
        key = tuple(self.beats)                           # cached: it is asked for once per note on big pieces
        if getattr(self, "_ck", None) == key:
            return self._cv
        total, out = Fraction(0), []
        for b in self.beats:
            out.append(total)
            total += Fraction(b).limit_denominator(48)
        out.append(total)
        self._ck, self._cv, self._cf = key, out, [float(x) for x in out]
        return out                                        # n+1 values: beat position of every bar line

    def sec_to_beat(self, t):
        cum = self.cumulative()
        i = bisect.bisect_right(self.anchors, t) - 1
        i = max(0, min(i, self.bar_count - 1))
        a0, a1 = self.anchors[i], self.anchors[i + 1]
        frac = (t - a0) / (a1 - a0) if a1 > a0 else 0.0
        return float(cum[i]) + frac * self.beats[i]

    def beat_to_sec(self, beat):
        self.cumulative()
        cum = self._cf
        i = max(0, min(bisect.bisect_right(cum, beat + 1e-9) - 1, self.bar_count - 1))
        frac = (beat - cum[i]) / self.beats[i] if self.beats[i] else 0.0
        return self.anchors[i] + frac * (self.anchors[i + 1] - self.anchors[i])

    def bar_of_beat(self, beat):
        self.cumulative()
        i = bisect.bisect_right(self._cf, float(beat) + 1e-9) - 1
        return max(0, min(i, self.bar_count - 1))

    def average_bpm(self):
        total_beats = sum(self.beats)
        span = self.anchors[-1] - self.anchors[0] if len(self.anchors) > 1 else 0
        return 60.0 * total_beats / span if span > 0 else 120.0


def _weights(notes):
    return [(n.start, n.vel * (1.0 + (127 - n.pitch) / 127.0)) for n in notes]      # low notes mark the bar


def estimate_bpm(notes, lo=45, hi=150):
    """Strongest pulse in the onset pattern, preferring a comfortable 60-110 range over double / half speed."""
    if len(notes) < 4:
        return 90.0
    step = 0.01
    end = max(n.end for n in notes)
    size = int(end / step) + 2
    signal = [0.0] * size
    for t, w in _weights(notes):
        signal[int(t / step)] += w
    best, best_score = 90.0, -1.0
    for bpm in range(lo, hi + 1):
        lag = 60.0 / bpm / step
        score, count = 0.0, 0
        for i in range(0, size - int(lag) - 1, 2):
            if signal[i]:
                j = i + lag
                k = int(j)
                score += signal[i] * (signal[k] * (1 - (j - k)) + signal[k + 1] * (j - k))
                count += 1
        score = score / max(1, count)
        score *= 1.0 + 0.25 * math.exp(-((bpm - 80.0) / 30.0) ** 2)
        if score > best_score:
            best, best_score = float(bpm), score
    return best


def estimate_bars(notes, beats_per_bar=4.0, bpm=None, follow=0.6):
    """First guess at the bar lines. `follow` 0 = rigid metronome grid, 1 = chase every onset (rubato players).
    Everything it gets wrong can be dragged into place in the editor."""
    if not notes:
        return BarMap([0.0, 2.0], default_beats=beats_per_bar)
    bpm = bpm or estimate_bpm(notes)
    period = 60.0 / bpm
    onsets = sorted({round(n.start, 3) for n in notes})
    weight = {}
    for t, w in _weights(notes):
        weight[round(t, 3)] = weight.get(round(t, 3), 0) + w
    first, last = notes[0].start, max(n.end for n in notes)
    # beat phase: the offset where the most onset weight sits on the beat
    best_off, best_score = first, -1.0
    for k in range(40):
        off = first + period * k / 40.0
        score = sum(w * math.cos(2 * math.pi * (t - off) / period) for t, w in weight.items())
        if score > best_score:
            best_off, best_score = off, score
    start = best_off
    while start - period >= first - period * 0.25:
        start -= period
    # follow the player: nudge each predicted beat towards a nearby strong onset
    beats = [start]
    window = 0.3 * period
    while beats[-1] < last + period:
        predicted = beats[-1] + period
        near = [t for t in onsets if abs(t - predicted) <= window]
        if near and follow > 0:
            chosen = max(near, key=lambda t: weight[t] * (1 - abs(t - predicted) / window * 0.5))
            predicted += follow * 0.7 * (chosen - predicted)
            period = 0.92 * period + 0.08 * (predicted - beats[-1])
        beats.append(predicted)
    bpb = max(1, int(round(beats_per_bar)))
    # which beat is the downbeat: low notes carry the bar, and pieces usually begin ON a downbeat
    best_phase, best_weight = 0, -1.0
    top = max(weight.values())
    for phase in range(bpb):
        total = sum(weight[t] for t in onsets for b in beats[phase::bpb] if abs(t - b) < period * 0.2)
        if abs(beats[phase] - first) < period * 0.3:
            total += top * 2.5                              # the first note sits on this beat: favour it
        if total > best_weight:
            best_phase, best_weight = phase, total
    anchors = beats[best_phase::bpb]
    if best_phase and anchors[0] > first + period * 0.3:    # a pick-up: the first bar line falls before the first note
        anchors = [anchors[0] - period * bpb] + anchors
    elif best_phase:
        anchors = [anchors[0]] + anchors[1:]
    return BarMap(anchors, default_beats=beats_per_bar)


# --------------------------------------------------------------------------------------------------- quantising
GRID_CHOICES = {"1/4 (quarter)": Fraction(1), "1/8": Fraction(1, 2), "1/16": Fraction(1, 4), "1/32": Fraction(1, 8),
                "1/64": Fraction(1, 16)}


@dataclass
class QNote:
    start: Fraction       # beat position (quarter notes) counted from the first bar line
    end: Fraction
    pitch: int
    vel: int
    ch: int
    bar: int
    rs: float = 0.0       # unquantised start / end in beats (kept for phrasing: slurs, staccato)
    re: float = 0.0
    track: int = 0
    src: int = -1          # index of the source note in the list that was quantised (score click -> note)
    stave: int = -1        # forced stave index (see Note.stave)


def _snap(value, unit):
    return Fraction(round(value / unit)) * unit if unit else value


def quantise(notes, barmap, grid=Fraction(1, 4), triplets=True, chord_window=0.045, min_len=None,
             legato_gap=Fraction(1, 2), bar_grid=None):
    """Snap notes to the grid inside the warped bars.

    grid        smallest straight subdivision, in quarter notes (1/4 = sixteenths).
    triplets    each beat may use a triplet grid when that fits the played notes clearly better.
    bar_grid    {bar_index: Fraction | 't'}: per-bar override of the grid ('t' forces triplets in that bar).
    legato_gap  rests shorter than this (quarters) between notes of one line are closed (play was not that short).
    """
    bar_grid = bar_grid or {}
    min_len = min_len or grid
    position = {id(n): i for i, n in enumerate(notes)}
    ordered = sorted(notes, key=lambda n: n.start)
    # chords: onsets a few ms apart belong together (stops hands from looking like grace notes)
    clustered, anchor_t = [], None
    for n in ordered:
        if anchor_t is not None and n.start - anchor_t <= chord_window:
            clustered.append((anchor_t, n))
        else:
            anchor_t = n.start
            clustered.append((anchor_t, n))
    raw = []
    for t0, n in clustered:
        raw.append((barmap.sec_to_beat(t0), barmap.sec_to_beat(max(n.end, t0 + 0.02)), n))
    # decide straight or triplet per beat from the onsets that fall in it
    per_beat = {}
    for b0, _, _ in raw:
        per_beat.setdefault(int(math.floor(b0 + 1e-9)), []).append(b0)

    def unit_for(beat_index, bar_index):
        override = bar_grid.get(bar_index)
        if override == "t":
            return Fraction(1, 3)
        base = override if isinstance(override, Fraction) else grid
        if not triplets or bar_index in bar_grid and isinstance(override, Fraction):
            return base
        points = per_beat.get(beat_index, [])
        if len(points) < 3:                                # a real triplet beat has three onsets
            return base
        err_straight = sum((p - float(_snap(Fraction(p).limit_denominator(1000), base))) ** 2 for p in points)
        err_triplet = sum((p - float(_snap(Fraction(p).limit_denominator(1000), Fraction(1, 3)))) ** 2 for p in points)
        return Fraction(1, 3) if err_triplet < err_straight * 0.35 and err_triplet < 0.0015 * len(points) else base

    out = []
    for b0, b1, n in raw:
        bar = barmap.bar_of_beat(b0)
        u0 = unit_for(int(math.floor(b0 + 1e-9)), bar)
        s = _snap(Fraction(b0).limit_denominator(1000), u0)
        duration = _snap(Fraction(max(b1 - b0, 0.0)).limit_denominator(1000), u0 if u0 != Fraction(1, 3) or b1 - b0 < 1 else grid)
        if duration < min_len and u0 != Fraction(1, 3):
            duration = min_len
        duration = max(duration, Fraction(1, 3) if u0 == Fraction(1, 3) else min_len)
        e = s + duration                                    # length snapped in the SAME grid family as its start
        out.append(QNote(s, e, n.pitch, n.vel, n.ch, bar, b0, b1, n.track, position.get(id(n), -1), getattr(n, 'stave', -1)))
    return out


# ------------------------------------------------------------------------------------------------------ staves
@dataclass
class StaveSpec:
    name: str
    clef: str = "treble"          # treble / bass
    lo: int = 0
    hi: int = 127
    channels: tuple = ()          # empty = any
    voices: tuple = ()            # ((track, channel), ...) this stave takes; empty = any
    go_chs: tuple = None          # MIDI channels (1-16) this stave is written on (one per manual it plays); empty = keep source
    role: str = ""                # "manual:<n>" (0 = first manual) or "pedal": lets the editor suggest the GrandOrgue manual
    lead_limit: int = None        # pedal stave fed only by the lowest note of each chord, at or below this MIDI note


NAME_SETS = {"English": (["Great", "Swell", "Choir", "Solo", "Echo"], "Pedal"),
             "German": (["Hauptwerk", "Schwellwerk", "Positiv", "Solowerk", "Echowerk"], "Pedal"),
             "French": (["Grand-Orgue", "R\u00e9cit", "Positif", "Solo", "\u00c9cho"], "P\u00e9dale"),
             "Numbered": (["Manual I", "Manual II", "Manual III", "Manual IV", "Manual V"], "Pedal")}


def organ_staves(organ, split, pedal):
    """N manual staves (highest band first) and an optional pedal stave. organ = {"manuals": 1-5, "names": [...],
    "pedal_name": str, "pedal": "range" | "bass" | "off"}. Manual names are display names: the slot (first manual,
    second manual ...) is what maps to GrandOrgue."""
    n = max(1, min(5, int(organ.get("manuals", 2))))
    names = [x.strip() for x in organ.get("names", []) if x and x.strip()]
    names += [f"Manual {'I' * (i + 1) if i < 3 else ('IV', 'V')[i - 3]}" for i in range(len(names), n)]
    mode = organ.get("pedal", "range")
    low = pedal if mode == "range" else 0                 # lowest note a manual stave takes
    if n == 1:
        edges = [(low, 127)]
    elif n == 2:
        edges = [(split, 127), (low, split - 1)]
    else:
        pts = [low + round((128 - low) * k / n) for k in range(n + 1)]
        edges = [(pts[n - 1 - k], pts[n - k] - 1) for k in range(n)]
    result = []
    for i, (lo, hi) in enumerate(edges):
        result.append(StaveSpec(names[i], "treble" if lo >= 55 else "bass", lo, hi, role=f"manual:{i}"))
    if mode != "off":
        pedal_name = organ.get("pedal_name") or "Pedal"
        if mode == "bass":
            result.append(StaveSpec(pedal_name, "bass", 0, 127, role="pedal", lead_limit=pedal))
        else:
            result.append(StaveSpec(pedal_name, "bass", 0, pedal - 1, role="pedal"))
    return result


def make_staves(kind, split=60, split2=53, split3=67, pedal=48, notes=None, voice_names=None, organ=None):
    if kind == "organbass":
        return organ_staves(dict(organ or {}, manuals=2, pedal="bass"), split, pedal)
    if kind == "organx":
        return organ_staves(organ or {}, split, pedal)
    if kind == "grand":
        return [StaveSpec("Right hand", "treble", split, 127), StaveSpec("Left hand", "bass", 0, split - 1)]
    if kind == "organ":
        return [StaveSpec("Manual I", "treble", split, 127), StaveSpec("Manual II", "bass", pedal, split - 1),
                StaveSpec("Pedal", "bass", 0, pedal - 1)]
    if kind == "choir":
        return [StaveSpec("Soprano", "treble", split3, 127), StaveSpec("Alto", "treble", split, split3 - 1),
                StaveSpec("Tenor", "bass", split2, split - 1), StaveSpec("Bass", "bass", 0, split2 - 1)]
    if kind == "voices":                       # orchestral: one stave per MIDI track / channel, highest first
        groups = {}
        for n in notes or []:
            groups.setdefault((n.track, n.ch), []).append(n.pitch)
        keys = [k for k in groups if k[1] != 9] or list(groups)          # channel 10 = drums: left out
        keys.sort(key=lambda k: -sorted(groups[k])[len(groups[k]) // 2])
        result = []
        for k in keys:
            mid = sorted(groups[k])[len(groups[k]) // 2]
            title = (voice_names or {}).get(k) or f"Track {k[0] + 1} ch {k[1] + 1}"
            result.append(StaveSpec(title, "treble" if mid >= 55 else "bass", 0, 127, (), (k,)))
        return result or [StaveSpec("Solo")]
    if kind == "channels":
        chans = sorted({n.ch for n in notes or []}) or [0]
        result = []
        for c in chans:
            mine = sorted(n.pitch for n in notes or [] if n.ch == c) or [60]
            result.append(StaveSpec(f"Channel {c + 1}", "treble" if mine[len(mine) // 2] >= 55 else "bass", 0, 127, (c,)))
        return result
    pitches = sorted(n.pitch for n in notes or []) or [60]
    return [StaveSpec("Solo", "treble" if pitches[len(pitches) // 2] >= 55 else "bass", 0, 127)]


def split_voices(notes, max_voices=2):
    """Voice separation inside one stave. Legato overlaps (a tail running into the next onset) are trimmed to the next onset;
    what is really sustained under moving notes goes to a second voice. Units (same start+end = a chord) are dealt greedily to
    the free voice whose last pitch is nearest. Returns voices upper first."""
    import dataclasses
    if not notes:
        return [notes]
    onsets = sorted({q.start for q in notes})
    prepared = []
    for q in notes:
        nxt = next((o for o in onsets if o > q.start), None)
        if nxt is not None and q.end > nxt:
            over, dur = float(q.end - nxt), float(q.end - q.start)
            if over <= max(0.26, 0.34 * dur):
                q = dataclasses.replace(q, end=nxt)
        prepared.append(q)
    units = {}
    for q in prepared:
        units.setdefault((q.start, q.end), []).append(q)
    ordered = sorted(units.items(), key=lambda kv: (kv[0][0], -sum(x.pitch for x in kv[1]) / len(kv[1])))
    voices = []                                     # each: {"units": [], "end": Fraction, "last": mean pitch}
    for (start, end), members in ordered:
        mean = sum(x.pitch for x in members) / len(members)
        free = [v for v in voices if v["end"] <= start]
        if free:
            v = min(free, key=lambda v: abs(v["last"] - mean) + abs(v["avg"] - mean))
        elif len(voices) < max_voices:
            v = {"units": [], "end": start, "last": mean, "avg": mean, "n": 0}
            voices.append(v)
        else:                                       # both voices busy: cut the nearest voice's current unit short
            v = min(voices, key=lambda v: abs(v["last"] - mean) + abs(v["avg"] - mean))
            if v["units"]:
                (ps, pe), pm = v["units"][-1]
                v["units"][-1] = ((ps, min(pe, start)), [dataclasses.replace(x, end=min(x.end, start)) for x in pm])
                v["units"] = [u for u in v["units"] if u[0][1] > u[0][0]]
        v["units"].append(((start, end), members))
        v["end"], v["last"] = end, mean
        v["avg"] = (v["avg"] * v["n"] + mean) / (v["n"] + 1)
        v["n"] += 1
    voices.sort(key=lambda v: -sum(sum(x.pitch for x in m) / len(m) for _k, m in v["units"]) / max(1, len(v["units"])))
    return [[x for _k, m in v["units"] for x in m] for v in voices] or [notes]


STAVE_HOLD = 0.0       # beats: a line that dips just past a split point stays on its stave if it came from there this recently


def _accepts(spec, q):
    return (not spec.channels or q.ch in spec.channels) and (not spec.voices or (q.track, q.ch) in spec.voices)


def assign(qnotes, staves, hold=None):
    """Notes -> staves. A note with a forced stave goes there whatever its pitch (hand crossing). Otherwise by pitch range, with
    hysteresis: a line that has just been on a stave keeps it for notes up to 5 semitones past that stave's edge when
    they follow within `hold` beats (no jumping between staves for one low passing note)."""
    hold = STAVE_HOLD if hold is None else hold
    result = [[] for _ in staves]
    last = {}                                          # (track, ch) -> (stave index, end beat)
    lead_of = next((i for i, sp in enumerate(staves) if getattr(sp, "lead_limit", None) is not None), None)
    lead_ids = set()
    if lead_of is not None:                            # pedal fed by the lowest note of each chord
        lows = {}
        for q in qnotes:
            if lows.get(q.start) is None or q.pitch < lows[q.start].pitch:
                lows[q.start] = q
        lead_ids = {id(q) for q in lows.values() if q.pitch <= staves[lead_of].lead_limit}
    for q in sorted(qnotes, key=lambda x: (x.start, x.pitch)):
        forced = getattr(q, "stave", -1)
        target = None
        if 0 <= forced < len(staves):
            target = forced
        elif lead_of is not None and id(q) in lead_ids:
            target = lead_of
        else:
            for i, spec in enumerate(staves):
                if spec.lead_limit is None and spec.lo <= q.pitch <= spec.hi and _accepts(spec, q):
                    target = i
                    break
            if target is not None and hold > 0:
                prev = last.get((q.track, q.ch))
                if prev and prev[0] != target and float(q.start) - prev[1] <= hold:
                    spec = staves[prev[0]]
                    if _accepts(spec, q) and spec.lo - 5 <= q.pitch <= spec.hi + 5:
                        target = prev[0]
        if target is None:
            continue
        result[target].append(q)
        last[(q.track, q.ch)] = (target, float(q.end))
    for lst in result:
        lst.sort(key=lambda x: (x.start, x.pitch))
    return result


TRACK_SPLIT = {}       # (track, source channel) -> (pedal channels, other channels), 1-16: lowest note of each chord on the pedal, the rest elsewhere
PEDAL_LEAD_IDS = set()  # id() of the notes that are the lowest of their chord in a split track
PEDAL_LEAD_IDX = set()  # the same as indexes into the editor's note list (for the quantised notes, which carry `src`)


def pedal_leads(notes, keys, window=0.045, limit=127):
    """Notes that are the lowest of each onset cluster (starts within `window` s) in the tracks `keys`, and no higher than
    MIDI note `limit` (a lone melody note above it stays on the manual): [(index, note)]."""
    result = []
    for key in keys:
        mine = sorted(((i, n) for i, n in enumerate(notes) if (n.track, n.ch) == key), key=lambda x: x[1].start)
        cluster = []
        for item in mine + [None]:
            if item is not None and (not cluster or item[1].start - cluster[0][1].start <= window):
                cluster.append(item)
                continue
            if cluster:
                low = min(cluster, key=lambda x: x[1].pitch)
                if low[1].pitch <= limit:
                    result.append(low)
            cluster = [item] if item is not None else []
    return result


def is_polyphonic(notes, key, window=0.045):
    starts = sorted(n.start for n in notes if (n.track, n.ch) == key)
    return any(b - a <= window for a, b in zip(starts, starts[1:])) or any(
        a.end > b.start + 0.02 for a, b in zip(sorted((n for n in notes if (n.track, n.ch) == key), key=lambda n: n.start),
                                                sorted((n for n in notes if (n.track, n.ch) == key), key=lambda n: n.start)[1:]))


TRACK_ROUTES = {}      # (track, source channel) -> GrandOrgue channels 1-16 chosen for that track in the Tracks list (set by the editor)


def stave_go_channels(pitch, ch, staves, track=0, forced=-1, lead=False):
    """Output channels (0-15) for a note, from the stave that owns it (same rule as assign). A stave that plays
    several manuals gives several channels (the note is written once per manual); source channel if none set."""
    split = TRACK_SPLIT.get((track, ch))
    if split and not (staves and 0 <= forced < len(staves)):
        return [c - 1 for c in (split[0] if lead else split[1])]
    route = TRACK_ROUTES.get((track, ch))
    if route and not (staves and 0 <= forced < len(staves)):          # the track's own manual mapping wins over the stave layout
        return [c - 1 for c in route]
    if staves and 0 <= forced < len(staves):
        spec = staves[forced]
        return [c - 1 for c in spec.go_chs] if spec.go_chs is not None else [ch]
    for spec in staves or []:
        if spec.lo <= pitch <= spec.hi and (not spec.channels or ch in spec.channels) and (not spec.voices or (track, ch) in spec.voices):
            return [c - 1 for c in spec.go_chs] if spec.go_chs is not None else [ch]
    mapped = any(spec.go_chs is not None for spec in staves or [])
    return [] if mapped else [ch]                      # notes no stave owns (e.g. drums) are dropped once manuals are mapped


def melodic_line(stave_notes, legato_gap=Fraction(1, 2)):
    """One stave -> a list of (start, end, [pitches], mean_velocity, legato) with no overlaps: a chord lasts until the
    next onset (long tails under moving notes are cut, the usual single-voice simplification). `legato` is how much of
    the distance to the next onset the player really held the note (1.0 = joined up, 0.3 = detached)."""
    groups = {}
    for q in stave_notes:
        groups.setdefault(q.start, []).append(q)
    starts = sorted(groups)
    line = []
    for i, s in enumerate(starts):
        members = groups[s]
        end = max(m.end for m in members)
        legato = 1.0
        if i + 1 < len(starts):
            nxt = starts[i + 1]
            raw_start = min(m.rs for m in members)
            raw_next = min(m.rs for m in groups[nxt])
            raw_end = max(m.re for m in members)
            if raw_next > raw_start:
                legato = max(0.0, min(1.0, (raw_end - raw_start) / (raw_next - raw_start)))
            end = min(end, nxt)
            if nxt - end <= legato_gap:
                end = nxt                                   # close small gaps: sustained / legato playing
        line.append((s, end, sorted({m.pitch for m in members}), sum(m.vel for m in members) // len(members), legato))
    return line


def slur_phrases(line, threshold=0.9, min_events=3, max_events=8):
    """Runs of joined-up notes -> lists of event indexes to slur."""
    phrases, run = [], [0] if line else []
    for i in range(len(line) - 1):
        joined = line[i][4] >= threshold and line[i + 1][0] - line[i][1] <= 0
        if joined and len(run) < max_events:
            run.append(i + 1)
        else:
            if len(run) >= min_events:
                phrases.append(run)
            run = [i + 1]
    if len(run) >= min_events:
        phrases.append(run)
    return phrases


# ------------------------------------------------------------------------------------------------- MusicXML in
def load_musicxml(path):
    """Read a MusicXML / .mxl file as a 'performance' at its written tempo: (notes, info). info["barmap"] holds the
    bar lines exactly as written (so nothing needs detecting), info["names"] the part names."""
    from music21 import converter, tempo, stream
    score = converter.parse(path)
    parts = list(score.parts) or [score]
    bpm = 90.0
    for mark in score.recurse().getElementsByClass(tempo.MetronomeMark):
        value = mark.getQuarterBPM() or mark.number
        if value:
            bpm = float(value)
            break
    spq = 60.0 / bpm
    notes, names, open_ties = [], [], {}
    for pi, part in enumerate(parts):
        names.append(str(part.partName or f"Part {pi + 1}"))
        found = []
        for el in part.recurse().notes:
            if el.duration.quarterLength <= 0:
                continue                                        # grace notes
            start = float(el.getOffsetInHierarchy(part))
            vel = el.volume.velocity if getattr(el, "volume", None) is not None and el.volume.velocity else 80
            for n in (el.notes if hasattr(el, "notes") and el.isChord else [el]):
                found.append((start, float(el.duration.quarterLength), n.pitch.midi, vel,
                              n.tie.type if n.tie is not None else None))
        found.sort(key=lambda f: (f[0], f[2]))
        for start, length, midi, vel, tie_type in found:
            key = (pi, midi)
            if tie_type in ("stop", "continue") and key in open_ties:
                open_ties[key].end = (start + length) * spq
                if tie_type == "stop":
                    del open_ties[key]
                continue
            note = Note(start * spq, (start + length) * spq, midi, int(vel), min(pi, 15), pi)
            notes.append(note)
            if tie_type == "start":
                open_ties[key] = note
    notes.sort(key=lambda n: (n.start, n.pitch))
    measures = list(parts[0].getElementsByClass(stream.Measure))
    anchors, beats = [], []
    for i, m in enumerate(measures):
        offset = float(m.offset)
        length = (float(measures[i + 1].offset) - offset) if i + 1 < len(measures) else \
            max(float(m.highestTime), float(m.barDuration.quarterLength) if m.barDuration else 4.0)
        if length <= 0:
            continue
        anchors.append(offset * spq)
        beats.append(length)
    if anchors:
        anchors.append(anchors[-1] + beats[-1] * spq)
    barmap = BarMap(anchors, beats) if len(anchors) > 1 else estimate_bars(notes, 4.0)
    info = {"duration": max((n.end for n in notes), default=0.0), "channels": sorted({n.ch for n in notes}),
            "barmap": barmap, "names": names, "bpm": bpm, "title": str(getattr(score.metadata, "title", "") or "")}
    return notes, info


# ------------------------------------------------------------------------------------------------ fixed MIDI
def export_fixed_midi(notes, barmap, path, bpm=None, quantised=None, staves=None, markers=None, transpose=0):
    """Write the performance on a steady beat: bars are straightened (rushed bars slowed, slow bars sped up) but the
    notes keep their human feel unless `quantised` notes are given, then those are written exactly on the grid.
    staves: StaveSpecs with go_ch set write each stave on its own channel. markers: [(beat, text)] MIDI marker events
    (organ setter changes, see sessionmeta)."""
    import mido
    bpm = bpm or barmap.average_bpm()
    tpb = 480
    events = []
    if quantised is not None:
        for q in quantised:
            for ch in stave_go_channels(q.pitch, q.ch, staves, q.track, getattr(q, 'stave', -1), q.src in PEDAL_LEAD_IDX):
                events.append((int(round(float(q.start) * tpb)), 1, max(0, min(127, q.pitch + transpose)), q.vel, ch))
                events.append((int(round(float(q.end) * tpb)), 0, max(0, min(127, q.pitch + transpose)), 0, ch))
    else:
        for n in notes:
            for ch in stave_go_channels(n.pitch, n.ch, staves, n.track, getattr(n, 'stave', -1), id(n) in PEDAL_LEAD_IDS):
                events.append((int(round(barmap.sec_to_beat(n.start) * tpb)), 1, max(0, min(127, n.pitch + transpose)), n.vel, ch))
                events.append((int(round(barmap.sec_to_beat(n.end) * tpb)), 0, max(0, min(127, n.pitch + transpose)), 0, ch))
    for beat, text in markers or []:
        events.append((int(round(float(beat) * tpb)), -1, 0, 0, text))        # -1 sorts before notes at the same tick
    events.sort(key=lambda e: (e[0], e[1]))
    track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=int(60_000_000 / bpm), time=0)])
    previous = 0
    for tick, on, pitch, vel, ch in events:
        tick = max(0, tick)
        if on == -1:
            track.append(mido.MetaMessage("marker", text=ch, time=tick - previous))
            previous = tick
            continue
        track.append(mido.Message("note_on" if on else "note_off", channel=ch, note=pitch, velocity=vel, time=tick - previous))
        previous = tick
    mid = mido.MidiFile(type=0, ticks_per_beat=tpb)
    mid.tracks.append(track)
    mid.save(path)


# ------------------------------------------------------------------------------------------------ shape the MIDI timing
def shape_notes(notes, barmap, mode="grid", grid_beats=0.25, ms=50.0, strength=1.0, swing=0.0, humanise_ms=0.0,
                ends="keep", legato=1.0, lo=0, hi=127, only=None, seed=1, fingered=None, max_gap=1.0):
    """Re-time the RAW notes in place (the caller pushes undo first; `_raw` keeps each note's original start / end).

    mode        "grid": snap starts to a beat grid (grid_beats, in the warped bars); "time": snap to fixed milliseconds.
    strength    0..1: how far each start moves toward its snapped position (1 = fully snapped, 0.5 = half way: keeps feel).
    swing       0..1: delay the off-beat grid points by this fraction of a grid step (grid mode).
    humanise_ms random +- jitter on every start afterwards (seeded: same result every time).
    ends        "keep" the note length, "snap" the end to the grid / time step, or "legato": run each note on toward the
                next onset of the same voice, `legato` = fraction of that gap held (1 = joined, 1.2 = slight overlap slur).
                "fingered": notes carrying a finger number (`fingered` = set of note ids) are joined to the next fingered
                note of their voice (a finger-numbered run is played legato; a substitution mark means the key is held).
                "organ": any note is joined to the next onset when the gap is at most `max_gap` beats (piano-style MIDI made
                organ-friendly); a repeated pitch is always released 10 ms before it strikes again.
    lo, hi      only notes with MIDI numbers lo..hi are touched; `only` = optional set of note ids (the selection).
    Returns the number of notes changed."""
    import random
    rng = random.Random(seed)
    chosen = [n for n in notes if lo <= n.pitch <= hi and (only is None or id(n) in only)]
    for n in chosen:
        if not hasattr(n, "_raw"):
            n._raw = (n.start, n.end)
    for n in chosen:
        length = n.end - n.start
        if mode == "time":
            step = max(ms, 1.0) / 1000.0
            target = round(n.start / step) * step
        else:
            beat = barmap.sec_to_beat(n.start)
            unit = max(float(grid_beats), 1e-3)
            index = round(beat / unit)
            snapped = index * unit
            if swing and index % 2:
                snapped += swing * unit
            target = barmap.beat_to_sec(snapped)
        start = n.start + (target - n.start) * max(0.0, min(1.0, strength))
        if humanise_ms:
            start += rng.uniform(-humanise_ms, humanise_ms) / 1000.0
        n.start = max(0.0, start)
        n.end = n.start + length
    if ends in ("fingered", "organ"):
        voices = {}
        for n in chosen:
            if ends == "organ" or (fingered and id(n) in fingered):
                voices.setdefault((n.track, n.ch), []).append(n)
        for group in voices.values():
            group.sort(key=lambda n: (n.start, n.pitch))
            for i, n in enumerate(group):
                nxt = next((m.start for m in group[i + 1:] if m.start > n.start + 0.06), None)
                if nxt is None:
                    continue
                gap_beats = barmap.sec_to_beat(nxt) - barmap.sec_to_beat(n.end)
                if ends == "fingered" or gap_beats <= max_gap:
                    n.end = max(n.end, n.start + (nxt - n.start) * max(0.1, legato))     # only ever lengthens: held notes stay held
        if ends == "organ":                                    # same pitch must be released before it is struck again
            by_pitch = {}
            for n in chosen:
                by_pitch.setdefault((n.track, n.ch, n.pitch), []).append(n)
            for group in by_pitch.values():
                group.sort(key=lambda n: n.start)
                for a, b in zip(group, group[1:]):
                    if a.end > b.start - 0.01:
                        a.end = max(a.start + 0.02, b.start - 0.01)
    if ends in ("snap", "legato"):
        voices = {}
        for n in chosen:
            voices.setdefault((n.track, n.ch), []).append(n)
        for group in voices.values():
            group.sort(key=lambda n: (n.start, n.pitch))
            for i, n in enumerate(group):
                nxt = next((m.start for m in group[i + 1:] if m.start > n.start + 0.06), None)
                if ends == "legato" and nxt is not None:
                    n.end = n.start + max(0.02, (nxt - n.start) * max(0.1, legato))
                elif ends == "snap":
                    if mode == "time":
                        step = max(ms, 1.0) / 1000.0
                        n.end = max(n.start + step, round(n.end / step) * step)
                    else:
                        unit = max(float(grid_beats), 1e-3)
                        b0 = barmap.sec_to_beat(n.start)
                        b1 = max(b0 + unit, round(barmap.sec_to_beat(n.end) / unit) * unit)
                        n.end = barmap.beat_to_sec(b1)
    return len(chosen)


def restore_raw(notes, lo=0, hi=127, only=None):
    """Put back the original start / end that shape_notes remembered."""
    count = 0
    for n in notes:
        if hasattr(n, "_raw") and lo <= n.pitch <= hi and (only is None or id(n) in only):
            n.start, n.end = n._raw
            del n._raw
            count += 1
    return count
