"""Heuristic reading of a registration: which stop families it uses and which period / tradition it leans towards.

It looks only at the stop NAMES (family words, footage), so it is a hint for the Organ Setter Wiki, not a verdict:
the ratings it returns (0-5) sit beside the hand-written guide ratings.

CHANGELOG
2026-11-22  New: analyse(), FAMILIES.
"""
import re

FAMILIES = (
    ("mixture", r"mixtur|mixture|fourniture|plein ?jeu|scharf|cymbal|cimbel|zimbel|acuta|rauschp|sesquialt|terzian|progress"),
    ("reed", r"trompet|trumpet|posaun|trombon|bombard|clairon|hautbois|oboe|fagott|basson|cromorn|krummhorn|regal|dulzian|"
             r"clarin|vox hum|schalmei|englischhorn|cor anglais|chamade|tuba|musette"),
    ("string", r"gamba|viola|salicional|geige|violin|aeolin|celest|unda ?maris|voix c|schwebung|dulcian|fugara|quintaton"),
    ("flute", r"fl[oö]te|flute|gedackt|gedeckt|bourdon|rohr|nachthorn|quintade|hohl|traverso|piccolo|blockfl|gemshorn|spitz|"
              r"cor de nuit|bordun|subbass|sifflet|koppelfl|nasat|nazard|tierce|terz|larigot|septime"),
    ("principal", r"prinzipal|principal|oktave|octave|prestant|praestant|montre|superoct|doublette|fifteenth|diapason|"
                  r"salicet|quinte|quint|offenbass|open"),
)
_MUTATION = re.compile(r"nasat|nazard|tierce|terz|larigot|septime|quint(?!ad|at)|sesquialt|cornet|2 ?2/3|1 ?3/5|1 ?1/3|1 ?1/7")
_CELESTE = re.compile(r"celest|unda ?maris|voix c|schwebung|vox angel")
_HARSH = re.compile(r"chamade|tuba|bombard")
_FOOT = re.compile(r"(\d{1,2})(?:\s?['′]|\s?(?:ft|fu|pieds))|\b(\d{1,2})\s*$")


def family_of(name):
    text = str(name).casefold()
    for family, pattern in FAMILIES:
        if re.search(pattern, text):
            return family
    return "other"


def footage(name):
    """Pitch in feet (32, 16, 8, 4, 2, 1) read from the name; None when it has none."""
    found = _FOOT.search(str(name))
    if not found:
        return None
    return int(found.group(1) or found.group(2))


def _stars(value):
    return max(0, min(5, int(round(value))))


def analyse(stops):
    """stops: iterable of (division, name). Returns {"period", "tradition", "families", "lines", "count"}."""
    stops = [(str(d or ""), str(n or "")) for d, n in stops]
    count = len(stops)
    fam = {}
    divisions = {}
    for division, name in stops:
        family = family_of(name)
        fam[family] = fam.get(family, 0) + 1
        divisions.setdefault(division or "Other", []).append((family, footage(name), name))
    celeste = sum(1 for _, n in stops if _CELESTE.search(n.casefold()))
    mutations = sum(1 for _, n in stops if _MUTATION.search(n.casefold()))
    harsh = sum(1 for _, n in stops if _HARSH.search(n.casefold()))
    sixteen = sum(1 for _, n in stops if footage(n) in (16, 32))
    bright = sum(1 for _, n in stops if (footage(n) or 8) <= 2)
    foundation8 = sum(1 for _, n in stops if footage(n) == 8)
    mix, red, stg, flu, pri = (fam.get(k, 0) for k in ("mixture", "reed", "string", "flute", "principal"))
    if not count:
        return {"period": dict.fromkeys(("baroque", "classical", "romantic", "modern"), 0),
                "tradition": dict.fromkeys(("catholic", "early_protestant", "modern_church"), 0),
                "families": {}, "lines": ["No stops selected."], "count": 0}
    chorus = pri + mix
    baroque = 1.5 + 1.0 * min(pri, 3) + 1.2 * min(mix, 2) + 0.7 * min(mutations, 3) - 1.2 * min(celeste, 2) - 0.8 * min(stg, 3) - 1.5 * min(harsh, 1)
    classical = 2.0 + 0.8 * min(pri, 3) + 0.6 * min(flu, 3) + 0.4 * min(mix, 1) - 0.5 * min(celeste, 2) - 0.5 * max(0, count - 14) / 4
    romantic = 1.0 + 0.9 * min(stg, 3) + 1.2 * min(celeste, 1) + 0.6 * min(foundation8, 4) + 0.6 * min(sixteen, 2) + 0.4 * min(red, 2) - 0.5 * min(mutations, 3)
    modern = 1.5 + 0.7 * min(bright, 3) + 0.6 * min(red, 3) + 0.5 * min(mix, 2) + 0.4 * min(harsh, 1) + 0.15 * min(count, 12)
    catholic = 1.5 + 0.7 * min(flu, 3) + 0.8 * min(celeste, 1) + 0.6 * min(red, 2) + 0.4 * min(stg, 2) + 0.3 * min(foundation8, 3)
    protestant = 1.0 + 1.0 * min(pri, 3) + 0.8 * min(mix, 2) + 0.6 * min(mutations, 2) - 0.8 * min(celeste, 1) - 0.8 * min(harsh, 1)
    modern_church = 1.5 + 0.5 * min(pri, 2) + 0.5 * min(flu, 2) + 0.5 * min(red, 2) + 0.15 * min(count, 12) - 0.4 * min(mutations, 3) * (mix == 0)
    lines = []
    for division, items in divisions.items():
        parts = [f"{n}" for _, _, n in sorted(items, key=lambda i: -(i[1] or 0))]
        lines.append(f"{division}: " + ", ".join(parts))
    notes = []
    if chorus >= 4 and mix:
        notes.append("a principal chorus topped by a mixture (the classical plenum)")
    if stg and celeste:
        notes.append("strings with a celeste (romantic colour)")
    if mutations:
        notes.append("mutation stops (baroque / classical solo colours)")
    if red:
        notes.append(f"{red} reed{'s' if red > 1 else ''} for brightness / solo")
    if sixteen:
        notes.append("16' or 32' weight")
    if count > 14:
        notes.append("a large registration: full organ / tutti character")
    return {"period": {"baroque": _stars(baroque), "classical": _stars(classical), "romantic": _stars(romantic), "modern": _stars(modern)},
            "tradition": {"catholic": _stars(catholic), "early_protestant": _stars(protestant), "modern_church": _stars(modern_church)},
            "families": fam, "lines": lines, "notes": notes, "count": count}
