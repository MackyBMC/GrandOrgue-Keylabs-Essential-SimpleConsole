"""Organ divisions, switch paths, and configurable bank layout."""

DIVISIONS = [   # (code, name, manual number in the organ, stop names as shown on the 16-char LCD)
    ("P", "Pedal", 0, ["Untersatz 32'", "Contrabass 16'", "Subbass 16'", "Octavbass 8'", "Gedackt 8'",
                       "Choralbass 4'", "Posaune 32'", "Posaune 16'", "Trompete 8'"]),
    ("H", "Hauptwerk", 1, ["Praestant 16'", "Principal 8'", "Holzflote 8'", "Rohrflote 8'", "Gambe 8'",
                           "Octave 4'", "Spitzflote 4'", "Quinte 2 2/3'", "Octave 2'", "Mixtur mj 2 2/3'",
                           "Mixtur mi 1 1/3'", "Trompete 16'", "Trompete 8'"]),
    ("S", "Schwellwerk", 2, ["Bourdon 16'", "Principal 8'", "Nacht.Ged. 8'", "Corno dolce 8'", "Viola 8'",
                             "V. celeste 8'", "Geigenpr. 4'", "Querflote 4'", "Nazard 2 2/3'", "Flageolett 2'",
                             "Tierce 1 3/5'", "Larigot 1 1/3'", "Plein jeu 2'", "Scharff 1'", "Trp. harm. 8'",
                             "Hautbois 8'", "Clairon 4'"]),
    ("L", "Solowerk", 3, ["Jubalflote 8'", "Trichterfl. 4'", "Cornet 8'", "Trp.chamade 8'", "Engl. Horn 8'"]),
]


OTHERS = [  # (kind, manual, number, LCD name, GrandOrgue object name) - couplers 1-3 pedal, 4-5 Hauptwerk, 6 Schwellwerk
    ("coupler", 0, 1, "Coupler 1 (ped)", "Coupler 1"), ("coupler", 0, 2, "Coupler 2 (ped)", "Coupler 2"),
    ("coupler", 0, 3, "Coupler 3 (ped)", "Coupler 3"), ("coupler", 1, 1, "Coupler 4 (HW)", "Coupler 4"),
    ("coupler", 1, 2, "Coupler 5 (HW)", "Coupler 5"), ("coupler", 2, 1, "Coupler 6 (SW)", "Coupler 6"),
    ("tremulant", None, 1, "Tremolo II", ""), ("tremulant", None, 2, "Tremolo III", ""),
]


BANK_SIZE = 8


SWITCH_OFFSET = {0: 3, 1: 2, 2: 1, 3: 0}     # manual -> how many switches come before its first stop


TREMULANT_SWITCH = {1: 47, 2: 53}           # tremulant number -> global switch number


STOP_CHANNELS = [15]                         # 1-based MIDI channels carrying the stop/coupler CCs, 127 controls each
DEFAULT_SPILL_CHANNELS = [13, 11, 9, 8, 7, 6]   # tried in order when an organ needs more than 127 controls
CCS_PER_CHANNEL = 127
PATH_OVERRIDES = {}                           # (kind, manual, number) -> explicit GrandOrgue object path


