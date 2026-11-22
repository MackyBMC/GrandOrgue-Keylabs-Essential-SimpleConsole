"""Seed setter guides (drafts) from setter file names and stop content. Usage: seed_guides.py <setter folder> <out folder>"""
import os, re, sys, yaml

FAMILIES = {
    "principals": r"principal|praestant|prestant|octav|oktav|quinte|superoct|super oct|nasat|oktave|octave",
    "flutes": r"fl[öo]te|flute|gedackt|bourdon|rohr|hohl|traversi|jubal|bordun|quintad|spitzfl",
    "strings": r"viola|salicional|gamba|aeolin|celest|voix|geige|dulciana|unda",
    "reeds": r"trompet|posaun|oboe|fagott|clarin|krummhorn|horn|englisch|schalmei|trumpet|bombard|chamade|regal",
    "mixtures": r"mixtur|cymbel|zimbel|scharff|sesquialt|terz|cornet|plein|cymbal|rauschpf",
}

def families(label):
    low = label.lower()
    return [k for k, rx in FAMILIES.items() if re.search(rx, low)]

def footage(label):
    m = re.search(r"(\d+(?: \d/\d)?)'", label)
    return m.group(1) if m else ""

def analyse(step):
    stops = []
    for man in (step.get("manuals") or {}).values():
        for category in ("stops", "switches"):
            stops += [str(v) for v in (man.get(category) or {}).values()
                      if not str(v).startswith(("Coupler", "Key action"))]
    stops = list(dict.fromkeys(stops))
    tremulant = any("remulant" in str(v) for v in (step.get("switches") or {}).values())
    count = {k: 0 for k in FAMILIES}
    for s in stops:
        for f in families(s):
            count[f] += 1
    return stops, count, tremulant

KEYWORDS = [  # name hint -> (periods, traditions, composers)
    (r"baroque", {"baroque": 5, "classical": 2}, {}, "Bach, Buxtehude"),
    (r"classical", {"classical": 5, "baroque": 2, "romantic": 1}, {}, "Mozart, Haydn"),
    (r"romantic|grand choeur", {"romantic": 5, "modern": 2}, {"catholic": 3}, "Franck, Vierne, Widor"),
    (r"french", {"classical": 4, "baroque": 3, "romantic": 2}, {"catholic": 5}, "Couperin, Clerambault, Boyvin"),
    (r"bach|bwv|jesu joy|g string|ich ruf", {"baroque": 5}, {"early_protestant": 5}, "J. S. Bach"),
    (r"mozart|ave verum", {"classical": 5}, {"catholic": 4}, "Mozart"),
    (r"elgar|nimrod", {"romantic": 5, "modern": 2}, {"modern_church": 2}, "Elgar"),
    (r"moravian", {"classical": 3, "romantic": 3}, {"early_protestant": 5}, "Moravian chorale tradition"),
    (r"lent|jesus buig|funeral|lament|solemn|processional", {"romantic": 3, "modern": 3}, {"modern_church": 4}, ""),
    (r"general verse|playover|hymn|soft tones", {"modern": 4, "romantic": 3}, {"modern_church": 5, "early_protestant": 3}, ""),
]

def stars(value):
    return max(0, min(5, int(round(value))))

def guide_for(name, data):
    period = {"baroque": 0, "classical": 0, "romantic": 0, "modern": 0}
    tradition = {"catholic": 0, "early_protestant": 0, "modern_church": 0}
    composers = []
    for rx, p, t, c in KEYWORDS:
        if re.search(rx, name.lower()):
            for k, v in p.items(): period[k] = max(period[k], v)
            for k, v in t.items(): tradition[k] = max(tradition[k], v)
            composers += [x.strip() for x in c.split(",") if x.strip()]
    steps = [s for s in (data.get("sequencer") or {}).values() if isinstance(s, dict)]
    total = {k: 0 for k in FAMILIES}
    trem = False
    lines = []
    biggest = 0
    for step in steps:
        stops, count, t = analyse(step)
        trem = trem or t
        biggest = max(biggest, len(stops))
        for k in total: total[k] = max(total[k], count[k])
        used = [f"{k} {count[k]}" for k in FAMILIES if count[k]]
        lines.append(f"Step '{step.get('name', '')}': {len(stops)} stops" + (f" ({', '.join(used)})" if used else "") + (" + tremulant" if t else ""))
    # content nudges (evidence from the stops themselves)
    if total["mixtures"] and total["principals"] >= 3 and not total["strings"]:
        period["baroque"] = max(period["baroque"], 3)
    if total["strings"] or trem:
        period["romantic"] = max(period["romantic"], 3)
    if total["reeds"] >= 2 and total["mixtures"]:
        period["baroque"] = max(period["baroque"], 3); period["classical"] = max(period["classical"], 3)
    if not any(period.values()):
        period.update({"classical": 2, "romantic": 2, "modern": 3})
    if not any(tradition.values()):                    # no hint in the name: follow the strongest period
        top = max(period, key=lambda k: period[k])
        tradition.update({"baroque": {"early_protestant": 3, "catholic": 2}, "classical": {"catholic": 3, "early_protestant": 2},
                          "romantic": {"catholic": 3, "modern_church": 2}, "modern": {"modern_church": 4}}[top])
    fam = [k for k in FAMILIES if total[k]]
    reason = ("DRAFT generated from the setter's name and stops; edit freely. "
              + (f"Registers used: {', '.join(fam)}. " if fam else "Few stops identified by name. ")
              + (f"Largest step has {biggest} stops. " if biggest else "")
              + ("Uses the tremulant. " if trem else ""))
    layering = "\n".join(lines) if lines else "No steps found."
    return {"period": {k: stars(v) for k, v in period.items()}, "tradition": {k: stars(v) for k, v in tradition.items()},
            "composers": list(dict.fromkeys(composers)), "reason": reason.strip(), "layering": layering}

def main(folder, out):
    os.makedirs(out, exist_ok=True)
    n = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".yaml") or name.endswith(".guide.yaml"):
            continue
        data = yaml.safe_load(open(os.path.join(folder, name), encoding="utf-8")) or {}
        guide = guide_for(os.path.splitext(name)[0], data)
        with open(os.path.join(out, os.path.splitext(name)[0] + ".guide.yaml"), "w", encoding="utf-8", newline="\n") as h:
            h.write("# Setter guide (DRAFT): ratings 0-5 stars per period and tradition, composers, why this registration, how to layer it.\n")
            yaml.safe_dump(guide, h, sort_keys=False, allow_unicode=True, default_flow_style=False)
        n += 1
    print(n, "guides")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
