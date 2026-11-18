"""Write a GrandOrgue-native MIDI recording (what GrandOrgue's own MIDI recorder produces) from a bridge-ready MIDI file.

The bridge's MIDI files carry notes on the organ's manual channels plus markers (SETTER| / REG| / STOPS|) that only the bridge understands.
GrandOrgue's native format is a one-track MIDI file with millisecond timing (SMPTE, 1000 ticks per second) that starts with a clear message
and the organ's sample-set id, then maps each element name (M0 = pedal, S12 = switch 13 ...) to a channel / NRPN number and plays notes and
stop on / off (NRPN value 127 / 0) as events. A file in that format switches the stops by itself, with no bridge.

Format notes were read from GrandOrgue's own source (GOMidiRecorder, GOMidiEvent, GOMidiPlayerContent). Not verified on the real organ.
No Qt in here.

CHANGELOG
2026-11-19  New.
"""
import hashlib
import os

CLEAR = bytes([0xF0, 0x7D, 0x47, 0x4F, 0x00, 0xF7])
HEADER = bytes([0x4D, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, 0xE7, 0x28])     # format 0, 1 track, -25 fps x 40 ticks = 1 ms


def sampleset_ids(organ_name):
    """The two 28-bit ids GrandOrgue derives from the organ name (SHA-1 of the UTF-8 name, 7 bits of each of the first 8 bytes)."""
    h = hashlib.sha1(organ_name.encode("utf-8")).digest()
    one = ((h[0] & 0x7F) << 24) | ((h[1] & 0x7F) << 16) | ((h[2] & 0x7F) << 8) | (h[3] & 0x7F)
    two = ((h[4] & 0x7F) << 24) | ((h[5] & 0x7F) << 16) | ((h[6] & 0x7F) << 8) | (h[7] & 0x7F)
    return one, two


def element_name(path, profile):
    """GrandOrgue's recorder element name for a bridge item path, or None.

    manuals/MMM/switches/NNN -> S<global switch number - 1> (through the ODF's ManualMMM SwitchNNN = ref); a bare "047" is global switch 47;
    manuals/MMM/stops/NNN -> M<M>S<NNN-1>; manuals/MMM/couplers/NNN -> M<M>C<NNN-1>."""
    parts = str(path).split("/")
    if len(parts) == 1 and parts[0].isdigit():
        return f"S{int(parts[0]) - 1}"
    if len(parts) == 4 and parts[0] == "manuals" and parts[2] in ("switches", "stops", "couplers"):
        manual, number = int(parts[1]), int(parts[3])
        if parts[2] == "stops":
            return f"M{manual}S{number - 1}"
        if parts[2] == "couplers":
            return f"M{manual}C{number - 1}"
        for m in profile.get("manuals", []):
            if m["number"] == manual:
                for s in m["switches"]:
                    if s["index"] == number:
                        return f"S{s['ref'] - 1}"
    return None


def _varlen(value):
    value = max(0, int(value))
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


class _Track:
    def __init__(self):
        self.data = bytearray()
        self.last_ms = 0

    def at(self, ms):
        ms = max(int(round(ms)), self.last_ms)
        self.data += _varlen(ms - self.last_ms)
        self.last_ms = ms

    def sysex(self, ms, message):
        self.at(ms)
        self.data += bytes([0xF0]) + _varlen(len(message) - 1) + bytes(message[1:])

    def short(self, ms, *message):
        self.at(ms)
        self.data += bytes(message)

    def nrpn(self, ms, channel, key, value):
        c = (channel - 1) & 0x0F
        self.short(ms, 0xB0 | c, 99, (key >> 7) & 0x7F)
        self.short(ms, 0xB0 | c, 98, key & 0x7F)
        self.short(ms, 0xB0 | c, 6, value & 0x7F)