def wire_for(cc, channels):
    """Control number (1-based, unique across the organ) -> (0-based MIDI channel, CC key 1-127)."""
    return channels[(cc - 1) // CCS_PER_CHANNEL] - 1, (cc - 1) % CCS_PER_CHANNEL + 1


class Item:
    def __init__(self, kind, manual, number, name, cc, bank_code, division, odf_name=""):
        self.kind, self.manual, self.number, self.name, self.cc = kind, manual, number, name, cc
        self.bank_code, self.division, self.odf_name = bank_code, division, odf_name

    @property
    def channel(self):
        return wire_for(self.cc, STOP_CHANNELS)[0]

    @property
    def key(self):
        return wire_for(self.cc, STOP_CHANNELS)[1]

    @property
    def path(self):
        """The panel knobs are Switch objects in this organ: stops sit after the couplers in each manual's
        switch list (Pedal +3, Hauptwerk +2, Schwellwerk +1, Solowerk +0); couplers are switches 1-3 / 1-2 / 1;
        the two tremulant buttons are the global switches 47 and 53, which have no parent folder in the path."""
        override = PATH_OVERRIDES.get((self.kind, self.manual, self.number))
        if override:
            return override
        if self.kind == "stop":
            return f"manuals/{self.manual:03d}/switches/{self.number + SWITCH_OFFSET[self.manual]:03d}"
        if self.kind == "coupler":
            return f"manuals/{self.manual:03d}/switches/{self.number:03d}"
        return f"{TREMULANT_SWITCH[self.number]:03d}"


TREMULANT_DIVISION = {1: "S", 2: "L"}    # Tremolo II -> Schwellwerk bank, Tremolo III -> Solowerk bank (see config.yaml)


def build_banks(trem_div=None):
    """CC numbers never depend on the layout: stops 1-44, couplers 45-50, tremulants 51-52."""
    trem_div = TREMULANT_DIVISION if trem_div is None else trem_div
    items, stops_by_div, cc = [], {}, 0
    for code, dname, manual, names in DIVISIONS:
        lst = []
        for i, nm in enumerate(names):
            cc += 1
            lst.append(Item("stop", manual, i + 1, nm, cc, code, dname))
        stops_by_div[code] = lst
        items += lst
    others = []
    for kind, manual, number, nm, odf in OTHERS:
        cc += 1
        others.append(Item(kind, manual, number, nm, cc, "C1", "Couplers", odf))
    items += others
    banks = []
    for code, dname, manual, names in DIVISIONS:
        lst = stops_by_div[code]
        for b in range(0, len(lst), BANK_SIZE):
            chunk, bcode = lst[b:b + BANK_SIZE], f"{code}{b // BANK_SIZE + 1}"
            for it in chunk:
                it.bank_code, it.division = bcode, dname
            banks.append({"code": bcode, "division": dname, "items": chunk})
    rest = [it for it in others if it.kind in ("coupler", "tremulant")]
    banks.append({"code": "C1", "division": "Couplers", "items": rest})
    return items, banks


ITEMS, BANKS = build_banks()


ITEM_BY_CC = {it.cc: it for it in ITEMS}
ITEM_BY_WIRE = {(it.channel, it.key): it for it in ITEMS}      # what GrandOrgue feedback is matched against


def rebuild_layout(trem_div):
    """Re-cut the fader banks after config.yaml says which division each tremolo belongs to."""
    global ITEMS, BANKS, ITEM_BY_CC, ITEM_BY_WIRE
    items, banks = build_banks(trem_div)
    ITEMS[:] = items
    BANKS[:] = banks
    ITEM_BY_CC.clear()
    ITEM_BY_CC.update({it.cc: it for it in ITEMS})
    ITEM_BY_WIRE.clear()
    ITEM_BY_WIRE.update({(it.channel, it.key): it for it in ITEMS})


def current_spec():
    """The layout tables as a plain dict: exactly what Organs/<organ>.layout.yaml holds."""
    divisions = []
    for c, n, m, stops in DIVISIONS:
        entries = []
        for i, name in enumerate(stops):
            path = PATH_OVERRIDES.get(("stop", m, i + 1))
            entries.append({"name": name, "path": path} if path else name)
        divisions.append({"code": c, "name": n, "manual": m, "switch_offset": SWITCH_OFFSET.get(m, 0), "stops": entries})
    couplers = []
    for kind, m, num, nm, odf in OTHERS:
        if kind == "coupler":
            entry = {"manual": m, "number": num, "name": nm, "odf_name": odf}
            if ("coupler", m, num) in PATH_OVERRIDES:
                entry["path"] = PATH_OVERRIDES[("coupler", m, num)]
            couplers.append(entry)
    tremulants = []
    for kind, m, num, nm, odf in OTHERS:
        if kind == "tremulant":
            entry = {"number": num, "name": nm, "division": TREMULANT_DIVISION.get(num, "")}
            if num in TREMULANT_SWITCH:
                entry["switch"] = TREMULANT_SWITCH[num]
            if ("tremulant", None, num) in PATH_OVERRIDES:
                entry["path"] = PATH_OVERRIDES[("tremulant", None, num)]
            tremulants.append(entry)
    return {"stop_channels": list(STOP_CHANNELS), "divisions": divisions, "couplers": couplers, "tremulants": tremulants}


def items_for_spec(spec):
    """Pure: [(kind, path, cc, name, channel0, key)] a layout spec would produce, without touching the live tables.
    Numbering rule (unchanged): stops in division order, then couplers, then tremulants, from 1. Number n lives on
    stop channel (n-1)//127 at CC key (n-1)%127+1, so organs beyond 127 controls simply continue on the next channel."""
    channels = spec.get("stop_channels") or [15]
    out, n = [], 0

    def add(kind, path, name):
        nonlocal n
        n += 1
        channel, key = wire_for(n, channels) if (n - 1) // CCS_PER_CHANNEL < len(channels) else (None, None)
        out.append((kind, path, n, name, channel, key))

    for div in spec["divisions"]:
        for i, stop in enumerate(div["stops"]):
            if isinstance(stop, dict):
                add("stop", stop["path"], stop["name"])
            else:
                add("stop", f"manuals/{int(div['manual']):03d}/switches/{i + 1 + int(div.get('switch_offset', 0)):03d}", stop)
    for c in spec.get("couplers") or []:
        add("coupler", c.get("path") or f"manuals/{int(c['manual']):03d}/switches/{int(c['number']):03d}", c["name"])
    for t in spec.get("tremulants") or []:
        add("tremulant", t.get("path") or f"{int(t['switch']):03d}", t["name"])
    return out


ACTIVE_LAYOUT = {"source": "built-in (Friesach)"}


def configure_layout(spec, source=""):
    """Swap the live layout tables for another organ's (in place, so every importer stays valid)."""
    divisions = spec.get("divisions") or []
    if not divisions:
        raise ValueError("layout has no divisions")
    codes = [d["code"] for d in divisions]
    if len(set(codes)) != len(codes):
        raise ValueError(f"duplicate division codes in layout: {codes}")
    channels = [int(c) for c in (spec.get("stop_channels") or [15])]
    if len(set(channels)) != len(channels) or any(not 1 <= c <= 16 for c in channels):
        raise ValueError(f"bad stop_channels {channels}")
    needed = len(items_for_spec(spec))
    if needed > CCS_PER_CHANNEL * len(channels):
        raise ValueError(f"layout needs {needed} controls; {len(channels)} channel(s) carry {CCS_PER_CHANNEL * len(channels)}")
    couplers, tremulants = spec.get("couplers") or [], spec.get("tremulants") or []
    overrides, names_by_division = {}, []
    for d in divisions:
        names = []
        for i, stop in enumerate(d["stops"]):
            if isinstance(stop, dict):
                overrides[("stop", int(d["manual"]), i + 1)] = stop["path"]
                names.append(str(stop["name"]))
            else:
                names.append(str(stop))
        names_by_division.append(names)
    for c in couplers:
        if c.get("path"):
            overrides[("coupler", int(c["manual"]), int(c["number"]))] = c["path"]
    for t in tremulants:
        if t.get("path"):
            overrides[("tremulant", None, int(t["number"]))] = t["path"]
    DIVISIONS[:] = [(d["code"], d["name"], int(d["manual"]), names) for d, names in zip(divisions, names_by_division)]
    SWITCH_OFFSET.clear()
    SWITCH_OFFSET.update({int(d["manual"]): int(d.get("switch_offset", 0)) for d in divisions})
    OTHERS[:] = ([("coupler", int(c["manual"]), int(c["number"]), str(c["name"]), str(c.get("odf_name", ""))) for c in couplers]
                 + [("tremulant", None, int(t["number"]), str(t["name"]), "") for t in tremulants])
    TREMULANT_SWITCH.clear()
    TREMULANT_SWITCH.update({int(t["number"]): int(t["switch"]) for t in tremulants if "switch" in t})
    TREMULANT_DIVISION.clear()
    TREMULANT_DIVISION.update({int(t["number"]): str(t.get("division", "")) for t in tremulants})
    STOP_CHANNELS[:] = channels
    PATH_OVERRIDES.clear()
    PATH_OVERRIDES.update(overrides)
    rebuild_layout(dict(TREMULANT_DIVISION))
    ACTIVE_LAYOUT["source"] = source or "custom layout"