def convert(src, dst, organ_name, manuals, items, profile, setter_paths, speed=1.0):
    """Convert the bridge-ready MIDI `src` to a GrandOrgue-native recording `dst`.

    manuals: [(name, "manuals/00N", channel 1-16)]; items: the bridge's stop / coupler / tremulant items (.kind .path .manual);
    profile: scan_odf() of the organ file; setter_paths(filename, id) -> set of item paths or None; speed: playback speed to bake in.
    Returns a short summary text. Raises ValueError when nothing can be written."""
    import mido
    names = {}                                            # item path -> element name
    for it in items:
        name = element_name(it.path, profile)
        if name:
            names[it.path] = name
    manual_ch = {int(path.rsplit("/", 1)[-1]): ch for _n, path, ch in manuals}
    by_channel = {ch: number for number, ch in manual_ch.items()}
    nrpn_of, track = {}, _Track()
    track.at(0)
    track.data += bytes([0xFF, 0x04, len(organ_name.encode("ascii", "replace"))]) + organ_name.encode("ascii", "replace")
    track.sysex(0, CLEAR)
    one, two = sampleset_ids(organ_name)
    track.sysex(0, bytes([0xF0, 0x7D, 0x47, 0x4F, 0x01]) + bytes((v >> s) & 0x7F for v in (one, two) for s in (24, 16, 8, 0)) + b"\xF7")

    def setup(name, channel, key):
        raw = name.encode("ascii", "replace")
        track.sysex(0, bytes([0xF0, 0x7D, 0x47, 0x4F, 0x10 | ((channel - 1) & 0x0F), (key >> 7) & 0x7F, key & 0x7F]) + bytes(b & 0x7F for b in raw) + b"\xF7")

    for number, ch in sorted(manual_ch.items()):
        setup(f"M{number}", ch, 0)
    for path in sorted(set(names), key=lambda p: names[p]):
        n = len(nrpn_of)
        if n >= 1 << 18:
            break
        nrpn_of[path] = (1 + n // (1 << 14), n % (1 << 14))
        setup(names[path], *nrpn_of[path])
    state = {path: False for path in names}
    for path in sorted(names, key=lambda p: names[p]):     # the starting state of every element, like GrandOrgue's own recordings
        track.nrpn(0, *nrpn_of[path], 0)
    voice = {}

    def wanted_for(reg):
        if reg[0] == "stops":
            return reg[1]
        return setter_paths(reg[1], reg[2])

    def apply(ms, new):
        for path, on in new.items():
            if path in state and state[path] != on:
                state[path] = on
                track.nrpn(ms, *nrpn_of[path], 0x7F if on else 0)

    def reapply_voice(ms):
        for manual, reg in voice.items():
            wanted = wanted_for(reg)
            if wanted is None:
                continue
            apply(ms, {it.path: it.path in wanted for it in items if it.kind == "stop" and it.manual == manual})

    now, notes, dropped, markers = 0.0, 0, 0, 0
    for msg in mido.MidiFile(src):
        now += msg.time / max(speed, 0.01)
        ms = now * 1000.0
        if msg.type in ("note_on", "note_off"):
            number = by_channel.get(msg.channel + 1)
            if number is None:
                dropped += 1
                continue
            track.short(ms, (0x90 if msg.type == "note_on" else 0x80) | msg.channel, msg.note, msg.velocity if msg.type == "note_on" else 0)
            notes += 1
        elif msg.type == "marker":
            parts = str(msg.text).split("|")
            if parts[0] == "SETTER" and len(parts) >= 3:
                paths = setter_paths(parts[1], parts[2])
                if paths is not None:
                    apply(ms, {p: p in paths for p in names})
                    reapply_voice(ms)
                    markers += 1
            elif parts[0] == "REG" and len(parts) >= 4:
                voice[_manual_number(parts[1], manuals)] = ("setter", parts[2], parts[3])
                reapply_voice(ms)
                markers += 1
            elif parts[0] == "STOPS" and len(parts) >= 3:
                voice[_manual_number(parts[1], manuals)] = ("stops", {p for p in parts[2].split(";") if p})
                reapply_voice(ms)
                markers += 1
    if not notes:
        raise ValueError("no notes on the organ's manual channels in that file")
    for number, ch in sorted(manual_ch.items()):          # all notes off, as GrandOrgue's recorder ends
        track.short(now * 1000.0, 0xB0 | (ch - 1), 123, 0)
    track.data += bytes([0x00, 0xFF, 0x2F, 0x00])
    with open(dst, "wb") as handle:
        handle.write(HEADER + b"MTrk" + len(track.data).to_bytes(4, "big") + bytes(track.data))
    return f"{notes} notes, {markers} registration changes, {len(names)} stops / couplers; {os.path.basename(dst)}" + (f" ({dropped} notes on other channels left out)" if dropped else "")


def _manual_number(name, manuals):
    for n, path, _ch in manuals:
        if n == name:
            return int(path.rsplit("/", 1)[-1])
    return -1
